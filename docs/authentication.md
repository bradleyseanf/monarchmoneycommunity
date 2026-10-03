# Authentication

Both `MonarchMoney` and `TypedMonarchMoney` use the same authentication and session helpers. These examples run locally in Python; the documentation site does not collect credentials or make authenticated requests.

## Interactive login

```python
import asyncio

from monarchmoney import MonarchMoney


async def main():
    mm = MonarchMoney()
    await mm.interactive_login(use_saved_session=False)
    print(len((await mm.get_accounts())["accounts"]))


if __name__ == "__main__":
    asyncio.run(main())
```

This prompts for an email and password, then an MFA code if required. It saves the resulting session by default. Pass `save_session=False` to avoid writing a session file. `interactive_login()` prompts for credentials even when a saved session exists; use `load_session()` to reuse one without prompts.

## Password and MFA

Use `login()` when your application supplies the credentials. If Monarch requests an MFA code, catch `RequireMFAException` and complete authentication:

```python
import asyncio
import getpass

from monarchmoney import MonarchMoney, RequireMFAException


async def main():
    email = input("Monarch email: ").strip()
    password = getpass.getpass("Monarch password: ")
    mm = MonarchMoney()

    try:
        await mm.login(
            email=email,
            password=password,
            use_saved_session=False,
            save_session=False,
        )
    except RequireMFAException:
        code = getpass.getpass("MFA code: ").strip()
        await mm.multi_factor_authenticate(email, password, code)

    mm.save_session()
    print(len((await mm.get_accounts())["accounts"]))


if __name__ == "__main__":
    asyncio.run(main())
```

`multi_factor_authenticate()` requests a trusted-device session by default. It does **not** save the session itself; call `save_session()` afterward if you want persistence.

For unattended login, `login()` also accepts the MFA setup secret as `mfa_secret_key` and generates a one-time code. Inside an async function:

```python
import os

await mm.login(
    email=os.environ["MONARCH_EMAIL"],
    password=os.environ["MONARCH_PASSWORD"],
    mfa_secret_key=os.environ["MONARCH_MFA_SECRET"],
    use_saved_session=False,
    save_session=False,
)
```

The MFA secret is the setup key, not a current six-digit code. Keep passwords, MFA secrets, tokens, and cookies outside source control and documentation builds.

## Reuse a session

The default session path is `.mm/mm_session.pickle`, relative to the current working directory. Set `session_file` to choose a stable location:

```python
from pathlib import Path

from monarchmoney import MonarchMoney

session_file = Path.home() / ".mm" / "mm_session.pickle"
mm = MonarchMoney(session_file=str(session_file))
mm.load_session()
# Inside an async function:
# response = await mm.get_accounts()
```

`login()` also loads an existing session when `use_saved_session=True` (the default), before using any supplied credentials. Loading a session does not verify it or refresh expired credentials. If a later request fails because the session has expired, log in again with `use_saved_session=False`.

Session files contain authentication credentials and use Python pickle. Keep them private and load only files you created and trust. `delete_session()` removes the file; it does not revoke the remote session or clear credentials already loaded into an instance.

## Browser cookies and CAPTCHA

`CaptchaRequiredException` means programmatic login needs a CAPTCHA challenge. Sign in normally through the Monarch web app, then use the browser session's cookies:

1. Open your browser's developer tools and the **Network** panel.
2. Find an authenticated request to Monarch's API and copy its `Cookie` request header value.
3. Supply that value to `login_with_cookies()`. It must include both `session_id` and `csrftoken`.

```python
import asyncio
import getpass

from monarchmoney import MonarchMoney


async def main():
    mm = MonarchMoney()
    cookie_header = getpass.getpass("Monarch Cookie header value: ")
    await mm.login_with_cookies(cookie_header)
    print(len((await mm.get_accounts())["accounts"]))


if __name__ == "__main__":
    asyncio.run(main())
```

By default, cookie login verifies the session with `get_accounts()` and saves it. Cookie sessions can also be restored with `load_session()`.

See the [authentication methods](reference/client.md#monarchmoney.monarchmoney.MonarchMoney.login) and [exception reference](reference/exceptions.md) for signatures and error types.
