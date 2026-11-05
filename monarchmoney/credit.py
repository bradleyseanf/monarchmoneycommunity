"""Credit client operations."""

from .monarchmoney import (
    Any,
    Dict,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class CreditMixin:

    async def get_credit_history(self) -> Dict[str, Any]:
        """
        Gets credit score history and related user details.
        """
        query = _query("credit/get_credit_history")
        return await self.gql_call(
            operation="Common_GetSpinwheelCreditScoreSnapshots", graphql_query=query
        )
