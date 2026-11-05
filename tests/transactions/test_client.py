import unittest
from unittest.mock import AsyncMock, patch

from gql import Client
from monarchmoney import MonarchMoney


from tests._fixtures import MonarchFixture


class TestTransactionsClient(MonarchFixture):

    @patch.object(Client, "execute_async")
    async def test_get_transactions_summary(self, mock_execute_async):
        """
        Test the get_transactions_summary method.
        """
        mock_execute_async.return_value = self.loadTestData(
            filename="get_transactions_summary.json",
        )
        result = await self.monarch_money.get_transactions_summary()
        mock_execute_async.assert_called_once()
        self.assertIsNotNone(result, "Expected result to not be None")
        self.assertEqual(
            result["aggregates"][0]["summary"]["sumIncome"],
            50000,
            "Expected sumIncome to be 50000",
        )

    @patch.object(Client, "execute_async")
    async def test_get_transactions_needs_review_filter(self, mock_execute_async):
        """
        Test that needs_review parameter is passed as needsReview in GraphQL filters.
        """
        mock_execute_async.return_value = {
            "allTransactions": {"results": [], "totalCount": 0},
            "transactionRules": [],
        }

        await self.monarch_money.get_transactions(needs_review=True)

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertIn("variable_values", kwargs)
        self.assertTrue(
            kwargs["variable_values"]["filters"]["needsReview"],
            "Expected needsReview filter to be True",
        )

    async def test_update_transaction_category_moves_group(self):
        client = MonarchMoney()
        category = {"id": "cat-1", "name": "Fertility", "group": {"id": "grp-2"}}
        client.gql_call = AsyncMock(
            return_value={"updateCategory": {"errors": None, "category": category}}
        )
        result = await client.update_transaction_category("cat-1", group_id="grp-2")
        self.assertEqual(result, category)
        self.assertEqual(
            client.gql_call.await_args.kwargs["variables"],
            {"input": {"id": "cat-1", "group": "grp-2"}},
        )

    @patch.object(Client, "execute_async")
    async def test_update_transaction_owner(self, mock_execute_async):
        """Assign a household member or explicitly restore Shared ownership."""
        for owner_user_id, expected in (("user-1", "user-1"), ("", None)):
            with self.subTest(owner_user_id=owner_user_id):
                mock_execute_async.reset_mock()
                await self.monarch_money.update_transaction(
                    "txn-1", owner_user_id=owner_user_id
                )
                mock_execute_async.assert_called_once()
                self.assertEqual(
                    mock_execute_async.call_args.kwargs["variable_values"]["input"],
                    {
                        "id": "txn-1",
                        "category": None,
                        "name": None,
                        "ownerUserId": expected,
                    },
                )

    @patch.object(Client, "execute_async")
    async def test_update_transaction_preserves_owner(self, mock_execute_async):
        """Omitted or None ownership must not turn a category edit into Shared."""
        for kwargs in ({}, {"owner_user_id": None}):
            with self.subTest(kwargs=kwargs):
                mock_execute_async.reset_mock()
                await self.monarch_money.update_transaction(
                    "txn-1", category_id="cat-1", **kwargs
                )
                mock_execute_async.assert_called_once()
                self.assertEqual(
                    mock_execute_async.call_args.kwargs["variable_values"]["input"],
                    {"id": "txn-1", "category": "cat-1", "name": None},
                )


class TestTransactionsStandalone(unittest.IsolatedAsyncioTestCase):

    async def test_page_limit_preserves_duplicates_and_default_full_scan(self):
        transactions = [
            {
                "id": str(index),
                "date": "2026-09-20",
                "amount": -10,
                "plaidName": "same reference",
                "account": {"id": "123"},
                "createdAt": str(index),
            }
            for index in range(4)
        ]

        async def page(**kwargs):
            offset = kwargs["offset"]
            return {
                "allTransactions": {
                    "results": transactions[offset : offset + kwargs["limit"]],
                    "totalCount": len(transactions),
                }
            }

        for options, expected_calls, expected_count in (
            ({}, 2, 4),
            ({"max_pages": 1}, 1, 2),
            ({"max_pages": 2}, 2, 4),
        ):
            with self.subTest(options=options):
                client = MonarchMoney()
                client.get_transactions = AsyncMock(side_effect=page)
                result = await client.find_duplicate_transactions(
                    page_size=2, **options
                )
                self.assertEqual(client.get_transactions.await_count, expected_calls)
                self.assertEqual(len(result), 1)
                self.assertEqual(len(result[0]["transactions"]), expected_count)
                self.assertEqual(
                    [
                        call.kwargs["offset"]
                        for call in client.get_transactions.await_args_list
                    ],
                    list(range(0, expected_count, 2)),
                )

    async def test_nonpositive_page_limit_is_rejected_before_requests(self):
        client = MonarchMoney()
        client.get_transactions = AsyncMock()
        for max_pages in (0, -1):
            with self.assertRaisesRegex(ValueError, "max_pages must be positive"):
                await client.find_duplicate_transactions(max_pages=max_pages)
        client.get_transactions.assert_not_awaited()
