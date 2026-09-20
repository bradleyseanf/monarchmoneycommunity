"""Typed wrapper around Monarch Money."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from monarchmoney.monarchmoney import DEFAULT_RECORD_LIMIT, MonarchMoney, SESSION_FILE


def _parse_float(value: Any, default: float = -1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    value_str = str(value)
    if value_str.endswith("Z"):
        value_str = value_str[:-1] + "+00:00"
    return datetime.fromisoformat(value_str)


def _normalize_url(url: Optional[str]) -> str:
    if not url:
        return "https://monarch.com"
    if url.startswith(("http://", "https://")):
        return url
    return f"http://{url}"


VALUE_ACCOUNT_TYPES = {
    "other_assets",
    "real-estate",
    "valuables",
    "vehicle",
}


class MonarchAccount:
    def __init__(self, data: Dict[str, Any]) -> None:
        institution = data.get("institution") or {}
        credential = data.get("credential") or {}
        account_type = data.get("type") or {}
        account_subtype = data.get("subtype") or {}

        self.id = str(data.get("id", ""))
        self.logo_url = data.get("logoUrl") or institution.get("logo")
        self.name = data.get("displayName") or data.get("name") or ""
        self.balance = _parse_float(
            data.get("currentBalance", data.get("displayBalance"))
        )
        self.type = account_type.get("name", "")
        self.type_name = account_type.get("display", self.type)
        self.subtype = account_subtype.get("name", "")
        self.subtype_name = account_subtype.get("display", self.subtype)
        self.data_provider = (
            credential.get("dataProvider") or data.get("dataProvider") or "Manual entry"
        )
        self.last_update = _parse_datetime(
            data.get("updatedAt")
            or data.get("displayLastUpdatedAt")
            or data.get("createdAt")
            or datetime.fromtimestamp(0, tz=timezone.utc).isoformat()
        )
        self.date_created = _parse_datetime(
            data.get("createdAt")
            or data.get("updatedAt")
            or datetime.fromtimestamp(0, tz=timezone.utc).isoformat()
        )
        self.institution_url = _normalize_url(
            institution.get("url") or data.get("institutionUrl")
        )
        self.institution_name = (
            institution.get("name") or data.get("institutionName") or "Manual entry"
        )
        self.account_owner = data.get("ownedByUser")
        self.holdings = None

    @property
    def is_value_account(self) -> bool:
        return self.type in VALUE_ACCOUNT_TYPES

    @property
    def is_balance_account(self) -> bool:
        return not self.is_value_account


class MonarchCashflowSummary:
    def __init__(self, data: Dict[str, Any]) -> None:
        summary_data = data
        summary = data.get("summary")
        if isinstance(summary, list) and summary:
            summary_data = summary[0].get("summary", summary[0])
        elif isinstance(summary, dict):
            summary_data = summary

        self.income = _parse_float(summary_data.get("sumIncome", -1.0))
        self.expenses = _parse_float(summary_data.get("sumExpense", -1.0))
        self.savings = _parse_float(summary_data.get("savings", -1.0))
        self.savings_rate = _parse_float(summary_data.get("savingsRate", -1.0))


class MonarchBudgetMonth:
    """Amounts assigned to a budget category for one calendar month."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.month = str(data["month"])
        self.planned_amount = _parse_optional_float(data.get("plannedCashFlowAmount"))
        self.actual_amount = _parse_optional_float(data.get("actualAmount"))
        self.remaining_amount = _parse_optional_float(data.get("remainingAmount"))


