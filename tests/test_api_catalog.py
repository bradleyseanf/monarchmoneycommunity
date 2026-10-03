"""Static documentation must not pretend GraphQL selections are a typed API."""

import ast
import builtins
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from graphql import parse

from scripts.api_catalog import (
    CLIENTS,
    _example_schema,
    _graphql,
    _project_response,
    build_catalog,
)


ROOT = Path(__file__).resolve().parents[1]


def public_method_ids():
    expected = set()
    for client_name, path in CLIENTS:
        module = ast.parse((ROOT / path).read_text())
        client = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == client_name
        )
        expected.update(
            f"{client_name}.{node.name}"
            for node in client.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
            and not any(
                ast.unparse(decorator) == "property"
                for decorator in node.decorator_list
            )
        )
    return expected


class TestApiCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = build_catalog(ROOT)
        cls.methods = {method["id"]: method for method in cls.catalog["methods"]}

    def method(self, name, client="MonarchMoney"):
        return self.methods[f"{client}.{name}"]

    def test_all_public_methods_are_present_once(self):
        expected = public_method_ids()
        self.assertEqual(set(self.methods), expected)
        self.assertEqual(len(self.catalog["methods"]), len(expected))
        self.assertTrue(
            {
                "MonarchMoney.login",
                "MonarchMoney.get_accounts",
                "TypedMonarchMoney.get_accounts",
            }.issubset(expected)
        )

    def test_build_never_imports_the_clients(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split(".")[0] in {"monarchmoney", "typedmonarchmoney"}:
                raise AssertionError("Documentation imported an application module")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            methods = build_catalog(ROOT)["methods"]
            self.assertEqual({method["id"] for method in methods}, public_method_ids())

    def test_accounts_fixture_schema_is_example_derived(self):
        method = self.method("get_accounts")
        self.assertEqual(len(method["response_example"]["accounts"]), 1)
        schema = method["response_schema"]
        account = schema["properties"]["accounts"]["items"]["properties"]
        self.assertEqual(account["id"]["type"], "string")
        self.assertEqual(account["currentBalance"]["type"], "number")
        # Later fixture accounts contain null credentials. Schema must use all
        # projected rows, even though the displayed example keeps only one.
        self.assertEqual(account["credential"]["type"], ["object", "null"])
        self.assertEqual(schema["x-schema-source"], "tests/get_accounts.json")
        self.assertIn("not a complete API contract", method["response_note"])
        example_account = method["response_example"]["accounts"][0]
        self.assertNotIn("icon", example_account)
        self.assertNotIn("logo", example_account["institution"])
        self.assertNotIn("logo", example_account["credential"]["institution"])
        self.assertNotIn("icon", account)
        self.assertNotIn("logo", account["institution"]["properties"])
        self.assertNotIn(
            "logo", account["credential"]["properties"]["institution"]["properties"]
        )
        self.assertEqual(example_account["displayName"], "Brokerage")
        self.assertEqual(example_account["type"]["name"], "brokerage")
        self.assertEqual(example_account["institution"]["name"], "Rando Brokerage")
        self.assertEqual(
            example_account["credential"]["institution"]["id"], "700000000"
        )

        def check_conservative(value):
            if isinstance(value, dict):
                self.assertNotIn("required", value)
                self.assertIsNot(value.get("additionalProperties"), False)
                for child in value.values():
                    check_conservative(child)
            elif isinstance(value, list):
                for child in value:
                    check_conservative(child)

        check_conservative(schema)

    def test_fixture_projection_preserves_aliases_arrays_and_observed_shapes(self):
        method = ast.parse(
            """
async def get_items(self):
    query = gql("query { items: accounts { id owner { name } } }")
"""
        ).body[0]
        fields = _graphql(method)[3]
        fixture = {
            "items": [
                {
                    "id": "one",
                    "owner": {"name": "Example", "obsolete": 1},
                    "obsolete": True,
                },
                {"id": "two", "owner": None},
            ],
            "obsolete": "removed",
        }
        projected = _project_response(fixture, fields)
        self.assertEqual(
            projected,
            {
                "items": [
                    {"id": "one", "owner": {"name": "Example"}},
                    {"id": "two", "owner": None},
                ]
            },
        )
        schema = _example_schema(projected, "test fixture")
        owner = schema["properties"]["items"]["items"]["properties"]["owner"]
        self.assertEqual(owner["type"], ["object", "null"])
        self.assertEqual(set(owner["properties"]), {"name"})

    def test_example_schema_keeps_mixed_observed_types_and_null(self):
        schema = _example_schema({"values": ["10.0", 10.0, None]}, "test fixture")
        choices = schema["properties"]["values"]["items"]["anyOf"]
        self.assertEqual(
            {choice["type"] for choice in choices}, {"string", "number", "null"}
        )

    def test_graphql_fields_expand_fragments_and_preserve_aliases(self):
        fields = self.method("get_transactions")["response_fields"]
        self.assertIn("allTransactions.results.merchant.name", fields)
        self.assertIn("allTransactions.results.account.displayName", fields)
        self.assertIn("allTransactions.results.category.name", fields)
        self.assertIn("allTransactions.totalCount", fields)
        self.assertEqual(len(fields), len(set(fields)))
        for field in fields:
            self.assertNotIn("...", field)
        history = self.method("get_account_history")
        self.assertEqual(
            set(history["response_fields"]),
            {"date", "signedBalance", "accountId", "accountName"},
        )

    def test_requests_use_real_operation_names_and_documents(self):
        for method in self.catalog["methods"]:
            with self.subTest(method=method["id"]):
                if method["graphql"]:
                    parse(method["graphql"])
                body = method["request_body"]
                if body:
                    self.assertEqual(body["query"], method["graphql"])
                    operation = next(
                        node
                        for node in parse(body["query"]).definitions
                        if node.kind == "operation_definition"
                    )
                    self.assertEqual(operation.name.value, body["operationName"])
                    required = {
                        variable["name"]
                        for variable in method["graphql_variables"]
                        if variable["required"]
                    }
                    self.assertTrue(required.issubset(body["variables"]))
        self.assertEqual(self.method("delete_account")["kind"], "mutation")
        self.assertEqual(self.method("get_accounts")["kind"], "query")
        self.assertEqual(
            self.method("delete_account")["request_body"]["variables"],
            {"id": "YOUR_ACCOUNT_ID"},
        )
        self.assertEqual(
            self.method("get_transaction_details")["graphql_variables"],
            [
                {"name": "id", "type": "UUID!", "required": True},
                {"name": "redirectPosted", "type": "Boolean", "required": False},
            ],
        )

    def test_transformed_returns_do_not_show_the_raw_graphql_response(self):
        for name in (
            "delete_transaction",
            "delete_transaction_category",
            "request_accounts_refresh",
            "is_accounts_refresh_complete",
        ):
            method = self.method(name)
            self.assertIs(method["response_example"], True)
            self.assertEqual(method["response_schema"], {"type": "boolean"})
            self.assertEqual(method["response_fields"], [])
        all_holdings = self.method("get_all_holdings")
        wrapper = all_holdings["response_example"]["accounts"][0]
        self.assertEqual(set(wrapper), {"id", "displayName", "holdings"})
        self.assertIn("portfolio", wrapper["holdings"])
        self.assertIsNone(all_holdings["graphql"])
        history = self.method("get_account_history")
        self.assertEqual(history["response_schema"]["type"], "array")
        self.assertIn("implementation returns a list", history["response_note"])

    def test_auth_and_local_methods_have_no_fabricated_http_contract(self):
        for name in ("login", "login_with_cookies", "save_session", "set_timeout"):
            method = self.method(name)
            self.assertIsNone(method["graphql"])
            self.assertIsNone(method["request_body"])
            self.assertEqual(method["response_fields"], [])
            self.assertEqual(method["return_type"], "None")
            self.assertEqual(method["response_schema"]["type"], "null")
            self.assertIn("Returns None", method["response_note"])
            self.assertNotIn("endpoint", method)
            self.assertNotIn("http_method", method)
        self.assertEqual(self.method("gql_call")["kind"], "graphql")

    def test_unknown_shape_is_explicit_and_not_fabricated(self):
        method = self.method("get_credit_history")
        self.assertIsNone(method["response_example"])
        self.assertIsNone(method["response_schema"])
        self.assertGreater(len(method["response_fields"]), 0)
        self.assertIn("do not establish field types", method["response_note"])
        helper = self.method("delete_transaction_categories")
        self.assertIsNone(helper["response_example"])
        self.assertIsNone(helper["graphql"])
        self.assertEqual(helper["return_type"], "List[Union[bool, BaseException]]")

    def test_typed_schema_describes_python_attributes(self):
        accounts = self.method("get_accounts", "TypedMonarchMoney")
        self.assertEqual(accounts["return_type"], "List[MonarchAccount]")
        self.assertEqual(
            accounts["response_schema"]["items"], {"$ref": "#/$defs/MonarchAccount"}
        )
        fields = accounts["response_schema"]["$defs"]["MonarchAccount"]["properties"]
        self.assertIn("balance", fields)
        self.assertNotIn("currentBalance", fields)
        self.assertIn("last_update", fields)
        self.assertEqual(fields["balance"]["type"], "number")
        self.assertEqual(fields["last_update"]["format"], "date-time")
        self.assertIn("Python model objects", accounts["response_note"])
        budgets = self.method("get_budgets_as_dict_with_id_key", "TypedMonarchMoney")[
            "response_schema"
        ]
        self.assertEqual(
            budgets["additionalProperties"], {"$ref": "#/$defs/MonarchBudget"}
        )
        self.assertIn("MonarchBudgetMonth", budgets["$defs"])

    def test_parameters_signatures_and_examples_are_usable(self):
        method = self.method("get_transactions")
        parameters = {
            parameter["name"]: parameter for parameter in method["parameters"]
        }
        self.assertNotIn("self", parameters)
        self.assertEqual(parameters["limit"]["default"], "DEFAULT_RECORD_LIMIT")
        self.assertFalse(parameters["limit"]["required"])
        self.assertIn("maximum", parameters["limit"]["description"])
        self.assertNotIn("self", method["signature"])
        typed = self.method("get_accounts", "TypedMonarchMoney")
        self.assertIn("*, with_holdings", typed["signature"])
        self.assertTrue(self.method("delete_account")["parameters"][0]["required"])
        self.assertIn(
            "category_id=", self.method("set_budget_amount")["python_example"]
        )
        for method in self.catalog["methods"]:
            with self.subTest(method=method["id"]):
                ast.parse(method["python_example"])
        json.dumps(self.catalog, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
