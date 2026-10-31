import asyncio
import calendar
import csv
import getpass
import json
import mimetypes
import os
import sys
import pickle
import time
import uuid
from dataclasses import dataclass
from io import StringIO
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Union, Literal

import oathtool
from aiohttp import ClientSession, FormData
from gql import Client, GraphQLRequest, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import DocumentNode

from importlib.resources import files

from .read_types import JSONObject, MerchantPaginationError, MerchantsResponse


_LEGACY_QUERIES = {
    "Common_GetHouseholdPreferences": "household/Common_GetHouseholdPreferences",
    "Common_GetMe": "household/Common_GetMe",
    "Common_GetNotificationCenter": "activity/Common_GetNotificationCenter",
    "Common_GetRecurringStreams": "recurring/Common_GetRecurringStreams",
    "Common_GetReportConfigurations": "household/Common_GetReportConfigurations",
    "Common_RetailTransactionsConnection": "transactions/Common_RetailTransactionsConnection",
    "ExportAccountComplete": "accounts/ExportAccountComplete",
    "ExportMerchantsComplete": "merchants/ExportMerchantsComplete",
    "GetAccountRoster": "accounts/GetAccountRoster",
}


def _query(operation: str) -> GraphQLRequest:
    return gql(
        files("monarchmoney")
        .joinpath("queries")
        .joinpath(f"{_LEGACY_QUERIES.get(operation, operation)}.graphql")
        .read_text(encoding="utf-8")
    )


AUTH_HEADER_KEY = "authorization"
CSRF_KEY = "csrftoken"
DEFAULT_RECORD_LIMIT = 100
DEFAULT_DELAY_SECS = 10
ERRORS_KEY = "error_code"
SESSION_DIR = ".mm"
SESSION_FILE = f"{SESSION_DIR}/mm_session.pickle"
DEFAULT_TIMEOUT_SECS = 300

REQUIRED_COOKIES = ("session_id", "csrftoken")

MONARCH_COOKIE_HEADERS = {
    "Origin": "https://app.monarch.com",
    "Referer": "https://app.monarch.com/",
    "monarch-client": "web",
    "monarch-client-version": "2025.05",
}


@dataclass
class BalanceHistoryRow:
    date: datetime
    amount: float
    account_name: Optional[str] = None


class MonarchMoneyEndpoints(object):
    BASE_URL = "https://api.monarch.com"
    CLOUDINARY_BASE_URL = "https://api.cloudinary.com"

    @classmethod
    def getLoginEndpoint(cls) -> str:
        return cls.BASE_URL + "/auth/login/"

    @classmethod
    def getGraphQL(cls) -> str:
        return cls.BASE_URL + "/graphql"

    @classmethod
    def getAccountBalanceHistoryUploadEndpoint(cls) -> str:
        return cls.BASE_URL + "/account-balance-history/upload/"

    @classmethod
    def getAttachmentUploadEndpoint(cls) -> str:
        return cls.CLOUDINARY_BASE_URL + "/v1_1/monarch-money/image/upload/"

    @classmethod
    def getRetailSyncFilesEndpoint(cls, sync_id: str) -> str:
        return cls.BASE_URL + f"/retail-sync/{sync_id}/files"


class RequireMFAException(Exception):
    pass


class LoginFailedException(Exception):
    pass


class RequestFailedException(Exception):
    pass


class CaptchaRequiredException(LoginFailedException):
    pass


class _UnsetType:
    """Distinguishes an omitted update argument from an explicit null."""


_UNSET = _UnsetType()


