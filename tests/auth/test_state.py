import unittest
from unittest.mock import AsyncMock, Mock

from monarchmoney import LoginFailedException, MonarchMoney


class TestAuthState(unittest.IsolatedAsyncioTestCase):
    async def test_cookie_login_preserves_verification_and_save_order(self):
        client = MonarchMoney(token="old-token")
        calls = []
        client.get_accounts = AsyncMock(side_effect=lambda: calls.append("verify"))
        client.save_session = Mock(side_effect=lambda _: calls.append("save"))

        await client.login_with_cookies(
            "ignored; session_id=session=part; csrftoken=csrf", verify=True
        )

        self.assertEqual(calls, ["verify", "save"])
        self.assertEqual(client._cookies["session_id"], "session=part")
        self.assertEqual(client._auth_mode, "cookie")
        self.assertNotIn("Authorization", client._headers)
        self.assertEqual(client._headers["X-Csrftoken"], "csrf")

    async def test_missing_cookie_keeps_existing_auth_state(self):
        client = MonarchMoney(token="old-token")
        with self.assertRaises(LoginFailedException):
            await client.login_with_cookies("session_id=one", verify=False)
        self.assertEqual(client._headers["Authorization"], "Token old-token")
        self.assertEqual(client._auth_mode, "token")
