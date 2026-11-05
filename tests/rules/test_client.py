import unittest
from unittest.mock import AsyncMock, patch

import json
from gql import Client
from graphql import print_ast
from monarchmoney import MonarchMoney
from monarchmoney.monarchmoney import RequestFailedException


from tests._fixtures import MonarchFixture


class TestRulesClient(MonarchFixture):

    @patch.object(Client, "execute_async")
    async def test_get_transaction_rules_includes_complete_rule_fields(
        self, mock_execute_async
    ):
        """Transaction rules include every criterion and action used by the web UI."""
        expected = {
            "transactionRules": [
                {
                    "id": "rule-1",
                    "originalStatementCriteria": [
                        {"operator": "contains", "value": "core account"}
                    ],
                    "merchantNameCriteria": [{"operator": "eq", "value": "fees"}],
                    "criteriaOwnerIsJoint": False,
                    "criteriaOwnerUserIds": ["user-1"],
                    "criteriaOwnerUsers": [{"id": "user-1", "displayName": "Owner"}],
                    "criteriaBusinessEntityIds": ["business-1"],
                    "criteriaBusinessEntityIsUnassigned": False,
                    "criteriaBusinessEntities": [
                        {"id": "business-1", "name": "Business"}
                    ],
                    "linkSavingsGoalAction": {"id": "goal-1", "name": "Reserve"},
                    "setLinkToPaydownBudgetAction": True,
                    "actionSetOwnerIsJoint": False,
                    "actionSetOwner": {"id": "user-1", "displayName": "Owner"},
                    "actionSetBusinessEntity": {
                        "id": "business-1",
                        "name": "Business",
                    },
                    "actionSetBusinessEntityIsUnassigned": False,
                    "splitTransactionsAction": {
                        "splitsInfo": [
                            {
                                "savingsGoalId": "goal-1",
                                "ownerUserId": "user-1",
                                "ownerIsJoint": False,
                                "businessEntityId": "business-1",
                                "businessEntityIsUnassigned": False,
                            }
                        ]
                    },
                }
            ]
        }
        mock_execute_async.return_value = expected

        result = await self.monarch_money.get_transaction_rules()

        self.assertEqual(result, expected)
        request = mock_execute_async.call_args.kwargs["request"]
        query = print_ast(request.document)
        required_fields = (
            "originalStatementCriteria",
            "merchantNameCriteria",
            "criteriaOwnerIsJoint",
            "criteriaOwnerUserIds",
            "criteriaOwnerUsers",
            "criteriaBusinessEntityIds",
            "criteriaBusinessEntityIsUnassigned",
            "criteriaBusinessEntities",
            "linkSavingsGoalAction",
            "setLinkToPaydownBudgetAction",
            "actionSetOwnerIsJoint",
            "actionSetOwner",
            "actionSetBusinessEntity",
            "actionSetBusinessEntityIsUnassigned",
            "savingsGoalId",
            "ownerUserId",
            "ownerIsJoint",
            "businessEntityId",
            "businessEntityIsUnassigned",
        )
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, query)


