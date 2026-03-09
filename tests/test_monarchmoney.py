import os
import pickle
import unittest
from unittest.mock import patch

import json
from gql import Client
from monarchmoney import MonarchMoney
from monarchmoney.monarchmoney import LoginFailedException


class TestMonarchMoney(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """
        Set up any necessary data or variables for the tests here.
        This method will be called before each test method is executed.
        """
        with open("temp_session.pickle", "wb") as fh:
            session_data = {
                "cookies": {"test_cookie": "test_value"},
                "token": "test_token",
            }
            pickle.dump(session_data, fh)
        self.monarch_money = MonarchMoney()
        self.monarch_money.load_session("temp_session.pickle")

    @patch.object(Client, "execute_async")
    async def test_get_accounts(self, mock_execute_async):
        """
        Test the get_accounts method.
        """
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
            filename="get_accounts.json",
        )
        result = await self.monarch_money.get_accounts()
        mock_execute_async.assert_called_once()
        self.assertIsNotNone(result, "Expected result to not be None")
        self.assertEqual(len(result["accounts"]), 7, "Expected 7 accounts")
        self.assertEqual(
            result["accounts"][0]["displayName"],
            "Brokerage",
            "Expected displayName to be Brokerage",
        )
        self.assertEqual(
            result["accounts"][1]["currentBalance"],
            1000.02,
            "Expected currentBalance to be 1000.02",
        )
        self.assertFalse(
            result["accounts"][2]["isAsset"],
            "Expected isAsset to be False",
        )
        self.assertEqual(
            result["accounts"][3]["subtype"]["display"],
            "Roth IRA",
            "Expected subtype display to be 'Roth IRA'",
        )
        self.assertFalse(
            result["accounts"][4]["isManual"],
            "Expected isManual to be False",
        )
        self.assertEqual(
            result["accounts"][5]["institution"]["name"],
            "Rando Employer Investments",
            "Expected institution name to be 'Rando Employer Investments'",
        )
        self.assertEqual(
            result["accounts"][6]["id"],
            "90000000030",
            "Expected id to be '90000000030'",
        )
        self.assertEqual(
            result["accounts"][6]["type"]["name"],
            "loan",
            "Expected type name to be 'loan'",
        )

    @patch.object(Client, "execute_async")
    async def test_get_transactions_summary(self, mock_execute_async):
        """
        Test the get_transactions_summary method.
        """
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
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
    async def test_get_transactions_with_updated_after(self, mock_execute_async):
        """
        Test the get_transactions method with updated_after parameter.
        """
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
            filename="get_transactions.json",
        )
        updated_after_timestamp = "2024-01-01T00:00:00Z"
        result = await self.monarch_money.get_transactions(
            limit=10, updated_after=updated_after_timestamp
        )
        mock_execute_async.assert_called_once()
        self.assertIsNotNone(result, "Expected result to not be None")
        self.assertEqual(result["allTransactions"]["totalCount"], 1)
        self.assertEqual(len(result["allTransactions"]["results"]), 1)
        self.assertEqual(
            result["allTransactions"]["results"][0]["id"], "123456789"
        )

        # Verify that the updatedAfter filter was included in the call
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(kwargs["operation_name"], "GetTransactionsList")
        self.assertIn("updatedAfter", kwargs["variable_values"]["filters"])
        self.assertEqual(
            kwargs["variable_values"]["filters"]["updatedAfter"],
            updated_after_timestamp
        )

    @patch.object(Client, "execute_async")
    async def test_get_transactions_basic(self, mock_execute_async):
        """
        Test the get_transactions method without filters.
        """
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
            filename="get_transactions.json",
        )
        result = await self.monarch_money.get_transactions(limit=10)
        mock_execute_async.assert_called_once()
        self.assertIsNotNone(result, "Expected result to not be None")
        self.assertEqual(result["allTransactions"]["totalCount"], 1)

        # Verify that updatedAfter filter is not included when not specified
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(kwargs["operation_name"], "GetTransactionsList")
        self.assertNotIn("updatedAfter", kwargs["variable_values"]["filters"])

    @patch.object(Client, "execute_async")
    async def test_delete_account(self, mock_execute_async):
        """
        Test the delete_account method.
        """

        mock_execute_async.return_value = {
            "deleteAccount": {
                "deleted": True,
                "errors": None,
                "__typename": "DeleteAccountMutation",
            }
        }

        result = await self.monarch_money.delete_account("170123456789012345")

        mock_execute_async.assert_called_once()

        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(kwargs["operation_name"], "Common_DeleteAccount")
        self.assertEqual(kwargs["variable_values"], {"id": "170123456789012345"})

        self.assertIsNotNone(result, "Expected result to not be None")
        self.assertEqual(result["deleteAccount"]["deleted"], True)
        self.assertEqual(result["deleteAccount"]["errors"], None)

    @patch.object(Client, "execute_async")
    async def test_get_account_type_options(self, mock_execute_async):
        """
        Test the get_account_type_options method.
        """
        # Mock the execute_async method to return a test result
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
            filename="get_account_type_options.json",
        )

        # Call the get_account_type_options method
        result = await self.monarch_money.get_account_type_options()

        # Assert that the execute_async method was called once
        mock_execute_async.assert_called_once()

        # Assert that the result is not None
        self.assertIsNotNone(result, "Expected result to not be None")

        # Assert that the result matches the expected output
        self.assertEqual(
            len(result["accountTypeOptions"]), 10, "Expected 10 account type options"
        )
        self.assertEqual(
            result["accountTypeOptions"][0]["type"]["name"],
            "depository",
            "Expected first account type option name to be 'depository'",
        )
        self.assertEqual(
            result["accountTypeOptions"][1]["type"]["name"],
            "brokerage",
            "Expected second account type option name to be 'brokerage'",
        )
        self.assertEqual(
            result["accountTypeOptions"][2]["type"]["name"],
            "real_estate",
            "Expected third account type option name to be 'real_estate'",
        )

    @patch.object(Client, "execute_async")
    async def test_get_account_holdings(self, mock_execute_async):
        """
        Test the get_account_holdings method.
        """
        # Mock the execute_async method to return a test result
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
            filename="get_account_holdings.json",
        )

        # Call the get_account_holdings method
        result = await self.monarch_money.get_account_holdings(account_id=1234)

        # Assert that the execute_async method was called once
        mock_execute_async.assert_called_once()

        # Assert that the result is not None
        self.assertIsNotNone(result, "Expected result to not be None")

        # Assert that the result matches the expected output
        self.assertEqual(
            len(result["portfolio"]["aggregateHoldings"]["edges"]),
            3,
            "Expected 3 holdings",
        )
        self.assertEqual(
            result["portfolio"]["aggregateHoldings"]["edges"][0]["node"]["quantity"],
            101,
            "Expected first holding to be 101 in quantity",
        )
        self.assertEqual(
            result["portfolio"]["aggregateHoldings"]["edges"][1]["node"]["totalValue"],
            10000,
            "Expected second holding to be 10000 in total value",
        )
        self.assertEqual(
            result["portfolio"]["aggregateHoldings"]["edges"][2]["node"]["holdings"][0][
                "name"
            ],
            "U S Dollar",
            "Expected third holding name to be 'U S Dollar'",
        )

    @patch.object(Client, "execute_async")
    async def test_get_budgets(self, mock_execute_async):
        """
        Test the get_accounts method.
        """
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
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

    async def test_login(self):
        """
        Test the login method with empty values for email and password.
        """
        with self.assertRaises(LoginFailedException):
            await self.monarch_money.login(use_saved_session=False)
        with self.assertRaises(LoginFailedException):
            await self.monarch_money.login(
                email="", password="", use_saved_session=False
            )

    @patch("builtins.input", return_value="")
    @patch("getpass.getpass", return_value="")
    async def test_interactive_login(self, _input_mock, _getpass_mock):
        """
        Test the interactive_login method with empty values for email and password.
        """
        with self.assertRaises(LoginFailedException):
            await self.monarch_money.interactive_login(use_saved_session=False)

    @classmethod
    def loadTestData(cls, filename) -> dict:
        filename = f"{os.path.dirname(os.path.realpath(__file__))}/{filename}"
        with open(filename, "r") as file:
            return json.load(file)

    def tearDown(self):
        """
        Tear down any necessary data or variables for the tests here.
        This method will be called after each test method is executed.
        """
        self.monarch_money.delete_session("temp_session.pickle")


if __name__ == "__main__":
    unittest.main()
