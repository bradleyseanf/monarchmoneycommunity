"""Household client operations."""

from .monarchmoney import (
    Any,
    Dict,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class HouseholdMixin:

    async def get_household_members(self) -> Dict[str, Any]:
        """
        Gets household member IDs, names, display names, and roles.

        Returns myHousehold.users with each member's id, name, displayName,
        and householdRole. Pending invitations are not household members.
        """
        query = _query("household/get_household_members")
        return await self.gql_call(
            operation="Common_GetHouseHoldMemberSettings",
            graphql_query=query,
        )

    async def get_subscription_details(self) -> Dict[str, Any]:
        """
        The type of subscription for the Monarch Money account.
        """
        query = _query("household/get_subscription_details")
        return await self.gql_call(
            operation="GetSubscriptionDetails",
            graphql_query=query,
        )

    async def get_user_profile(self) -> "JSONObject":
        """Return me, including the profile and preferences selected by the UI."""
        return await self.gql_call(
            operation="Common_GetMe", graphql_query=_query("Common_GetMe")
        )

    async def get_household_preferences(self) -> "JSONObject":
        """Return preferences, insight topics, and household budget settings."""
        return await self.gql_call(
            operation="Common_GetHouseholdPreferences",
            graphql_query=_query("Common_GetHouseholdPreferences"),
        )

    async def get_report_configurations(self) -> "JSONObject":
        """Return saved report configurations, views, and transaction filters."""
        return await self.gql_call(
            operation="Common_GetReportConfigurations",
            graphql_query=_query("Common_GetReportConfigurations"),
        )
