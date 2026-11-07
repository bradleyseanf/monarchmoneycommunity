# Exceptions & endpoints

## Exceptions

| Exception | Meaning |
| --- | --- |
| `RequireMFAException` | Login requires a second factor. Call `multi_factor_authenticate`. |
| `LoginFailedException` | Authentication failed, or required credentials/cookies are missing. |
| `CaptchaRequiredException` | Login requires CAPTCHA. A subclass of `LoginFailedException`; see the cookie login guide. |
| `RequestFailedException` | An operation reports a request failure. |

All four exceptions can be imported explicitly from `monarchmoney`. Transport
and GraphQL errors from dependencies may also propagate; they are not all wrapped
in `RequestFailedException`. See [authentication](../authentication.md).

::: monarchmoney.monarchmoney.RequireMFAException
    options:
      members: false

::: monarchmoney.monarchmoney.LoginFailedException
    options:
      members: false

::: monarchmoney.monarchmoney.CaptchaRequiredException
    options:
      members: false

::: monarchmoney.monarchmoney.RequestFailedException
    options:
      members: false

## Endpoint helpers

The client normally manages these URLs. They are exposed here for reference,
alongside the advanced
[`gql_call`](client.md#monarchmoney.monarchmoney.MonarchMoney.gql_call) method.

::: monarchmoney.monarchmoney.MonarchMoneyEndpoints

## Default values

Some signatures refer to named constants. These values are read directly from
the source. The constructor's `timeout=10` controls GraphQL requests;
`DEFAULT_TIMEOUT_SECS` is the default polling timeout for refreshes and uploads.

::: monarchmoney.monarchmoney
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - SESSION_DIR
        - SESSION_FILE
        - DEFAULT_RECORD_LIMIT
        - DEFAULT_TIMEOUT_SECS
        - DEFAULT_DELAY_SECS
