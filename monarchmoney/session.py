"""Session and client compatibility operations."""

from .monarchmoney import (
    Any,
    Dict,
    LoginFailedException,
    Optional,
    REQUIRED_COOKIES,
    os,
    pickle,
)


class SessionMixin:

    def save_session(self, filename: Optional[str] = None) -> None:
        """Saves auth credentials needed to access a Monarch Money account."""
        if filename is None:
            filename = self._session_file
        filename = os.path.abspath(filename)

        if not self._token and not self._cookies:
            raise LoginFailedException("No credentials set; cannot save session.")

        if self._token and self._looks_like_jwt(self._token):
            raise LoginFailedException(
                "Refusing to save a JWT-style token to session; this looks like the 1-hour "
                "features token, not the long-lived login session token."
            )

        session_data: Dict[str, Any] = {
            "token": self._token,
            "auth_mode": self._auth_mode,
        }
        if self._cookies:
            session_data["cookies"] = self._cookies

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as fh:
            pickle.dump(session_data, fh)

    def load_session(self, filename: Optional[str] = None) -> None:
        """Loads auth credentials from a pickle file."""
        if filename is None:
            filename = self._session_file

        with open(filename, "rb") as fh:
            data = pickle.load(fh)

        auth_mode = data.get("auth_mode", "token")

        saved_cookies = data.get("cookies")
        if isinstance(saved_cookies, dict):
            self._cookies = saved_cookies

        if auth_mode == "cookie" and isinstance(saved_cookies, dict):
            has_required = all(k in saved_cookies for k in REQUIRED_COOKIES)
            if has_required:
                self.set_cookies(saved_cookies)
                if data.get("token"):
                    self._token = data["token"]
                return

        if data.get("token"):
            self.set_token(data["token"])
            self._headers["Authorization"] = f"Token {self._token}"
        else:
            raise LoginFailedException(
                "Session file contains no valid credentials. "
                "Re-login or use login_with_cookies()."
            )

    def delete_session(self, filename: Optional[str] = None) -> None:
        """
        Deletes the session file.
        """
        if filename is None:
            filename = self._session_file

        if os.path.exists(filename):
            os.remove(filename)
