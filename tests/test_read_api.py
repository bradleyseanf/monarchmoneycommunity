import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from gql import Client
from graphql import print_ast

from monarchmoney import MonarchMoney
from monarchmoney.read_types import JSONObject, MerchantPaginationError
from typedmonarchmoney.monarchmoney_typed import TypedMonarchMoney


class TestReadApi(unittest.IsolatedAsyncioTestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.client: MonarchMoney = MonarchMoney()
        self.execute: AsyncMock = AsyncMock()

    def setUp(self) -> None:
        patcher = patch.object(Client, "execute_async", self.execute)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_request(self, operation: str, variables: JSONObject) -> str:
        self.execute.assert_awaited_once()
        awaited = self.execute.await_args
        assert awaited is not None
        kwargs = awaited.kwargs
        self.assertEqual(kwargs["operation_name"], operation)
        self.assertEqual(kwargs["variable_values"], variables)
        return print_ast(kwargs["request"].document)

    async def test_account_details_preserve_metadata_notes_and_snapshots(self) -> None:
        expected: JSONObject = {
            "account": {
                "id": "account-1",
                "notes": "Synthetic note",
                "hideInBudget": True,
                "useAvailableBalance": False,
                "deletedAt": None,
                "originalProviderData": {"apr": 0},
                "equityGrants": [{"id": "grant-1", "notes": "Synthetic grant"}],
            },
            "snapshotsForAccount": [{"date": "2026-01-01", "signedBalance": 0}],
        }
        self.execute.return_value = expected

        result = await self.client.get_account_details("account-1")

        self.assertIs(result, expected)
        query = self.assert_request("ExportAccountComplete", {"id": "account-1"})
        for field in (
            "notes",
            "originalProviderData",
            "equityGrants",
            "goalAllocations",
            "useAvailableBalance",
            "snapshotsForAccount",
            "deletedAt",
        ):
            self.assertIn(field, query)

    async def test_account_details_preserve_inaccessible_account(self) -> None:
        expected: JSONObject = {"account": None, "snapshotsForAccount": []}
        self.execute.return_value = expected

        result = await self.client.get_account_details(123)

        self.assertIs(result, expected)
        self.assert_request("ExportAccountComplete", {"id": "123"})

    async def test_account_history_keeps_existing_enriched_list_shape(self) -> None:
        self.execute.return_value = {
            "account": {
                "id": "123",
                "displayName": "Synthetic account",
                "notes": "Not returned",
            },
            "snapshots": [{"date": "2026-01-01", "signedBalance": 0}],
        }

        result = await self.client.get_account_history(123)

        self.assertEqual(
            result,
            [
                {
                    "date": "2026-01-01",
                    "signedBalance": 0,
                    "accountId": "123",
                    "accountName": "Synthetic account",
                }
            ],
        )

    async def test_account_roster_preserves_deleted_and_hidden_identities(self) -> None:
        expected: JSONObject = {
            "accounts": [
                {"id": "deleted-1", "deletedAt": "2026-01-01", "hideFromList": True},
            ]
        }
        self.execute.return_value = expected

        result = await self.client.get_account_roster()

        self.assertIs(result, expected)
        query = self.assert_request(
            "GetAccountRoster", {"includeDeleted": True, "includeHidden": True}
        )
        self.assertIn("includeDeleted: $includeDeleted", query)
        self.assertIn("includeHidden: $includeHidden", query)
        self.assertIn("deletedAt", query)

    async def test_account_roster_passes_false_flags(self) -> None:
        self.execute.return_value = {"accounts": []}

        await self.client.get_account_roster(
            include_deleted=False, include_hidden=False
        )

        self.assert_request(
            "GetAccountRoster", {"includeDeleted": False, "includeHidden": False}
        )

    async def test_merchants_preserve_full_metadata_and_paging_controls(self) -> None:
        expected: JSONObject = {
            "merchantCount": 1,
            "merchants": [
                {
                    "id": "merchant-1",
                    "ruleCount": 0,
                    "recurrenceIgnoredAt": "2026-01-01",
                    "defaultCategoryApplicationMode": None,
                    "defaultCategory": None,
                    "recurringTransactionStream": {"id": "stream-1", "isActive": False},
                }
            ],
        }
        self.execute.return_value = expected

        result = await self.client.get_merchants(25, 75, False)

        self.assertIs(result, expected)
        query = self.assert_request(
            "ExportMerchantsComplete",
            {
                "limit": 25,
                "offset": 75,
                "includeMerchantsWithoutTransactions": False,
            },
        )
        for field in (
            "ruleCount",
            "defaultCategoryApplicationMode",
            "recurrenceIgnoredAt",
            "recurringTransactionStream",
            "showDefaultCategoryPrompt",
        ):
            self.assertIn(field, query)

    async def test_retail_page_preserves_cursor_filters_items_and_order(self) -> None:
        filters: JSONObject = {"search": "synthetic"}
        expected: JSONObject = {
            "retailTransactionsConnection": {
                "pageInfo": {"hasNextPage": True, "endCursor": "next-retail"},
                "edges": [
                    {
                        "node": {
                            "id": "retail-1",
                            "lineItems": [{"id": "item-1", "category": None}],
                            "retailOrder": {"id": "order-1", "grandTotal": 0},
                        }
                    }
                ],
            }
        }
        self.execute.return_value = expected

        result = await self.client.get_retail_transactions(25, "prior-retail", filters)

        self.assertIs(result, expected)
        query = self.assert_request(
            "Common_RetailTransactionsConnection",
            {
                "first": 25,
                "afterCursor": "prior-retail",
                "filters": filters,
            },
        )
        for field in (
            "pageInfo",
            "hasNextPage",
            "endCursor",
            "lineItems",
            "retailOrder",
            "splitTransactions",
            "category",
            "vendorOrderId",
        ):
            self.assertIn(field, query)
        self.assertEqual(filters, {"search": "synthetic"})

    async def test_activity_page_preserves_cursor_and_unread_state(self) -> None:
        expected: JSONObject = {
            "activityEvents": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [{"node": {"id": "event-1", "readAt": None, "eventData": {}}}],
            }
        }
        self.execute.return_value = expected

        result = await self.client.get_activity_events(25, "prior-event", [])

        self.assertIs(result, expected)
        query = self.assert_request(
            "Common_GetNotificationCenter",
            {
                "first": 25,
                "afterCursor": "prior-event",
                "excludeEventTypes": [],
            },
        )
        for field in (
            "pageInfo",
            "hasNextPage",
            "endCursor",
            "readAt",
            "dismissedAt",
            "eventData",
        ):
            self.assertIn(field, query)
        self.assertNotIn("mutation", query)

    async def test_cursor_defaults_request_first_page(self) -> None:
        for method_name, connection in (
            ("get_retail_transactions", "retailTransactionsConnection"),
            ("get_activity_events", "activityEvents"),
        ):
            with self.subTest(method=method_name):
                self.execute.reset_mock()
                self.execute.return_value = {
                    connection: {"edges": [], "pageInfo": {"hasNextPage": False}}
                }

                await getattr(self.client, method_name)()

                awaited = self.execute.await_args
                assert awaited is not None
                self.assertEqual(awaited.kwargs["variable_values"]["first"], 100)
                self.assertIsNone(awaited.kwargs["variable_values"]["afterCursor"])

    async def test_profile_household_and_reports_preserve_selected_objects(
        self,
    ) -> None:
        cases = (
            (
                "get_user_profile",
                "Common_GetMe",
                {"me": {"profile": {"webUiThemePreference": None}}},
                (
                    "UserFields",
                    "mobileUiThemePreference",
                    "activeSupportAccountAccessGrant",
                ),
            ),
            (
                "get_household_preferences",
                "Common_GetHouseholdPreferences",
                {
                    "householdPreferences": {"aiAssistantEnabled": False},
                    "budgetSystem": None,
                    "insightTopics": [],
                },
                (
                    "HouseholdPreferencesFields",
                    "HouseholdBudgetSettingsFields",
                    "disabledInsightTopics",
                ),
            ),
            (
                "get_report_configurations",
                "Common_GetReportConfigurations",
                {
                    "reportConfigurations": [
                        {"id": "report-1", "transactionFilterSet": {}, "reportView": {}}
                    ]
                },
                (
                    "ownershipSet",
                    "businessEntitySet",
                    "excludedSavingsGoals",
                    "chartCalculation",
                    "timeframePeriod",
                ),
            ),
        )
        for method_name, operation, expected, fields in cases:
            with self.subTest(method=method_name):
                self.execute.reset_mock()
                self.execute.return_value = expected

                result = await getattr(self.client, method_name)()

                self.assertIs(result, expected)
                query = self.assert_request(operation, {})
                for field in fields:
                    self.assertIn(field, query)

    async def test_recurring_streams_preserve_inactive_and_pending_definitions(
        self,
    ) -> None:
        expected: JSONObject = {
            "recurringTransactionStreams": [
                {
                    "stream": {
                        "id": "stream-1",
                        "isActive": False,
                        "reviewStatus": "UNREVIEWED",
                    },
                    "nextForecastedTransaction": None,
                    "category": None,
                    "account": None,
                },
            ]
        }
        for include_liabilities in (True, False):
            with self.subTest(include_liabilities=include_liabilities):
                self.execute.reset_mock()
                self.execute.return_value = expected

                result = await self.client.get_recurring_transaction_streams(
                    include_liabilities
                )

                self.assertIs(result, expected)
                query = self.assert_request(
                    "Common_GetRecurringStreams",
                    {"includeLiabilities": include_liabilities},
                )
                for field in (
                    "includePending: true",
                    "isActive",
                    "reviewStatus",
                    "baseDate",
                    "lastStatement",
                    "nextForecastedTransaction",
                    "category",
                    "account",
                ):
                    self.assertIn(field, query)
                self.assertNotIn("recurringTransactionItems(", query)

    async def test_invalid_page_sizes_are_rejected_before_requests(self) -> None:
        for method_name in (
            "get_merchants",
            "get_all_merchants",
            "get_retail_transactions",
            "get_activity_events",
        ):
            for size in (0, -1):
                with self.subTest(method=method_name, size=size):
                    with self.assertRaises(ValueError):
                        await getattr(self.client, method_name)(size)
        self.execute.assert_not_awaited()

    async def test_negative_merchant_offset_is_rejected_before_requests(self) -> None:
        with self.assertRaises(ValueError):
            await self.client.get_merchants(offset=-1)
        self.execute.assert_not_awaited()


