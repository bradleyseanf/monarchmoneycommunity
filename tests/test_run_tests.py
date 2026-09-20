import asyncio
import contextlib
import inspect
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from monarchmoney import CaptchaRequiredException, MonarchMoney, RequireMFAException
from run_tests import (
    ArgumentResolver,
    LiveReadSuite,
    ReadMethodDiscovery,
    SampleValues,
    SessionAuthenticator,
    SmokeTestError,
    TerminalReporter,
)
from typedmonarchmoney import TypedMonarchMoney


class TestArgumentResolver(unittest.TestCase):
    def test_transaction_filters_keep_declared_defaults(self):
        resolver = ArgumentResolver(SampleValues(account_id="123", category_id="456"))
        for client_type in (MonarchMoney, TypedMonarchMoney):
            with self.subTest(client=client_type.__name__):
                args, kwargs = resolver.resolve(client_type().get_transactions)
                self.assertEqual(args, [])
                self.assertEqual(kwargs, {"limit": 10})

    def test_optional_true_boolean_is_preserved(self):
        method = MonarchMoney().get_budgets
        args, kwargs = ArgumentResolver(SampleValues()).resolve(method)
        bound = inspect.signature(method).bind(*args, **kwargs)
        bound.apply_defaults()
        self.assertTrue(bound.arguments["use_v2_goals"])
        self.assertFalse(bound.arguments["use_legacy_goals"])

    def test_required_dates_and_account_ids_are_still_supplied(self):
        resolver = ArgumentResolver(SampleValues(account_id="123"))
        _, kwargs = resolver.resolve(MonarchMoney().get_account_history)
        self.assertEqual(kwargs, {"account_id": 123})
        _, kwargs = resolver.resolve(MonarchMoney().get_account_snapshots_by_type)
        self.assertEqual(kwargs["timeframe"], "month")
        self.assertRegex(kwargs["start_date"], r"^\d{4}-\d{2}-\d{2}$")


