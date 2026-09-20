import json
import os
import pickle
import unittest
from unittest.mock import patch

from gql import Client

from monarchmoney import (
    MonarchMoney,
)
from typedmonarchmoney import (
    MonarchAccount,
    MonarchBudget,
    MonarchBudgetMonth,
    MonarchCashflowSummary,
    MonarchHolding,
    MonarchHoldings,
    MonarchMoneyTyped,
    MonarchSubscription,
    TypedMonarchMoney,
)
from typedmonarchmoney.models import (
    MonarchBudget as ExportedMonarchBudget,
    MonarchBudgetMonth as ExportedMonarchBudgetMonth,
)


class TestMonarchMoneyTyped(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session_file = "temp_typed_session.pickle"
        with open(self.session_file, "wb") as fh:
            pickle.dump({"cookies": {}, "token": "test_token"}, fh)
        self.monarch_money = TypedMonarchMoney()
        self.monarch_money.load_session(self.session_file)

    def test_top_level_monarch_money_aliases_typed_client(self):
        self.assertEqual(MonarchMoney.__name__, "MonarchMoney")
        self.assertIs(MonarchMoneyTyped, TypedMonarchMoney)
        self.assertIs(ExportedMonarchBudget, MonarchBudget)
        self.assertIs(ExportedMonarchBudgetMonth, MonarchBudgetMonth)

    def tearDown(self):
        self.monarch_money.delete_session(self.session_file)

    @classmethod
    def load_test_data(cls, filename: str) -> dict:
        path = os.path.join(os.path.dirname(__file__), filename)
        with open(path, "r") as fh:
            return json.load(fh)

    @patch.object(Client, "execute_async")
    async def test_accounts_are_typed(self, mock_execute_async):
        mock_execute_async.return_value = self.load_test_data("get_accounts.json")

        accounts = await self.monarch_money.get_accounts()

        self.assertIsInstance(accounts[0], MonarchAccount)
        self.assertEqual(accounts[0].name, "Brokerage")
        self.assertEqual(accounts[4].type, "real_estate")
        self.assertTrue(accounts[4].is_balance_account)
        self.assertFalse(accounts[4].is_value_account)

    @patch.object(Client, "execute_async")
    async def test_cashflow_and_subscription_are_typed(self, mock_execute_async):
        mock_execute_async.return_value = {
            "summary": [
                {
                    "summary": {
                        "sumIncome": 8,
                        "sumExpense": -3,
                        "savings": 5,
                        "savingsRate": 0.625,
                    }
                }
            ],
            "subscription": {
                "id": "185960257876876964",
                "paymentSource": "STRIPE",
                "referralCode": "go3dpvrdmw",
                "isOnFreeTrial": True,
                "hasPremiumEntitlement": True,
            },
        }

        summary = await self.monarch_money.get_cashflow_summary()
        subscription = await self.monarch_money.get_subscription_details()

        self.assertIsInstance(summary, MonarchCashflowSummary)
        self.assertEqual(summary.income, 8.0)
        self.assertIsInstance(subscription, MonarchSubscription)
        self.assertEqual(subscription.id, "185960257876876964")

    @patch.object(MonarchMoney, "get_budgets")
    async def test_budgets_are_typed(self, mock_get_budgets):
        mock_get_budgets.return_value = self.load_test_data("get_budgets_typed.json")

        budgets = await self.monarch_money.get_budgets_as_dict_with_id_key(
            start_date="2026-01-01",
            end_date="2026-03-31",
            use_legacy_goals=True,
            use_v2_goals=False,
        )

        mock_get_budgets.assert_awaited_once_with(
            start_date="2026-01-01",
            end_date="2026-03-31",
            use_legacy_goals=True,
            use_v2_goals=False,
        )
        self.assertEqual(set(budgets), {"food", "empty", "paycheck"})

        food = budgets["food"]
        self.assertIsInstance(food, MonarchBudget)
        self.assertEqual(food.id, "food")
        self.assertEqual(food.name, "Groceries")
        self.assertEqual(food.group_name, "Food & Dining")
        self.assertEqual(
            list(food.monthly_amounts),
            ["2026-01-01", "2026-02-01", "2026-03-01"],
        )

        january = food.monthly_amounts["2026-01-01"]
        self.assertIsInstance(january, MonarchBudgetMonth)
        self.assertEqual(january.month, "2026-01-01")
        self.assertEqual(january.planned_amount, 100.0)
        self.assertEqual(january.actual_amount, -40.0)
        self.assertEqual(january.remaining_amount, 125.0)

        february = food.monthly_amounts["2026-02-01"]
        self.assertIsNone(february.planned_amount)
        self.assertEqual(february.actual_amount, 0.0)
        self.assertEqual(february.remaining_amount, -12.5)

        march = food.monthly_amounts["2026-03-01"]
        self.assertIsNone(march.planned_amount)
        self.assertIsNone(march.actual_amount)
        self.assertIsNone(march.remaining_amount)
        self.assertEqual(budgets["empty"].monthly_amounts, {})
        self.assertEqual(budgets["paycheck"].monthly_amounts, {})
        self.assertNotIn("dangling", budgets)

    @patch.object(MonarchMoney, "get_budgets")
    async def test_empty_budgets_are_typed(self, mock_get_budgets):
        mock_get_budgets.return_value = {}

        budgets = await self.monarch_money.get_budgets_as_dict_with_id_key()

        mock_get_budgets.assert_awaited_once_with(
            start_date=None,
            end_date=None,
            use_legacy_goals=False,
            use_v2_goals=True,
        )
        self.assertEqual(budgets, {})

    @patch.object(MonarchMoney, "get_budgets")
    async def test_budget_categories_without_budget_data_are_typed(
        self, mock_get_budgets
    ):
        mock_get_budgets.return_value = {
            "budgetData": None,
            "categoryGroups": [
                {
                    "name": "Other",
                    "categories": [{"id": "uncategorized", "name": "Other"}],
                }
            ],
        }

        budgets = await self.monarch_money.get_budgets_as_dict_with_id_key()

        self.assertEqual(set(budgets), {"uncategorized"})
        self.assertEqual(budgets["uncategorized"].monthly_amounts, {})

    @patch.object(Client, "execute_async")
    async def test_get_budgets_returns_raw_dict(self, mock_execute_async):
        raw_budgets = self.load_test_data("get_budgets_typed.json")
        mock_execute_async.return_value = raw_budgets

        result = await self.monarch_money.get_budgets(
            start_date="2026-01-01", end_date="2026-03-31"
        )

        self.assertIs(result, raw_budgets)
        self.assertIsInstance(result["budgetData"], dict)

    @patch.object(Client, "execute_async")
    async def test_holdings_are_typed(self, mock_execute_async):
        mock_execute_async.return_value = self.load_test_data(
            "get_account_holdings.json"
        )
        account = MonarchAccount(
            self.load_test_data("get_accounts.json")["accounts"][4]
        )

        holdings = await self.monarch_money.get_account_holdings(account)

        self.assertIsInstance(holdings, MonarchHoldings)
        self.assertEqual(len(holdings.holdings), 3)
        self.assertEqual(holdings.holdings[0].ticker, "CMF")
        self.assertIsInstance(holdings.holdings[0], MonarchHolding)

    @patch.object(Client, "execute_async")
    async def test_get_all_holdings_returns_raw_dict(self, mock_execute_async):
        # Regression test: get_all_holdings must bypass the typed overrides of
        # get_accounts/get_account_holdings and keep returning the raw dict
        # format even on the typed client.
        mock_execute_async.side_effect = [
            self.load_test_data("get_accounts.json"),
            self.load_test_data("get_account_holdings.json"),
            self.load_test_data("get_account_holdings.json"),
            self.load_test_data("get_account_holdings.json"),
        ]

        result = await self.monarch_money.get_all_holdings()

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["accounts"]), 3)
        for entry in result["accounts"]:
            self.assertIsInstance(entry["holdings"], dict)
            self.assertIn("portfolio", entry["holdings"])
