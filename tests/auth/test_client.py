from unittest.mock import AsyncMock, MagicMock, patch

from monarchmoney.monarchmoney import LoginFailedException


from tests._fixtures import MonarchFixture


class TestAuthClient(MonarchFixture):

    async def test_login(self):
        """
        Test the login method with empty values for email and password.
        """
        with self.assertRaises(LoginFailedException):
            await self.monarch_money.login(use_saved_session=False)
        with self.assertRaises(LoginFailedException):
            await self.monarch_money.login(
                email="", password="", use_saved_session=False
            )

    @patch("builtins.input", return_value="")
    @patch("getpass.getpass", return_value="")
    async def test_interactive_login(self, _input_mock, _getpass_mock):
        """
        Test the interactive_login method with empty values for email and password.
        """
        with self.assertRaises(LoginFailedException):
            await self.monarch_money.interactive_login(use_saved_session=False)

    @patch("monarchmoney.monarchmoney.ClientSession")
    async def test_multi_factor_authenticate_bad_code_raises_login_failed(
        self, mock_client_session
    ):
        """
        Bad MFA codes should raise LoginFailedException, not RequireMFAException.
        """
        response = AsyncMock()
        response.status = 400
        response.reason = "Bad Request"
        response.json = AsyncMock(return_value={"detail": "Invalid MFA code"})

        post_context = MagicMock()
        post_context.__aenter__.return_value = response

        session = MagicMock()
        session.post.return_value = post_context

        client_context = MagicMock()
        client_context.__aenter__.return_value = session
        mock_client_session.return_value = client_context

        with self.assertRaises(LoginFailedException) as ctx:
            await self.monarch_money.multi_factor_authenticate(
                "bradley@example.com", "password", "123456"
            )

        self.assertEqual(str(ctx.exception), "Invalid MFA code")
