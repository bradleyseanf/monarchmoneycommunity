#!/usr/bin/env python3
"""Run the full local release check against a MonarchMoney account."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import getpass
import inspect
import io
import json
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from monarchmoney import MonarchMoney, RequireMFAException
from monarchmoney.monarchmoney import BalanceHistoryRow

DEFAULT_SESSION_FILE = Path(".mm") / "mm_session.pickle"
DEFAULT_TERMINAL_WIDTH = 100
MAX_TERMINAL_WIDTH = 120

READ_METHOD_NAMES: Tuple[str, ...] = (
    "get_accounts",
    "get_account_type_options",
    "get_recent_account_balances",
    "get_account_snapshots_by_type",
    "get_aggregate_snapshots",
    "is_accounts_refresh_complete",
    "get_account_holdings",
    "get_all_holdings",
    "get_account_history",
    "get_institutions",
    "get_budgets",
    "get_subscription_details",
    "get_transactions_summary",
    "get_transactions",
    "get_transaction_categories",
    "get_transaction_category_groups",
    "get_transaction_tags",
    "get_transaction_details",
    "get_transaction_splits",
    "get_cashflow",
    "get_cashflow_summary",
    "find_duplicate_transactions",
    "get_recurring_transactions",
    "get_credit_history",
    "get_transaction_rules",
)

MUTATING_METHOD_NAMES: Tuple[str, ...] = (
    "create_manual_account",
    "update_account",
    "delete_account",
    "request_accounts_refresh",
    "request_accounts_refresh_and_wait",
    "create_transaction",
    "delete_transaction",
    "delete_transaction_category",
    "delete_transaction_categories",
    "create_transaction_category",
    "create_transaction_tag",
    "set_transaction_tags",
    "update_transaction_splits",
    "update_transaction",
    "set_budget_amount",
    "update_flexible_budget",
    "update_flex_rollover_settings",
    "reset_budget",
    "upload_account_balance_history",
    "upload_attachment",
    "upload_receipt_to_inbox",
    "update_reoccuring",
)

NON_DATA_METHOD_NAMES = {
    "login_with_cookies",
    "interactive_login",
    "login",
    "multi_factor_authenticate",
    "gql_call",
}


class SmokeTestError(Exception):
    """An error raised by the smoke test itself."""


def _truncate(value: Any, limit: int) -> str:
    value = " ".join(str(value).split())
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)] + "…"


def _preview(value: Any, limit: int) -> str:
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    except Exception as error:  # noqa: BLE001
        rendered = repr(value) or f"<preview failed: {error}>"
    return _truncate(rendered, limit)


class TerminalReporter:
    """Print compact, terminal-width-safe result rows."""

    def __init__(self, force_color: bool = False, no_color: bool = False) -> None:
        self.width = max(
            80,
            min(
                shutil.get_terminal_size((DEFAULT_TERMINAL_WIDTH, 24)).columns,
                MAX_TERMINAL_WIDTH,
            ),
        )
        self.use_color = (
            not no_color
            and (force_color or sys.stdout.isatty())
            and "NO_COLOR" not in os.environ
        )
        self.passed = 0
        self.failed = 0

    def pass_result(self, label: str, result: Any) -> None:
        self.passed += 1
        detail_limit = self._detail_limit(label)
        self._write("PASS", label, _preview(result, detail_limit))

    def pass_note(self, label: str, note: str) -> None:
        self.passed += 1
        self._write("PASS", label, _truncate(note, self._detail_limit(label)))

    def fail(self, label: str, error: BaseException) -> None:
        self.failed += 1
        frames = (
            traceback.extract_tb(error.__traceback__) if error.__traceback__ else []
        )
        line = frames[-1].lineno if frames else "?"
        detail = (
            f"ERROR ON LINE {line}: {error.__class__.__name__}: "
            f"{str(error) or error.__class__.__name__}"
        )
        self._write("FAIL", label, detail)

    def summary(self) -> None:
        text = f"TOTAL: {self.passed} passed, {self.failed} failed"
        if self.use_color:
            color = "\033[32m" if self.failed == 0 else "\033[31m"
            text = f"{color}{text}\033[0m"
        print(text)

    def status(self, status: str, label: str, detail: str) -> None:
        self._write(status, label, detail)

    def _detail_limit(self, label: str) -> int:
        return max(20, self.width - len(f"[PASS] {label}") - 3)

    def _write(self, status: str, label: str, detail: str) -> None:
        visible_prefix = f"[{status}] {label}"
        limit = max(20, self.width - len(visible_prefix) - 3)
        detail = _truncate(detail, limit)
        token = f"[{status}]"
        if self.use_color:
            color = "\033[32m" if status == "PASS" else "\033[31m"
            token = f"{color}{token}\033[0m"
        print(f"{token} {label} - {detail}")


@dataclass(frozen=True)
class AccountSamples:
    """IDs and values used to exercise methods that require account data."""

    account_id: Optional[str] = None
    transaction_id: Optional[str] = None
    category_id: Optional[str] = None
    category_group_id: Optional[str] = None
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None
    account_type: str = "other_asset"
    account_subtype: str = "other"

    @classmethod
    def from_responses(cls, responses: Dict[str, Any]) -> "AccountSamples":
        transaction = cls._first_transaction(responses.get("transactions"))
        merchant = cls._transaction_merchant(transaction)
        if merchant is None:
            merchant = cls._recurring_merchant(responses.get("recurring"))
        account_type, account_subtype = cls._account_type(
            responses.get("account_type_options")
        )
        return cls(
            account_id=cls._first_id(responses.get("accounts"), "accounts"),
            transaction_id=(str(transaction["id"]) if transaction else None),
            category_id=cls._first_id(responses.get("categories"), "categories"),
            category_group_id=cls._first_id(
                responses.get("category_groups"), "categoryGroups"
            ),
            merchant_id=merchant[0] if merchant else None,
            merchant_name=merchant[1] if merchant else None,
            account_type=account_type,
            account_subtype=account_subtype,
        )

    def for_dry_run(self) -> "AccountSamples":
        return AccountSamples(
            account_id=self.account_id or "dry-run-account-id",
            transaction_id=self.transaction_id or "dry-run-transaction-id",
            category_id=self.category_id or "dry-run-category-id",
            category_group_id=self.category_group_id or "dry-run-group-id",
            merchant_id=self.merchant_id or "dry-run-merchant-id",
            merchant_name=self.merchant_name or "Smoke test",
            account_type=self.account_type,
            account_subtype=self.account_subtype,
        )

    @staticmethod
    def _first_id(response: Any, key: str) -> Optional[str]:
        if not isinstance(response, dict) or not isinstance(response.get(key), list):
            return None
        for item in response[key]:
            if isinstance(item, dict) and item.get("id") is not None:
                return str(item["id"])
        return None

    @staticmethod
    def _first_transaction(response: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(response, dict):
            return None
        all_transactions = response.get("allTransactions")
        if not isinstance(all_transactions, dict):
            return None
        transactions = all_transactions.get("results", [])
        if not isinstance(transactions, list):
            return None
        for transaction in transactions:
            if isinstance(transaction, dict) and transaction.get("id") is not None:
                return transaction
        return None

    @staticmethod
    def _transaction_merchant(
        transaction: Optional[Dict[str, Any]],
    ) -> Optional[Tuple[str, str]]:
        merchant = transaction.get("merchant") if transaction else None
        if not isinstance(merchant, dict) or merchant.get("id") is None:
            return None
        return str(merchant["id"]), str(merchant.get("name") or "Smoke test")

    @staticmethod
    def _recurring_merchant(response: Any) -> Optional[Tuple[str, str]]:
        if not isinstance(response, dict):
            return None
        items = response.get("recurringTransactionItems", [])
        if not isinstance(items, list):
            return None
        for item in items:
            stream = item.get("stream", {}) if isinstance(item, dict) else {}
            merchant = stream.get("merchant") if isinstance(stream, dict) else None
            if isinstance(merchant, dict) and merchant.get("id") is not None:
                return str(merchant["id"]), str(merchant.get("name") or "Smoke test")
        return None

    @staticmethod
    def _account_type(response: Any) -> Tuple[str, str]:
        if not isinstance(response, dict):
            return "other_asset", "other"
        options = response.get("accountTypeOptions", [])
        if not isinstance(options, list):
            return "other_asset", "other"
        for option in options:
            if not isinstance(option, dict):
                continue
            account_type = option.get("type") or {}
            subtype = option.get("subtype") or {}
            if not isinstance(account_type, dict) or not isinstance(subtype, dict):
                continue
            possible = account_type.get("possibleSubtypes", [])
            possible_subtype = possible[0] if possible else subtype
            if isinstance(possible_subtype, dict):
                type_name = account_type.get("name")
                subtype_name = possible_subtype.get("name")
                if type_name and subtype_name:
                    return str(type_name), str(subtype_name)
        return "other_asset", "other"


class DryRunMonarchMoney(MonarchMoney):
    """MonarchMoney client with inert GraphQL and upload boundaries."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.refresh_account_ids: List[str] = []

    async def gql_call(
        self,
        operation: str,
        graphql_query: Any,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        del graphql_query, variables
        if operation == "Common_ForceRefreshAccountsMutation":
            return {"forceRefreshAccounts": {"success": True, "errors": []}}
        if operation == "ForceRefreshAccountsQuery":
            return {
                "accounts": [
                    {"id": account_id, "hasSyncInProgress": False}
                    for account_id in self.refresh_account_ids
                ]
            }
        if operation == "Common_DeleteTransactionMutation":
            return {"deleteTransaction": {"deleted": True, "errors": []}}
        if operation == "Web_DeleteCategory":
            return {"deleteCategory": {"deleted": True, "errors": []}}
        if operation == "Web_ParseUploadBalanceHistorySession":
            return {
                "parseBalanceHistory": {
                    "uploadBalanceHistorySession": {"status": "completed"}
                }
            }
        if operation == "Web_GetUploadBalanceHistorySession":
            return {"uploadBalanceHistorySession": {"status": "completed"}}
        if operation == "Common_GetTransactionAttachmentUploadInfo":
            return {
                "getTransactionAttachmentUploadInfo": {
                    "info": {
                        "requestParams": {
                            "timestamp": 0,
                            "folder": "dry-run",
                            "signature": "dry-run",
                            "api_key": "dry-run",
                            "upload_preset": "dry-run",
                        }
                    }
                }
            }
        if operation == "Common_CreateBulkRetailSync":
            return {
                "createBulkRetailSync": {
                    "retailSyncs": [{"id": "dry-run-sync"}],
                    "errors": [],
                }
            }
        if operation == "Common_StartRetailSync":
            return {
                "startRetailSync": {
                    "retailSync": {"id": "dry-run-sync", "status": "dry-run"},
                    "errors": [],
                }
            }
        return {"dryRun": True, "operation": operation}

    async def _upload_form_data(self, url: str, data: Any) -> Dict[str, Any]:
        del data
        if "account-balance-history/upload" in url:
            return {"session_key": "dry-run-session"}
        if "cloudinary.com" in url:
            return {"public_id": "dry-run-attachment", "format": "txt", "bytes": 0}
        return {}


class GitHubStatusPublisher:
    """Publish the local result for the current committed revision."""

    CONTEXT = "full-tests-local"

    def __init__(self, root: Path) -> None:
        self.root = root

    def publish(self, passed: bool) -> str:
        sha = self._current_sha()
        self._require_clean_worktree()
        gh = shutil.which("gh")
        if gh is None:
            raise SmokeTestError(
                "GitHub CLI (gh) is required to publish the local status"
            )

        state = "success" if passed else "failure"
        result = subprocess.run(
            [
                gh,
                "api",
                f"repos/{{owner}}/{{repo}}/statuses/{sha}",
                "--method",
                "POST",
                "--raw-field",
                f"state={state}",
                "--raw-field",
                f"context={self.CONTEXT}",
                "--raw-field",
                f"description=full_tests.py {'passed' if passed else 'failed'} locally",
                "--silent",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise SmokeTestError(
                f"GitHub status could not be published{': ' + detail if detail else ''}"
            )
        return state

    def _current_sha(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SmokeTestError("full_tests.py must run inside a Git repository")
        return result.stdout.strip()

    def _require_clean_worktree(self) -> None:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SmokeTestError("could not inspect the Git worktree")
        if result.stdout.strip():
            raise SmokeTestError(
                "commit all changes before publishing the local status"
            )


class ReleaseSmokeTest:
    """Run live reads and safe local mutation checks."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.session_file = Path(args.session_file).expanduser()
        self.client = MonarchMoney(
            session_file=str(self.session_file), timeout=args.timeout
        )
        self.reporter = TerminalReporter(args.color, args.no_color)
        self.responses: Dict[str, Any] = {}
        self.samples = AccountSamples()

    async def run(self) -> int:
        self._check_method_coverage()
        try:
            description = await self._authenticate()
            self.reporter.pass_note("login", description)
        except Exception as error:  # noqa: BLE001
            self.reporter.fail("login", error)
            self._report_read_auth_failures()
        else:
            await self._run_read_methods()
        await self._run_mutation_methods()
        self.reporter.summary()
        return int(self.reporter.failed > 0)

    async def _authenticate(self) -> str:
        saved_error: Optional[BaseException] = None
        if self.session_file.is_file():
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    await self.client.login(use_saved_session=True, save_session=True)
                return f"saved session {self.session_file}"
            except Exception as error:  # noqa: BLE001
                saved_error = error

        email = os.getenv("MONARCH_EMAIL") or input("Email: ").strip()
        password = os.getenv("MONARCH_PASSWORD") or getpass.getpass("Password: ")
        try:
            await self.client.login(
                email=email,
                password=password,
                use_saved_session=False,
                save_session=True,
                mfa_secret_key=os.getenv("MONARCH_MFA_SECRET_KEY"),
            )
        except RequireMFAException:
            code = os.getenv("MONARCH_MFA_CODE") or input("MFA code: ").strip()
            await self.client.multi_factor_authenticate(
                email, password, code, trusted_device=True
            )
            self.client.save_session(str(self.session_file))
        except Exception as error:
            if saved_error is not None:
                raise SmokeTestError(
                    f"saved session unavailable; fresh login failed: {error}"
                ) from error
            raise
        return f"new session saved to {self.session_file}"

    async def _check(
        self,
        label: str,
        call: Callable[[], Awaitable[Any]],
        show_result: bool = True,
    ) -> Any:
        try:
            result = await call()
            if result is None:
                raise SmokeTestError("method returned null instead of JSON data")
            json.dumps(result)
        except Exception as error:  # noqa: BLE001
            self.reporter.fail(label, error)
            return None
        if show_result:
            self.reporter.pass_result(label, result)
        else:
            self.reporter.pass_note(label, "dry-run")
        return result

    def _check_method_coverage(self) -> None:
        public_coroutines = {
            name
            for name, method in inspect.getmembers(
                MonarchMoney, predicate=inspect.iscoroutinefunction
            )
            if not name.startswith("_")
        }
        registered = set(READ_METHOD_NAMES) | set(MUTATING_METHOD_NAMES)
        missing = sorted(public_coroutines - registered - NON_DATA_METHOD_NAMES)
        if missing:
            self.reporter.fail(
                "method_coverage",
                SmokeTestError("unregistered public methods: " + ", ".join(missing)),
            )

    def _report_read_auth_failures(self) -> None:
        error = SmokeTestError("authentication unavailable; read check was not run")
        for name in READ_METHOD_NAMES:
            self.reporter.fail(name, error)

    async def _run_read_methods(self) -> None:
        today = dt.date.today()
        month_start = today.replace(day=1).isoformat()
        year_start = today.replace(month=1, day=1).isoformat()

        self.responses["accounts"] = await self._check(
            "get_accounts", self.client.get_accounts
        )
        account_id = AccountSamples._first_id(self.responses["accounts"], "accounts")

        self.responses["account_type_options"] = await self._check(
            "get_account_type_options", self.client.get_account_type_options
        )
        await self._check(
            "get_recent_account_balances",
            self.client.get_recent_account_balances,
        )
        await self._check(
            "get_account_snapshots_by_type",
            lambda: self.client.get_account_snapshots_by_type(year_start, "month"),
        )
        await self._check(
            "get_aggregate_snapshots",
            lambda: self.client.get_aggregate_snapshots(
                start_date=(today - dt.timedelta(days=31)).isoformat(),
                end_date=today.isoformat(),
            ),
        )
        await self._check(
            "is_accounts_refresh_complete",
            lambda: self.client.is_accounts_refresh_complete(
                [account_id] if account_id else None
            ),
        )

        if account_id is None:
            self.reporter.pass_note("get_account_holdings", "no account to sample")
            self.reporter.pass_note("get_account_history", "no account to sample")
        else:
            account_argument: Any = (
                int(account_id) if account_id.isdigit() else account_id
            )
            await self._check(
                "get_account_holdings",
                lambda: self.client.get_account_holdings(account_argument),
            )
            await self._check(
                "get_account_history",
                lambda: self.client.get_account_history(account_argument),
            )

        await self._check("get_all_holdings", self.client.get_all_holdings)
        await self._check("get_institutions", self.client.get_institutions)
        self.responses["budgets"] = await self._check(
            "get_budgets", self.client.get_budgets
        )
        await self._check(
            "get_subscription_details", self.client.get_subscription_details
        )
        await self._check(
            "get_transactions_summary", self.client.get_transactions_summary
        )
        self.responses["transactions"] = await self._check(
            "get_transactions", lambda: self.client.get_transactions(limit=10)
        )
        self.responses["categories"] = await self._check(
            "get_transaction_categories", self.client.get_transaction_categories
        )
        self.responses["category_groups"] = await self._check(
            "get_transaction_category_groups",
            self.client.get_transaction_category_groups,
        )
        await self._check("get_transaction_tags", self.client.get_transaction_tags)

        transaction = AccountSamples._first_transaction(self.responses["transactions"])
        transaction_id = str(transaction["id"]) if transaction else None
        if transaction_id is None:
            self.reporter.pass_note(
                "get_transaction_details", "no transaction to sample"
            )
            self.reporter.pass_note(
                "get_transaction_splits", "no transaction to sample"
            )
        else:
            await self._check(
                "get_transaction_details",
                lambda: self.client.get_transaction_details(transaction_id),
            )
            await self._check(
                "get_transaction_splits",
                lambda: self.client.get_transaction_splits(transaction_id),
            )

        await self._check(
            "get_cashflow",
            lambda: self.client.get_cashflow(
                limit=10, start_date=month_start, end_date=today.isoformat()
            ),
        )
        await self._check(
            "get_cashflow_summary",
            lambda: self.client.get_cashflow_summary(
                limit=10, start_date=month_start, end_date=today.isoformat()
            ),
        )
        await self._check(
            "find_duplicate_transactions",
            lambda: self.client.find_duplicate_transactions(
                start_date=month_start,
                end_date=today.isoformat(),
                page_size=100,
            ),
        )
        self.responses["recurring"] = await self._check(
            "get_recurring_transactions", self.client.get_recurring_transactions
        )
        await self._check("get_credit_history", self.client.get_credit_history)
        await self._check("get_transaction_rules", self.client.get_transaction_rules)
        self.samples = AccountSamples.from_responses(self.responses)

    async def _run_mutation_methods(self) -> None:
        samples = self.samples.for_dry_run()
        client = DryRunMonarchMoney(
            session_file=str(self.session_file), timeout=self.args.timeout
        )
        client.refresh_account_ids = [str(samples.account_id)]
        for label, call in self._mutation_calls(client, samples):
            await self._check(label, call, show_result=False)

    @staticmethod
    def _mutation_calls(
        client: DryRunMonarchMoney, samples: AccountSamples
    ) -> Sequence[Tuple[str, Callable[[], Awaitable[Any]]]]:
        account_id = str(samples.account_id)
        transaction_id = str(samples.transaction_id)
        category_id = str(samples.category_id)
        category_group_id = str(samples.category_group_id)
        merchant_id = str(samples.merchant_id)
        merchant_name = str(samples.merchant_name)
        return (
            (
                "create_manual_account",
                lambda: client.create_manual_account(
                    samples.account_type,
                    samples.account_subtype,
                    True,
                    "release-smoke-test",
                    0,
                ),
            ),
            ("update_account", lambda: client.update_account(account_id)),
            ("delete_account", lambda: client.delete_account(account_id)),
            (
                "request_accounts_refresh",
                lambda: client.request_accounts_refresh([account_id]),
            ),
            (
                "request_accounts_refresh_and_wait",
                lambda: client.request_accounts_refresh_and_wait(
                    [account_id], timeout=1, delay=0
                ),
            ),
            (
                "create_transaction",
                lambda: client.create_transaction(
                    dt.date.today().isoformat(),
                    account_id,
                    0,
                    "release-smoke-test",
                    category_id,
                ),
            ),
            ("delete_transaction", lambda: client.delete_transaction(transaction_id)),
            (
                "delete_transaction_category",
                lambda: client.delete_transaction_category(category_id),
            ),
            (
                "delete_transaction_categories",
                lambda: client.delete_transaction_categories([category_id]),
            ),
            (
                "create_transaction_category",
                lambda: client.create_transaction_category(
                    category_group_id,
                    "release-smoke-test",
                    rollover_start_month=dt.datetime.today().replace(day=1),
                ),
            ),
            (
                "create_transaction_tag",
                lambda: client.create_transaction_tag("release-smoke-test", "#000000"),
            ),
            (
                "set_transaction_tags",
                lambda: client.set_transaction_tags(transaction_id, []),
            ),
            (
                "update_transaction_splits",
                lambda: client.update_transaction_splits(transaction_id, []),
            ),
            ("update_transaction", lambda: client.update_transaction(transaction_id)),
            (
                "set_budget_amount",
                lambda: client.set_budget_amount(0, category_id=category_id),
            ),
            ("update_flexible_budget", lambda: client.update_flexible_budget(0)),
            (
                "update_flex_rollover_settings",
                lambda: client.update_flex_rollover_settings(),
            ),
            ("reset_budget", lambda: client.reset_budget()),
            (
                "upload_account_balance_history",
                lambda: client.upload_account_balance_history(
                    account_id,
                    [
                        BalanceHistoryRow(
                            date=dt.datetime.today(),
                            amount=0,
                            account_name="Smoke test",
                        )
                    ],
                    timeout=1,
                    delay=0,
                ),
            ),
            (
                "upload_attachment",
                lambda: client.upload_attachment(
                    transaction_id, b"release smoke test", "release-smoke-test.txt"
                ),
            ),
            (
                "upload_receipt_to_inbox",
                lambda: client.upload_receipt_to_inbox(
                    b"release smoke test", "release-smoke-test.txt"
                ),
            ),
            (
                "update_reoccuring",
                lambda: client.update_reoccuring(merchant_id, merchant_name),
            ),
        )


class FullTestRunner:
    """Run the account smoke test and the repository unit tests."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.root = Path(__file__).resolve().parent
        self.args = args
        self.reporter = TerminalReporter(args.color, args.no_color)

    def run(self) -> int:
        try:
            smoke_code = asyncio.run(ReleaseSmokeTest(self.args).run())
        except Exception as error:  # noqa: BLE001
            self.reporter.fail("smoke_test", error)
            smoke_code = 1

        unit_result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if unit_result.returncode == 0:
            self.reporter.status("PASS", "tests/", "unittest suite passed")
        else:
            output = (unit_result.stdout + unit_result.stderr).strip()
            detail = " ".join(output.split()) if output else "unittest suite failed"
            self.reporter.status("FAIL", "tests/", detail)

        all_passed = smoke_code == 0 and unit_result.returncode == 0
        if self.args.skip_github_status:
            self.reporter.status("PASS", "github-status", "skipped")
        else:
            try:
                state = GitHubStatusPublisher(self.root).publish(all_passed)
            except Exception as error:  # noqa: BLE001
                self.reporter.fail("github-status", error)
                all_passed = False
            else:
                self.reporter.status(
                    "PASS",
                    "github-status",
                    f"{GitHubStatusPublisher.CONTEXT}={state} posted",
                )
        self.reporter.status(
            "PASS" if all_passed else "FAIL",
            "full_tests",
            "all checks passed" if all_passed else "one or more checks failed",
        )
        return int(not all_passed)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-file",
        default=str(DEFAULT_SESSION_FILE),
        help="saved session path (default: .mm/mm_session.pickle)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="GraphQL request timeout in seconds (default: 30)",
    )
    colors = parser.add_mutually_exclusive_group()
    colors.add_argument(
        "--color",
        action="store_true",
        help="force ANSI colors even when stdout is not a terminal",
    )
    colors.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI colors",
    )
    parser.add_argument(
        "--skip-github-status",
        action="store_true",
        help="run locally without publishing a GitHub commit status",
    )
    return parser.parse_args(argv)


def run(argv: Optional[Sequence[str]] = None) -> int:
    return FullTestRunner(_parse_args(argv)).run()


def main(argv: Optional[Sequence[str]] = None) -> None:
    try:
        raise SystemExit(run(argv))
    except KeyboardInterrupt:
        print("[FAIL] full_tests - interrupted", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
