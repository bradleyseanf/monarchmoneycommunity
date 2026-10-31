"""Read-only datasets selected by Monarch's web application."""

from __future__ import annotations

from importlib.resources import files
from typing import Protocol

from gql import GraphQLRequest, gql
from graphql import DocumentNode

from .read_types import (
    JSONObject,
    MerchantPaginationError,
    MerchantsResponse,
)


def _query(operation: str) -> GraphQLRequest:
    return gql(
        files("monarchmoney")
        .joinpath("queries")
        .joinpath(f"{operation}.graphql")
        .read_text(encoding="utf-8")
    )


class ReadApiMixin(Protocol):
    """Additional reads sharing the client's existing authenticated gql_call."""

    async def gql_call(
        self,
        operation: str,
        graphql_query: DocumentNode | GraphQLRequest,
        variables: JSONObject = ...,
    ) -> JSONObject: ...

    async def get_account_details(self, account_id: str | int) -> JSONObject:
        """Return the account's metadata/settings/notes and snapshotsForAccount."""
        return await self.gql_call(
            operation="ExportAccountComplete",
            graphql_query=_query("ExportAccountComplete"),
            variables={"id": str(account_id)},
        )

    async def get_account_roster(
        self, include_deleted: bool = True, include_hidden: bool = True
    ) -> JSONObject:
        """Return account identities, including deletedAt, from institution settings.

        Deleted identities may not be accessible through get_account_details.
        This roster does not replace the richer metadata returned by get_accounts.
        """
        return await self.gql_call(
            operation="GetAccountRoster",
            graphql_query=_query("GetAccountRoster"),
            variables={
                "includeDeleted": include_deleted,
                "includeHidden": include_hidden,
            },
        )

    async def get_merchants(
        self,
        limit: int = 100,
        offset: int = 0,
        include_merchants_without_transactions: bool = True,
    ) -> JSONObject:
        """Return a merchant page and merchantCount, whose scope can differ."""
        if limit <= 0 or offset < 0:
            message = "limit must be positive and offset must be nonnegative"
            raise ValueError(message)
        return await self.gql_call(
            operation="ExportMerchantsComplete",
            graphql_query=_query("ExportMerchantsComplete"),
            variables={
                "limit": limit,
                "offset": offset,
                "includeMerchantsWithoutTransactions": include_merchants_without_transactions,
            },
        )

    async def get_all_merchants(
        self,
        limit: int = 100,
        include_merchants_without_transactions: bool = True,
    ) -> MerchantsResponse:
        """Exhaust offset pages; reject duplicate IDs instead of losing records.

        merchantCount is the first page's server-reported count, not a stopping
        condition or a guarantee of len(merchants). A short or empty page ends
        the scan. Concurrent merchant changes can invalidate an offset scan.
        """
        merchants: list[JSONObject] = []
        seen_ids: set[str] = set()
        offset = 0
        reported_count = 0
        while True:
            page = await self.get_merchants(
                limit=limit,
                offset=offset,
                include_merchants_without_transactions=include_merchants_without_transactions,
            )
            count = page.get("merchantCount")
            records = page.get("merchants")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise MerchantPaginationError(
                    offset, "merchantCount must be a nonnegative integer"
                )
            if not isinstance(records, list):
                raise MerchantPaginationError(offset, "merchants must be a list")
            if offset == 0:
                reported_count = count
            for record in records:
                if not isinstance(record, dict):
                    raise MerchantPaginationError(offset, "merchant must be an object")
                merchant_id = record.get("id")
                if not isinstance(merchant_id, str) or not merchant_id:
                    raise MerchantPaginationError(
                        offset, "merchant id must be a nonempty string"
                    )
                if merchant_id in seen_ids:
                    raise MerchantPaginationError(offset, "duplicate merchant id")
                seen_ids.add(merchant_id)
                merchants.append(record)
            if len(records) < limit:
                return {"merchants": merchants, "merchantCount": reported_count}
            offset += len(records)

    async def get_retail_transactions(
        self,
        first: int = 100,
        after_cursor: str | None = None,
        filters: JSONObject | None = None,
    ) -> JSONObject:
        """Return a retailTransactionsConnection page, including pageInfo."""
        if first <= 0:
            message = "first must be positive"
            raise ValueError(message)
        return await self.gql_call(
            operation="Common_RetailTransactionsConnection",
            graphql_query=_query("Common_RetailTransactionsConnection"),
            variables={"first": first, "afterCursor": after_cursor, "filters": filters},
        )

    async def get_activity_events(
        self,
        first: int = 100,
        after_cursor: str | None = None,
        exclude_event_types: list[str] | None = None,
    ) -> JSONObject:
        """Return an activityEvents page without marking notifications read."""
        if first <= 0:
            message = "first must be positive"
            raise ValueError(message)
        variables: JSONObject = {"first": first, "afterCursor": after_cursor}
        variables["excludeEventTypes"] = (
            list(exclude_event_types) if exclude_event_types is not None else None
        )
        return await self.gql_call(
            operation="Common_GetNotificationCenter",
            graphql_query=_query("Common_GetNotificationCenter"),
            variables=variables,
        )

    async def get_user_profile(self) -> JSONObject:
        """Return me, including the profile and preferences selected by the UI."""
        return await self.gql_call(
            operation="Common_GetMe", graphql_query=_query("Common_GetMe")
        )

    async def get_household_preferences(self) -> JSONObject:
        """Return preferences, insight topics, and household budget settings."""
        return await self.gql_call(
            operation="Common_GetHouseholdPreferences",
            graphql_query=_query("Common_GetHouseholdPreferences"),
        )

    async def get_report_configurations(self) -> JSONObject:
        """Return saved report configurations, views, and transaction filters."""
        return await self.gql_call(
            operation="Common_GetReportConfigurations",
            graphql_query=_query("Common_GetReportConfigurations"),
        )

    async def get_recurring_transaction_streams(
        self, include_liabilities: bool = True
    ) -> JSONObject:
        """Return stream definitions and next forecasts, not occurrence history.

        Includes pending streams and preserves isActive/reviewStatus as returned.
        The web queries do not establish coverage of ignored/deleted streams.
        """
        return await self.gql_call(
            operation="Common_GetRecurringStreams",
            graphql_query=_query("Common_GetRecurringStreams"),
            variables={"includeLiabilities": include_liabilities},
        )
