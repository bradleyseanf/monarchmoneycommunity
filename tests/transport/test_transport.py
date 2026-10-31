import unittest
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import FormData
from gql import gql

from monarchmoney import MonarchMoney


class TestTransport(unittest.IsolatedAsyncioTestCase):
    def test_client_factory_uses_facade_patch_and_timeout(self):
        client = MonarchMoney(timeout=17)
        client.set_cookies({"session_id": "session", "csrftoken": "csrf"})
        with patch("monarchmoney.monarchmoney.AIOHTTPTransport") as transport, patch(
            "monarchmoney.monarchmoney.Client"
        ) as client_factory:
            result = client._get_graphql_client()
        self.assertIs(result, client_factory.return_value)
        self.assertEqual(transport.call_args.kwargs["timeout"], 17)
        self.assertEqual(
            transport.call_args.kwargs["cookies"],
            {"session_id": "session", "csrftoken": "csrf"},
        )
        self.assertEqual(client_factory.call_args.kwargs["execute_timeout"], 17)

    async def test_graphql_call_preserves_operation_variables_and_result(self):
        client = MonarchMoney()
        expected = {"accounts": []}
        execute = AsyncMock(return_value=expected)
        client._get_graphql_client = Mock(return_value=Mock(execute_async=execute))
        request = gql("query GetAccounts { accounts { id } }")
        result = await client.gql_call("GetAccounts", request, {"limit": 2})
        self.assertIs(result, expected)
        execute.assert_awaited_once_with(
            request=request, variable_values={"limit": 2}, operation_name="GetAccounts"
        )

    async def test_external_upload_omits_browser_cookies(self):
        client = MonarchMoney()
        client.set_cookies({"session_id": "session", "csrftoken": "csrf"})
        response = Mock(status=200)
        response.json = AsyncMock(return_value={"uploaded": True})
        session = Mock(post=AsyncMock(return_value=response))
        context = AsyncMock()
        context.__aenter__.return_value = session
        with patch(
            "monarchmoney.monarchmoney.ClientSession", return_value=context
        ) as factory:
            result = await client._upload_form_data(
                "https://example.com/upload", FormData()
            )
        self.assertEqual(result, {"uploaded": True})
        self.assertIsNone(factory.call_args.kwargs["cookies"])
        self.assertNotIn("X-Csrftoken", factory.call_args.kwargs["headers"])
        self.assertNotIn("Origin", factory.call_args.kwargs["headers"])
