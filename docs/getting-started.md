# Getting started

Monarch Money Community is a Python client for accessing your Monarch Money account. Its asynchronous methods handle the GraphQL requests and return data you can use in scripts and applications.

## Install

Create a virtual environment and install the package:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install monarchmoneycommunity
```

On Windows, activate the environment with `.venv\Scripts\activate` instead. The distribution is named `monarchmoneycommunity`; the Python import is `monarchmoney`.

To work from a checkout of this repository, use `python -m pip install -e .` instead of the last command.

## Make your first request

Save this as `accounts.py` and run `python accounts.py`:

```python
import asyncio

from monarchmoney import MonarchMoney


async def main():
    mm = MonarchMoney()
    await mm.interactive_login(use_saved_session=False)

    response = await mm.get_accounts()
    for account in response["accounts"]:
        print(account["id"], account["displayName"], account["currentBalance"])


if __name__ == "__main__":
    asyncio.run(main())
```

The login prompts for your email, password, and MFA code when required. A successful login saves credentials in `.mm/mm_session.pickle` by default. See [authentication](authentication.md) for session reuse, MFA, and browser cookie login when CAPTCHA prevents programmatic login.

In a Jupyter notebook with an active event loop, run `await main()` instead of `asyncio.run(main())`. Network methods require `await`; local session helpers such as `load_session()` and `save_session()` are synchronous.

## Understand the response

Most `MonarchMoney` methods return dictionaries with the fields selected by their GraphQL query. For example:

```python
accounts = (await mm.get_accounts())["accounts"]
transactions = (await mm.get_transactions())["allTransactions"]["results"]
goals = (await mm.get_savings_goals())["savingsGoals"]
```

There is no extra `data` wrapper around these results. Response keys generally use Monarch's camelCase field names. Fields can be `None`, so account for that when processing optional values.

For Python objects with attributes, use the [typed client](typed-client.md). It converts selected responses, including accounts and holdings, into models while preserving the base client's authentication methods.

## Find a method

- [Client reference](reference/client.md): method signatures, parameters, defaults, and source documentation.
- [Examples](examples.md): transactions, pagination, budgets, and savings goals.
- [Models](reference/models.md): typed response attributes.
- [Exceptions](reference/exceptions.md): authentication and request failures.

Methods named `create_*`, `update_*`, `delete_*`, `set_*`, `archive_*`, and `unarchive_*` can change account data. Read their parameters and response before using them in an automation.
