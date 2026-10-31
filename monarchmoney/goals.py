"""Goals client operations."""

from .monarchmoney import (
    Any,
    Dict,
    Optional,
    Union,
    _to_iso_date,
    date,
    datetime,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class GoalsMixin:

    async def get_savings_goals(self) -> Dict[str, Any]:
        """
        Gets all Savings Goals in the household (the Goals page "Save up" tab).

        Archived goals are returned too; there is no filter variable, so
        callers filter on ``status == "archived"`` or a non-null
        ``archivedAt``.

        This covers Savings Goals only. Legacy goals are the ``goalsV2``
        field returned by ``get_budgets``.
        """
        query = _query("goals/get_savings_goals")

        return await self.gql_call(
            operation="Common_SavingsGoals",
            graphql_query=query,
        )

    async def get_savings_goal(self, goal_id: str) -> Dict[str, Any]:
        """
        Gets a single Savings Goal by id.

        :param goal_id: The savings goal id.
        """
        query = _query("goals/get_savings_goal")

        return await self.gql_call(
            operation="Common_SavingsGoal",
            graphql_query=query,
            variables={"id": goal_id},
        )

    async def get_goal_options(self) -> Dict[str, Any]:
        """
        Gets the preset Savings Goal templates offered when creating a goal
        (e.g. Emergency fund, Down payment, Custom), with their default names,
        objectives, types and images.
        """
        query = _query("goals/get_goal_options")

        return await self.gql_call(
            operation="Common_GoalOptions",
            graphql_query=query,
        )

    async def archive_savings_goal(self, goal_id: str) -> Dict[str, Any]:
        """
        Archives a savings goal.

        Per Monarch's archive dialog this withdraws all allocated funds,
        keeps the goal's history, and removes it from future budgets. It is
        reversible with :meth:`unarchive_savings_goal`, but the withdrawn
        allocations are not restored.

        :param goal_id: The savings goal id to archive.
        """
        query = _query("goals/archive_savings_goal")

        return await self.gql_call(
            operation="Common_ArchiveSavingsGoal",
            graphql_query=query,
            variables={"input": {"id": goal_id}},
        )

    async def unarchive_savings_goal(self, goal_id: str) -> Dict[str, Any]:
        """
        Unarchives a previously archived savings goal.

        Allocations withdrawn when the goal was archived are not restored.

        :param goal_id: The savings goal id to unarchive.
        """
        query = _query("goals/unarchive_savings_goal")

        return await self.gql_call(
            operation="Common_UnarchiveSavingsGoal",
            graphql_query=query,
            variables={"input": {"id": goal_id}},
        )

    async def get_savings_goal_events(
        self,
        goal_id: str,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[Union[date, datetime, str]] = None,
        end_date: Optional[Union[date, datetime, str]] = None,
    ) -> Dict[str, Any]:
        """
        Gets the paginated event history (contributions, withdrawals, etc.)
        for a savings goal.

        :param goal_id: The savings goal id.
        :param limit: The maximum number of events to return.
        :param offset: The number of events to skip before returning results.
        :param start_date: Optional earliest event date (date, datetime, or
            "yyyy-mm-dd"). Omitted from the request when not given.
        :param end_date: Optional latest event date (date, datetime, or
            "yyyy-mm-dd"). Omitted from the request when not given.

        Page with ``offset=nextOffset`` while ``hasMoreEvents`` is true.
        ``nextOffset`` is never null, so don't stop on a falsy value.
        """
        query = _query("goals/get_savings_goal_events")

        variables: Dict[str, Any] = {"id": goal_id, "limit": limit, "offset": offset}
        if start_date is not None:
            variables["startDate"] = _to_iso_date(start_date)
        if end_date is not None:
            variables["endDate"] = _to_iso_date(end_date)

        return await self.gql_call(
            operation="Common_SavingsGoalEventsPaginated",
            graphql_query=query,
            variables=variables,
        )
