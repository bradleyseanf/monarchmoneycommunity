"""JSON-compatible types for read-only export responses."""

from typing import TypedDict

JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject = dict[str, JSONValue]


class MerchantsResponse(TypedDict):
    """Collected merchants and the server's independently reported count."""

    merchants: list[JSONObject]
    merchantCount: int


class MerchantPaginationError(RuntimeError):
    """A merchant page cannot be safely included in a complete result."""

    def __init__(self, offset: int, reason: str) -> None:
        self.offset: int = offset
        self.reason: str = reason
        super().__init__(f"Invalid merchant page at offset {offset}: {reason}")