class TestLiveReadSuite(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def suite(self, client_type, samples=None):
        return LiveReadSuite(
            client_type,
            client_type.__name__,
            Path("unused-session"),
            1,
            TerminalReporter(no_color=True),
            samples or SampleValues(),
        )

    async def test_empty_household_skips_only_sample_dependent_probes(self):
        for client_type in (MonarchMoney, TypedMonarchMoney):
            with self.subTest(client=client_type.__name__):
                suite = self.suite(client_type)
                suite.client.gql_call = AsyncMock(return_value={"accounts": []})
                self.assertTrue(
                    await suite._check("get_accounts", suite.client.get_accounts)
                )
                suite.client.gql_call.reset_mock()
                names = [
                    "get_account_history",
                    "get_account_holdings",
                    "get_transaction_details",
                    "get_transaction_splits",
                ]
                if client_type is TypedMonarchMoney:
                    names.append("get_account_holdings_for_id")
                for name in names:
                    self.assertTrue(
                        await suite._check(name, getattr(suite.client, name))
                    )
                suite.client.gql_call.assert_not_awaited()
                self.assertEqual(suite.reporter.skipped, len(names))
                self.assertEqual(suite.reporter.failed, 0)
                self.assertEqual(suite.reporter.passed, 1)
        self.assertIn("[SKIP]", self.output.getvalue())

    async def test_unfiltered_transactions_provide_detail_sample(self):
        suite = self.suite(
            MonarchMoney, SampleValues(account_id="123", category_id="456")
        )
        suite.client.gql_call = AsyncMock(
            return_value={"allTransactions": {"results": [{"id": "789"}]}},
        )
        self.assertTrue(
            await suite._check("get_transactions", suite.client.get_transactions)
        )
        variables = suite.client.gql_call.call_args.kwargs["variables"]
        self.assertEqual(variables["limit"], 10)
        self.assertEqual(
            variables["filters"],
            {"search": "", "categories": [], "accounts": [], "tags": []},
        )
        self.assertEqual(suite.samples.transaction_id, "789")
        suite.client.gql_call = AsyncMock(return_value={"transaction": {"id": "789"}})
        self.assertTrue(
            await suite._check(
                "get_transaction_details", suite.client.get_transaction_details
            )
        )
        suite.client.gql_call.assert_awaited_once()
        self.assertEqual(suite.reporter.skipped, 0)

    async def test_endpoint_failure_is_not_a_skip(self):
        suite = self.suite(MonarchMoney, SampleValues(account_id="123"))
        suite.client.gql_call = AsyncMock(side_effect=RuntimeError("endpoint failed"))
        self.assertFalse(
            await suite._check("get_account_history", suite.client.get_account_history)
        )
        self.assertEqual(suite.reporter.failed, 1)
        self.assertEqual(suite.reporter.skipped, 0)

    async def test_duplicate_probe_fetches_only_one_small_page(self):
        for client_type in (MonarchMoney, TypedMonarchMoney):
            with self.subTest(client=client_type.__name__):
                suite = self.suite(client_type)
                discovered = dict(ReadMethodDiscovery.discover(suite.client))
                self.assertIn("find_duplicate_transactions", discovered)
                transactions = [{"id": str(index)} for index in range(520)]

                async def page(**kwargs):
                    offset = kwargs["offset"]
                    return {
                        "allTransactions": {
                            "results": transactions[offset : offset + kwargs["limit"]],
                            "totalCount": len(transactions),
                        }
                    }

                suite.client.get_transactions = AsyncMock(side_effect=page)
                self.assertTrue(
                    await suite._check(
                        "find_duplicate_transactions",
                        suite.client.find_duplicate_transactions,
                    )
                )
                suite.client.get_transactions.assert_awaited_once_with(
                    limit=10,
                    offset=0,
                    start_date=None,
                    end_date=None,
                    account_ids=[],
                )
                self.assertEqual(suite.reporter.passed, 1)
                self.assertEqual(suite.reporter.skipped, 0)

    async def test_slow_probe_reports_progress_times_out_and_allows_next_probe(self):
        suite = self.suite(MonarchMoney)
        suite.timeout = 0.01
        cancelled = asyncio.Event()

        async def get_slow():
            self.assertIn("[RUN] MonarchMoney.get_slow", self.output.getvalue())
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        self.assertFalse(await suite._check("get_slow", get_slow))
        self.assertTrue(cancelled.is_set())
        self.assertIn("timed out after 0.01 seconds", self.output.getvalue())
        self.assertEqual(suite.reporter.failed, 1)

        async def get_next():
            return {}

        self.assertTrue(await suite._check("get_next", get_next))
        self.assertEqual(suite.reporter.passed, 1)

    def test_empty_results_clear_samples_from_previous_client(self):
        samples = SampleValues(
            account_id="123", transaction_id="789", account_object=object()
        )
        samples.update("get_accounts", [])
        samples.update("get_transactions", {"allTransactions": {"results": []}})
        self.assertIsNone(samples.account_id)
        self.assertIsNone(samples.account_object)
        self.assertIsNone(samples.transaction_id)


class TestSessionAuthenticator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.session_file = Path(temporary.name) / "session.pickle"
        self.client = MonarchMoney(session_file=str(self.session_file))
        self.authenticator = SessionAuthenticator(self.session_file)
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    async def test_cookie_environment_verifies_saves_and_reuses_for_typed_client(self):
        os.environ["MONARCH_COOKIE_STRING"] = (
            "session_id=test-session; csrftoken=test-csrf"
        )
        self.client.get_accounts = AsyncMock(return_value={"accounts": []})
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            description = await self.authenticator.authenticate(self.client, True)
            self.assertIn("cookie session saved", description)
            self.client.get_accounts.assert_awaited_once()
            self.assertTrue(self.session_file.is_file())
            typed = TypedMonarchMoney(session_file=str(self.session_file))
            typed.get_accounts = AsyncMock(return_value=[])
            await self.authenticator.authenticate(typed, False)
            typed.get_accounts.assert_awaited_once()
        self.assertEqual(typed._auth_mode, "cookie")
        self.assertEqual(typed._cookies, self.client._cookies)

    async def test_expired_saved_token_falls_back_to_fresh_cookies(self):
        stale = MonarchMoney(session_file=str(self.session_file), token="expired-token")
        stale.save_session()
        os.environ["MONARCH_COOKIE_STRING"] = "session_id=fresh; csrftoken=fresh-csrf"
        self.client.get_accounts = AsyncMock(
            side_effect=[RuntimeError("expired session"), {"accounts": []}]
        )
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            description = await self.authenticator.authenticate(self.client, True)
        self.assertIn("cookie session saved", description)
        self.assertEqual(self.client.get_accounts.await_count, 2)
        restored = MonarchMoney(session_file=str(self.session_file))
        restored.load_session()
        self.assertEqual(restored._auth_mode, "cookie")
        self.assertEqual(restored._cookies["session_id"], "fresh")
        self.assertIsNone(restored.token)

    async def test_expired_cookie_session_does_not_contaminate_password_login(self):
        stale = MonarchMoney(session_file=str(self.session_file))
        stale.set_cookies({"session_id": "expired", "csrftoken": "expired-csrf"})
        stale.save_session()
        os.environ.update(MONARCH_EMAIL="test@example.com", MONARCH_PASSWORD="password")
        initial_headers = self.client._headers.copy()
        self.client.get_accounts = AsyncMock(
            side_effect=RuntimeError("expired session")
        )

        async def login_user(email, password, mfa_secret_key):
            self.assertEqual(self.client._auth_mode, "token")
            self.assertIsNone(self.client._cookies)
            self.assertEqual(self.client._headers, initial_headers)
            self.client.set_token("fresh-token")
            self.client._headers["Authorization"] = "Token fresh-token"

        with patch.object(self.client, "_login_user", side_effect=login_user) as login:
            description = await self.authenticator.authenticate(self.client, True)
        login.assert_awaited_once_with("test@example.com", "password", None)
        self.assertIn("new session saved", description)
        restored = MonarchMoney(session_file=str(self.session_file))
        restored.load_session()
        self.assertEqual(restored.token, "fresh-token")
        self.assertEqual(restored._auth_mode, "token")
        self.assertIsNone(restored._cookies)

    async def test_valid_saved_token_is_verified_and_reused_without_prompting(self):
        stale = MonarchMoney(session_file=str(self.session_file), token="valid-token")
        stale.save_session()
        self.client.get_accounts = AsyncMock(return_value={"accounts": []})
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            description = await self.authenticator.authenticate(self.client, True)
        self.client.get_accounts.assert_awaited_once()
        self.assertIn("saved session", description)
        self.assertEqual(self.client.token, "valid-token")

    async def test_typed_client_rejects_expired_session_without_prompting(self):
        stale = MonarchMoney(session_file=str(self.session_file), token="expired-token")
        stale.save_session()
        typed = TypedMonarchMoney(session_file=str(self.session_file))
        typed.get_accounts = AsyncMock(side_effect=RuntimeError("expired session"))
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            with self.assertRaisesRegex(SmokeTestError, "saved session unavailable"):
                await self.authenticator.authenticate(typed, False)
        self.assertIsNone(typed.token)

    async def test_invalid_cookie_session_is_not_saved(self):
        os.environ["MONARCH_COOKIE_STRING"] = (
            "session_id=test-session; csrftoken=test-csrf"
        )
        self.client.get_accounts = AsyncMock(
            side_effect=RuntimeError("invalid session")
        )
        with self.assertRaisesRegex(RuntimeError, "invalid session"):
            await self.authenticator.authenticate(self.client, True)
        self.assertFalse(self.session_file.exists())

    async def test_captcha_during_password_or_mfa_uses_hidden_cookie_prompt(self):
        os.environ.update(
            MONARCH_EMAIL="test@example.com",
            MONARCH_PASSWORD="test-password",
            MONARCH_MFA_CODE="123456",
        )
        for mfa in (False, True):
            with self.subTest(mfa=mfa):
                self.client.login = AsyncMock(
                    side_effect=(
                        RequireMFAException() if mfa else CaptchaRequiredException()
                    )
                )
                self.client.multi_factor_authenticate = AsyncMock(
                    side_effect=CaptchaRequiredException()
                )
                self.client.login_with_cookies = AsyncMock()
                with patch(
                    "run_tests.getpass.getpass",
                    return_value="session_id=test; csrftoken=test",
                ) as prompt:
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        await self.authenticator.authenticate(self.client, True)
                prompt.assert_called_once_with("Cookie header (hidden): ")
                self.client.login_with_cookies.assert_awaited_once_with(
                    "session_id=test; csrftoken=test", save_session=True
                )
                self.assertNotIn("session_id=test", output.getvalue())

    async def test_password_and_mfa_paths_still_work(self):
        os.environ.update(
            MONARCH_EMAIL="test@example.com",
            MONARCH_PASSWORD="test-password",
            MONARCH_MFA_CODE="123456",
        )
        self.client.login = AsyncMock()
        await self.authenticator.authenticate(self.client, True)
        self.client.login.assert_awaited_once_with(
            email="test@example.com",
            password="test-password",
            use_saved_session=False,
            save_session=True,
            mfa_secret_key=None,
        )
        self.client.login.side_effect = RequireMFAException()
        self.client.multi_factor_authenticate = AsyncMock()
        with patch.object(self.client, "save_session") as save:
            await self.authenticator.authenticate(self.client, True)
        self.client.multi_factor_authenticate.assert_awaited_once_with(
            "test@example.com", "test-password", "123456", trusted_device=True
        )
        save.assert_called_once_with(str(self.session_file))
