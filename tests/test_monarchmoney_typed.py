import json
import os
import pickle
import unittest
from unittest.mock import patch

from gql import Client

from monarchmoney.monarchmoney_typed import (
    MonarchAccount,
    MonarchCashflowSummary,
    MonarchHoldings,
    MonarchSubscription,
    TypedMonarchMoney,
)


class TestMonarchMoneyTyped(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session_file = "temp_typed_session.pickle"
        with open(self.session_file, "wb") as fh:
            pickle.dump({"cookies": {}, "token": "test_token"}, fh)
        self.monarch_money = TypedMonarchMoney()
        self.monarch_money.load_session(self.session_file)

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

    @patch.object(Client, "execute_async")
    async def test_cashflow_and_subscription_are_typed(self, mock_execute_async):
        mock_execute_async.return_value = {
            "summary": [{"summary": {"sumIncome": 8, "sumExpense": -3, "savings": 5, "savingsRate": 0.625}}],
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

    @patch.object(Client, "execute_async")
    async def test_holdings_are_typed(self, mock_execute_async):
        mock_execute_async.return_value = self.load_test_data("get_account_holdings.json")
        account = MonarchAccount(self.load_test_data("get_accounts.json")["accounts"][4])

        holdings = await self.monarch_money.get_account_holdings(account)

        self.assertIsInstance(holdings, MonarchHoldings)
        self.assertEqual(len(holdings.holdings), 3)
        self.assertEqual(holdings.holdings[0].ticker, "CMF")