class TestRulesStandalone(unittest.IsolatedAsyncioTestCase):

    def _rule(self, **overrides):
        rule = {
            "id": "rule-1",
            "merchantCriteriaUseOriginalStatement": False,
            "merchantCriteria": None,
            "originalStatementCriteria": None,
            "merchantNameCriteria": [
                {"operator": "eq", "value": "raul maciel", "__typename": "X"}
            ],
            "amountCriteria": None,
            "categoryIds": None,
            "accountIds": None,
            "criteriaOwnerIsJoint": False,
            "setCategoryAction": {"id": "cat-old", "name": "Home Maintenance"},
            "addTagsAction": None,
            "setHideFromReportsAction": False,
        }
        rule.update(overrides)
        return rule

    async def test_delete_transaction_rule_ignores_deleted_false(self):
        client = MonarchMoney()
        client.gql_call = AsyncMock(
            return_value={"deleteTransactionRule": {"deleted": False, "errors": None}}
        )
        self.assertTrue(await client.delete_transaction_rule("rule-1"))
        self.assertEqual(
            client.gql_call.await_args.kwargs["variables"], {"id": "rule-1"}
        )

    async def test_delete_transaction_rule_raises_on_errors(self):
        client = MonarchMoney()
        client.gql_call = AsyncMock(
            return_value={
                "deleteTransactionRule": {
                    "deleted": False,
                    "errors": {"message": "nope", "fieldErrors": None, "code": None},
                }
            }
        )
        with self.assertRaises(RequestFailedException):
            await client.delete_transaction_rule("rule-1")

    async def test_create_transaction_rule(self):
        client = MonarchMoney()
        client.gql_call = AsyncMock(
            return_value={
                "createTransactionRuleV2": {
                    "errors": None,
                    "transactionRule": {"id": "rule-9"},
                }
            }
        )
        result = await client.create_transaction_rule(
            "cat-rx", merchant_criteria=[{"operator": "eq", "value": "walgreens"}]
        )
        self.assertEqual(result, {"id": "rule-9"})
        sent = client.gql_call.await_args.kwargs["variables"]["input"]
        self.assertEqual(sent["setCategoryAction"], "cat-rx")
        self.assertEqual(
            sent["merchantCriteria"], [{"operator": "eq", "value": "walgreens"}]
        )
        self.assertFalse(sent["applyToExistingTransactions"])

    async def test_update_transaction_rule_resends_existing_criteria(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={"transactionRules": [self._rule()]}
        )
        client.gql_call = AsyncMock(
            return_value={
                "updateTransactionRuleV2": {
                    "errors": None,
                    "transactionRule": {"id": "rule-1"},
                }
            }
        )
        result = await client.update_transaction_rule(
            "rule-1", set_category_id="cat-new"
        )
        self.assertEqual(result, {"id": "rule-1"})
        sent = client.gql_call.await_args.kwargs["variables"]["input"]
        self.assertEqual(
            sent,
            {
                "id": "rule-1",
                "applyToExistingTransactions": False,
                "merchantCriteriaUseOriginalStatement": False,
                "merchantCriteria": None,
                "originalStatementCriteria": None,
                "merchantNameCriteria": [{"operator": "eq", "value": "raul maciel"}],
                "amountCriteria": None,
                "categoryIds": None,
                "accountIds": None,
                "setCategoryAction": "cat-new",
                "setMerchantAction": None,
                "addTagsAction": None,
            },
        )

    async def test_update_transaction_rule_preserves_omitted_arguments(self):
        current = self._rule(
            merchantCriteriaUseOriginalStatement=True,
            merchantCriteria=[{"operator": "contains", "value": "example"}],
            amountCriteria={"operator": "gt", "value": 10, "isExpense": True},
            categoryIds=["cat-filter"],
            accountIds=["account-1"],
        )
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={"transactionRules": [current]}
        )
        client.gql_call = AsyncMock(
            return_value={
                "updateTransactionRuleV2": {
                    "errors": None,
                    "transactionRule": {"id": "rule-1"},
                }
            }
        )

        await client.update_transaction_rule("rule-1")

        sent = client.gql_call.await_args.kwargs["variables"]["input"]
        for field in client._TRANSACTION_RULE_CRITERIA_FIELDS:
            self.assertEqual(sent[field], client._strip_typename(current[field]))
        self.assertEqual(sent["setCategoryAction"], "cat-old")
        json.dumps(sent)

    async def test_update_transaction_rule_sends_explicit_nulls(self):
        current = self._rule(
            merchantCriteriaUseOriginalStatement=True,
            merchantCriteria=[{"operator": "contains", "value": "example"}],
            amountCriteria={"operator": "gt", "value": 10, "isExpense": True},
            categoryIds=["cat-filter"],
            accountIds=["account-1"],
        )
        fields = {
            "set_category_id": "setCategoryAction",
            "merchant_criteria": "merchantCriteria",
            "merchant_criteria_use_original_statement": "merchantCriteriaUseOriginalStatement",
            "amount_criteria": "amountCriteria",
            "category_ids": "categoryIds",
            "account_ids": "accountIds",
        }
        for argument, field in fields.items():
            with self.subTest(argument=argument):
                client = MonarchMoney()
                client.get_transaction_rules = AsyncMock(
                    return_value={"transactionRules": [current]}
                )
                client.gql_call = AsyncMock(
                    return_value={
                        "updateTransactionRuleV2": {
                            "errors": None,
                            "transactionRule": {"id": "rule-1"},
                        }
                    }
                )

                await client.update_transaction_rule("rule-1", **{argument: None})

                sent = client.gql_call.await_args.kwargs["variables"]["input"]
                self.assertIsNone(sent[field])
                for other_field in fields.values():
                    if other_field != field:
                        expected = (
                            "cat-old"
                            if other_field == "setCategoryAction"
                            else current[other_field]
                        )
                        self.assertEqual(sent[other_field], expected)
                json.dumps(sent)

    async def test_update_transaction_rule_replaces_or_clears_active_merchant(self):
        old_criterion = [{"operator": "eq", "value": "old merchant"}]
        replacement = [{"operator": "contains", "value": "new merchant"}]
        merchant_fields = (
            "merchantCriteria",
            "originalStatementCriteria",
            "merchantNameCriteria",
        )
        for active_field in ("merchantNameCriteria", "originalStatementCriteria"):
            for value in (replacement, None):
                with self.subTest(active_field=active_field, value=value):
                    current = self._rule(
                        merchantCriteria=old_criterion,
                        merchantNameCriteria=None,
                        originalStatementCriteria=None,
                    )
                    current[active_field] = old_criterion
                    client = MonarchMoney()
                    client.get_transaction_rules = AsyncMock(
                        return_value={"transactionRules": [current]}
                    )
                    client.gql_call = AsyncMock(
                        return_value={
                            "updateTransactionRuleV2": {
                                "errors": None,
                                "transactionRule": {"id": "rule-1"},
                            }
                        }
                    )

                    await client.update_transaction_rule(
                        "rule-1", merchant_criteria=value
                    )

                    sent = client.gql_call.await_args.kwargs["variables"]["input"]
                    for field in merchant_fields:
                        self.assertEqual(
                            sent[field], value if field == active_field else None
                        )
                    self.assertEqual(sent["setCategoryAction"], "cat-old")

    async def test_update_transaction_rule_switches_active_merchant_field(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={"transactionRules": [self._rule()]}
        )
        client.gql_call = AsyncMock(
            return_value={
                "updateTransactionRuleV2": {
                    "errors": None,
                    "transactionRule": {"id": "rule-1"},
                }
            }
        )

        criteria = [{"operator": "eq", "value": "new statement"}]
        await client.update_transaction_rule(
            "rule-1",
            merchant_criteria=criteria,
            merchant_criteria_use_original_statement=True,
        )

        sent = client.gql_call.await_args.kwargs["variables"]["input"]
        self.assertEqual(sent["originalStatementCriteria"], criteria)
        self.assertIsNone(sent["merchantNameCriteria"])
        self.assertIsNone(sent["merchantCriteria"])
        self.assertIs(sent["merchantCriteriaUseOriginalStatement"], True)

    async def test_update_transaction_rule_sends_false_and_empty_lists(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={
                "transactionRules": [
                    self._rule(
                        merchantCriteriaUseOriginalStatement=True,
                        merchantCriteria=[{"operator": "eq", "value": "example"}],
                        categoryIds=["cat-filter"],
                        accountIds=["account-1"],
                    )
                ]
            }
        )
        client.gql_call = AsyncMock(
            return_value={
                "updateTransactionRuleV2": {
                    "errors": None,
                    "transactionRule": {"id": "rule-1"},
                }
            }
        )

        await client.update_transaction_rule(
            "rule-1",
            merchant_criteria_use_original_statement=False,
            merchant_criteria=[],
            amount_criteria={"operator": "gt", "value": 0, "isExpense": True},
            category_ids=[],
            account_ids=[],
            apply_to_existing_transactions=True,
        )

        sent = client.gql_call.await_args.kwargs["variables"]["input"]
        self.assertIs(sent["merchantCriteriaUseOriginalStatement"], False)
        self.assertIsNone(sent["merchantCriteria"])
        self.assertEqual(sent["merchantNameCriteria"], [])
        self.assertEqual(sent["amountCriteria"]["value"], 0)
        self.assertEqual(sent["categoryIds"], [])
        self.assertEqual(sent["accountIds"], [])
        self.assertIs(sent["applyToExistingTransactions"], True)
        self.assertEqual(sent["setCategoryAction"], "cat-old")

    async def test_update_transaction_rule_raises_on_silent_noop(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={"transactionRules": [self._rule()]}
        )
        client.gql_call = AsyncMock(
            return_value={
                "updateTransactionRuleV2": {
                    "errors": {"fieldErrors": None, "message": None, "code": None},
                    "transactionRule": None,
                }
            }
        )
        with self.assertRaises(RequestFailedException):
            await client.update_transaction_rule("rule-1", set_category_id="cat-new")

    async def test_update_transaction_rule_refuses_unsupported_actions(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={
                "transactionRules": [self._rule(setHideFromReportsAction=True)]
            }
        )
        client.gql_call = AsyncMock()
        with self.assertRaisesRegex(NotImplementedError, "setHideFromReportsAction"):
            await client.update_transaction_rule("rule-1", set_category_id="cat-new")
        client.gql_call.assert_not_awaited()

    async def test_update_transaction_rule_keeps_merchant_and_tags(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={
                "transactionRules": [
                    self._rule(
                        setMerchantAction={"id": "m-1", "name": "Darshana Avila"},
                        addTagsAction=[{"id": "tag-1", "name": "Subscription"}],
                    )
                ]
            }
        )
        client.gql_call = AsyncMock(
            return_value={
                "updateTransactionRuleV2": {
                    "errors": None,
                    "transactionRule": {"id": "rule-1"},
                }
            }
        )
        await client.update_transaction_rule("rule-1", set_category_id="cat-new")
        sent = client.gql_call.await_args.kwargs["variables"]["input"]
        self.assertEqual(sent["setMerchantAction"], "Darshana Avila")
        self.assertEqual(sent["addTagsAction"], ["tag-1"])
        self.assertEqual(sent["setCategoryAction"], "cat-new")

    async def test_update_transaction_rule_refuses_split_rules(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(
            return_value={
                "transactionRules": [
                    self._rule(splitTransactionsAction={"splitsInfo": []})
                ]
            }
        )
        client.gql_call = AsyncMock()
        with self.assertRaisesRegex(NotImplementedError, "splitTransactionsAction"):
            await client.update_transaction_rule("rule-1", set_category_id="cat-new")
        client.gql_call.assert_not_awaited()

    async def test_update_transaction_rule_missing_rule(self):
        client = MonarchMoney()
        client.get_transaction_rules = AsyncMock(return_value={"transactionRules": []})
        with self.assertRaises(RequestFailedException):
            await client.update_transaction_rule("nope", set_category_id="cat-new")