class TestDirectReadMethods(unittest.TestCase):
    def test_new_getters_live_on_raw_client_and_are_inherited_by_typed_client(
        self,
    ) -> None:
        methods = (
            "get_account_details",
            "get_account_roster",
            "get_merchants",
            "get_all_merchants",
            "get_retail_transactions",
            "get_activity_events",
            "get_user_profile",
            "get_household_preferences",
            "get_report_configurations",
            "get_recurring_transaction_streams",
        )
        for name in methods:
            with self.subTest(name=name):
                self.assertIn(name, MonarchMoney.__dict__)
                self.assertIs(
                    getattr(TypedMonarchMoney, name), MonarchMoney.__dict__[name]
                )

    def test_pagination_error_remains_public_type(self) -> None:
        error = MerchantPaginationError(4, "duplicate merchant id")
        self.assertEqual(error.offset, 4)
        self.assertEqual(error.reason, "duplicate merchant id")
        self.assertIsInstance(error, RuntimeError)


class TestLegacyReadImportCompatibility(unittest.TestCase):
    def test_signatures_match_170_baseline(self) -> None:
        baseline = json.loads(
            (Path(__file__).with_name("read_api_170_signatures.json")).read_text()
        )
        for name, signature in baseline.items():
            with self.subTest(name=name):
                self.assertEqual(
                    str(inspect.signature(getattr(MonarchMoney, name))), signature
                )
                self.assertTrue(
                    inspect.iscoroutinefunction(getattr(MonarchMoney, name))
                )

    def test_legacy_imports_and_monkeypatch_reach_direct_client(self) -> None:
        from monarchmoney.read_api import (
            MerchantPaginationError as LegacyError,
            ReadApiMixin,
            _query,
        )
        from monarchmoney.monarchmoney import _query as direct_query

        self.assertIs(ReadApiMixin, MonarchMoney)
        self.assertIs(LegacyError, MerchantPaginationError)
        self.assertIs(_query, direct_query)
        with patch.object(
            ReadApiMixin, "get_user_profile", new=AsyncMock(return_value={"me": None})
        ):
            self.assertEqual(
                self.run_async(MonarchMoney().get_user_profile()), {"me": None}
            )

    @staticmethod
    def run_async(coroutine):
        import asyncio

        return asyncio.run(coroutine)
