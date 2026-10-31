<p align="center">
  <img src=".github/assets/monarch-logo.svg" alt="Monarch Money Community logo" />
</p>

[![Maintenance](https://img.shields.io/maintenance/yes/2026)](https://github.com/bradleyseanf/monarchmoneycommunity/graphs/commit-activity)
[![Issues](https://img.shields.io/github/issues/bradleyseanf/monarchmoneycommunity)](https://github.com/bradleyseanf/monarchmoneycommunity/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/bradleyseanf/monarchmoneycommunity)](https://github.com/bradleyseanf/monarchmoneycommunity/pulls)
[![Contributors](https://img.shields.io/github/contributors/bradleyseanf/monarchmoneycommunity)](https://github.com/bradleyseanf/monarchmoneycommunity/graphs/contributors)

> [!WARNING]
> This project was forked from https://github.com/hammem/monarchmoney and would not be possible without it.
> The upstream fork is no longer maintained. This fork fixes issues that prevent the library from working today, including the Monarch Money domain change to `api.monarch.com`, auth persistence, and the `get_budget()` GraphQL query.
> Moving forward, please report issues here.

# Monarch Money Community

Python library for accessing [Monarch Money](https://www.monarchmoney.com) data.

# Installation

## From Source Code

Clone this repository from Git

`git clone https://github.com/bradleyseanf/monarchmoneycommunity.git`

## Via `pip`

`pip install monarchmoneycommunity`

Import the library as `monarchmoney` after installation.

This package pins `gql` to `4.0`.

# Instantiate & Login

There are two ways to use this library: interactive and non-interactive.

## Interactive

If you're using this library in something like iPython or Jupyter, you can run an interactive-login which supports multi-factor authentication:

```python
from monarchmoney import MonarchMoney

mm = MonarchMoney()
await mm.interactive_login()
```
This will prompt you for the email, password and, if needed, the multi-factor token.

## Non-interactive

For a non-interactive session, you'll need to create an instance and login:

```python
from monarchmoney import MonarchMoney

mm = MonarchMoney()
await mm.login(email, password)
```

This may throw a `RequireMFAException`.  If it does, you'll need to get a multi-factor token and call the following method:

```python
from monarchmoney import MonarchMoney, RequireMFAException

mm = MonarchMoney()
try:
        await mm.login(email, password)
except RequireMFAException:
        await mm.multi_factor_authenticate(email, password, multi_factor_code)
```

Alternatively, you can provide the MFA Secret Key. The MFA Secret Key is found when setting up the MFA in Monarch Money by going to Settings -> Security -> Enable MFA -> and copy the `Two-factor text code`. Then provide it in the login() method:
```python
from monarchmoney import MonarchMoney, RequireMFAException

mm = MonarchMoney()
await mm.login(
        email=email,
        password=password,
        save_session=False,
        use_saved_session=False,
        mfa_secret_key=mfa_secret_key,
    )

```

# Use a Saved Session

You can easily save your session for use later on.  While we don't know precisely how long a session lasts, authors of this library have found it can last several months.

```python
from monarchmoney import MonarchMoney, RequireMFAException

mm = MonarchMoney()
mm.interactive_login()

# Save it for later, no more need to login!
mm.save_session()
```

Once you've logged in, you can simply load the saved session to pick up where you left off.

```python
from monarchmoney import MonarchMoney, RequireMFAException

mm = MonarchMoney()
mm.load_session()

# Then, start accessing data!
await mm.get_accounts()
```

# Accessing Data

As of writing this README, the following methods are supported:

## Non-Mutating Methods

<table>
  <thead>
    <tr>
      <th width="280">Method</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>get_accounts</code></td>
      <td>gets the default account list linked to Monarch Money; use <code>get_account_roster()</code> to include deleted and hidden account identities explicitly</td>
    </tr>
    <tr>
      <td><code>get_account_holdings</code></td>
      <td>gets all of the securities in a brokerage or similar type of account</td>
    </tr>
    <tr>
      <td><code>get_goal_accounts_allocation_summary</code></td>
      <td>gets each goal account's total balance, unallocated balance, and split by Savings Goal</td>
    </tr>
    <tr>
      <td><code>get_all_holdings</code></td>
      <td>gets the securities in every brokerage or similar type of account in one call (no parameters) — example: <code>await mm.get_all_holdings()</code></td>
    </tr>
    <tr>
      <td><code>get_account_type_options</code></td>
      <td>all account types and their subtypes available in Monarch Money</td>
    </tr>
    <tr>
      <td><code>get_account_history</code></td>
      <td>gets all daily account history for the specified account</td>
    </tr>
    <tr>
      <td><code>get_account_details(account_id)</code></td>
      <td>gets the full UI-selected account metadata, settings, notes, provider/owner details, goals, equity data, and daily snapshots; <code>account_id</code> accepts a string or integer. Returns <code>account</code> and <code>snapshotsForAccount</code> without changing <code>get_account_history()</code></td>
    </tr>
    <tr>
      <td><code>get_account_roster(include_deleted=True, include_hidden=True)</code></td>
      <td>gets account identities from institution settings, including <code>deletedAt</code>, owner, and visibility. Boolean flags control deleted/hidden inclusion. Deleted identities may be inaccessible through the account detail endpoint</td>
    </tr>
    <tr>
      <td><code>get_merchants(limit=100, offset=0, include_merchants_without_transactions=True)</code></td>
      <td>gets one offset page with full UI-selected merchant settings, default category/application mode, recurrence, rule count, and <code>merchantCount</code>. <code>limit</code> must be positive; <code>offset</code> must be nonnegative</td>
    </tr>
    <tr>
      <td><code>get_all_merchants(limit=100, include_merchants_without_transactions=True)</code></td>
      <td>collects offset pages until a short or empty page; rejects duplicate merchant IDs with <code>monarchmoney.read_types.MerchantPaginationError</code>. Returns <code>merchants</code> and the first page's reported <code>merchantCount</code>, which can differ from the number collected</td>
    </tr>
    <tr>
      <td><code>get_retail_transactions(first=100, after_cursor=None, filters=None)</code></td>
      <td>gets one <code>retailTransactionsConnection</code> page, preserving <code>edges</code>, <code>pageInfo</code>, line items, orders, and transaction/category links. Positive integer <code>first</code> controls page size; <code>after_cursor</code> is an opaque string; <code>filters</code> is a GraphQL <code>RetailTransactionFiltersInput</code> dictionary</td>
    </tr>
    <tr>
      <td><code>get_activity_events(first=100, after_cursor=None, exclude_event_types=None)</code></td>
      <td>gets one <code>activityEvents</code> page without marking notifications read. Positive integer <code>first</code> controls page size; <code>after_cursor</code> is an opaque string; <code>exclude_event_types</code> accepts a list of GraphQL <code>ActivityEventType</code> enum names</td>
    </tr>
    <tr>
      <td><code>get_user_profile()</code></td>
      <td>gets <code>me</code> with the profile, preferences, onboarding information, and account access metadata selected by the web UI; no parameters</td>
    </tr>
    <tr>
      <td><code>get_household_preferences()</code></td>
      <td>gets <code>householdPreferences</code>, <code>insightTopics</code>, <code>budgetSystem</code>, and <code>budgetApplyToFutureMonthsDefault</code>; no parameters</td>
    </tr>
    <tr>
      <td><code>get_report_configurations()</code></td>
      <td>gets saved <code>reportConfigurations</code>, including complete UI-selected transaction filters and report views; no parameters</td>
    </tr>
    <tr>
      <td><code>get_recurring_transaction_streams(include_liabilities=True)</code></td>
      <td>gets <code>recurringTransactionStreams</code> definitions, review/active status, schedules, next forecast, category, and account. The boolean flag controls liability inclusion; pending streams are included. Preserves inactive records when returned, but the web queries do not establish ignored/deleted stream coverage. Not a complete occurrence history</td>
    </tr>
    <tr>
      <td><code>get_institutions</code></td>
      <td>gets institutions linked to Monarch Money</td>
    </tr>
    <tr>
      <td><code>get_budgets</code></td>
      <td>all the budgets and the corresponding actual amounts</td>
    </tr>
    <tr>
      <td><code>get_savings_goals</code></td>
      <td>gets all Savings Goals, including archived ones (filter on <code>status == "archived"</code> or <code>archivedAt</code>)</td>
    </tr>
    <tr>
      <td><code>get_savings_goal</code></td>
      <td>gets a single Savings Goal by id</td>
    </tr>
    <tr>
      <td><code>get_credit_history</code></td>
      <td>gets credit score snapshots and Spinwheel user details</td>
    </tr>
    <tr>
      <td><code>get_subscription_details</code></td>
      <td>gets the Monarch Money account's status (e.g. paid or trial)</td>
    </tr>
    <tr>
      <td><code>get_recurring_transactions</code></td>
      <td>gets the future recurring transactions, including merchant and account details</td>
    </tr>
    <tr>
      <td><code>get_savings_goal_budget_amounts</code></td>
      <td>gets a savings goal's planned, actual, and remaining amounts per month (with per-account breakdown) between two months</td>
    </tr>
    <tr>
      <td><code>get_transactions_summary</code></td>
      <td>gets the transaction summary data from the transactions page</td>
    </tr>
    <tr>
      <td><code>get_transactions</code></td>
      <td>gets transaction data, defaults to returning the last 100 transactions; can also be searched by date range</td>
    </tr>
    <tr>
      <td><code>find_duplicate_transactions</code></td>
      <td>finds duplicate transaction groups using Plaid-reported fields</td>
    </tr>
      <tr>
        <td><code>get_transaction_categories</code></td>
        <td>gets all of the categories configured in the account</td>
      </tr>
    <tr>
      <td><code>get_transaction_category_groups</code></td>
      <td>all category groups configured in the account</td>
    </tr>
    <tr>
      <td><code>get_household_members</code></td>
      <td>gets household member IDs, names, display names, and roles</td>
    </tr>
    <tr>
      <td><code>get_transaction_details</code></td>
      <td>gets detailed transaction data for a single transaction</td>
    </tr>
    <tr>
      <td><code>get_transaction_splits</code></td>
      <td>gets transaction splits for a single transaction</td>
    </tr>
    <tr>
      <td><code>get_savings_goal_events</code></td>
      <td>gets a Savings Goal's paginated event history (contributions, withdrawals), optionally filtered by <code>start_date</code>/<code>end_date</code></td>
    </tr>
    <tr>
      <td><code>get_transaction_tags</code></td>
      <td>gets all of the tags configured in the account</td>
    </tr>
    <tr>
      <td><code>get_transaction_rules</code></td>
      <td>gets all transaction rules configured in the account, in priority order</td>
    </tr>
    <tr>
      <td><code>get_cashflow</code></td>
      <td>gets cashflow data (by category, category group, merchant and a summary)</td>
    </tr>
    <tr>
      <td><code>get_cashflow_summary</code></td>
      <td>gets cashflow summary (income, expense, savings, savings rate)</td>
    </tr>
    <tr>
      <td><code>get_goal_options</code></td>
      <td>gets the preset Savings Goal templates (Emergency fund, Down payment, Custom, ...)</td>
    </tr>
    <tr>
      <td><code>is_accounts_refresh_complete</code></td>
      <td>gets the status of a running account refresh</td>
    </tr>
  </tbody>
</table>

### Read-Only Export Examples

These methods use the same authenticated client as the existing getters and return JSON-compatible dictionaries. Single-page methods preserve the server response and do not silently fetch subsequent pages.

Account roster:

```python
roster = await mm.get_account_roster(include_deleted=True, include_hidden=True)
```

Account details:

```python
account = await mm.get_account_details("account-id")
```

Merchant page:

```python
merchant_page = await mm.get_merchants(limit=100, offset=0)
```

All merchants:

```python
merchants = await mm.get_all_merchants(limit=100)
```

Retail transaction page:

```python
retail = await mm.get_retail_transactions(first=100, filters=None)
```

Activity event page:

```python
activity = await mm.get_activity_events(first=100, exclude_event_types=[])
```

User profile:

```python
profile = await mm.get_user_profile()
```

Household preferences:

```python
preferences = await mm.get_household_preferences()
```

Report configurations:

```python
reports = await mm.get_report_configurations()
```

Recurring streams:

```python
streams = await mm.get_recurring_transaction_streams(include_liabilities=True)
```

Process or save each cursor page before fetching the next one. Pass the same filters/exclusions on every page. Only `get_all_merchants()` collects all pages automatically. With merchants that have no transactions included, the collected list can exceed `merchantCount`; the helper never treats that reported count as an export limit or claims equality. Offset pagination assumes the merchant list remains stable while scanning; overlapping/repeated IDs raise an error rather than returning an apparently complete export.

`get_account_roster()` is an identity roster, not a replacement for `get_accounts()` metadata. Use its IDs to request details, preserving null responses or access errors for deleted accounts instead of silently excluding them. `get_account_details()` leaves `account` and `snapshotsForAccount` unchanged; the older `get_account_history()` still returns its enriched snapshot list. Recurring stream definitions and their next forecasts are separate from the date-bounded calendar returned by `get_recurring_transactions()`.

## Mutating Methods

<table>
  <thead>
    <tr>
      <th width="280">Method</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>delete_transaction_category</code></td>
      <td>deletes a category for transactions</td>
    </tr>
    <tr>
      <td><code>delete_transaction_categories</code></td>
      <td>deletes a list of transaction categories for transactions</td>
    </tr>
    <tr>
      <td><code>update_transaction_category(category_id, name=None, icon=None, group_id=None)</code></td>
      <td>updates a category by its required string <code>category_id</code>. Optional string parameters are <code>name</code> (new name), <code>icon</code> (unicode string or emoji), and <code>group_id</code> (destination group id from <code>get_transaction_category_groups()</code>). Fields set to <code>None</code> are omitted from the request. Example: <code>await mm.update_transaction_category("cat-1", name="Groceries", icon="🛒", group_id="grp-2")</code>. To move only the group: <code>await mm.update_transaction_category("cat-1", group_id="grp-2")</code>. Returns the updated category, including its group.</td>
    </tr>
    <tr>
      <td><code>create_transaction_category</code></td>
      <td>creates a category for transactions</td>
    </tr>
    <tr>
      <td><code>create_transaction_rule</code></td>
      <td>creates a transaction rule that sets a category for transactions matching merchant, amount, category, or account criteria</td>
    </tr>
    <tr>
      <td><code>update_transaction_rule</code></td>
      <td>updates a transaction rule. Reads the current rule and resends its criteria, category action, merchant rename, and tags, because Monarch silently ignores partial rule updates. Required: <code>rule_id</code> (str, from <code>get_transaction_rules()</code>). Optional replacements: <code>set_category_id</code> (str or None), <code>merchant_criteria</code> (list of operator/value dicts or None), <code>merchant_criteria_use_original_statement</code> (bool or None), <code>amount_criteria</code> (dict or None), <code>category_ids</code> and <code>account_ids</code> (lists of ids or None). Omitted replacements keep their current values. Explicit <code>None</code> sends GraphQL null to clear nullable fields. <code>False</code> and empty lists are sent unchanged. <code>apply_to_existing_transactions</code> (bool, default False) also applies the rule to past matches. Example: <code>await mm.update_transaction_rule("rule-1", set_category_id="category-2")</code>. To clear the amount criterion: <code>await mm.update_transaction_rule("rule-1", amount_criteria=None)</code>. Returns the updated rule's id in a dict. Raises <code>RequestFailedException</code> for a missing rule, payload errors, or a silent no-op. Rules with unsupported criteria or actions raise <code>NotImplementedError</code> before the update request.</td>
    </tr>
    <tr>
      <td><code>request_accounts_refresh</code></td>
      <td>requests a synchronization / refresh of all accounts linked to Monarch Money. This is a <strong>non-blocking call</strong>. If the user wants to check on the status afterwards, they must call <code>is_accounts_refresh_complete</code>.</td>
    </tr>
    <tr>
      <td><code>request_accounts_refresh_and_wait</code></td>
      <td>requests a synchronization / refresh of all accounts linked to Monarch Money. This is a <strong>blocking call</strong> and will not return until the refresh is complete or no longer running.</td>
    </tr>
    <tr>
      <td><code>create_transaction</code></td>
      <td>creates a transaction with the given attributes</td>
    </tr>
    <tr>
      <td><code>update_transaction</code></td>
      <td>modifies one or more attributes for an existing transaction</td>
    </tr>
    <tr>
      <td><code>delete_merchant</code></td>
      <td>deletes a merchant by id. Pass <code>move_to_merchant_id</code> to merge it into another merchant first (Monarch's "Merge &amp; delete"), e.g. <code>await mm.delete_merchant("170000000000000001", move_to_merchant_id="170000000000000002")</code></td>
    </tr>
    <tr>
      <td><code>archive_savings_goal</code></td>
      <td>archives a savings goal by id. Monarch withdraws the goal's allocated funds and removes it from future budgets; history is kept</td>
    </tr>
    <tr>
      <td><code>unarchive_savings_goal</code></td>
      <td>unarchives a savings goal by id (funds withdrawn on archive are not restored)</td>
    </tr>
    <tr>
      <td><code>update_reoccuring</code></td>
      <td>updates recurring merchant settings (frequency, amount, date, active status)</td>
    </tr>
    <tr>
      <td><code>delete_transaction_rule(rule_id)</code></td>
      <td>deletes a transaction rule by its required string <code>rule_id</code> from <code>get_transaction_rules()</code>. Example: <code>await mm.delete_transaction_rule("rule-1")</code>. Returns <code>True</code> when the payload has no errors, even if <code>deleted</code> is <code>False</code>. Raises <code>RequestFailedException</code> for payload errors.</td>
    </tr>
    <tr>
      <td><code>delete_transaction</code></td>
      <td>deletes a given transaction by the provided transaction id</td>
    </tr>
    <tr>
      <td><code>update_transaction_splits</code></td>
      <td>modifies how a transaction is split (or not)</td>
    </tr>
    <tr>
      <td><code>create_transaction_tag</code></td>
      <td>creates a tag for transactions</td>
    </tr>
    <tr>
      <td><code>set_transaction_tags</code></td>
      <td>sets the tags on a transaction</td>
    </tr>
    <tr>
      <td><code>set_budget_amount</code></td>
      <td>sets a budget's value to the given amount (date allowed, will only apply to month specified by default). A zero amount value will <code>unset</code> or <code>clear</code> the budget for the given category.</td>
    </tr>
    <tr>
      <td><code>set_savings_goal_budget_amount</code></td>
      <td>sets a savings goal's planned contribution for a month (applies to future months by default). Pass <code>account_id</code> for a per-account contribution; omit it for the general contribution</td>
    </tr>
    <tr>
      <td><code>update_flexible_budget</code></td>
      <td>updates the Flexible budget bucket amount for a month</td>
    </tr>
    <tr>
      <td><code>update_flex_rollover_settings</code></td>
      <td>updates the Flex rollover settings, including the start month and starting balance</td>
    </tr>
    <tr>
      <td><code>reset_budget</code></td>
      <td>resets the budget for a month back to its defaults</td>
    </tr>
      <tr>
        <td><code>create_manual_account</code></td>
        <td>creates a new manual account</td>
      </tr>
    <tr>
      <td><code>delete_account</code></td>
      <td>deletes an account by the provided account id</td>
    </tr>
    <tr>
      <td><code>update_account</code></td>
      <td>updates settings and/or balance of the provided account id</td>
    </tr>
    <tr>
      <td><code>upload_account_balance_history</code></td>
      <td>uploads account history csv file for a given account</td>
    </tr>
    <tr>
      <td><code>upload_attachment</code></td>
      <td>uploads a binary file for a given transaction by the provided transaction id</td>
    </tr>
    <tr>
      <td><code>upload_receipt_to_inbox(file_content, filename)</code></td>
      <td>uploads a receipt image to the Monarch general receipt inbox (not attached to a specific transaction), triggering Monarch's AI to auto-categorize and match it</td>
    </tr>
  </tbody>
</table>

## Typed Client

If you want typed account, budget, subscription, and holdings models, import the typed client:

```python
from typedmonarchmoney import TypedMonarchMoney

mm = TypedMonarchMoney()
accounts = await mm.get_accounts()
```

The typed client provides `MonarchAccount`, `MonarchBudget`, `MonarchBudgetMonth`, `MonarchSubscription`, `MonarchCashflowSummary`, and `MonarchHoldings` models.

# Contributing

Any and all contributions - code, documentation, feature requests, feedback - are welcome!

If you plan to submit up a pull request, you can expect a timely review.  There aren't any strict requirements around the environment you'll need.

## Opening a pull request

This library requires a pre-push check requiring that you log into your Monarch account and test all NON-MUTATING methods return valid JSON data including those of new types. If any fail, the push fails.

```sh
# One-time setup
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make install-hooks
```

```sh
# Automatically runs run_tests.py before pushing
git push
```

# FAQ

**How do I use this API if I login to Monarch via Google?**

If you currently use Google or 'Continue with Google' to access your Monarch account, you'll need to set a password to leverage this API.  You can set a password on your Monarch account by going to your [security settings](https://app.monarchmoney.com/settings/security).  

Don't forget to use a password unique to your Monarch account and to enable multi-factor authentication!

# Projects Using This Library
*Open a PR adjusting the README if you would like to be added to this list*

*Disclaimer: These projects are neither affiliated nor endorsed by Monarch Money.*

- [mmoney-cli](https://github.com/theFong/mmoney-cli) - Access your MonarchMoney data via CLI
- [monarchmoney-typed](https://github.com/jeeftor/monarchmoney-typed) - MonarchMoney Home Assistant Integration
- [monarch-mcp-server](https://github.com/robcerda/monarch-mcp-server) - Model Context Protocol (MCP) server for integrating with Monarch Money.
