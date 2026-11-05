import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


from monarchmoney import MonarchMoney
from monarchmoney.read_types import MerchantPaginationError
from typedmonarchmoney.monarchmoney_typed import TypedMonarchMoney


from tests._fixtures import ReadFixture


class TestCompatibilityRead(ReadFixture):

    async def test_cursor_defaults_request_first_page(self) -> None:
        for method_name, connection in (
            ("get_retail_transactions", "retailTransactionsConnection"),
            ("get_activity_events", "activityEvents"),
        ):
            with self.subTest(method=method_name):
                self.execute.reset_mock()
                self.execute.return_value = {
                    connection: {"edges": [], "pageInfo": {"hasNextPage": False}}
                }

                await getattr(self.client, method_name)()

                awaited = self.execute.await_args
                assert awaited is not None
                self.assertEqual(awaited.kwargs["variable_values"]["first"], 100)
                self.assertIsNone(awaited.kwargs["variable_values"]["afterCursor"])

    async def test_invalid_page_sizes_are_rejected_before_requests(self) -> None:
        for method_name in (
            "get_merchants",
            "get_all_merchants",
            "get_retail_transactions",
            "get_activity_events",
        ):
            for size in (0, -1):
                with self.subTest(method=method_name, size=size):
                    with self.assertRaises(ValueError):
                        await getattr(self.client, method_name)(size)
        self.execute.assert_not_awaited()


class TestDirectReadMethods(unittest.TestCase):
    def test_new_getters_live_on_raw_client_and_are_inherited_by_typed_client(
        self,
    ) -> None:
        methods = (
            "get_account_details",
            "get_account_roster",
            "get_merchants",
            "get_all_merchants",
            "get_retail_transactions",
            "get_activity_events",
            "get_user_profile",
            "get_household_preferences",
            "get_report_configurations",
            "get_recurring_transaction_streams",
        )
        for name in methods:
            with self.subTest(name=name):
                self.assertIn(name, MonarchMoney.__dict__)
                self.assertIs(
                    getattr(TypedMonarchMoney, name), MonarchMoney.__dict__[name]
                )

    def test_pagination_error_remains_public_type(self) -> None:
        error = MerchantPaginationError(4, "duplicate merchant id")
        self.assertEqual(error.offset, 4)
        self.assertEqual(error.reason, "duplicate merchant id")
        self.assertIsInstance(error, RuntimeError)


class TestLegacyReadImportCompatibility(unittest.TestCase):
    def test_signatures_match_170_baseline(self) -> None:
        baseline = json.loads(
            (
                Path(__file__).resolve().parents[1] / "read_api_170_signatures.json"
            ).read_text()
        )
        for name, signature in baseline.items():
            with self.subTest(name=name):
                self.assertEqual(
                    str(inspect.signature(getattr(MonarchMoney, name))), signature
                )
                self.assertTrue(
                    inspect.iscoroutinefunction(getattr(MonarchMoney, name))
                )

    def test_legacy_imports_and_monkeypatch_reach_direct_client(self) -> None:
        from monarchmoney.read_api import (
            MerchantPaginationError as LegacyError,
            ReadApiMixin,
            _query,
        )
        from monarchmoney.monarchmoney import _query as direct_query

        self.assertIs(ReadApiMixin, MonarchMoney)
        self.assertIs(LegacyError, MerchantPaginationError)
        self.assertIs(_query, direct_query)
        with patch.object(
            ReadApiMixin, "get_user_profile", new=AsyncMock(return_value={"me": None})
        ):
            self.assertEqual(
                self.run_async(MonarchMoney().get_user_profile()), {"me": None}
            )

    @staticmethod
    def run_async(coroutine):
        import asyncio

        return asyncio.run(coroutine)