class MonarchBudget:
    """A Monarch budget category and all monthly amounts returned for it."""

    def __init__(
        self,
        data: Dict[str, Any],
        group_name: str,
        monthly_amounts: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.id = str(data.get("id", ""))
        self.name = data.get("name", "")
        self.group_name = group_name
        self.monthly_amounts: Dict[str, MonarchBudgetMonth] = {}
        for month_data in monthly_amounts or []:
            month = MonarchBudgetMonth(month_data)
            self.monthly_amounts[month.month] = month


class MonarchSubscription:
    def __init__(self, data: Dict[str, Any]) -> None:
        subscription = (
            data.get("subscription")
            if isinstance(data.get("subscription"), dict)
            else data
        )
        self.id = str(subscription.get("id", ""))
        self.payment_source = subscription.get("paymentSource", "")
        self.referral_code = subscription.get("referralCode", "")
        self.is_on_free_trial = bool(subscription.get("isOnFreeTrial"))
        self.has_premium_entitlement = bool(subscription.get("hasPremiumEntitlement"))


class MonarchHolding:
    def __init__(self, data: Dict[str, Any]) -> None:
        node = data.get("node") or {}
        holdings = node.get("holdings") or []
        first_holding = holdings[0] if holdings else {}
        security = node.get("security") or {}

        self.total_value = _parse_float(node.get("totalValue"))
        self.quantity = _parse_float(node.get("quantity"))
        self.percentage = 0.0

        if security:
            self.ticker = security.get("ticker", "")
            self.name = security.get("name") or first_holding.get("name", "")
            self.type = security.get("type") or first_holding.get("type")
            self.type_name = security.get("typeDisplay") or first_holding.get(
                "typeDisplay", ""
            )
            self.price = _parse_float(security.get("currentPrice"))
            self.price_date = security.get("currentPriceUpdatedAt")
        else:
            self.ticker = first_holding.get("ticker", "")
            self.name = first_holding.get("name", "")
            self.type = first_holding.get("type")
            self.type_name = first_holding.get("typeDisplay", "")
            self.price = _parse_float(first_holding.get("closingPrice"))
            self.price_date = first_holding.get("closingPriceUpdatedAt")
            if self.ticker == "CUR:USD" and not self.name:
                self.name = "cash"
                self.price = 1.0


class MonarchHoldings:
    def __init__(
        self,
        data: Dict[str, Any],
        account_or_id: Optional[Union[MonarchAccount, int, str]] = None,
    ) -> None:
        self.holdings: List[MonarchHolding] = []
        self.total_value = 0.0
        self._account = (
            account_or_id if isinstance(account_or_id, MonarchAccount) else None
        )
        self._account_id_str = (
            str(account_or_id.id)
            if isinstance(account_or_id, MonarchAccount)
            else str(account_or_id) if account_or_id is not None else "UNKNOWN"
        )

        edges = data.get("portfolio", {}).get("aggregateHoldings", {}).get("edges", [])
        for item in edges:
            holding = MonarchHolding(item)
            self.holdings.append(holding)
            self.total_value += holding.total_value

        for holding in self.holdings:
            holding.percentage = (
                holding.total_value / self.total_value if self.total_value else 0.0
            )

    def to_json(self) -> str:
        return json.dumps(
            {
                holding.ticker: {
                    "quantity": holding.quantity,
                    "totalValue": holding.total_value,
                    "type": holding.type_name,
                    "percentage": round(holding.percentage * 100.0, 1),
                    "name": holding.name,
                    "sharePrice": holding.price,
                    "sharePriceUpdate": holding.price_date,
                }
                for holding in self.holdings
            },
            separators=(",", ":"),
        )


class TypedMonarchMoney(MonarchMoney):
    def __init__(
        self,
        session_file: str = SESSION_FILE,
        timeout: int = 10,
        token: Optional[str] = None,
    ) -> None:
        super().__init__(session_file, timeout, token)

    async def get_accounts(
        self, *, with_holdings: bool = False
    ) -> List[MonarchAccount]:
        data = await super().get_accounts()
        accounts = [MonarchAccount(account) for account in data.get("accounts", [])]
        if with_holdings and accounts:
            holdings = await asyncio.gather(
                *(self.get_account_holdings(account) for account in accounts)
            )
            for account, holding in zip(accounts, holdings):
                account.holdings = holding
        return accounts

    async def get_accounts_as_dict_with_id_key(
        self, *, with_holdings: bool = False
    ) -> Dict[str, MonarchAccount]:
        accounts = await self.get_accounts(with_holdings=with_holdings)
        return {account.id: account for account in accounts}

    async def get_cashflow_summary(
        self,
        limit: int = DEFAULT_RECORD_LIMIT,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> MonarchCashflowSummary:
        return MonarchCashflowSummary(
            await super().get_cashflow_summary(limit, start_date, end_date)
        )

    async def get_budgets_as_dict_with_id_key(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_legacy_goals: bool = False,
        use_v2_goals: bool = True,
    ) -> Dict[str, MonarchBudget]:
        """Return all budget categories keyed by category ID."""
        data = await super().get_budgets(
            start_date=start_date,
            end_date=end_date,
            use_legacy_goals=use_legacy_goals,
            use_v2_goals=use_v2_goals,
        )

        monthly_amounts_by_category: Dict[str, List[Dict[str, Any]]] = {}
        budget_data = data.get("budgetData") or {}
        for category_amounts in budget_data.get("monthlyAmountsByCategory", []):
            category_id = str((category_amounts.get("category") or {}).get("id", ""))
            if category_id:
                monthly_amounts_by_category[category_id] = (
                    category_amounts.get("monthlyAmounts") or []
                )

        budgets: Dict[str, MonarchBudget] = {}
        for group in data.get("categoryGroups", []):
            for category in group.get("categories") or []:
                category_id = str(category.get("id", ""))
                if not category_id:
                    continue
                budgets[category_id] = MonarchBudget(
                    category,
                    group_name=group.get("name", ""),
                    monthly_amounts=monthly_amounts_by_category.get(category_id),
                )
        return budgets

    async def get_subscription_details(self) -> MonarchSubscription:
        return MonarchSubscription(await super().get_subscription_details())

    async def get_account_holdings_for_id(
        self, account_id: Union[str, int]
    ) -> Optional[MonarchHoldings]:
        data = await super().get_account_holdings(int(account_id))
        edges = data.get("portfolio", {}).get("aggregateHoldings", {}).get("edges", [])
        if not edges:
            return None
        return MonarchHoldings(data, account_id)

    async def get_account_holdings(
        self, account: Union[MonarchAccount, str, int]
    ) -> Optional[MonarchHoldings]:
        if isinstance(account, MonarchAccount):
            return await self.get_account_holdings_for_id(account.id)
        return await self.get_account_holdings_for_id(account)


MonarchMoneyTyped = TypedMonarchMoney
