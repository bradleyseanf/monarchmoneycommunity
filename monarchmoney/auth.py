"""Auth and client compatibility operations."""

import importlib

from .monarchmoney import (
    CaptchaRequiredException,
    Dict,
    LoginFailedException,
    MONARCH_COOKIE_HEADERS,
    MonarchMoneyEndpoints,
    Optional,
    REQUIRED_COOKIES,
    RequireMFAException,
    getpass,
    os,
    sys,
)

_facade = importlib.import_module(__package__ + ".monarchmoney")


class AuthMixin:

    @staticmethod
    def _looks_like_jwt(token: str) -> bool:
        # Ably/features tokens are JWTs (header.payload.signature)
        return isinstance(token, str) and token.count(".") == 2

    @staticmethod
    def _is_long_lived(token_expiration) -> bool:
        # Monarch long-lived browser-style sessions return tokenExpiration = null/None
        return token_expiration in (None, "null")

    @property
    def token(self) -> Optional[str]:
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token

    def set_cookies(self, cookies: Dict[str, str]) -> None:
        missing = [k for k in REQUIRED_COOKIES if k not in cookies]
        if missing:
            raise LoginFailedException(
                f"Missing required cookies: {', '.join(missing)}. "
                "Ensure you copy both session_id and csrftoken from your browser."
            )
        self._cookies = cookies
        self._auth_mode = "cookie"
        self._headers.pop("Authorization", None)
        self._headers.update(MONARCH_COOKIE_HEADERS)
        self._headers["X-Csrftoken"] = cookies["csrftoken"]

    async def login_with_cookies(
        self,
        cookie_string: str,
        save_session: bool = True,
        verify: bool = True,
    ) -> None:
        """Authenticate using a browser Cookie header string."""
        cookies = self._parse_cookie_string(cookie_string)
        self.set_cookies(cookies)
        if verify:
            await self.get_accounts()
        if save_session:
            self.save_session(self._session_file)

    @staticmethod
    def _parse_cookie_string(cookie_string: str) -> Dict[str, str]:
        cookies: Dict[str, str] = {}
        for pair in cookie_string.split(";"):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, _, value = pair.partition("=")
            cookies[key.strip()] = value.strip()
        return cookies

    async def interactive_login(
        self, use_saved_session: bool = True, save_session: bool = True
    ) -> None:
        """Performs an interactive login for iPython and similar environments."""
        email = input("Email: ")
        passwd = getpass.getpass("Password: ")
        try:
            await self.login(email, passwd, use_saved_session, save_session)
        except RequireMFAException:
            await self.multi_factor_authenticate(
                email, passwd, input("Two Factor Code: ")
            )
            if save_session:
                self.save_session(self._session_file)

    async def login(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        use_saved_session: bool = True,
        save_session: bool = True,
        mfa_secret_key: Optional[str] = None,
    ) -> None:
        """Logs into a Monarch Money account."""
        if use_saved_session and os.path.exists(self._session_file):
            print(f"Using saved session found at {self._session_file}", file=sys.stderr)
            self.load_session(self._session_file)
            return

        if (email is None) or (password is None) or (email == "") or (password == ""):
            raise LoginFailedException(
                "Email and password are required to login when not using a saved session."
            )
        await self._login_user(email, password, mfa_secret_key)
        if save_session:
            self.save_session(self._session_file)

    async def multi_factor_authenticate(
        self, email: str, password: str, code: str, trusted_device: bool = True
    ) -> None:
        """Performs multi-factor authentication to access a Monarch Money account.

        Set trusted_device=True to request a long-lived token (browser-style session).
        """
        await self._multi_factor_authenticate(email, password, code, trusted_device)

    async def _login_user(
        self, email: str, password: str, mfa_secret_key: Optional[str]
    ) -> None:
        """
        Performs the initial login to a Monarch Money account.
        Requires/persists only the long-lived login token (NOT the 1-hour features JWT).
        """
        data = {
            "password": password,
            "supports_mfa": True,
            "trusted_device": True,
            "username": email,
        }
        if mfa_secret_key:
            data["totp"] = _facade.oathtool.generate_otp(mfa_secret_key)

        async with _facade.ClientSession(
            headers=self._headers, trust_env=True
        ) as session:
            async with session.post(
                MonarchMoneyEndpoints.getLoginEndpoint(), json=data
            ) as resp:
                if resp.status == 403:
                    try:
                        body = await resp.json()
                        if body.get("error_code") == "CAPTCHA_REQUIRED":
                            raise CaptchaRequiredException(
                                "Programmatic login is blocked by CAPTCHA. "
                                "Use login_with_cookies() to authenticate with "
                                "browser cookies instead."
                            )
                    except CaptchaRequiredException:
                        raise
                    except Exception:
                        pass
                    raise RequireMFAException("Multi-Factor Auth Required")
                if resp.status != 200:
                    try:
                        response = await resp.json()
                        if "detail" in response:
                            raise LoginFailedException(response["detail"])
                        if "error_code" in response:
                            raise LoginFailedException(response["error_code"])
                        raise LoginFailedException(f"Unrecognized error: {response}")
                    except (
                        LoginFailedException,
                        RequireMFAException,
                        CaptchaRequiredException,
                    ):
                        raise
                    except Exception:
                        raise LoginFailedException(
                            f"HTTP Code {resp.status}: {resp.reason}"
                        )

                response = await resp.json()
                tok = response.get("token")
                tokexp = response.get("tokenExpiration")

                if not tok:
                    raise LoginFailedException("Login succeeded but no token returned.")
                if self._looks_like_jwt(tok):
                    raise LoginFailedException(
                        "Received a JWT-style token (likely 1-hour features token). "
                        "Refusing to save; ensure we are using /auth/login/ token."
                    )
                if tokexp not in (None, "null"):
                    raise LoginFailedException(
                        f"Short-lived token returned (tokenExpiration={tokexp}). "
                        "Retry with trusted_device=True or complete MFA as trusted device."
                    )

                self.set_token(tok)
                self._headers["Authorization"] = f"Token {self._token}"

    async def _multi_factor_authenticate(
        self,
        email: str,
        password: str,
        code: Optional[str] = None,
        trusted_device: bool = True,
    ) -> None:
        """
        Performs the MFA step of login.
        Requires/persists only the long-lived login token (NOT the 1-hour features JWT).
        """

        data = {
            "password": password,
            "supports_mfa": True,
            "totp": code,
            "trusted_device": bool(trusted_device),  # request trusted device token
            "username": email,
        }

        async with _facade.ClientSession(
            headers=self._headers, trust_env=True
        ) as session:
            async with session.post(
                MonarchMoneyEndpoints.getLoginEndpoint(), json=data
            ) as resp:
                if resp.status == 403:
                    try:
                        body = await resp.json()
                        if body.get("error_code") == "CAPTCHA_REQUIRED":
                            raise CaptchaRequiredException(
                                "Programmatic login is blocked by CAPTCHA. "
                                "Use login_with_cookies() to authenticate with "
                                "browser cookies instead."
                            )
                    except CaptchaRequiredException:
                        raise
                    except Exception:
                        pass
                    raise RequireMFAException("Multi-Factor Auth Required")
                if resp.status != 200:
                    try:
                        response = await resp.json()
                        if "detail" in response:
                            raise LoginFailedException(response["detail"])
                        if "error_code" in response:
                            raise LoginFailedException(response["error_code"])
                        raise LoginFailedException(f"Unrecognized error: {response}")
                    except (
                        LoginFailedException,
                        RequireMFAException,
                        CaptchaRequiredException,
                    ):
                        raise
                    except Exception:
                        raise LoginFailedException(
                            f"HTTP Code {resp.status}: {resp.reason}"
                        )

                response = await resp.json()
                tok = response.get("token")
                tokexp = response.get("tokenExpiration")

                if not tok:
                    raise LoginFailedException("MFA succeeded but no token returned.")

                if self._looks_like_jwt(tok):
                    raise LoginFailedException(
                        "Received a JWT-style token (likely 1-hour features token). "
                        "Refusing to save; ensure this is the /auth/login/ token."
                    )

                if tokexp not in (None, "null"):
                    raise LoginFailedException(
                        f"MFA returned short-lived token (tokenExpiration={tokexp}). "
                        "Make sure trusted_device=True when performing MFA."
                    )

                self.set_token(tok)
                self._headers["Authorization"] = f"Token {self._token}"
