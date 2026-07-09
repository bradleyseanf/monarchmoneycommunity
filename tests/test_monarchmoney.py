import os
import pickle
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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
        kwargs = mock_execute_async.call_args.kwargs
        self.assertIn("request", kwargs)
        self.assertNotIn("document", kwargs)
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
        self.assertIn("request", kwargs)
        self.assertNotIn("document", kwargs)
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

    @patch.object(Client, "execute_async")
    async def test_get_transaction_rules(self, mock_execute_async):
        """
        Test the get_transaction_rules method.
        """
        mock_execute_async.return_value = TestMonarchMoney.loadTestData(
            filename="get_transaction_rules.json",
        )

        result = await self.monarch_money.get_transaction_rules()

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertIn("request", kwargs)
        self.assertNotIn("document", kwargs)
        self.assertEqual(kwargs["operation_name"], "Web_GetTransactionRules")
        self.assertEqual(kwargs["variable_values"], {})
        self.assertIsNotNone(result, "Expected result to not be None")
        self.assertEqual(len(result["transactionRules"]), 2, "Expected 2 rules")
        self.assertEqual(result["transactionRules"][0]["order"], 1)
        self.assertEqual(
            result["transactionRules"][0]["merchantNameCriteria"][0]["operator"],
            "contains",
        )
        self.assertEqual(
            result["transactionRules"][0]["setCategoryAction"]["name"],
            "Groceries",
        )
        self.assertEqual(
            result["transactionRules"][1]["splitTransactionsAction"]["amountType"],
            "absolute",
        )

    @patch.object(Client, "execute_async")
    async def test_preview_transaction_rule(self, mock_execute_async):
        """
        Test the preview_transaction_rule method.
        """
        mock_execute_async.return_value = {
            "transactionRulePreview": {"totalCount": 1, "results": []}
        }
        rule = {
            "merchantCriteria": [
                {"operator": "contains", "value": "Example Market"}
            ],
            "setCategoryAction": "category_1",
        }

        result = await self.monarch_money.preview_transaction_rule(rule, offset=30)

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(kwargs["operation_name"], "Common_PreviewTransactionRule")
        self.assertEqual(
            kwargs["variable_values"], {"rule": rule, "offset": 30}
        )
        self.assertEqual(result["transactionRulePreview"]["totalCount"], 1)

    @patch.object(Client, "execute_async")
    async def test_create_transaction_rule(self, mock_execute_async):
        """
        Test the create_transaction_rule method.
        """
        mock_execute_async.return_value = {
            "createTransactionRuleV2": {
                "transactionRule": {"id": "rule_1"},
                "errors": None,
            }
        }
        rule = {
            "merchantCriteria": [
                {"operator": "contains", "value": "Example Market"}
            ],
            "setCategoryAction": "category_1",
            "applyToExistingTransactions": False,
        }

        result = await self.monarch_money.create_transaction_rule(rule)

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(
            kwargs["operation_name"], "Common_CreateTransactionRuleMutationV2"
        )
        self.assertEqual(kwargs["variable_values"], {"input": rule})
        self.assertEqual(
            result["createTransactionRuleV2"]["transactionRule"]["id"], "rule_1"
        )

    @patch.object(Client, "execute_async")
    async def test_update_transaction_rule(self, mock_execute_async):
        """
        Test the update_transaction_rule method.
        """
        mock_execute_async.return_value = {
            "updateTransactionRuleV2": {
                "transactionRule": {"id": "rule_1"},
                "errors": None,
            }
        }
        rule = {
            "merchantCriteria": [
                {"operator": "contains", "value": "Updated Market"}
            ],
            "setCategoryAction": "category_2",
            "applyToExistingTransactions": False,
        }

        result = await self.monarch_money.update_transaction_rule("rule_1", rule)

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(
            kwargs["operation_name"], "Common_UpdateTransactionRuleMutationV2"
        )
        expected_input = {
            "merchantCriteria": [
                {"operator": "contains", "value": "Updated Market"}
            ],
            "setCategoryAction": "category_2",
            "applyToExistingTransactions": False,
            "id": "rule_1",
        }
        self.assertEqual(
            kwargs["variable_values"],
            {"input": expected_input},
        )
        self.assertEqual(
            result["updateTransactionRuleV2"]["transactionRule"]["id"], "rule_1"
        )

    @patch.object(Client, "execute_async")
    async def test_update_transaction_rule_order(self, mock_execute_async):
        """
        Test the update_transaction_rule_order method.
        """
        mock_execute_async.return_value = {
            "updateTransactionRuleOrderV2": {
                "transactionRules": [{"id": "rule_1", "order": 2}]
            }
        }

        result = await self.monarch_money.update_transaction_rule_order("rule_1", 2)

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(kwargs["operation_name"], "Web_UpdateRuleOrderMutation")
        self.assertEqual(kwargs["variable_values"], {"id": "rule_1", "order": 2})
        self.assertEqual(
            result["updateTransactionRuleOrderV2"]["transactionRules"][0]["order"], 2
        )

    @patch.object(Client, "execute_async")
    async def test_delete_transaction_rule(self, mock_execute_async):
        """
        Test the delete_transaction_rule method.
        """
        mock_execute_async.return_value = {
            "deleteTransactionRule": {"deleted": True, "errors": None}
        }

        result = await self.monarch_money.delete_transaction_rule("rule_1")

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(kwargs["operation_name"], "Common_DeleteTransactionRule")
        self.assertEqual(kwargs["variable_values"], {"id": "rule_1"})
        self.assertTrue(result)

    @patch.object(Client, "execute_async")
    async def test_delete_transaction_rule_false_without_errors(self, mock_execute_async):
        """
        Test the delete_transaction_rule method when Monarch returns a falsey
        deleted flag without payload errors.
        """
        mock_execute_async.return_value = {
            "deleteTransactionRule": {"deleted": False, "errors": None}
        }

        result = await self.monarch_money.delete_transaction_rule("rule_1")

        mock_execute_async.assert_called_once()
        self.assertTrue(result)

    @patch.object(Client, "execute_async")
    async def test_delete_all_transaction_rules(self, mock_execute_async):
        """
        Test the delete_all_transaction_rules method.
        """
        mock_execute_async.return_value = {
            "deleteAllTransactionRules": {"deleted": True, "errors": None}
        }

        result = await self.monarch_money.delete_all_transaction_rules()

        mock_execute_async.assert_called_once()
        kwargs = mock_execute_async.call_args.kwargs
        self.assertEqual(
            kwargs["operation_name"], "Web_DeleteAllTransactionRulesMutation"
        )
        self.assertEqual(kwargs["variable_values"], {})
        self.assertTrue(result)

    @patch("builtins.input", return_value="")
    @patch("getpass.getpass", return_value="")
    async def test_interactive_login(self, _input_mock, _getpass_mock):
        """
        Test the interactive_login method with empty values for email and password.
        """
        with self.assertRaises(LoginFailedException):
            await self.monarch_money.interactive_login(use_saved_session=False)

    @patch("monarchmoney.monarchmoney.ClientSession")
    async def test_multi_factor_authenticate_bad_code_raises_login_failed(
        self, mock_client_session
    ):
        """
        Bad MFA codes should raise LoginFailedException, not RequireMFAException.
        """
        response = AsyncMock()
        response.status = 400
        response.reason = "Bad Request"
        response.json = AsyncMock(return_value={"detail": "Invalid MFA code"})

        post_context = MagicMock()
        post_context.__aenter__.return_value = response

        session = MagicMock()
        session.post.return_value = post_context

        client_context = MagicMock()
        client_context.__aenter__.return_value = session
        mock_client_session.return_value = client_context

        with self.assertRaises(LoginFailedException) as ctx:
            await self.monarch_money.multi_factor_authenticate(
                "bradley@example.com", "password", "123456"
            )

        self.assertEqual(str(ctx.exception), "Invalid MFA code")

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
