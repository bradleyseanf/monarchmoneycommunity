"""Compatibility imports for the pre-1.7.1 read API path.

The getters and query resource loader now live in monarchmoney.monarchmoney.
This module deliberately contains no second implementation.
"""

from gql import GraphQLRequest
from graphql import DocumentNode

from .monarchmoney import MonarchMoney, _query
from .read_types import JSONObject, MerchantPaginationError, MerchantsResponse

# Legacy mixin imports and method monkeypatches resolve to the actual client.
ReadApiMixin = MonarchMoney
