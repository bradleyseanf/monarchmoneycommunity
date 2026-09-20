#!/usr/bin/env python3
"""Run live read probes and the repository unit tests."""

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
import textwrap
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple, Type

from monarchmoney import CaptchaRequiredException, MonarchMoney, RequireMFAException
from typedmonarchmoney import TypedMonarchMoney

DEFAULT_SESSION_FILE = Path(".mm") / "mm_session.pickle"
DEFAULT_TERMINAL_WIDTH = 100
MAX_TERMINAL_WIDTH = 120
READ_METHOD_PREFIXES = ("get_", "find_", "is_", "list_", "search_")


class SmokeTestError(Exception):
    """An error raised by the test runner."""


class MissingSampleError(SmokeTestError):
    """A read probe requires data that this household does not have."""


class ConsentPrompt:
    """Require explicit consent before accessing a live account."""

    PARAGRAPHS = (
        "TO SUBMIT A PULL REQUEST WITH THIS LIBRARY, YOU MUST RUN THE LOCAL TEST "
        "SUITE DIRECTLY WITH YOUR MONARCH MONEY ACCOUNT.",
        "THE REQUESTS ARE NON-MUTATING READ-ONLY METHODS. THE CHECKS ONLY VALIDATE "
        "THAT VALID JSON IS RETURNED.",
        "THE READ-ONLY REQUESTS GO TO MONARCH MONEY. RETURNED DATA IS USED ONLY ON "
        "YOUR DEVICE DURING THE LOCAL PRE-PUSH CHECK AND IS NOT SENT TO THIS PROJECT "
        "OR GITHUB.",
        "IF YOU ACCEPT THESE CONDITIONS, PLEASE CONTINUE.",
    )

    @classmethod
    def request(cls) -> bool:
        width = min(
            88,
            max(20, shutil.get_terminal_size((DEFAULT_TERMINAL_WIDTH, 24)).columns - 4),
        )
        print()
        print("WARNING")
        print("-" * width)
        for paragraph in cls.PARAGRAPHS:
            print(
                textwrap.fill(
                    paragraph,
                    width=width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
            print()
        print("-" * width)
        while True:
            answer = input("Continue [y/n]: ").strip().lower()
            if answer in {"y", "yes"}:
                print()
                return True
            if answer in {"n", "no"}:
                print()
                return False
            print("Please enter y or n: ", end="", flush=True)


def _truncate(value: Any, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]

    to_json = getattr(value, "to_json", None)
    if callable(to_json):
        encoded = to_json()
        if isinstance(encoded, str):
            return _json_ready(json.loads(encoded))
        return _json_ready(encoded)

    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return {
            key: _json_ready(item)
            for key, item in attributes.items()
            if not key.startswith("_")
        }
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _preview(value: Any, limit: int) -> str:
    try:
        rendered = json.dumps(
            _json_ready(value),
            ensure_ascii=False,
            separators=(",", ":"),
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
        self.skipped = 0

    def skip(self, label: str, detail: str) -> None:
        self.skipped += 1
        self._write("SKIP", label, detail)

    def pass_result(self, label: str, result: Any) -> None:
        self.passed += 1
        self._write("PASS", label, _preview(result, self._detail_limit(label)))

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

    def fail_note(self, label: str, detail: str) -> None:
        self.failed += 1
        self._write("FAIL", label, detail)

    def summary(self) -> None:
        text = (
            f"TOTAL: {self.passed} passed, {self.failed} failed, "
            f"{self.skipped} skipped"
        )
        if self.use_color:
            color = "\033[32m" if self.failed == 0 else "\033[31m"
            text = f"{color}{text}\033[0m"
        print(text)

    def _detail_limit(self, label: str) -> int:
        return max(20, self.width - len(f"[PASS] {label}") - 3)

    def _write(self, status: str, label: str, detail: str) -> None:
        visible_prefix = f"[{status}] {label}"
        detail = _truncate(detail, max(20, self.width - len(visible_prefix) - 3))
        token = f"[{status}]"
        if self.use_color:
            color = {
                "PASS": "\033[32m",
                "FAIL": "\033[31m",
                "SKIP": "\033[33m",
            }[status]
            token = f"{color}{token}\033[0m"
        print(f"{token} {label} - {detail}")


@dataclass
class SampleValues:
    """Values used to satisfy common read-method parameters."""

    account_id: Optional[str] = None
    transaction_id: Optional[str] = None
    category_id: Optional[str] = None
    category_group_id: Optional[str] = None
    account_object: Any = None

    def update(self, method_name: str, result: Any) -> None:
        if method_name == "get_accounts":
            accounts = result.get("accounts") if isinstance(result, dict) else result
            if isinstance(result, dict) and "accounts" not in result:
                accounts = list(result.values())
            account = self._preferred_account(accounts, self.account_id)
            account_id = self._object_id(account)
            self.account_id = account_id
            self.account_object = account if not isinstance(account, dict) else None

        if method_name == "get_all_holdings" and isinstance(result, dict):
            account = self._account_with_holdings(result.get("accounts"))
            account_id = self._object_id(account)
            if account_id is not None:
                self.account_id = account_id

        if method_name == "get_transactions" and isinstance(result, dict):
            transactions = result.get("allTransactions", {}).get("results", [])
            transaction_id = self._first_id(transactions)
            self.transaction_id = transaction_id

        if method_name == "get_transaction_categories" and isinstance(result, dict):
            category_id = self._first_id(result.get("categories"))
            self.category_id = category_id

        if method_name == "get_transaction_category_groups" and isinstance(
            result, dict
        ):
            group_id = self._first_id(result.get("categoryGroups"))
            self.category_group_id = group_id

    @classmethod
    def _preferred_account(cls, accounts: Any, preferred_id: Optional[str]) -> Any:
        if not isinstance(accounts, list):
            return None
        for account in accounts:
            if preferred_id is not None and cls._object_id(account) == preferred_id:
                return account
        for account in accounts:
            account_type = cls._account_type(account)
            if account_type in {
                "brokerage",
                "investment",
                "real_estate",
                "other_assets",
                "vehicle",
                "valuables",
            }:
                return account
        return accounts[0] if accounts else None

    @classmethod
    def _account_with_holdings(cls, accounts: Any) -> Any:
        if not isinstance(accounts, list):
            return None
        for account in accounts:
            if not isinstance(account, dict):
                continue
            holdings = account.get("holdings")
            edges = (
                holdings.get("portfolio", {})
                .get("aggregateHoldings", {})
                .get("edges", [])
                if isinstance(holdings, dict)
                else []
            )
            if edges:
                return account
        return None

    @staticmethod
    def _account_type(account: Any) -> Optional[str]:
        if isinstance(account, dict):
            account_type = account.get("type")
            return account_type.get("name") if isinstance(account_type, dict) else None
        return getattr(account, "type", None)

    @staticmethod
    def _object_id(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            value = value.get("id")
        else:
            value = getattr(value, "id", None)
        return str(value) if value is not None else None

    @classmethod
    def _first_id(cls, values: Any) -> Optional[str]:
        if not isinstance(values, list):
            return None
        for value in values:
            value_id = cls._object_id(value)
            if value_id is not None:
                return value_id
        return None


class ReadMethodDiscovery:
    """Find public asynchronous methods with read-only naming conventions."""

    @staticmethod
    def discover(client: Any) -> List[Tuple[str, Callable[..., Awaitable[Any]]]]:
        methods = []
        for name, method in inspect.getmembers(client, predicate=inspect.ismethod):
            if not name.startswith(
                READ_METHOD_PREFIXES
            ) or not inspect.iscoroutinefunction(method):
                continue
            methods.append((name, method))

        priority = {
            "get_accounts": 0,
            "get_transaction_categories": 1,
            "get_transaction_category_groups": 2,
            "get_transactions": 3,
        }
        return sorted(methods, key=lambda item: (priority.get(item[0], 10), item[0]))


class ArgumentResolver:
    """Build conservative arguments for discovered read methods."""

    def __init__(self, samples: SampleValues) -> None:
        self.samples = samples
        self.today = dt.date.today()

    def resolve(
        self, method: Callable[..., Awaitable[Any]]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        positional: List[Any] = []
        keyword: Dict[str, Any] = {}
        for parameter in inspect.signature(method).parameters.values():
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            value = self._value(parameter)
            if value is None and parameter.default is not inspect.Parameter.empty:
                continue
            if value is None:
                raise MissingSampleError(
                    f"no sample available for required parameter {parameter.name}"
                )

            if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                positional.append(value)
            else:
                keyword[parameter.name] = value
        return positional, keyword

    def _value(self, parameter: inspect.Parameter) -> Any:
        name = parameter.name.lower()
        if name in {"limit", "page_size"}:
            return 10
        # Keep optional filters (including dates and booleans) at their defaults.
        # Only pagination size is overridden to keep live responses small.
        if parameter.default is not inspect.Parameter.empty:
            return None
        if name in {"offset", "page"}:
            return 0
        if name == "start_date":
            return (self.today - dt.timedelta(days=30)).isoformat()
        if name == "end_date":
            return self.today.isoformat()
        if name in {"timeframe", "period"}:
            return "month"
        if name in {
            "account",
        }:
            return self.samples.account_object or self.samples.account_id
        if name in {"account_id", "user_id", "institution_id"}:
            return self._account_id(parameter.annotation)
        if name in {"account_ids", "user_ids", "institution_ids"}:
            return [self.samples.account_id] if self.samples.account_id else None
        if name in {"transaction_id", "merchant_id"}:
            return self.samples.transaction_id if name == "transaction_id" else "0"
        if name == "category_id":
            return self.samples.category_id
        if name == "category_ids":
            return [self.samples.category_id] if self.samples.category_id else None
        if name in {"category_group_id", "group_id"}:
            return self.samples.category_group_id
        if name in {"query", "search"}:
            return ""

        annotation = str(parameter.annotation)
        if "bool" in annotation:
            return False
        if "list" in annotation.lower():
            return []
        if "dict" in annotation.lower():
            return {}
        if "datetime" in annotation:
            return dt.datetime.now()
        if "date" in annotation:
            return self.today
        if parameter.annotation is int or (
            "int" in annotation and "str" not in annotation
        ):
            return 0
        if parameter.annotation is float or "float" in annotation:
            return 0.0
        return ""

    def _account_id(self, annotation: Any) -> Any:
        if self.samples.account_id is None:
            return None
        annotation_text = str(annotation)
        if annotation is int or (
            "int" in annotation_text and "str" not in annotation_text
        ):
            try:
                return int(self.samples.account_id)
            except ValueError as error:
                raise SmokeTestError("sample account ID is not an integer") from error
        return self.samples.account_id


class SessionAuthenticator:
    """Authenticate once and reuse the saved session for the typed client."""

    def __init__(self, session_file: Path) -> None:
        self.session_file = session_file

    async def authenticate(self, client: MonarchMoney, allow_interactive: bool) -> str:
        saved_error: Optional[BaseException] = None
        if self.session_file.is_file():
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    await client.login(use_saved_session=True, save_session=True)
                return f"saved session {self.session_file}"
            except Exception as error:  # noqa: BLE001
                saved_error = error

        if not allow_interactive:
            detail = "saved session unavailable for typed client"
            if saved_error is not None:
                detail += f": {saved_error}"
            raise SmokeTestError(detail)

        cookie_string = os.getenv("MONARCH_COOKIE_STRING", "").strip()
        if cookie_string:
            await client.login_with_cookies(cookie_string, save_session=True)
            return f"cookie session saved to {self.session_file}"

        email = os.getenv("MONARCH_EMAIL", "").strip()
        if not email:
            email = self._prompt_email()
        password = os.getenv("MONARCH_PASSWORD", "")
        if not password:
            password = self._prompt_password()
        try:
            try:
                await client.login(
                    email=email,
                    password=password,
                    use_saved_session=False,
                    save_session=True,
                    mfa_secret_key=os.getenv("MONARCH_MFA_SECRET_KEY"),
                )
            except RequireMFAException:
                code = os.getenv("MONARCH_MFA_CODE", "").strip()
                if not code:
                    code = self._prompt_mfa_code()
                await client.multi_factor_authenticate(
                    email,
                    password,
                    code,
                    trusted_device=True,
                )
                client.save_session(str(self.session_file))
        except CaptchaRequiredException:
            print(
                "Password login requires CAPTCHA. Log in through your browser, "
                "then copy the Cookie request header containing session_id and csrftoken."
            )
            cookie_string = getpass.getpass("Cookie header (hidden): ").strip()
            await client.login_with_cookies(cookie_string, save_session=True)
            return f"cookie session saved to {self.session_file}"
        except Exception as error:
            if saved_error is not None:
                raise SmokeTestError(
                    f"saved session unavailable; fresh login failed: {error}"
                ) from error
            raise
        return f"new session saved to {self.session_file}"

    @staticmethod
    def _prompt_email() -> str:
        while True:
            email = input("Email: ").strip()
            if email:
                return email
            print("Email cannot be blank.")

    @staticmethod
    def _prompt_password() -> str:
        while True:
            password = getpass.getpass("Password: ")
            if password:
                return password
            print("Password cannot be blank.")

    @staticmethod
    def _prompt_mfa_code() -> str:
        while True:
            code = input("MFA code: ").strip()
            if code:
                return code
            print("MFA code cannot be blank.")


class LiveReadSuite:
    """Run discovered read methods against one client implementation."""

    def __init__(
        self,
        client_type: Type[MonarchMoney],
        label: str,
        session_file: Path,
        timeout: int,
        reporter: TerminalReporter,
        samples: SampleValues,
    ) -> None:
        self.client = client_type(session_file=str(session_file), timeout=timeout)
        self.label = label
        self.session_file = session_file
        self.reporter = reporter
        self.samples = samples
        self.resolver = ArgumentResolver(samples)
        self.authenticated = False

    async def run(self, allow_interactive_login: bool) -> bool:
        methods = ReadMethodDiscovery.discover(self.client)
        if not methods:
            self.reporter.fail_note(
                f"{self.label}.discovery",
                "ERROR: no public read methods discovered",
            )
            return False

        try:
            description = await SessionAuthenticator(self.session_file).authenticate(
                self.client,
                allow_interactive_login,
            )
        except Exception as error:  # noqa: BLE001
            self.reporter.fail(f"{self.label}.login", error)
            self._report_unavailable(methods)
            return False

        self.reporter.pass_note(f"{self.label}.login", description)
        self.authenticated = True
        methods_passed = True
        for method_name, method in methods:
            methods_passed = await self._check(method_name, method) and methods_passed
        return methods_passed

    def report_login_unavailable(self, detail: str) -> None:
        methods = ReadMethodDiscovery.discover(self.client)
        self.reporter.fail_note(f"{self.label}.login", detail)
        self._report_unavailable(methods)

    async def _check(
        self,
        method_name: str,
        method: Callable[..., Awaitable[Any]],
    ) -> bool:
        label = f"{self.label}.{method_name}"
        try:
            positional, keyword = self.resolver.resolve(method)
        except MissingSampleError as error:
            self.reporter.skip(label, str(error))
            return True
        except Exception as error:  # noqa: BLE001
            self.reporter.fail(label, error)
            return False

        try:
            result = await method(*positional, **keyword)
            if result is None:
                if self.label == "TypedMonarchMoney" and "holdings" in method_name:
                    self.reporter.pass_note(label, "no holdings")
                    return True
                raise SmokeTestError("method returned null instead of JSON data")
            _json_ready(result)
        except Exception as error:  # noqa: BLE001
            self.reporter.fail(label, error)
            return False

        self.samples.update(method_name, result)
        self.reporter.pass_result(label, result)
        return True

    def _report_unavailable(
        self,
        methods: Sequence[Tuple[str, Callable[..., Awaitable[Any]]]],
    ) -> None:
        error = SmokeTestError("authentication unavailable; read check was not run")
        for method_name, _ in methods:
            self.reporter.fail(f"{self.label}.{method_name}", error)


class UnitTestSuite:
    """Run the repository's fixture and model tests."""

    def __init__(self, root: Path, reporter: TerminalReporter) -> None:
        self.root = root
        self.reporter = reporter

    def run(self) -> bool:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            self.reporter.pass_note("tests/", "unittest suite passed")
            return True

        output = (result.stdout + result.stderr).strip()
        detail = " ".join(output.split()) if output else "unittest suite failed"
        self.reporter.fail_note("tests/", _truncate(detail, 200))
        return False


class TestRunner:
    """Run live read probes for both clients, followed by unit tests."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.root = Path(__file__).resolve().parent
        self.args = args
        self.reporter = TerminalReporter(args.color, args.no_color)

    def run(self) -> int:
        if not ConsentPrompt.request():
            self.reporter.fail_note("consent", "live account testing was declined")
            live_passed = False
        else:
            try:
                live_passed = asyncio.run(self._run_live_suites())
            except Exception as error:  # noqa: BLE001
                self.reporter.fail("live-tests", error)
                live_passed = False

        unit_passed = UnitTestSuite(self.root, self.reporter).run()
        all_passed = live_passed and unit_passed
        (
            self.reporter.pass_note("run_tests", "all checks passed")
            if all_passed
            else self.reporter.fail_note("run_tests", "one or more checks failed")
        )
        self.reporter.summary()
        return int(not all_passed)

    async def _run_live_suites(self) -> bool:
        samples = SampleValues()
        raw_suite = LiveReadSuite(
            MonarchMoney,
            "MonarchMoney",
            Path(self.args.session_file).expanduser(),
            self.args.timeout,
            self.reporter,
            samples,
        )
        raw_passed = await raw_suite.run(allow_interactive_login=True)

        typed_suite = LiveReadSuite(
            TypedMonarchMoney,
            "TypedMonarchMoney",
            Path(self.args.session_file).expanduser(),
            self.args.timeout,
            self.reporter,
            samples,
        )
        if raw_suite.authenticated:
            typed_passed = await typed_suite.run(allow_interactive_login=False)
        else:
            typed_suite.report_login_unavailable(
                "ERROR: raw client authentication failed; typed check was not run"
            )
            typed_passed = False
        return raw_passed and typed_passed


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
        help="request timeout in seconds (default: 30)",
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
    return parser.parse_args(argv)


def run(argv: Optional[Sequence[str]] = None) -> int:
    return TestRunner(_parse_args(argv)).run()


def main(argv: Optional[Sequence[str]] = None) -> None:
    try:
        raise SystemExit(run(argv))
    except KeyboardInterrupt:
        print("[FAIL] run_tests - interrupted", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
