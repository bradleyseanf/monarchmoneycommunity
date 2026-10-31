"""Activity client operations."""

from .monarchmoney import *  # noqa: F401,F403
from .monarchmoney import _UNSET, _to_iso_date


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class ActivityMixin:

    async def get_activity_events(
        self,
        first: "int" = 100,
        after_cursor: "str | None" = None,
        exclude_event_types: "list[str] | None" = None,
    ) -> "JSONObject":
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