def _to_iso_date(
    value: Optional[Union[date, datetime, str]],
) -> Optional[str]:
    """
    Normalizes a date, a datetime, or an already-ISO datestring into a
    YYYY-MM-DD string that can be JSON-encoded for a GraphQL variable.
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


from . import accounts as _accounts
from .accounts import AccountsMixin
from . import budgets as _budgets
from .budgets import BudgetsMixin
from . import household as _household
from .household import HouseholdMixin
from . import transactions as _transactions
from .transactions import TransactionsMixin
from . import uploads as _uploads
from .uploads import UploadsMixin
from . import merchants as _merchants
from .merchants import MerchantsMixin
from . import goals as _goals
from .goals import GoalsMixin
from . import recurring as _recurring
from .recurring import RecurringMixin
from . import credit as _credit
from .credit import CreditMixin
from . import rules as _rules
from .rules import RulesMixin
from . import activity as _activity
from .activity import ActivityMixin


class MonarchMoney(
    AccountsMixin,
    BudgetsMixin,
    HouseholdMixin,
    TransactionsMixin,
    UploadsMixin,
    MerchantsMixin,
    GoalsMixin,
    RecurringMixin,
    CreditMixin,
    RulesMixin,
    ActivityMixin,
):
    def __init__(
        self,
        session_file: str = SESSION_FILE,
        timeout: int = 10,
        token: Optional[str] = None,
    ) -> None:
        self._headers = {
            "Accept": "application/json",
            "Client-Platform": "web",
            "Content-Type": "application/json",
            "User-Agent": "MonarchMoneyAPI (https://github.com/bradleyseanf/monarchmoneycommunity)",
        }
        if token:
            self._headers["Authorization"] = f"Token {token}"

        self._session_file = session_file
        self._token = token
        self._cookies: Optional[Dict[str, str]] = None
        self._auth_mode: str = "token"
        self._timeout = timeout

    @staticmethod
    def _looks_like_jwt(token: str) -> bool:
        # Ably/features tokens are JWTs (header.payload.signature)
        return isinstance(token, str) and token.count(".") == 2

    @staticmethod
    def _is_long_lived(token_expiration) -> bool:
        # Monarch long-lived browser-style sessions return tokenExpiration = null/None
        return token_expiration in (None, "null")

    @property
    def timeout(self) -> int:
        """The timeout, in seconds, for GraphQL calls."""
        return self._timeout

    def set_timeout(self, timeout_secs: int) -> None:
        """Sets the default timeout on GraphQL API calls, in seconds."""
        self._timeout = timeout_secs

    @property
    def token(self) -> Optional[str]:
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token

    def set_cookies(self, cookies: Dict[str, str]) -> None:
        missing = [k for k in REQUIRED_COOKIES if k not in cookies]
        if missing:
            raise LoginFailedException(
                f"Missing required cookies: {', '.join(missing)}. "
                "Ensure you copy both session_id and csrftoken from your browser."
            )
        self._cookies = cookies
        self._auth_mode = "cookie"
        self._headers.pop("Authorization", None)
        self._headers.update(MONARCH_COOKIE_HEADERS)
        self._headers["X-Csrftoken"] = cookies["csrftoken"]

    async def login_with_cookies(
        self,
        cookie_string: str,
        save_session: bool = True,
        verify: bool = True,
    ) -> None:
        """Authenticate using a browser Cookie header string."""
        cookies = self._parse_cookie_string(cookie_string)
        self.set_cookies(cookies)
        if verify:
            await self.get_accounts()
        if save_session:
            self.save_session(self._session_file)

    @staticmethod
    def _parse_cookie_string(cookie_string: str) -> Dict[str, str]:
        cookies: Dict[str, str] = {}
        for pair in cookie_string.split(";"):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, _, value = pair.partition("=")
            cookies[key.strip()] = value.strip()
        return cookies

    async def interactive_login(
        self, use_saved_session: bool = True, save_session: bool = True
    ) -> None:
        """Performs an interactive login for iPython and similar environments."""
        email = input("Email: ")
        passwd = getpass.getpass("Password: ")
        try:
            await self.login(email, passwd, use_saved_session, save_session)
        except RequireMFAException:
            await self.multi_factor_authenticate(
                email, passwd, input("Two Factor Code: ")
            )
            if save_session:
                self.save_session(self._session_file)

    async def login(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        use_saved_session: bool = True,
        save_session: bool = True,
        mfa_secret_key: Optional[str] = None,
    ) -> None:
        """Logs into a Monarch Money account."""
        if use_saved_session and os.path.exists(self._session_file):
            print(f"Using saved session found at {self._session_file}", file=sys.stderr)
            self.load_session(self._session_file)
            return

        if (email is None) or (password is None) or (email == "") or (password == ""):
            raise LoginFailedException(
                "Email and password are required to login when not using a saved session."
            )
        await self._login_user(email, password, mfa_secret_key)
        if save_session:
            self.save_session(self._session_file)

    async def multi_factor_authenticate(
        self, email: str, password: str, code: str, trusted_device: bool = True
    ) -> None:
        """Performs multi-factor authentication to access a Monarch Money account.

        Set trusted_device=True to request a long-lived token (browser-style session).
        """
        await self._multi_factor_authenticate(email, password, code, trusted_device)

    async def _upload_form_data(self, url: str, data: FormData) -> dict:
        """
        Retrieves the response from the server for a given URL and form data.
        """

        # Remove Accept and Content-Type headers because the Monarch upload endpoint
        # rejects these values and returns an "Unsupported Media Type" error.
        headers = self._headers.copy()
        headers.pop("Accept", None)
        headers.pop("Content-Type", None)

        if "monarch.com" in url:
            cookies = self._cookies if self._auth_mode == "cookie" else None
        else:
            cookies = None
            for key in list(MONARCH_COOKIE_HEADERS) + ["X-Csrftoken"]:
                headers.pop(key, None)
        async with ClientSession(
            headers=headers, cookies=cookies, trust_env=True
        ) as session:
            resp = await session.post(url, data=data)
            if resp.status != 200:
                raise RequestFailedException(f"HTTP Code {resp.status}: {resp.reason}")

            return await resp.json()

    def _get_current_date(self) -> str:
        """
        Returns the current date as a string formatted like %Y-%m-%d.
        """
        return _to_iso_date(datetime.now())

    def _get_start_of_current_month(self) -> str:
        """
        Returns the date for the first day of the current month as a string formatted as %Y-%m-%d.
        """
        now = datetime.now()
        start_of_month = now.replace(day=1)
        return _to_iso_date(start_of_month)

    def _get_end_of_current_month(self) -> str:
        """
        Returns the date for the last day of the current month as a string formatted as %Y-%m-%d.
        """
        now = datetime.now()
        _, last_day = calendar.monthrange(now.year, now.month)
        end_of_month = now.replace(day=last_day)
        return _to_iso_date(end_of_month)

    async def gql_call(
        self,
        operation: str,
        graphql_query: Union[DocumentNode, GraphQLRequest],
        variables: Dict[str, Any] = {},
    ) -> Dict[str, Any]:
        """
        Makes a GraphQL call to Monarch Money's API.
        """
        return await self._get_graphql_client().execute_async(
            request=graphql_query,
            variable_values=variables,
            operation_name=operation,
        )

    def save_session(self, filename: Optional[str] = None) -> None:
        """Saves auth credentials needed to access a Monarch Money account."""
        if filename is None:
            filename = self._session_file
        filename = os.path.abspath(filename)

        if not self._token and not self._cookies:
            raise LoginFailedException("No credentials set; cannot save session.")

        if self._token and self._looks_like_jwt(self._token):
            raise LoginFailedException(
                "Refusing to save a JWT-style token to session; this looks like the 1-hour "
                "features token, not the long-lived login session token."
            )

        session_data: Dict[str, Any] = {
            "token": self._token,
            "auth_mode": self._auth_mode,
        }
        if self._cookies:
            session_data["cookies"] = self._cookies

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as fh:
            pickle.dump(session_data, fh)

    def load_session(self, filename: Optional[str] = None) -> None:
        """Loads auth credentials from a pickle file."""
        if filename is None:
            filename = self._session_file

        with open(filename, "rb") as fh:
            data = pickle.load(fh)

        auth_mode = data.get("auth_mode", "token")

        saved_cookies = data.get("cookies")
        if isinstance(saved_cookies, dict):
            self._cookies = saved_cookies

        if auth_mode == "cookie" and isinstance(saved_cookies, dict):
            has_required = all(k in saved_cookies for k in REQUIRED_COOKIES)
            if has_required:
                self.set_cookies(saved_cookies)
                if data.get("token"):
                    self._token = data["token"]
                return

        if data.get("token"):
            self.set_token(data["token"])
            self._headers["Authorization"] = f"Token {self._token}"
        else:
            raise LoginFailedException(
                "Session file contains no valid credentials. "
                "Re-login or use login_with_cookies()."
            )

    def delete_session(self, filename: Optional[str] = None) -> None:
        """
        Deletes the session file.
        """
        if filename is None:
            filename = self._session_file

        if os.path.exists(filename):
            os.remove(filename)

    async def _login_user(
        self, email: str, password: str, mfa_secret_key: Optional[str]
    ) -> None:
        """
        Performs the initial login to a Monarch Money account.
        Requires/persists only the long-lived login token (NOT the 1-hour features JWT).
        """
        data = {
            "password": password,
            "supports_mfa": True,
            "trusted_device": True,
            "username": email,
        }
        if mfa_secret_key:
            data["totp"] = oathtool.generate_otp(mfa_secret_key)

        async with ClientSession(headers=self._headers, trust_env=True) as session:
            async with session.post(
                MonarchMoneyEndpoints.getLoginEndpoint(), json=data
            ) as resp:
                if resp.status == 403:
                    try:
                        body = await resp.json()
                        if body.get("error_code") == "CAPTCHA_REQUIRED":
                            raise CaptchaRequiredException(
                                "Programmatic login is blocked by CAPTCHA. "
                                "Use login_with_cookies() to authenticate with "
                                "browser cookies instead."
                            )
                    except CaptchaRequiredException:
                        raise
                    except Exception:
                        pass
                    raise RequireMFAException("Multi-Factor Auth Required")
                if resp.status != 200:
                    try:
                        response = await resp.json()
                        if "detail" in response:
                            raise LoginFailedException(response["detail"])
                        if "error_code" in response:
                            raise LoginFailedException(response["error_code"])
                        raise LoginFailedException(f"Unrecognized error: {response}")
                    except (
                        LoginFailedException,
                        RequireMFAException,
                        CaptchaRequiredException,
                    ):
                        raise
                    except Exception:
                        raise LoginFailedException(
                            f"HTTP Code {resp.status}: {resp.reason}"
                        )

                response = await resp.json()
                tok = response.get("token")
                tokexp = response.get("tokenExpiration")

                if not tok:
                    raise LoginFailedException("Login succeeded but no token returned.")
                if self._looks_like_jwt(tok):
                    raise LoginFailedException(
                        "Received a JWT-style token (likely 1-hour features token). "
                        "Refusing to save; ensure we are using /auth/login/ token."
                    )
                if tokexp not in (None, "null"):
                    raise LoginFailedException(
                        f"Short-lived token returned (tokenExpiration={tokexp}). "
                        "Retry with trusted_device=True or complete MFA as trusted device."
                    )

                self.set_token(tok)
                self._headers["Authorization"] = f"Token {self._token}"

    async def _multi_factor_authenticate(
        self,
        email: str,
        password: str,
        code: Optional[str] = None,
        trusted_device: bool = True,
    ) -> None:
        """
        Performs the MFA step of login.
        Requires/persists only the long-lived login token (NOT the 1-hour features JWT).
        """

        data = {
            "password": password,
            "supports_mfa": True,
            "totp": code,
            "trusted_device": bool(trusted_device),  # request trusted device token
            "username": email,
        }

        async with ClientSession(headers=self._headers, trust_env=True) as session:
            async with session.post(
                MonarchMoneyEndpoints.getLoginEndpoint(), json=data
            ) as resp:
                if resp.status == 403:
                    try:
                        body = await resp.json()
                        if body.get("error_code") == "CAPTCHA_REQUIRED":
                            raise CaptchaRequiredException(
                                "Programmatic login is blocked by CAPTCHA. "
                                "Use login_with_cookies() to authenticate with "
                                "browser cookies instead."
                            )
                    except CaptchaRequiredException:
                        raise
                    except Exception:
                        pass
                    raise RequireMFAException("Multi-Factor Auth Required")
                if resp.status != 200:
                    try:
                        response = await resp.json()
                        if "detail" in response:
                            raise LoginFailedException(response["detail"])
                        if "error_code" in response:
                            raise LoginFailedException(response["error_code"])
                        raise LoginFailedException(f"Unrecognized error: {response}")
                    except (
                        LoginFailedException,
                        RequireMFAException,
                        CaptchaRequiredException,
                    ):
                        raise
                    except Exception:
                        raise LoginFailedException(
                            f"HTTP Code {resp.status}: {resp.reason}"
                        )

                response = await resp.json()
                tok = response.get("token")
                tokexp = response.get("tokenExpiration")

                if not tok:
                    raise LoginFailedException("MFA succeeded but no token returned.")

                if self._looks_like_jwt(tok):
                    raise LoginFailedException(
                        "Received a JWT-style token (likely 1-hour features token). "
                        "Refusing to save; ensure this is the /auth/login/ token."
                    )

                if tokexp not in (None, "null"):
                    raise LoginFailedException(
                        f"MFA returned short-lived token (tokenExpiration={tokexp}). "
                        "Make sure trusted_device=True when performing MFA."
                    )

                self.set_token(tok)
                self._headers["Authorization"] = f"Token {self._token}"

    def _get_graphql_client(self) -> Client:
        """
        Creates a correctly configured GraphQL client for connecting to Monarch Money.
        """
        if self._headers is None:
            raise LoginFailedException(
                "Make sure you call login() first or provide a session token!"
            )
        cookies = self._cookies if self._auth_mode == "cookie" else None
        transport = AIOHTTPTransport(
            url=MonarchMoneyEndpoints.getGraphQL(),
            headers=self._headers,
            cookies=cookies,
            timeout=self._timeout,
            ssl=True,
            client_session_args={"trust_env": True},
        )
        return Client(
            transport=transport,
            fetch_schema_from_transport=False,
            execute_timeout=self._timeout,
        )

    def _convert_to_csv_string(self, csv_content: List[BalanceHistoryRow]) -> str:
        """
        Converts a list of BalanceHistoryRow to CSV string
        :param csv_content: A list of BalanceHistoryRow to upload to the account balance
        """

        if not csv_content:
            return ""

        csv_string = StringIO()
        writer = csv.writer(csv_string)
        writer.writerow(["Date", "Amount", "Account Name"])

        for row in csv_content:
            writer.writerow(
                [row.date.strftime("%Y-%m-%d"), row.amount, row.account_name]
            )

        return csv_string.getvalue()


_accounts.MonarchMoney = MonarchMoney
_rules.MonarchMoney = MonarchMoney

# Keep every historical method directly on MonarchMoney for code that inspects or
# monkeypatches its own __dict__, while implementations remain purpose-based.
for _mixin in (
    AccountsMixin,
    BudgetsMixin,
    HouseholdMixin,
    TransactionsMixin,
    UploadsMixin,
    MerchantsMixin,
    GoalsMixin,
    RecurringMixin,
    CreditMixin,
    RulesMixin,
    ActivityMixin,
):
    for _name, _member in _mixin.__dict__.items():
        if not _name.startswith("__") and _name not in MonarchMoney.__dict__:
            setattr(MonarchMoney, _name, _member)
del _mixin, _name, _member
