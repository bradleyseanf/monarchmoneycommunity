"""
Example: upload a receipt image to the Monarch Money general receipt inbox.

Monarch's AI will attempt to categorize and match the receipt to a transaction
automatically. The receipt is NOT attached to a specific transaction — it lands
in the inbox for Monarch to process.

Any login method works here; see the README for the available auth options.
"""

import asyncio

from monarchmoney import MonarchMoney


async def main():
    mm = MonarchMoney()
    await mm.interactive_login()

    with open("receipt.jpg", "rb") as f:
        result = await mm.upload_receipt_to_inbox(f.read(), "receipt.jpg")
    print(result)


asyncio.run(main())
