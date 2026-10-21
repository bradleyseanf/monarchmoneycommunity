import unittest
from unittest.mock import AsyncMock, patch

from monarchmoney import MonarchMoney
from monarchmoney.read_types import JSONObject, MerchantPaginationError


class TestMerchantPagination(unittest.IsolatedAsyncioTestCase):
    async def test_scan_continues_past_reported_count_until_short_page(self) -> None:
        for reported_count in (0, 2, 100):
            with self.subTest(reported_count=reported_count):
                pages = [
                    {"merchantCount": reported_count, "merchants": [{"id": "a"}, {"id": "b"}]},
                    {"merchantCount": reported_count + 1, "merchants": [{"id": "c"}, {"id": "d"}]},
                    {"merchantCount": reported_count + 1, "merchants": [{"id": "e"}]},
                ]
                client = MonarchMoney()
                with patch.object(client, "gql_call", AsyncMock(side_effect=pages)) as call:

                    result = await client.get_all_merchants(limit=2)

                self.assertEqual(result, {
                    "merchantCount": reported_count,
                    "merchants": [{"id": merchant_id} for merchant_id in "abcde"],
                })
                self.assertEqual([entry.kwargs["variables"]["offset"] for entry in call.await_args_list], [0, 2, 4])
                self.assertTrue(all(entry.kwargs["variables"]["includeMerchantsWithoutTransactions"] for entry in call.await_args_list))

    async def test_exact_page_multiple_requires_empty_terminal_page(self) -> None:
        client = MonarchMoney()
        pages = [
            {"merchantCount": 1, "merchants": [{"id": "a"}, {"id": "b"}]},
            {"merchantCount": 1, "merchants": []},
        ]
        with patch.object(client, "gql_call", AsyncMock(side_effect=pages)) as call:

            result = await client.get_all_merchants(limit=2, include_merchants_without_transactions=False)

        self.assertEqual(len(result["merchants"]), 2)
        self.assertEqual(call.await_count, 2)
        awaited = call.await_args
        assert awaited is not None
        self.assertEqual(awaited.kwargs["variables"], {
            "limit": 2, "offset": 2, "includeMerchantsWithoutTransactions": False,
        })

    async def test_empty_initial_page_preserves_reported_count(self) -> None:
        client = MonarchMoney()
        with patch.object(client, "gql_call", AsyncMock(return_value={"merchantCount": 5, "merchants": []})) as call:

            result = await client.get_all_merchants()

        self.assertEqual(result, {"merchantCount": 5, "merchants": []})
        call.assert_awaited_once()

    async def test_repeated_page_is_rejected_instead_of_looping(self) -> None:
        client = MonarchMoney()
        page: JSONObject = {"merchantCount": 100, "merchants": [{"id": "a"}, {"id": "b"}]}
        with patch.object(client, "gql_call", AsyncMock(return_value=page)) as call:

            with self.assertRaises(MerchantPaginationError) as caught:
                await client.get_all_merchants(limit=2)

        self.assertEqual(caught.exception.offset, 2)
        self.assertEqual(call.await_count, 2)

    async def test_duplicate_within_first_page_is_rejected(self) -> None:
        client = MonarchMoney()
        page: JSONObject = {"merchantCount": 2, "merchants": [{"id": "a"}, {"id": "a"}]}
        with patch.object(client, "gql_call", AsyncMock(return_value=page)):

            with self.assertRaises(MerchantPaginationError) as caught:
                await client.get_all_merchants(limit=2)

        self.assertEqual(caught.exception.offset, 0)

    async def test_overlap_on_short_final_page_is_rejected(self) -> None:
        client = MonarchMoney()
        pages = [
            {"merchantCount": 3, "merchants": [{"id": "a"}, {"id": "b"}]},
            {"merchantCount": 3, "merchants": [{"id": "b"}]},
        ]
        with patch.object(client, "gql_call", AsyncMock(side_effect=pages)):

            with self.assertRaises(MerchantPaginationError) as caught:
                await client.get_all_merchants(limit=2)

        self.assertEqual(caught.exception.offset, 2)

    async def test_malformed_pages_never_masquerade_as_complete(self) -> None:
        pages: list[JSONObject] = [
            {},
            {"merchantCount": 0, "merchants": None},
            {"merchantCount": True, "merchants": []},
            {"merchantCount": -1, "merchants": []},
            {"merchantCount": 0, "merchants": [None]},
            {"merchantCount": 1, "merchants": [{}]},
            {"merchantCount": 1, "merchants": [{"id": ""}]},
            {"merchantCount": 1, "merchants": [{"id": 1}]},
        ]
        for page in pages:
            with self.subTest(page=page):
                client = MonarchMoney()
                with patch.object(client, "gql_call", AsyncMock(return_value=page)):

                    with self.assertRaises(MerchantPaginationError):
                        await client.get_all_merchants()
