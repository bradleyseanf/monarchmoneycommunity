"""Budgets client operations."""

from .monarchmoney import (
    Any,
    Dict,
    Optional,
    Union,
    _to_iso_date,
    calendar,
    date,
    datetime,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class BudgetsMixin:

    async def get_budgets(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_legacy_goals: Optional[bool] = False,
        use_v2_goals: Optional[bool] = True,
    ) -> Dict[str, Any]:
        """
        Get your budgets and corresponding actual amounts from the account.

        When no date arguments given:
            | `start_date` will default to last month based on todays date
            | `end_date` will default to next month based on todays date

        :param start_date:
            the earliest date to get budget data, in "yyyy-mm-dd" format (default: last month)
        :param end_date:
            the latest date to get budget data, in "yyyy-mm-dd" format (default: next month)
        :param use_legacy_goals:
            Deprecated; legacy goals are no longer supported by the API.
        :param use_v2_goals:
            Set True to return a list of monthly budget set aside for version 2 goals (default list)
        """
        query = _query("budgets/get_budgets")

        variables = {
            "startDate": start_date,
            "endDate": end_date,
            "useV2Goals": use_v2_goals,
        }

        if not start_date and not end_date:
            # Default start_date to last month and end_date to next month
            today = datetime.today()

            # Get the first day of last month
            last_month = today.month - 1
            last_month_year = today.year
            first_day_of_last_month = 1
            if last_month < 1:
                last_month_year -= 1
                last_month = 12
            variables["startDate"] = _to_iso_date(
                datetime(last_month_year, last_month, first_day_of_last_month)
            )

            # Get the last day of next month
            next_month = today.month + 1
            next_month_year = today.year
            if next_month > 12:
                next_month_year += 1
                next_month = 1
            last_day_of_next_month = calendar.monthrange(next_month_year, next_month)[1]
            variables["endDate"] = _to_iso_date(
                datetime(next_month_year, next_month, last_day_of_next_month)
            )

        elif bool(start_date) != bool(end_date):
            raise Exception(
                "You must specify both a startDate and endDate, not just one of them."
            )

        return await self.gql_call(
            operation="GetJointPlanningData",
            graphql_query=query,
            variables=variables,
        )

    async def set_budget_amount(
        self,
        amount: float,
        category_id: Optional[str] = None,
        category_group_id: Optional[str] = None,
        timeframe: str = "month",  # I believe this is the only valid value right now
        start_date: Optional[str] = None,
        apply_to_future: bool = False,
    ) -> Dict[str, Any]:
        """
        Updates the budget amount for the given category.

        :param category_id:
            The ID of the category to set the budget for (cannot be provided w/ category_group_id)
        :param category_group_id:
            The ID of the category group to set the budget for (cannot be provided w/ category_id)
        :param amount:
            The amount to set the budget to. Can be negative (to indicate over-budget). A zero
            value will "unset" or "clear" the budget for the given category.
        :param timeframe:
            The timeframe of the budget. As of writing, it is believed that `month` is the
            only valid value for this parameter.
        :param start_date:
            The beginning of the given timeframe (ex: 2023-12-01). If not specified, then the
            beginning of today's month will be used.
        :param apply_to_future:
            Whether to apply the new budget amount to all proceeding timeframes
        """

        # Will be true if neither of the parameters are set, or both are
        if (category_id is None) is (category_group_id is None):
            raise Exception(
                "You must specify either a category_id OR category_group_id; not both"
            )

        query = _query("budgets/set_budget_amount")

        variables = {
            "input": {
                "startDate": start_date,
                "timeframe": timeframe,
                "categoryId": category_id,
                "categoryGroupId": category_group_id,
                "amount": amount,
                "applyToFuture": apply_to_future,
            }
        }

        if start_date is None:
            variables["input"]["startDate"] = self._get_start_of_current_month()

        return await self.gql_call(
            operation="Common_UpdateBudgetItem",
            variables=variables,
            graphql_query=query,
        )

    async def get_goal_accounts_allocation_summary(self) -> Dict[str, Any]:
        """
        Gets, per account, the total balance, the balance not yet allocated
        to any savings goal, and the split of the balance by goal.
        """
        query = _query("budgets/get_goal_accounts_allocation_summary")

        return await self.gql_call(
            operation="Common_SavingsGoalAccountsAllocationSummary",
            graphql_query=query,
        )

    async def update_flexible_budget(
        self,
        amount: float,
        start_date: Optional[str] = None,
        apply_to_future: bool = False,
    ) -> Dict[str, Any]:
        """
        Updates the Flexible budget amount.

        This is the bucket-level budget for the "fixed_and_flex" budget system.
        Unlike set_budget_amount() which targets a specific category, this method
        sets the total Flex bucket allowance for a month.

        :param amount:
            The amount to set the Flexible budget to. A zero value will unset it.
        :param start_date:
            The beginning of the target month (ex: 2026-04-01). Defaults to the
            start of the current month.
        :param apply_to_future:
            Whether to apply the new budget amount to all subsequent months.
        """
        query = _query("budgets/update_flexible_budget")

        variables = {
            "input": {
                "startDate": start_date or self._get_start_of_current_month(),
                "amount": amount,
                "applyToFuture": apply_to_future,
            }
        }

        return await self.gql_call(
            operation="Common_UpdateFlexBudgetMutation",
            variables=variables,
            graphql_query=query,
        )

    async def update_flex_rollover_settings(
        self,
        rollover_start_month: Optional[str] = None,
        rollover_starting_balance: float = 0.0,
        rollover_enabled: bool = True,
        budget_system: str = "fixed_and_flex",
    ) -> Dict[str, Any]:
        """
        Updates the Flex bucket rollover settings. Can be used to reset accumulated
        rollover by pointing the start month to the current (or desired) month with
        a starting balance of 0.

        This resolves the common "Flex bucket has huge negative rollover" problem
        where over-budget months accumulate for months or years. Resetting the
        period creates a fresh rollover period starting from the given month.

        :param rollover_start_month:
            ISO date string for the new rollover period start (ex: "2026-04-01").
            Defaults to start of current month.
        :param rollover_starting_balance:
            Balance to seed the new rollover period with. Default 0.0 (a fresh start).
        :param rollover_enabled:
            Whether flex rollover is enabled. Default True.
        :param budget_system:
            Budget system identifier. Default "fixed_and_flex".

        Example (reset flex rollover to $0 starting this month):
            await mm.update_flex_rollover_settings()
        """
        query = _query("budgets/update_flex_rollover_settings")

        variables = {
            "input": {
                "rolloverEnabled": rollover_enabled,
                "rolloverStartMonth": _to_iso_date(rollover_start_month)
                or self._get_start_of_current_month(),
                "rolloverStartingBalance": rollover_starting_balance,
                "budgetSystem": budget_system,
            }
        }

        return await self.gql_call(
            operation="Web_UpdateFlexibleGroupRolloverSettings",
            variables=variables,
            graphql_query=query,
        )

    async def reset_budget(
        self,
        start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resets the budget for a specific month. Clears planned amounts back to
        defaults/zero for the given month.

        :param start_date:
            The beginning of the month to reset (ex: "2026-04-01"). Defaults to
            start of current month.
        """
        query = _query("budgets/reset_budget")

        variables = {
            "input": {
                "startDate": start_date or self._get_start_of_current_month(),
            }
        }

        return await self.gql_call(
            operation="Common_ResetBudget",
            variables=variables,
            graphql_query=query,
        )

    async def set_savings_goal_budget_amount(
        self,
        goal_id: str,
        month: Union[date, datetime, str],
        amount: float,
        apply_to_future: bool = True,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sets a savings goal's planned monthly contribution (its budget line).

        :param goal_id: The savings goal id.
        :param month: The month to set, as a date, datetime, or
            ``YYYY-MM-DD`` string. Any day in the month is accepted and
            normalized to the first of the month.
        :param amount: The planned contribution amount.
        :param apply_to_future: Also apply the amount to later months
            (the web app's default).
        :param account_id: The account for a per-account planned
            contribution. Omit for the goal's "General contribution".
        """
        query = _query("budgets/set_savings_goal_budget_amount")

        variables = {
            "input": {
                "month": _to_iso_date(month)[:7] + "-01",
                "savingsGoalId": goal_id,
                "amount": amount,
                "applyToFuture": apply_to_future,
                "accountId": account_id,
            }
        }

        return await self.gql_call(
            operation="Common_SetSavingsGoalBudgetAmount",
            graphql_query=query,
            variables=variables,
        )

    async def get_savings_goal_budget_amounts(
        self,
        goal_id: str,
        start_month: Union[date, datetime, str],
        end_month: Union[date, datetime, str],
    ) -> Dict[str, Any]:
        """
        Gets a savings goal's monthly budget amounts (planned, actual, and
        remaining, with a per-account breakdown) for a range of months.

        :param goal_id: The savings goal id.
        :param start_month: The first month, as a date, datetime, or
            ``YYYY-MM-DD`` string. Any day in the month is accepted and
            normalized to the first of the month.
        :param end_month: The last month, normalized the same way.
        """
        query = _query("budgets/get_savings_goal_budget_amounts")

        variables = {
            "goalId": goal_id,
            "startMonth": _to_iso_date(start_month)[:7] + "-01",
            "endMonth": _to_iso_date(end_month)[:7] + "-01",
        }

        return await self.gql_call(
            operation="Common_SavingsGoalBudgetAmounts",
            graphql_query=query,
            variables=variables,
        )
