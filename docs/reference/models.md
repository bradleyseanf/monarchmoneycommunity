# Models

These models describe the typed wrapper's Python objects. Most are initialized
from Monarch response dictionaries. The attributes below are collected from the
source; attributes without type annotations may only show their names. Expand
the class source to inspect conversion and fallback behavior.

```python
from typedmonarchmoney import MonarchAccount, MonarchBudget, MonarchHoldings
from monarchmoney.monarchmoney import BalanceHistoryRow
```

::: typedmonarchmoney.models
    options:
      show_root_heading: false
      show_root_toc_entry: false
      heading_level: 2
      filters: ["^Monarch"]
      show_attribute_values: false
      show_source: true

## Balance history upload row

Pass `BalanceHistoryRow` instances to
[`upload_account_balance_history`](client.md#monarchmoney.monarchmoney.MonarchMoney.upload_account_balance_history).

::: monarchmoney.monarchmoney.BalanceHistoryRow
