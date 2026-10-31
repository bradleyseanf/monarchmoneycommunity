"""Recurring client operations."""

from .monarchmoney import (
    Any,
    Dict,
    Optional,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class RecurringMixin:

    async def get_recurring_transactions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetches upcoming recurring transactions from Monarch Money's API.  This includes
        all merchant data, as well as the accounts where the charge will take place.
        """
        query = _query("recurring/get_recurring_transactions")

        variables = {"startDate": start_date, "endDate": end_date}

        if (start_date is None) ^ (end_date is None):
            raise Exception(
                "You must specify both a start_date and end_date, not just one of them."
            )
        elif start_date is None and end_date is None:
            variables["startDate"] = self._get_start_of_current_month()
            variables["endDate"] = self._get_end_of_current_month()

        return await self.gql_call(
            "Web_GetUpcomingRecurringTransactionItems", query, variables
        )

    async def get_recurring_transaction_streams(
        self, include_liabilities: "bool" = True
    ) -> "JSONObject":
        """Return stream definitions and next forecasts, not occurrence history.

        Includes pending streams and preserves isActive/reviewStatus as returned.
        The web queries do not establish coverage of ignored/deleted streams.
        """
        return await self.gql_call(
            operation="Common_GetRecurringStreams",
            graphql_query=_query("Common_GetRecurringStreams"),
            variables={"includeLiabilities": include_liabilities},
        )
