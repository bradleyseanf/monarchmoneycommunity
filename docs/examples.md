# Examples

These recipes use the dictionary-based `MonarchMoney` client and an existing [saved session](authentication.md#reuse-a-session). Put a recipe above this runner, then call it from `main()`:

```python
import asyncio

from monarchmoney import MonarchMoney


async def show_accounts(mm):
    response = await mm.get_accounts()
    for account in response["accounts"]:
        print(account["id"], account["displayName"], account["currentBalance"])


async def main():
    mm = MonarchMoney()
    mm.load_session()
    await show_accounts(mm)


if __name__ == "__main__":
    asyncio.run(main())
```

## Filter transactions

[`get_transactions()`](reference/client.md#monarchmoney.monarchmoney.MonarchMoney.get_transactions) returns up to 100 transactions by default. Pass both `start_date` and `end_date` together, using `YYYY-MM-DD` strings.

```python
async def show_transactions(mm):
    response = await mm.get_transactions(
        limit=100,
        start_date="2026-01-01",
        end_date="2026-01-31",
        is_pending=False,
        transaction_visibility="all_transactions",
    )
    page = response["allTransactions"]
    print("Matching transactions:", page["totalCount"])
    for transaction in page["results"]:
        merchant = transaction.get("merchant") or {}
        print(transaction["date"], merchant.get("name"), transaction["amount"])
```

Use `account_ids`, `category_ids`, or `tag_ids` to filter by IDs returned from the corresponding listing methods. Boolean filters set to `None` are omitted. Omitting `transaction_visibility` returns non-hidden transactions; `"all_transactions"` includes hidden ones.

## Page through transactions

Use `limit` and `offset` to fetch multiple pages. This async generator processes one page at a time:

```python
async def iter_transactions(mm, start_date, end_date, page_size=100):
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    offset = 0
    while True:
        response = await mm.get_transactions(
            limit=page_size,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            transaction_visibility="all_transactions",
        )
        page = response["allTransactions"]
        transactions = page["results"]
        if not transactions:
            break

        for transaction in transactions:
            yield transaction

        offset += len(transactions)
        if offset >= page["totalCount"]:
            break


async def show_all_transactions(mm):
    async for transaction in iter_transactions(mm, "2026-01-01", "2026-01-31"):
        print(transaction["id"], transaction["date"], transaction["amount"])
```

Offset pagination is not a snapshot: records added or removed during the loop can shift subsequent pages.

## Read category budgets

[`get_budgets()`](reference/client.md#monarchmoney.monarchmoney.MonarchMoney.get_budgets) returns category metadata and monthly amounts separately. Join them by category ID:

```python
async def show_budgets(mm):
    response = await mm.get_budgets(
        start_date="2026-01-01",
        end_date="2026-03-31",
    )
    names = {
        category["id"]: category["name"]
        for group in response["categoryGroups"]
        for category in (group.get("categories") or [])
    }
    budget_data = response.get("budgetData") or {}
    for category in budget_data.get("monthlyAmountsByCategory", []):
        category_id = category["category"]["id"]
        for month in category.get("monthlyAmounts") or []:
            print(
                names.get(category_id, category_id),
                month["month"],
                month.get("plannedCashFlowAmount"),
                month.get("actualAmount"),
                month.get("remainingAmount"),
            )
```

Some monthly amounts may be `None`. The [typed budget helper](typed-client.md#budgets) performs this join and exposes model attributes.

## Read savings goals and their history

[`get_savings_goals()`](reference/client.md#monarchmoney.monarchmoney.MonarchMoney.get_savings_goals) includes archived goals. Filter them locally when you want active goals:

```python
async def show_active_goals(mm):
    response = await mm.get_savings_goals()
    for goal in response["savingsGoals"]:
        if goal.get("status") == "archived" or goal.get("archivedAt"):
            continue
        print(goal["id"], goal["name"], goal["currentBalance"], goal["targetAmount"])
```

For one goal, use `(await mm.get_savings_goal(goal_id))["savingsGoal"]`. Goal event history uses its own pagination fields:

```python
async def show_goal_events(mm, goal_id):
    offset = 0
    while True:
        response = await mm.get_savings_goal_events(
            goal_id=goal_id,
            limit=50,
            offset=offset,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        goal = response["savingsGoal"]
        if goal is None:
            return
        page = goal["goalEventsPaginated"]
        for event in page["events"]:
            print(event["date"], event["type"], event["amount"])
        if not page["hasMoreEvents"]:
            break
        offset = page["nextOffset"]
```

Stop when `hasMoreEvents` is false; `nextOffset` is not a completion indicator. Unlike transaction date filters, goal event dates can be supplied independently and also accept Python `date` or `datetime` values.

## Handle mutation results

Mutation methods can return an `errors` field within the operation's payload. Inspect that field before treating a change as successful. Consult the [client reference](reference/client.md) for the specific method's parameters and return structure.
