"""Transactions client operations."""

from .monarchmoney import (
    Any,
    DEFAULT_RECORD_LIMIT,
    Dict,
    List,
    Literal,
    Optional,
    RequestFailedException,
    Union,
    _to_iso_date,
    asyncio,
    datetime,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class TransactionsMixin:

    async def get_transactions_summary(self) -> Dict[str, Any]:
        """
        Gets transactions summary from the account.
        """

        query = _query("transactions/get_transactions_summary")
        return await self.gql_call(
            operation="GetTransactionsPage",
            graphql_query=query,
        )

    async def get_transactions(
        self,
        limit: int = DEFAULT_RECORD_LIMIT,
        offset: Optional[int] = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: str = "",
        category_ids: List[str] = [],
        account_ids: List[str] = [],
        tag_ids: List[str] = [],
        has_attachments: Optional[bool] = None,
        has_notes: Optional[bool] = None,
        hidden_from_reports: Optional[bool] = None,
        is_split: Optional[bool] = None,
        is_recurring: Optional[bool] = None,
        is_pending: Optional[bool] = None,
        imported_from_mint: Optional[bool] = None,
        synced_from_institution: Optional[bool] = None,
        needs_review: Optional[bool] = None,
        transaction_visibility: Optional[
            Literal["hidden_transactions_only", "all_transactions"]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Gets transaction data from the account.

        :param limit: the maximum number of transactions to download, defaults to DEFAULT_RECORD_LIMIT.
        :param offset: the number of transactions to skip (offset) before retrieving results.
        :param start_date: the earliest date to get transactions from, in "yyyy-mm-dd" format.
        :param end_date: the latest date to get transactions from, in "yyyy-mm-dd" format.
        :param search: a string to filter transactions. use empty string for all results.
        :param category_ids: a list of category ids to filter.
        :param account_ids: a list of account ids to filter.
        :param tag_ids: a list of tag ids to filter.
        :param has_attachments: a bool to filter for whether the transactions have attachments.
        :param has_notes: a bool to filter for whether the transactions have notes.
        :param hidden_from_reports: a bool to filter for whether the transactions are hidden from reports.
        :param is_split: a bool to filter for whether the transactions are split.
        :param is_recurring: a bool to filter for whether the transactions are recurring.
        :param is_pending: a bool to filter for whether the transactions are pending.
        :param imported_from_mint: a bool to filter for whether the transactions were imported from mint.
        :param synced_from_institution: a bool to filter for whether the transactions were synced from an institution.
        :param needs_review: a bool to filter for whether the transactions need review.
        :param transaction_visibility: a string to set scope of transactions to return.
          None (default) for only non-hidden transactions.
          "hidden_transactions_only" for only hidden transactions.
          "all_transactions" for hidden and non-hidden transactions.
        """

        query = _query("transactions/get_transactions")

        variables = {
            "offset": offset,
            "limit": limit,
            "orderBy": "date",
            "filters": {
                "search": search,
                "categories": category_ids,
                "accounts": account_ids,
                "tags": tag_ids,
            },
        }

        # If bool filters are not defined (i.e. None), then it should not apply the filter
        if has_attachments is not None:
            variables["filters"]["hasAttachments"] = has_attachments

        if has_notes is not None:
            variables["filters"]["hasNotes"] = has_notes

        if hidden_from_reports is not None:
            variables["filters"]["hideFromReports"] = hidden_from_reports

        if is_recurring is not None:
            variables["filters"]["isRecurring"] = is_recurring

        if is_split is not None:
            variables["filters"]["isSplit"] = is_split

        if is_pending is not None:
            variables["filters"]["isPending"] = is_pending

        if imported_from_mint is not None:
            variables["filters"]["importedFromMint"] = imported_from_mint

        if synced_from_institution is not None:
            variables["filters"]["syncedFromInstitution"] = synced_from_institution

        if needs_review is not None:
            variables["filters"]["needsReview"] = needs_review

        if transaction_visibility is not None:
            variables["filters"]["transactionVisibility"] = transaction_visibility

        if start_date and end_date:
            variables["filters"]["startDate"] = start_date
            variables["filters"]["endDate"] = end_date
        elif bool(start_date) != bool(end_date):
            raise Exception(
                "You must specify both a startDate and endDate, not just one of them."
            )

        return await self.gql_call(
            operation="GetTransactionsList", graphql_query=query, variables=variables
        )

    async def create_transaction(
        self,
        date: str,
        account_id: str,
        amount: float,
        merchant_name: str,
        category_id: str,
        notes: str = "",
        update_balance: bool = False,
    ) -> Dict[str, Any]:
        """
        Creates a transaction with the given parameters
        """
        query = _query("transactions/create_transaction")

        variables = {
            "input": {
                "date": date,
                "accountId": account_id,
                "amount": round(amount, 2),
                "merchantName": merchant_name,
                "categoryId": category_id,
                "notes": notes,
                "shouldUpdateBalance": update_balance,
            }
        }

        return await self.gql_call(
            operation="Common_CreateTransactionMutation",
            graphql_query=query,
            variables=variables,
        )

    async def delete_transaction(self, transaction_id: str) -> bool:
        """
        Deletes the given transaction.

        :param transaction_id: the ID of the transaction targeted for deletion.
        """
        query = _query("transactions/delete_transaction")

        variables = {
            "input": {
                "transactionId": transaction_id,
            },
        }

        response = await self.gql_call(
            operation="Common_DeleteTransactionMutation",
            graphql_query=query,
            variables=variables,
        )

        if not response["deleteTransaction"]["deleted"]:
            raise RequestFailedException(response["deleteTransaction"]["errors"])

        return True

    async def get_transaction_categories(self) -> Dict[str, Any]:
        """
        Gets all the categories configured in the account.
        """
        query = _query("transactions/get_transaction_categories")
        return await self.gql_call(operation="GetCategories", graphql_query=query)

    async def delete_transaction_category(self, category_id: str) -> bool:
        query = _query("transactions/delete_transaction_category")

        variables = {
            "id": category_id,
        }

        response = await self.gql_call(
            operation="Web_DeleteCategory", graphql_query=query, variables=variables
        )

        if not response["deleteCategory"]["deleted"]:
            raise RequestFailedException(response["deleteCategory"]["errors"])

        return True

    async def delete_transaction_categories(
        self, category_ids: List[str]
    ) -> List[Union[bool, BaseException]]:
        """
        Deletes a list of transaction categories.
        """
        return await asyncio.gather(
            *[self.delete_transaction_category(id) for id in category_ids],
            return_exceptions=True,
        )

    async def get_transaction_category_groups(self) -> Dict[str, Any]:
        """
        Gets all the category groups configured in the account.
        """
        query = _query("transactions/get_transaction_category_groups")
        return await self.gql_call(
            operation="ManageGetCategoryGroups", graphql_query=query
        )

    async def update_transaction_category(
        self,
        category_id: str,
        name: Optional[str] = None,
        icon: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates a transaction category. Only the fields you pass are changed.

        :param category_id: the id of the category to update.
        :param name: new name.
        :param icon: new icon (unicode string or emoji).
        :param group_id: move the category into this category group
          (ids from get_transaction_category_groups).
        :return: the updated category, including its group.
        """
        query = _query("transactions/update_transaction_category")
        category_input: Dict[str, Any] = {"id": category_id}
        if name is not None:
            category_input["name"] = name
        if icon is not None:
            category_input["icon"] = icon
        if group_id is not None:
            category_input["group"] = group_id

        response = await self.gql_call(
            operation="Web_UpdateCategory",
            graphql_query=query,
            variables={"input": category_input},
        )
        payload = response["updateCategory"]
        if self._has_payload_errors(payload.get("errors")) or not payload.get(
            "category"
        ):
            raise RequestFailedException(payload.get("errors"))
        return payload["category"]

    async def create_transaction_category(
        self,
        group_id: str,
        transaction_category_name: str,
        rollover_start_month: datetime = datetime.today().replace(day=1),
        icon: str = "\U00002753",
        rollover_enabled: bool = False,
        rollover_type: str = "monthly",
    ):
        """
        Creates a new transaction category
        :param group_id: The transaction category group id
        :param transaction_category_name: The name of the transaction category being created
        :param icon: The icon of the transaction category. This accepts the unicode string or emoji.
        :param rollover_start_month: The datetime of the rollover start month
        :param rollover_enabled: A bool whether the transaction category should be rolled over or not
        :param rollover_type: The budget roll over type
        """

        query = _query("transactions/create_transaction_category")
        variables = {
            "input": {
                "group": group_id,
                "name": transaction_category_name,
                "icon": icon,
                "rolloverEnabled": rollover_enabled,
                "rolloverType": rollover_type,
                "rolloverStartMonth": _to_iso_date(rollover_start_month),
            },
        }

        return await self.gql_call(
            operation="Web_CreateCategory",
            graphql_query=query,
            variables=variables,
        )

    async def create_transaction_tag(self, name: str, color: str) -> Dict[str, Any]:
        """
        Creates a new transaction tag.
        :param name: The name of the tag
        :param color: The color of the tag.
          The observed format is six-digit RGB hexadecimal, including the leading number sign.
          Example: color="#19D2A5".
          More information can be found https://en.wikipedia.org/wiki/Web_colors#Hex_triplet.
          Does not appear to be limited to the color selections in the dashboard.
        """
        mutation = _query("transactions/create_transaction_tag")
        variables = {"input": {"name": name, "color": color}}

        return await self.gql_call(
            operation="Common_CreateTransactionTag",
            graphql_query=mutation,
            variables=variables,
        )

    async def get_transaction_tags(self) -> Dict[str, Any]:
        """
        Gets all the tags configured in the account.
        """
        query = _query("transactions/get_transaction_tags")
        return await self.gql_call(
            operation="GetHouseholdTransactionTags", graphql_query=query
        )

    async def set_transaction_tags(
        self,
        transaction_id: str,
        tag_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Sets the tags on a transaction
        :param transaction_id: The transaction id
        :param tag_ids: The list of tag ids to set on the transaction.
          Overwrites existing tags. Empty list removes all tags.
        """

        query = _query("transactions/set_transaction_tags")

        variables = {
            "input": {"transactionId": transaction_id, "tagIds": tag_ids},
        }

        return await self.gql_call(
            operation="Web_SetTransactionTags",
            graphql_query=query,
            variables=variables,
        )

    async def get_transaction_details(
        self, transaction_id: str, redirect_posted: bool = True
    ) -> Dict[str, Any]:
        """
        Returns detailed information about a transaction.

        :param transaction_id: the transaction to fetch.
        :param redirect_posted: whether to redirect posted transactions. Defaults to True.
        """
        query = _query("transactions/get_transaction_details")

        variables = {
            "id": transaction_id,
            "redirectPosted": redirect_posted,
        }

        return await self.gql_call(
            operation="GetTransactionDrawer", variables=variables, graphql_query=query
        )

    async def get_transaction_splits(self, transaction_id: str) -> Dict[str, Any]:
        """
        Returns the transaction split information for a transaction.

        :param transaction_id: the transaction to query.
        """
        query = _query("transactions/get_transaction_splits")

        variables = {"id": transaction_id}

        return await self.gql_call(
            operation="TransactionSplitQuery", variables=variables, graphql_query=query
        )

    async def update_transaction_splits(
        self, transaction_id: str, split_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Creates, modifies, or deletes the splits for a given transaction.

        Returns the split information for the update transaction.

        :param transaction_id: the original transaction to modify.
        :param split_data: the splits to create, modify, or delete.
          If empty list or None is given, all splits will be deleted.
          If split_data is given, all existing splits for transaction_id will be replaced with the new splits.
          split_data takes the shape: [{"merchantName": "...", "amount": -12.34, "categoryId": "231"}, split2, split3, ...]
          sum([split.amount for split in split_data]) must equal transaction_id.amount.
        """
        query = _query("transactions/update_transaction_splits")

        if split_data is None:
            split_data = []

        variables = {
            "input": {"transactionId": transaction_id, "splitData": split_data}
        }

        return await self.gql_call(
            operation="Common_SplitTransactionMutation",
            variables=variables,
            graphql_query=query,
        )

    async def get_cashflow(
        self,
        limit: int = DEFAULT_RECORD_LIMIT,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gets all the categories configured in the account.
        """
        query = _query("transactions/get_cashflow")

        variables = {
            "limit": limit,
            "orderBy": "date",
            "filters": {
                "search": "",
                "categories": [],
                "accounts": [],
                "tags": [],
            },
        }

        if start_date and end_date:
            variables["filters"]["startDate"] = start_date
            variables["filters"]["endDate"] = end_date
        elif (start_date is None) ^ (end_date is None):
            raise Exception(
                "You must specify both a startDate and endDate, not just one of them."
            )
        else:
            variables["filters"]["startDate"] = self._get_start_of_current_month()
            variables["filters"]["endDate"] = self._get_end_of_current_month()

        return await self.gql_call(
            operation="Web_GetCashFlowPage", variables=variables, graphql_query=query
        )

    async def get_cashflow_summary(
        self,
        limit: int = DEFAULT_RECORD_LIMIT,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gets all the categories configured in the account.
        """
        query = _query("transactions/get_cashflow_summary")

        variables = {
            "limit": limit,
            "orderBy": "date",
            "filters": {
                "search": "",
                "categories": [],
                "accounts": [],
                "tags": [],
            },
        }

        if start_date and end_date:
            variables["filters"]["startDate"] = start_date
            variables["filters"]["endDate"] = end_date
        elif bool(start_date) != bool(end_date):
            raise Exception(
                "You must specify both a startDate and endDate, not just one of them."
            )
        else:
            variables["filters"]["startDate"] = self._get_start_of_current_month()
            variables["filters"]["endDate"] = self._get_end_of_current_month()

        return await self.gql_call(
            operation="Web_GetCashFlowPage", variables=variables, graphql_query=query
        )

    async def update_transaction(
        self,
        transaction_id: str,
        category_id: Optional[str] = None,
        merchant_name: Optional[str] = None,
        goal_id: Optional[str] = None,
        amount: Optional[float] = None,
        date: Optional[str] = None,
        hide_from_reports: Optional[bool] = None,
        needs_review: Optional[bool] = None,
        reviewed: Optional[bool] = None,
        notes: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates a single existing transaction as identified by the transaction_id
        The only required attribute is transaction_id. Calling this function with
        only the transaction_id will have no effect on the existing transaction data
        but will not cause an error.

        Comments on parameters:
        - transaction_id: Must match an existing transaction_id returned from Monarch
        - category_id: This parameter is only needed when the user wants to change the
            current category. When provided, it must match an existing category_id returned
            from Monarch. An empty string is equivalent to the parameter not being passed.
        - merchant_name: This parameter is only needed when the user wants to change
            the existing merchant name. Empty strings are ignored by the Monarch API
            when passed since a non-empty merchant name is required for all transactions
        - goal_id: This parameter is only needed when the user wants to change
            the existing goal.  When provided, it must match an existing goal_id returned
            from Monarch.  An empty string can be passed to clear out existing goal associations.
        - amount:  This parameter is only needed when the user wants to update
            the existing transaction amount. Empty strings are explicitly ignored by this code
            to avoid errors in the API.
        - date:  This parameter is only needed when the user wants to update
            the existing transaction date. Empty strings are explicitly ignored by this code
            to avoid errors in the API.  Required format is "2023-10-30"
        - hide_from_reports: This parameter is only needed when the user wants to update the
            existing transaction's hide-from-reports value.  If passed, the parameter is cast to
            Booleans to avoid API issues.
        - needs_review: This parameter is only needed when the user wants to update the
            existing transaction's needs-review value.  If passed, the parameter is cast to
            Booleans to avoid API issues.
        - reviewed: This parameter is only needed when the user wants to mark a transaction
            as reviewed. If passed, the parameter is cast to Boolean. To remove the reviewed
            status from a transaction, use needs_review=True.
        - notes: This parameter is only needed when the user wants to change
            the existing note.  An empty string can be passed to clear out existing notes.
        - owner_user_id: Member ID from get_household_members() to assign as owner.
            An empty string sets ownership to Shared. None leaves ownership unchanged.

        Examples:
        - To update a note: mm.update_transaction(
            transaction_id="160820461792094418",
            notes="my note")

        - To clear a note: mm.update_transaction(
            transaction_id="160820461792094418",
            notes="")

        - To update all items:
            mm.update_transaction(
                transaction_id="160820461792094418",
                category_id="160185840107743863",
                merchant_name="Amazon",
                goal_id="160826408575920275",
                amount=123.45,
                date="2023-11-09",
                hide_from_reports=False,
                needs_review="ThisWillBeCastToTrue",
                reviewed=True,
                notes=f'Updated On: {datetime.now().strftime("%m/%d/%Y %H:%M:%S")}',
            )
        """
        query = _query("transactions/update_transaction")

        variables: dict[str, Any] = {
            "input": {
                "id": transaction_id,
            }
        }

        # Within Monarch, these values cannot be empty. Monarch will simply ignore updates
        # to category and merchant name that are empty strings or None.
        # As such, no need to avoid adding to variables
        variables["input"].update({"category": category_id})
        variables["input"].update({"name": merchant_name})

        # Monarch will not accept nulls for amount and date.
        # Don't update values if an empty string is passed or if parameter is None
        if amount:
            variables["input"].update({"amount": amount})
        if date:
            variables["input"].update({"date": date})

        # Don't update values if the parameter is not passed or explicitly set to None.
        # Passed values must be cast to bool to avoid API errors
        if hide_from_reports is not None:
            variables["input"].update({"hideFromReports": bool(hide_from_reports)})
        if needs_review is not None:
            variables["input"].update({"needsReview": bool(needs_review)})
        if reviewed is not None:
            variables["input"].update({"reviewed": bool(reviewed)})

        # We want an empty string to clear the goal and notes parameters but the values should not
        # be cleared if the parameter isn't passed
        # Don't update values if the parameter is not passed or explicitly set to None.
        if goal_id is not None:
            variables["input"].update({"goalId": goal_id})
        if notes is not None:
            variables["input"].update({"notes": notes})
        if owner_user_id is not None:
            variables["input"].update({"ownerUserId": owner_user_id or None})

        return await self.gql_call(
            operation="Web_TransactionDrawerUpdateTransaction",
            variables=variables,
            graphql_query=query,
        )

    async def find_duplicate_transactions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        account_ids: Optional[List[str]] = None,
        page_size: int = 500,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Finds groups of duplicate transactions using the Plaid-reported fields.

        Two transactions are considered duplicates when they share the SAME:
          - date
          - amount
          - plaidName (Plaid's raw transaction description / reference string)
          - account id

        This is the correct dedup key because ``plaidName`` carries Plaid's
        per-event reference. Two legitimate same-day, same-merchant, same-amount
        charges (e.g. two separate Alaska Airlines seat fees) will carry
        DIFFERENT reference numbers inside ``plaidName`` and will not be grouped.
        Only rows that Plaid / Monarch wrote twice from a single upstream event
        share an identical ``plaidName`` string.

        Common causes of duplicates this method catches:
          - Re-linking an Apple Card / Apple Cash / Apple Savings account (Monarch
            re-inserts the full historical range as new rows — a known issue
            documented in Monarch's own help center).
          - Institution re-authentications after credential changes.
          - Plaid write retries (microsecond-spaced sequential IDs).

        :param start_date: Optional ISO date lower bound (inclusive).
        :param end_date: Optional ISO date upper bound (inclusive).
        :param account_ids: Optional account-id filter.
        :param page_size: Pagination size when walking ``get_transactions``.
        :param max_pages: Optional positive page limit. Defaults to scanning all
            matching transactions; a limited scan only finds duplicates within
            the fetched pages.

        :returns: A list of duplicate groups. Each group is a dict of the form::

            {
                "date": "2025-09-19",
                "amount": -54.03,
                "plaidName": "Apple",
                "account_id": "203496913710973596",
                "account_name": "Apple Card",
                "transactions": [<txn dict>, <txn dict>, ...],
            }

            The ``transactions`` list is sorted oldest-first by ``createdAt``, so
            callers wanting to keep the original and delete the re-inserted copies
            can simply retain ``transactions[0]`` and pass the rest to
            :meth:`delete_transaction`.
        """
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be positive")
        all_txns: List[Dict[str, Any]] = []
        offset = 0
        pages_fetched = 0
        while True:
            result = await self.get_transactions(
                limit=page_size,
                offset=offset,
                start_date=start_date,
                end_date=end_date,
                account_ids=account_ids or [],
            )
            pages_fetched += 1
            batch = result.get("allTransactions", {}).get("results", []) or []
            if not batch:
                break
            all_txns.extend(batch)
            total = result.get("allTransactions", {}).get("totalCount") or 0
            if len(all_txns) >= total or (
                max_pages is not None and pages_fetched >= max_pages
            ):
                break
            offset += page_size

        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for t in all_txns:
            plaid_name = (t.get("plaidName") or "").strip()
            if not plaid_name:
                continue
            account = t.get("account") or {}
            key = (
                t.get("date"),
                t.get("amount"),
                plaid_name,
                account.get("id"),
            )
            groups.setdefault(key, []).append(t)

        duplicates: List[Dict[str, Any]] = []
        for key, txns in groups.items():
            if len(txns) < 2:
                continue
            txns_sorted = sorted(txns, key=lambda x: x.get("createdAt") or "")
            duplicates.append(
                {
                    "date": key[0],
                    "amount": key[1],
                    "plaidName": key[2],
                    "account_id": key[3],
                    "account_name": (txns_sorted[0].get("account") or {}).get(
                        "displayName"
                    ),
                    "transactions": txns_sorted,
                }
            )

        return duplicates

    async def get_retail_transactions(
        self,
        first: "int" = 100,
        after_cursor: "str | None" = None,
        filters: "JSONObject | None" = None,
    ) -> "JSONObject":
        """Return a retailTransactionsConnection page, including pageInfo."""
        if first <= 0:
            message = "first must be positive"
            raise ValueError(message)
        return await self.gql_call(
            operation="Common_RetailTransactionsConnection",
            graphql_query=_query("Common_RetailTransactionsConnection"),
            variables={"first": first, "afterCursor": after_cursor, "filters": filters},
        )
