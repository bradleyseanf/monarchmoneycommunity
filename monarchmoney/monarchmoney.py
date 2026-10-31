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
from .auth import AuthMixin
from .session import SessionMixin
from .transport import TransportMixin


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
    AuthMixin,
    SessionMixin,
    TransportMixin,
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
    AuthMixin,
    SessionMixin,
    TransportMixin,
):
    for _name, _member in _mixin.__dict__.items():
        if not _name.startswith("__") and _name not in MonarchMoney.__dict__:
            setattr(MonarchMoney, _name, _member)
del _mixin, _name, _member
