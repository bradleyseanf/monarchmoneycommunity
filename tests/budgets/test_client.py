from unittest.mock import patch

from gql import Client


from tests._fixtures import MonarchFixture


class TestBudgetsClient(MonarchFixture):

    @patch.object(Client, "execute_async")
    async def test_get_budgets(self, mock_execute_async):
        """
        Test the get_accounts method.
        """
        mock_execute_async.return_value = self.loadTestData(
            filename="get_budgets.json",
        )
        result = await self.monarch_money.get_budgets(
            start_date="2024-12-01", end_date="2025-2-31"
        )
        mock_execute_async.assert_called_once()
        self.assertIsNotNone(result, "Expected result to not be None")
        self.assertEqual(
            len(result["budgetData"]["monthlyAmountsByCategory"]),
            2,
            "Expected 2 categories",
        )
        self.assertEqual(len(result["categoryGroups"]), 2, "Expected 2 category groups")
        self.assertEqual(len(result["goalsV2"]), 1, "Expected 1 goal")
