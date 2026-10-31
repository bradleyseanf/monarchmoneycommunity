"""Rules client operations."""

from .monarchmoney import (
    Any,
    Dict,
    List,
    Optional,
    RequestFailedException,
    Union,
    _UNSET,
    _UnsetType,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class RulesMixin:

    _TRANSACTION_RULE_CRITERIA_FIELDS = (
        "merchantCriteriaUseOriginalStatement",
        "merchantCriteria",
        "originalStatementCriteria",
        "merchantNameCriteria",
        "amountCriteria",
        "categoryIds",
        "accountIds",
    )

    _TRANSACTION_RULE_UNSUPPORTED_FIELDS = (
        "criteriaOwnerIsJoint",
        "criteriaOwnerUserIds",
        "criteriaBusinessEntityIds",
        "criteriaBusinessEntityIsUnassigned",
        "linkGoalAction",
        "linkSavingsGoalAction",
        "needsReviewByUserAction",
        "unassignNeedsReviewByUserAction",
        "sendNotificationAction",
        "setHideFromReportsAction",
        "setLinkToPaydownBudgetAction",
        "reviewStatusAction",
        "actionSetOwnerIsJoint",
        "actionSetOwner",
        "actionSetBusinessEntity",
        "actionSetBusinessEntityIsUnassigned",
        "splitTransactionsAction",
    )

    _TRANSACTION_RULE_MUTATION_ERRORS = """
                fragment PayloadErrorFields on PayloadError {
                    fieldErrors {
                        field
                        messages
                        __typename
                    }
                    message
                    code
                    __typename
                }
    """

    async def delete_transaction_rule(self, rule_id: str) -> bool:
        """
        Deletes a transaction rule.

        Note: Monarch returns ``deleted: false`` even when the delete succeeds,
        so success is judged by the absence of errors. Deleting an id that does
        not exist raises a "Not found" error.

        :param rule_id: the id of the rule (from get_transaction_rules).
        """
        query = _query("rules/delete_transaction_rule")
        response = await self.gql_call(
            operation="Common_DeleteTransactionRule",
            graphql_query=query,
            variables={"id": rule_id},
        )
        payload = response["deleteTransactionRule"]
        if self._has_payload_errors(payload.get("errors")):
            raise RequestFailedException(payload.get("errors"))
        return True

    async def get_transaction_rules(self) -> Dict[str, Any]:
        """
        Gets all transaction rules configured in the account.
        Rules are returned in their priority order.
        """
        query = _query("rules/get_transaction_rules")
        return await self.gql_call(
            operation="GetTransactionRules",
            graphql_query=query,
        )

    @staticmethod
    def _strip_typename(value: Any) -> Any:
        if isinstance(value, list):
            return [MonarchMoney._strip_typename(v) for v in value]
        if isinstance(value, dict):
            return {
                k: MonarchMoney._strip_typename(v)
                for k, v in value.items()
                if k != "__typename"
            }
        return value

    @staticmethod
    def _has_payload_errors(errors: Any) -> bool:
        if not errors:
            return False
        if isinstance(errors, dict):
            return bool(
                errors.get("message") or errors.get("fieldErrors") or errors.get("code")
            )
        return True

    async def create_transaction_rule(
        self,
        set_category_id: str,
        merchant_criteria: Optional[List[Dict[str, str]]] = None,
        merchant_criteria_use_original_statement: bool = False,
        amount_criteria: Optional[Dict[str, Any]] = None,
        category_ids: Optional[List[str]] = None,
        account_ids: Optional[List[str]] = None,
        apply_to_existing_transactions: bool = False,
    ) -> Dict[str, Any]:
        """
        Creates a transaction rule that recategorizes matching transactions.

        :param set_category_id: the category id to assign when the rule matches.
        :param merchant_criteria: list of conditions on the merchant, e.g.
          [{"operator": "eq", "value": "walgreens"}] or
          [{"operator": "contains", "value": "pharmac"}].
        :param merchant_criteria_use_original_statement: match merchant_criteria
          against the original bank statement text instead of the merchant name.
        :param amount_criteria: e.g. {"operator": "gt", "isExpense": True,
          "value": 20, "valueRange": None}.
        :param category_ids: only match transactions currently in these categories.
        :param account_ids: only match transactions in these accounts.
        :param apply_to_existing_transactions: also recategorize past matches.
        :return: the created rule ({"id": ...}).
        """
        query = _query("rules/create_transaction_rule")
        rule_input: Dict[str, Any] = {
            "merchantCriteria": merchant_criteria,
            "merchantCriteriaUseOriginalStatement": merchant_criteria_use_original_statement,
            "amountCriteria": amount_criteria,
            "categoryIds": category_ids,
            "accountIds": account_ids,
            "setCategoryAction": set_category_id,
            "applyToExistingTransactions": apply_to_existing_transactions,
        }
        response = await self.gql_call(
            operation="Common_CreateTransactionRuleMutationV2",
            graphql_query=query,
            variables={"input": rule_input},
        )
        payload = response["createTransactionRuleV2"]
        if self._has_payload_errors(payload.get("errors")) or not payload.get(
            "transactionRule"
        ):
            raise RequestFailedException(payload.get("errors"))
        return payload["transactionRule"]

    async def update_transaction_rule(
        self,
        rule_id: str,
        set_category_id: Union[str, None, _UnsetType] = _UNSET,
        merchant_criteria: Union[List[Dict[str, str]], None, _UnsetType] = _UNSET,
        merchant_criteria_use_original_statement: Union[
            bool, None, _UnsetType
        ] = _UNSET,
        amount_criteria: Union[Dict[str, Any], None, _UnsetType] = _UNSET,
        category_ids: Union[List[str], None, _UnsetType] = _UNSET,
        account_ids: Union[List[str], None, _UnsetType] = _UNSET,
        apply_to_existing_transactions: bool = False,
    ) -> Dict[str, Any]:
        """
        Updates an existing transaction rule.

        Monarch's update mutation does not support partial updates: an input that
        omits the rule's existing criteria returns an empty error payload and
        changes nothing. Monarch's web app resends the whole rule on every save,
        so this method does the same: it reads the current rule and resends its
        criteria, category, merchant rename, and tags along with your changes.
        Rules that link goals, split transactions, or set review status are
        refused until those shapes are verified.

        :param rule_id: the id of the rule (from get_transaction_rules).
        :param set_category_id: new category id to assign when the rule matches.
        :param merchant_criteria, merchant_criteria_use_original_statement,
          amount_criteria, category_ids, account_ids: replace those criteria.
          Omitted arguments keep their current values. Explicit None is sent as
          GraphQL null, allowing nullable criteria or the category action to be
          cleared. False and empty lists are sent as provided.
        :param apply_to_existing_transactions: also recategorize past matches.
        :return: the updated rule ({"id": ...}).
        """
        rules = (await self.get_transaction_rules())["transactionRules"]
        current = next((r for r in rules if r["id"] == rule_id), None)
        if current is None:
            raise RequestFailedException(f"Transaction rule {rule_id} not found")

        unsupported = [
            field
            for field in self._TRANSACTION_RULE_UNSUPPORTED_FIELDS
            if current.get(field)
        ]
        if unsupported:
            raise NotImplementedError(
                "update_transaction_rule can't safely round-trip these rule "
                "fields yet: " + ", ".join(unsupported)
            )

        rule_input: Dict[str, Any] = {
            "id": rule_id,
            "applyToExistingTransactions": apply_to_existing_transactions,
        }
        # Mirror what Monarch's web app sends on save: every criteria field
        # (including nulls) plus the current actions, flattened to ids.
        for field in self._TRANSACTION_RULE_CRITERIA_FIELDS:
            rule_input[field] = self._strip_typename(current.get(field))
        category_action = current.get("setCategoryAction")
        merchant_action = current.get("setMerchantAction")
        rule_input["setCategoryAction"] = (
            category_action["id"] if category_action else None
        )
        # setMerchantAction takes the merchant *name*. Passing an id creates a
        # new merchant literally named after that id.
        rule_input["setMerchantAction"] = (
            merchant_action["name"] if merchant_action else None
        )
        rule_input["addTagsAction"] = (
            [tag["id"] for tag in current["addTagsAction"]]
            if current.get("addTagsAction")
            else None
        )

        overrides = {
            "setCategoryAction": set_category_id,
            "merchantCriteria": merchant_criteria,
            "merchantCriteriaUseOriginalStatement": merchant_criteria_use_original_statement,
            "amountCriteria": amount_criteria,
            "categoryIds": category_ids,
            "accountIds": account_ids,
        }
        rule_input.update({k: v for k, v in overrides.items() if v is not _UNSET})

        if merchant_criteria is not _UNSET:
            # Newer rules use one of these fields instead of merchantCriteria.
            # Replace the active matcher and clear the other representations so
            # an old condition cannot survive a replacement (or explicit None).
            newer_fields = ("originalStatementCriteria", "merchantNameCriteria")
            active_newer = [
                field for field in newer_fields if current.get(field) is not None
            ]
            if not active_newer:
                target_field = "merchantCriteria"
            elif merchant_criteria_use_original_statement is not _UNSET:
                target_field = (
                    "originalStatementCriteria"
                    if merchant_criteria_use_original_statement
                    else "merchantNameCriteria"
                )
            elif len(active_newer) == 1:
                target_field = active_newer[0]
            else:
                target_field = (
                    "originalStatementCriteria"
                    if current.get("merchantCriteriaUseOriginalStatement")
                    else "merchantNameCriteria"
                )
            for field in ("merchantCriteria", *newer_fields):
                rule_input[field] = None
            rule_input[target_field] = merchant_criteria

        query = _query("rules/update_transaction_rule")
        response = await self.gql_call(
            operation="Common_UpdateTransactionRuleMutationV2",
            graphql_query=query,
            variables={"input": rule_input},
        )
        payload = response["updateTransactionRuleV2"]
        if self._has_payload_errors(payload.get("errors")) or not payload.get(
            "transactionRule"
        ):
            raise RequestFailedException(
                payload.get("errors") or f"Transaction rule {rule_id} was not updated"
            )
        return payload["transactionRule"]
