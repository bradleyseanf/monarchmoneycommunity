"""Merchants client operations."""

from .monarchmoney import (
    Any,
    Dict,
    JSONObject,
    MerchantPaginationError,
    Optional,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class MerchantsMixin:

    async def update_reoccuring(
        self,
        merchant_id: str,
        name: str,
        is_recurring: Optional[bool] = None,
        frequency: Optional[str] = None,
        base_date: Optional[str] = None,
        amount: Optional[float] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Updates recurring merchant settings for an existing merchant.

        :param merchant_id: The merchant id to update.
        :param name: The merchant name.
        :param is_recurring: Whether the merchant should be marked recurring.
        :param frequency: The recurrence frequency (e.g. monthly).
        :param base_date: The recurrence start date in YYYY-MM-DD format.
        :param amount: The recurrence amount.
        :param is_active: Whether the recurrence is active.
        """
        query = _query("merchants/update_reoccuring")

        variables: Dict[str, Any] = {
            "input": {
                "merchantId": merchant_id,
                "name": name,
            }
        }

        recurrence: Dict[str, Any] = {}
        if is_recurring is not None:
            recurrence["isRecurring"] = is_recurring
        if frequency is not None:
            recurrence["frequency"] = frequency
        if base_date is not None:
            recurrence["baseDate"] = base_date
        if amount is not None:
            recurrence["amount"] = amount
        if is_active is not None:
            recurrence["isActive"] = is_active

        if recurrence:
            variables["input"]["recurrence"] = recurrence

        return await self.gql_call(
            operation="Common_UpdateMerchant",
            graphql_query=query,
            variables=variables,
        )

    async def delete_merchant(
        self, merchant_id: str, move_to_merchant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deletes a merchant, optionally merging it into another merchant first.

        This is the "Merge & delete" action in Monarch's Edit merchant dialog.

        :param merchant_id: The merchant id to delete.
        :param move_to_merchant_id: Optional merchant id to move the deleted
            merchant's relations to. When given, this merges ``merchant_id``
            into ``move_to_merchant_id`` (the web app's "Merge & delete"):
            the source's transactions are reassigned to the target and the
            source merchant is removed. When omitted, the merchant record is
            deleted with nothing moved; the web app only offers this for
            merchants with no transactions.
        :raises ValueError: if ``move_to_merchant_id`` equals ``merchant_id``.
        """
        if move_to_merchant_id is not None and move_to_merchant_id == merchant_id:
            raise ValueError("move_to_merchant_id must differ from merchant_id")

        query = _query("merchants/delete_merchant")

        variables: Dict[str, Any] = {"merchantId": merchant_id}
        if move_to_merchant_id is not None:
            variables["moveToId"] = move_to_merchant_id

        return await self.gql_call(
            operation="Common_DeleteMerchant",
            graphql_query=query,
            variables=variables,
        )

    async def get_merchants(
        self,
        limit: "int" = 100,
        offset: "int" = 0,
        include_merchants_without_transactions: "bool" = True,
    ) -> "JSONObject":
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
        limit: "int" = 100,
        include_merchants_without_transactions: "bool" = True,
    ) -> "MerchantsResponse":
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
