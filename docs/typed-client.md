# Typed client

`TypedMonarchMoney` subclasses `MonarchMoney` and converts selected responses into Python models. Authentication, saved sessions, and the underlying requests work the same way as the base client.

## Accounts

```python
import asyncio

from typedmonarchmoney import TypedMonarchMoney


async def main():
    mm = TypedMonarchMoney()
    mm.load_session()
    accounts = await mm.get_accounts()
    for account in accounts:
        print(account.id, account.name, account.balance, account.last_update)


if __name__ == "__main__":
    asyncio.run(main())
```

Here, `accounts` is a list of `MonarchAccount` objects. The base client's equivalent is a dictionary containing an `"accounts"` list. Use `get_accounts_as_dict_with_id_key()` when you need a mapping from account IDs to account objects.

## Budgets

The typed budget helper joins category metadata with monthly budget amounts. Inside an async function with an authenticated typed client:

```python
budgets = await mm.get_budgets_as_dict_with_id_key(
    start_date="2026-01-01",
    end_date="2026-03-31",
)
for category_id, budget in budgets.items():
    for month, amounts in budget.monthly_amounts.items():
        print(
            category_id,
            budget.name,
            budget.group_name,
            month,
            amounts.planned_amount,
            amounts.actual_amount,
            amounts.remaining_amount,
        )
```

`monthly_amounts` is a dictionary keyed by month strings such as `"2026-01-01"`. Amounts are floats or `None`; categories with no returned monthly data have an empty dictionary. `get_budgets()` itself still returns the original dictionary response.

## Holdings

Pass an account object or a numeric account ID to `get_account_holdings()`:

```python
accounts = await mm.get_accounts()
if accounts:
    holdings = await mm.get_account_holdings(accounts[0])
    if holdings is not None:
        for holding in holdings.holdings:
            print(holding.ticker, holding.quantity, holding.total_value)
```

The method returns `None` when the response contains no holdings. `get_accounts(with_holdings=True)` fetches holdings for every returned account and attaches the result to each account's `holdings` attribute; it makes additional requests. A holding's `percentage` is a fraction of the returned total value, while `MonarchHoldings.to_json()` expresses it as a percentage.

## Which methods are typed?

| Method | Typed client result |
| --- | --- |
| `get_accounts()` | `list[MonarchAccount]` |
| `get_accounts_as_dict_with_id_key()` | `dict[str, MonarchAccount]` |
| `get_account_holdings()` / `get_account_holdings_for_id()` | `MonarchHoldings` or `None` |
| `get_cashflow_summary()` | `MonarchCashflowSummary` |
| `get_subscription_details()` | `MonarchSubscription` |
| `get_budgets_as_dict_with_id_key()` | `dict[str, MonarchBudget]` |
| `get_budgets()` / `get_all_holdings()` | Original dictionary response |
| Transactions, savings goals, and other inherited methods | Base client return type |

These models are convenience wrappers, not a complete validation schema for Monarch's GraphQL API. They select and normalize fields; use `MonarchMoney` when you need the full returned dictionary. For example, account and cashflow numeric fields use `-1.0` as a fallback for missing or unparseable values, whereas budget amounts preserve missing values as `None`.

`MonarchMoneyTyped` is an alias for `TypedMonarchMoney`. Both names and the model classes are exported from `typedmonarchmoney`.

See the [typed method reference](reference/typed.md) and [model reference](reference/models.md) for signatures and attributes.
