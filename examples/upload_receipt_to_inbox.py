"""
Example: upload a receipt image to the Monarch Money general receipt inbox.

Monarch's AI will attempt to categorize and match the receipt to a transaction
automatically. The receipt is NOT attached to a specific transaction — it lands
in the inbox for Monarch to process.

Three auth approaches are shown below; pick the one that fits your setup.
"""

import asyncio

from monarchmoney import MonarchMoney, RequireMFAException


# --- Auth option 1: email + password + TOTP secret (fully automated, no prompts) ---
# mfa_secret_key is the base-32 string shown when you first set up your authenticator
# app (Settings → Security → Enable MFA → "Two-factor text code" in Monarch).
# The library generates the 6-digit code automatically using oathtool.
async def example_totp():
    mm = MonarchMoney()
    await mm.login(
        email="you@example.com",
        password="yourpassword",
        mfa_secret_key="BASE32TOTPSECRETHERE",
    )
    with open("receipt.jpg", "rb") as f:
        result = await mm.upload_receipt_to_inbox(f.read(), "receipt.jpg")
    print(result)


# --- Auth option 2: email + password, then enter 2FA code interactively ---
# Use this if you don't have the base-32 TOTP secret but do have your authenticator app.
async def example_interactive_mfa():
    mm = MonarchMoney()
    try:
        await mm.login(email="you@example.com", password="yourpassword")
    except RequireMFAException:
        code = input("Enter your 6-digit MFA code: ")
        await mm.multi_factor_authenticate("you@example.com", "yourpassword", code)
    with open("receipt.jpg", "rb") as f:
        result = await mm.upload_receipt_to_inbox(f.read(), "receipt.jpg")
    print(result)


# --- Auth option 3: browser cookies (use when CAPTCHA blocks programmatic login) ---
# Open app.monarch.com, open DevTools → Application → Cookies, then copy the values
# of session_id and csrftoken and paste them below.
async def example_cookies():
    mm = MonarchMoney()
    await mm.login_with_cookies("session_id=xxx; csrftoken=yyy")
    with open("receipt.jpg", "rb") as f:
        result = await mm.upload_receipt_to_inbox(f.read(), "receipt.jpg")
    print(result)


asyncio.run(example_totp())
