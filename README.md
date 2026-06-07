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

Monarch Money requires multi-factor authentication and increasingly blocks programmatic logins with CAPTCHA. There are three supported auth approaches — pick the one that works for your setup.

## Option 1: TOTP secret key (fully automated, recommended for scripts)

If you have the base-32 secret from when you set up your authenticator app, the library can generate the 6-digit code automatically. In Monarch, go to **Settings → Security → Two-factor authentication** and copy the **"Two-factor text code"** (the raw base-32 string, not the QR code).

```python
from monarchmoney import MonarchMoney

mm = MonarchMoney()
await mm.login(
    email="you@example.com",
    password="yourpassword",
    mfa_secret_key="BASE32TOTPSECRETHERE",
)
```

## Option 2: Interactive MFA code prompt

If you don't have the base-32 secret but can read a 6-digit code from your authenticator app:

```python
from monarchmoney import MonarchMoney, RequireMFAException

mm = MonarchMoney()
try:
    await mm.login(email="you@example.com", password="yourpassword")
except RequireMFAException:
    code = input("Enter your 6-digit MFA code: ")
    await mm.multi_factor_authenticate("you@example.com", "yourpassword", code)
```

For iPython / Jupyter, `interactive_login()` handles this automatically:

```python
mm = MonarchMoney()
await mm.interactive_login()
```

## Option 3: Browser cookies (use when CAPTCHA blocks login)

If Monarch blocks the programmatic login with a CAPTCHA, authenticate via your browser instead:

1. Open [app.monarch.com](https://app.monarch.com) and log in normally
2. Open DevTools → **Application** → **Cookies** → `app.monarch.com`
3. Copy the values of `session_id` and `csrftoken`

```python
from monarchmoney import MonarchMoney

mm = MonarchMoney()
await mm.login_with_cookies("session_id=xxx; csrftoken=yyy")
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
      <td>gets all the accounts linked to Monarch Money</td>
    </tr>
    <tr>
      <td><code>get_account_holdings</code></td>
      <td>gets all of the securities in a brokerage or similar type of account</td>
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
      <td><code>get_institutions</code></td>
      <td>gets institutions linked to Monarch Money</td>
    </tr>
    <tr>
      <td><code>get_budgets</code></td>
      <td>all the budgets and the corresponding actual amounts</td>
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
      <td><code>get_transaction_details</code></td>
      <td>gets detailed transaction data for a single transaction</td>
    </tr>
    <tr>
      <td><code>get_transaction_splits</code></td>
      <td>gets transaction splits for a single transaction</td>
    </tr>
    <tr>
      <td><code>get_transaction_tags</code></td>
      <td>gets all of the tags configured in the account</td>
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
      <td><code>is_accounts_refresh_complete</code></td>
      <td>gets the status of a running account refresh</td>
    </tr>
  </tbody>
</table>

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
      <td><code>create_transaction_category</code></td>
      <td>creates a category for transactions</td>
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
      <td><code>update_reoccuring</code></td>
      <td>updates recurring merchant settings (frequency, amount, date, active status)</td>
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
  </tbody>
</table>

# Contributing

Any and all contributions - code, documentation, feature requests, feedback - are welcome!

If you plan to submit up a pull request, you can expect a timely review.  There aren't any strict requirements around the environment you'll need.

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
