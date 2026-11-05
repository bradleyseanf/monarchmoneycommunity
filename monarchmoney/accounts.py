"""Accounts client operations."""

from .monarchmoney import (
    Any,
    DEFAULT_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    Dict,
    List,
    Optional,
    RequestFailedException,
    Union,
    _to_iso_date,
    asyncio,
    date,
    datetime,
    time,
    timedelta,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class AccountsMixin:

    async def get_accounts(self) -> Dict[str, Any]:
        """
        Gets the list of accounts configured in the Monarch Money account.
        """
        query = _query("accounts/get_accounts")
        return await self.gql_call(
            operation="GetAccounts",
            graphql_query=query,
        )

    async def get_account_type_options(self) -> Dict[str, Any]:
        """
        Retrieves a list of available account types and their subtypes.
        """
        query = _query("accounts/get_account_type_options")
        return await self.gql_call(
            operation="GetAccountTypeOptions",
            graphql_query=query,
        )

    async def get_recent_account_balances(
        self, start_date: Optional[Union[date, datetime, str]] = None
    ) -> Dict[str, Any]:
        """
        Retrieves the daily balance for all accounts starting from `start_date`.
        `start_date` is an ISO formatted datestring, e.g. YYYY-MM-DD.
        If `start_date` is None, then the last 31 days are requested.
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=31)

        query = _query("accounts/get_recent_account_balances")
        return await self.gql_call(
            operation="GetAccountRecentBalances",
            graphql_query=query,
            variables={"startDate": _to_iso_date(start_date)},
        )

    async def get_account_snapshots_by_type(self, start_date: str, timeframe: str):
        """
        Retrieves snapshots of the net values of all accounts of a given type, with either a yearly
        monthly granularity.
        `start_date` is an ISO datestring in the format YYYY-MM-DD, e.g. 2024-04-01,
        containing the date to begin the snapshots from
        `timeframe` is one of "year" or "month".

        Note, `month` in the snapshot results is not a full ISO datestring, as it doesn't include the day.
        Instead, it looks like, e.g., 2023-01
        """
        if timeframe not in ("year", "month"):
            raise Exception(f'Unknown timeframe "{timeframe}"')

        query = _query("accounts/get_account_snapshots_by_type")
        return await self.gql_call(
            operation="GetSnapshotsByAccountType",
            graphql_query=query,
            variables={"startDate": start_date, "timeframe": timeframe},
        )

    async def get_aggregate_snapshots(
        self,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
        account_type: Optional[str] = None,
    ) -> dict:
        """
        Retrieves the daily net value of all accounts, optionally between `start_date` and `end_date`,
        and optionally only for accounts of type `account_type`.

        :param start_date: a `date`, a `datetime`, or an ISO datestring formatted as YYYY-MM-DD.
            Defaults to 150 years ago today, matching the mobile app.
        :param end_date: a `date`, a `datetime`, or an ISO datestring formatted as YYYY-MM-DD.
        """
        query = _query("accounts/get_aggregate_snapshots")

        if start_date is None:
            # The mobile app defaults to 150 years ago today
            # The mobile app might have a leap year bug, so instead default to setting day=1
            today = date.today()
            start_date = date(year=today.year - 150, month=today.month, day=1)

        return await self.gql_call(
            operation="GetAggregateSnapshots",
            graphql_query=query,
            variables={
                "filters": {
                    "startDate": _to_iso_date(start_date),
                    "endDate": _to_iso_date(end_date),
                    "accountType": account_type,
                }
            },
        )

    async def create_manual_account(
        self,
        account_type: str,
        account_sub_type: str,
        is_in_net_worth: bool,
        account_name: str,
        account_balance: float = 0,
    ) -> Dict[str, Any]:
        """
        Creates a new manual account

        :param account_type: The string of account group type (i.e. loan, other_liability, other_asset, etc)
        :param account_sub_type: The string sub type of the account (i.e. auto, commercial, mortgage, line_of_credit, etc)
        :param is_in_net_worth: A boolean if the account should be considered in the net worth calculation
        :param account_name: The string of the account name
        :param display_balance: a float of the amount of the account balance when the account is created
        """
        query = _query("accounts/create_manual_account")
        variables = {
            "input": {
                "type": account_type,
                "subtype": account_sub_type,
                "includeInNetWorth": is_in_net_worth,
                "name": account_name,
                "displayBalance": account_balance,
            },
        }

        return await self.gql_call(
            operation="Web_CreateManualAccount",
            graphql_query=query,
            variables=variables,
        )

    async def update_account(
        self,
        account_id: str,
        account_name: Optional[str] = None,
        account_balance: Optional[float] = None,
        account_type: Optional[str] = None,
        account_sub_type: Optional[str] = None,
        include_in_net_worth: Optional[bool] = None,
        hide_from_summary_list: Optional[bool] = None,
        hide_transactions_from_reports: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Updates the details of an account.

        With the exception of the account_balance parameter, the only available parameters currently are those
        that are valid for both synced and manual accounts.

        :param account_id: The string ID of the account to update
        :param account_name: The string of the account name
        :param account_balance: a float of the amount to update the account balance to
        :param account_type: The string of account group type (i.e. loan, other_liability, other_asset, etc)
        :param account_sub_type: The string sub type of the account (i.e. auto, commercial, mortgage, line_of_credit, etc)
        :param include_in_net_worth: A boolean if the account should be considered in the net worth calculation
        :param hide_from_summary_list: A boolean if the account should be hidden in the "Accounts" view
        :param hide_transactions_from_reports: A boolean if the account should be excluded from budgets and reports
        """
        query = _query("accounts/update_account")

        variables = {
            "id": str(account_id),
        }

        if account_type is not None:
            variables["type"] = account_type
        if account_sub_type is not None:
            variables["subtype"] = account_sub_type
        if include_in_net_worth is not None:
            variables["includeInNetWorth"] = include_in_net_worth
        if hide_from_summary_list is not None:
            variables["hideFromList"] = hide_from_summary_list
        if hide_transactions_from_reports is not None:
            variables["hideTransactionsFromReports"] = hide_transactions_from_reports
        if account_name is not None:
            variables["name"] = account_name
        if account_balance is not None:
            variables["displayBalance"] = account_balance

        return await self.gql_call(
            operation="Common_UpdateAccount",
            graphql_query=query,
            variables={"input": variables},
        )

    async def delete_account(
        self,
        account_id: str,
    ) -> Dict[str, Any]:
        """
        Deletes an account
        """
        query = _query("accounts/delete_account")

        variables = {"id": account_id}

        return await self.gql_call(
            operation="Common_DeleteAccount",
            graphql_query=query,
            variables=variables,
        )

    async def request_accounts_refresh(self, account_ids: List[str]) -> bool:
        """
        Requests Monarch to refresh account balances and transactions with
        source institutions.  Returns True if request was successfully started.

        Otherwise, throws a `RequestFailedException`.
        """
        query = _query("accounts/request_accounts_refresh")

        variables = {
            "input": {
                "accountIds": account_ids,
            },
        }

        response = await self.gql_call(
            operation="Common_ForceRefreshAccountsMutation",
            graphql_query=query,
            variables=variables,
        )

        if not response["forceRefreshAccounts"]["success"]:
            raise RequestFailedException(response["forceRefreshAccounts"]["errors"])

        return True

    async def is_accounts_refresh_complete(
        self, account_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Checks on the status of a prior request to refresh account balances.

        Returns:
          - True if refresh request is completed.
          - False if refresh request still in progress.

        Otherwise, throws a `RequestFailedException`.

        :param account_ids: The list of accounts IDs to check on the status of.
          If set to None, all account IDs will be checked.
        """
        query = _query("accounts/is_accounts_refresh_complete")

        response = await self.gql_call(
            operation="ForceRefreshAccountsQuery",
            graphql_query=query,
            variables={},
        )

        if "accounts" not in response:
            raise RequestFailedException("Unable to request status of refresh")

        if account_ids:
            return all(
                [
                    not x["hasSyncInProgress"]
                    for x in response["accounts"]
                    if x["id"] in account_ids
                ]
            )
        else:
            return all([not x["hasSyncInProgress"] for x in response["accounts"]])

    async def request_accounts_refresh_and_wait(
        self,
        account_ids: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT_SECS,
        delay: int = DEFAULT_DELAY_SECS,
    ) -> bool:
        """
        Convenience method for forcing an accounts refresh on Monarch, as well
        as waiting for the refresh to complete.

        Returns True if all accounts are refreshed within the timeout specified, False otherwise.

        :param account_ids: The list of accounts IDs to refresh.
          If set to None, all account IDs will be implicitly fetched.
        :param timeout: The number of seconds to wait for the refresh to complete
        :param delay: The number of seconds to wait for each check on the refresh request
        """
        if account_ids is None:
            account_data = await self.get_accounts()
            account_ids = [x["id"] for x in account_data["accounts"]]
        await self.request_accounts_refresh(account_ids)
        start = time.time()
        refreshed = False
        while not refreshed and (time.time() <= (start + timeout)):
            await asyncio.sleep(delay)
            refreshed = await self.is_accounts_refresh_complete(account_ids)
        return refreshed

    async def get_account_holdings(self, account_id: int) -> Dict[str, Any]:
        """
        Get the holdings information for a brokerage or similar type of account.
        """
        query = _query("accounts/get_account_holdings")

        variables = {
            "input": {
                "accountIds": [str(account_id)],
                "endDate": _to_iso_date(datetime.today()),
                "includeHiddenHoldings": True,
                "startDate": _to_iso_date(datetime.today()),
            },
        }

        return await self.gql_call(
            operation="Web_GetHoldings",
            graphql_query=query,
            variables=variables,
        )

    async def get_all_holdings(self) -> Dict[str, Any]:
        """
        Get the holdings information for all brokerage or similar type accounts.

        Convenience wrapper around get_account_holdings that first looks up
        every account of type "brokerage" and fetches its holdings.

        Returns a dict with an "accounts" list; each entry contains the
        account's "id", "displayName", and its "holdings" (in the same format
        returned by get_account_holdings).
        """
        # Call the base-class implementations explicitly so subclasses that
        # override get_accounts/get_account_holdings with different return
        # types (e.g. TypedMonarchMoney) don't break the raw dict handling.
        accounts = await MonarchMoney.get_accounts(self)
        brokerage_accounts = [
            account
            for account in accounts.get("accounts", [])
            if (account.get("type") or {}).get("name") == "brokerage"
        ]
        # Fetch holdings for all brokerage accounts concurrently so elapsed
        # time scales with the slowest request rather than the sum of all.
        holdings_list = await asyncio.gather(
            *(
                MonarchMoney.get_account_holdings(self, account["id"])
                for account in brokerage_accounts
            )
        )
        return {
            "accounts": [
                {
                    "id": account["id"],
                    "displayName": account.get("displayName"),
                    "holdings": holdings,
                }
                for account, holdings in zip(brokerage_accounts, holdings_list)
            ]
        }

    async def get_account_history(self, account_id: int) -> Dict[str, Any]:
        """
        Gets historical account snapshot data for the requested account

        Args:
          account_id: Monarch account ID as an integer

        Returns:
          json object with all historical snapshots of requested account's balances
        """

        query = _query("accounts/get_account_history")

        variables = {"id": str(account_id)}

        account_details = await self.gql_call(
            operation="AccountDetails_getAccount",
            graphql_query=query,
            variables=variables,
        )

        # Parse JSON
        account_name = account_details["account"]["displayName"]
        account_balance_history = account_details["snapshots"]

        # Append account identification data to account balance history
        for i in account_balance_history:
            i.update(dict(accountId=str(account_id)))
            i.update(dict(accountName=account_name))

        return account_balance_history

    async def get_institutions(self) -> Dict[str, Any]:
        """
        Gets institution data from the account.
        """

        query = _query("accounts/get_institutions")
        return await self.gql_call(
            operation="Web_GetInstitutionSettings",
            graphql_query=query,
        )

    async def get_account_details(self, account_id: "str | int") -> "JSONObject":
        """Return the account's metadata/settings/notes and snapshotsForAccount."""
        return await self.gql_call(
            operation="ExportAccountComplete",
            graphql_query=_query("ExportAccountComplete"),
            variables={"id": str(account_id)},
        )

    async def get_account_roster(
        self, include_deleted: "bool" = True, include_hidden: "bool" = True
    ) -> "JSONObject":
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
