"""Transport and client compatibility operations."""

import importlib

from .monarchmoney import (
    Any,
    Client,
    Dict,
    DocumentNode,
    FormData,
    GraphQLRequest,
    LoginFailedException,
    MONARCH_COOKIE_HEADERS,
    MonarchMoneyEndpoints,
    RequestFailedException,
    Union,
)

_facade = importlib.import_module(__package__ + ".monarchmoney")


class TransportMixin:

    @property
    def timeout(self) -> int:
        """The timeout, in seconds, for GraphQL calls."""
        return self._timeout

    def set_timeout(self, timeout_secs: int) -> None:
        """Sets the default timeout on GraphQL API calls, in seconds."""
        self._timeout = timeout_secs

    async def _upload_form_data(self, url: str, data: FormData) -> dict:
        """
        Retrieves the response from the server for a given URL and form data.
        """

        # Remove Accept and Content-Type headers because the Monarch upload endpoint
        # rejects these values and returns an "Unsupported Media Type" error.
        headers = self._headers.copy()
        headers.pop("Accept", None)
        headers.pop("Content-Type", None)

        if "monarch.com" in url:
            cookies = self._cookies if self._auth_mode == "cookie" else None
        else:
            cookies = None
            for key in list(MONARCH_COOKIE_HEADERS) + ["X-Csrftoken"]:
                headers.pop(key, None)
        async with _facade.ClientSession(
            headers=headers, cookies=cookies, trust_env=True
        ) as session:
            resp = await session.post(url, data=data)
            if resp.status != 200:
                raise RequestFailedException(f"HTTP Code {resp.status}: {resp.reason}")

            return await resp.json()

    async def gql_call(
        self,
        operation: str,
        graphql_query: Union[DocumentNode, GraphQLRequest],
        variables: Dict[str, Any] = {},
    ) -> Dict[str, Any]:
        """
        Makes a GraphQL call to Monarch Money's API.
        """
        return await self._get_graphql_client().execute_async(
            request=graphql_query,
            variable_values=variables,
            operation_name=operation,
        )

    def _get_graphql_client(self) -> Client:
        """
        Creates a correctly configured GraphQL client for connecting to Monarch Money.
        """
        if self._headers is None:
            raise LoginFailedException(
                "Make sure you call login() first or provide a session token!"
            )
        cookies = self._cookies if self._auth_mode == "cookie" else None
        transport = _facade.AIOHTTPTransport(
            url=MonarchMoneyEndpoints.getGraphQL(),
            headers=self._headers,
            cookies=cookies,
            timeout=self._timeout,
            ssl=True,
            client_session_args={"trust_env": True},
        )
        return _facade.Client(
            transport=transport,
            fetch_schema_from_transport=False,
            execute_timeout=self._timeout,
        )
