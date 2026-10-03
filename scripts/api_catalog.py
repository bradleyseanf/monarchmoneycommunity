"""Build the static method explorer from Python/GraphQL ASTs and checked-in examples.

No application modules are imported and no credentials or network are used. A
GraphQL selection describes fields, not their types: example-derived schemas are
deliberately separate from the selected field paths.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import textwrap
from pathlib import Path

from graphql import parse, print_ast
from graphql.language.ast import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    NonNullTypeNode,
    OperationDefinitionNode,
)


CLIENTS = (
    ("MonarchMoney", "monarchmoney/monarchmoney.py"),
    ("TypedMonarchMoney", "typedmonarchmoney/monarchmoney_typed.py"),
)
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
AUTH_METHODS = {
    "login",
    "interactive_login",
    "login_with_cookies",
    "multi_factor_authenticate",
    "set_token",
    "set_cookies",
}
LOCAL_METHODS = {"set_timeout", "save_session", "load_session", "delete_session"}
MUTATION_HELPERS = {
    "request_accounts_refresh_and_wait",
    "delete_transaction_categories",
    "upload_account_balance_history",
    "upload_attachment",
    "upload_receipt_to_inbox",
}


def _public_methods(module, class_name):
    client = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return [
        node
        for node in client.body
        if isinstance(node, FUNCTIONS)
        and not node.name.startswith("_")
        and not any(
            isinstance(item, ast.Name) and item.id == "property"
            for item in node.decorator_list
        )
    ]


def _group(name):
    if name in AUTH_METHODS or name.endswith("_session"):
        return "Authentication"
    if "holding" in name:
        return "Investments"
    if "goal" in name:
        return "Goals"
    if any(word in name for word in ("budget", "rollover")):
        return "Budgets"
    if "cashflow" in name:
        return "Cashflow"
    if any(
        word in name
        for word in ("transaction", "merchant", "reoccuring", "receipt", "attachment")
    ):
        return "Transactions"
    if any(word in name for word in ("account", "snapshot", "institution", "credit")):
        return "Accounts"
    return "Other"


def _kind(client, name, operation):
    if client == "TypedMonarchMoney":
        return "typed"
    if name in AUTH_METHODS:
        return "auth"
    if name in LOCAL_METHODS:
        return "local"
    if name == "gql_call":
        return "graphql"
    if operation is not None:
        return operation.operation.value
    if name in MUTATION_HELPERS:
        return "mutation"
    return "query"


def _parameter_descriptions(docstring):
    descriptions = {}
    active = None
    in_args = False
    for line in docstring.splitlines():
        stripped = line.strip()
        match = re.match(r":param\s+(\w+):\s*(.*)", stripped)
        if match:
            active, description = match.groups()
            descriptions[active] = description
            continue
        if stripped in {"Args:", "Arguments:", "Parameters:"}:
            in_args = True
            active = None
            continue
        if in_args:
            match = re.match(r"(\w+)(?:\s*\([^)]*\))?:\s*(.*)", stripped)
            if match:
                active, description = match.groups()
                descriptions[active] = description
                continue
        if stripped.startswith(":") or (
            stripped.endswith(":") and not line.startswith(" ")
        ):
            active = None
            in_args = False
        elif active and stripped and line.startswith(" "):
            descriptions[active] += " " + stripped
        elif not stripped:
            active = None
    return {key: " ".join(value.split()) for key, value in descriptions.items()}


def _parameters(method):
    args = method.args
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    pairs = list(zip(positional, defaults)) + list(
        zip(args.kwonlyargs, args.kw_defaults)
    )
    descriptions = _parameter_descriptions(ast.get_docstring(method) or "")
    return [
        {
            "name": arg.arg,
            "type": ast.unparse(arg.annotation) if arg.annotation else "Any",
            "required": default is None,
            "default": ast.unparse(default) if default is not None else None,
            "description": descriptions.get(arg.arg, ""),
        }
        for arg, default in pairs
        if arg.arg not in {"self", "cls"}
    ]


def _signature(method):
    arguments = copy.deepcopy(method.args)
    arguments.args = [arg for arg in arguments.args if arg.arg not in {"self", "cls"}]
    arguments.posonlyargs = [
        arg for arg in arguments.posonlyargs if arg.arg not in {"self", "cls"}
    ]
    suffix = f" -> {ast.unparse(method.returns)}" if method.returns is not None else ""
    return f"{method.name}({ast.unparse(arguments)}){suffix}"


def _summary(method):
    docstring = ast.get_docstring(method) or ""
    lines = []
    for line in docstring.splitlines():
        if not line.strip() or line.strip().startswith(
            (":param", ":return", "Args:", "Returns:")
        ):
            if lines:
                break
            continue
        lines.append(line.strip())
    return " ".join(lines) or method.name.replace("_", " ").capitalize() + "."


def _placeholder(name, annotation=""):
    if name == "file_content":
        return b"example file contents"
    if name == "csv_content":
        return None
    if name in {"date", "start_date", "month", "start_month", "base_date"}:
        return "2026-01-01"
    if name in {"end_date", "end_month"}:
        return "2026-01-31"
    if name == "email":
        return "you@example.com"
    if name == "password":
        return "YOUR_PASSWORD"
    if name == "code":
        return "123456"
    if name == "cookie_string":
        return "session_id=YOUR_SESSION_ID; csrftoken=YOUR_CSRF_TOKEN"
    if name == "cookies":
        return {"session_id": "YOUR_SESSION_ID", "csrftoken": "YOUR_CSRF_TOKEN"}
    if name == "token":
        return "YOUR_SESSION_TOKEN"
    if name == "split_data":
        return [
            {"amount": -25.0, "categoryId": "YOUR_CATEGORY_ID"},
            {"amount": -25.0, "categoryId": "YOUR_OTHER_CATEGORY_ID"},
        ]
    if name == "filename":
        return "receipt.jpg"
    if name == "color":
        return "#3366CC"
    if name in {"account", "account_id"} and annotation == "int":
        return 123456789
    if name.endswith("_ids"):
        return ["YOUR_" + name[:-1].upper()]
    if name.endswith("_id") or name == "account":
        return "YOUR_" + ("ACCOUNT_ID" if name == "account" else name.upper())
    if name == "account_type":
        return "depository"
    if name == "account_sub_type":
        return "checking"
    if name == "timeframe":
        return "month"
    if annotation == "bool":
        return True
    if annotation in {"float", "int"}:
        return 25.0 if annotation == "float" else 30
    if name in {"name", "merchant_name"}:
        return "Example merchant"
    if name == "account_name":
        return "Example checking"
    if name == "transaction_category_name":
        return "Example category"
    return "YOUR_" + name.upper()


def _python_example(method, parameters, client):
    prefix = "# mm is an authenticated " + client + " instance.\n"
    if method.name == "gql_call":
        return (
            prefix
            + 'from gql import gql\n\nresult = await mm.gql_call(\n    operation="GetAccounts",\n    graphql_query=gql("query GetAccounts { accounts { id displayName } }"),\n)'
        )
    arguments = {
        param["name"]: repr(_placeholder(param["name"], param["type"]))
        for param in parameters
        if param["required"]
    }
    if method.name == "login":
        arguments = {
            "email": '"you@example.com"',
            "password": '"YOUR_PASSWORD"',
            "use_saved_session": "False",
        }
    if method.name == "set_budget_amount":
        arguments["category_id"] = '"YOUR_CATEGORY_ID"'
    if method.name == "upload_account_balance_history":
        prefix += "from datetime import datetime\nfrom monarchmoney.monarchmoney import BalanceHistoryRow\n\n"
        arguments["csv_content"] = (
            "[BalanceHistoryRow(date=datetime(2026, 1, 1), amount=100.0)]"
        )
    call_args = ", ".join(f"{key}={value}" for key, value in arguments.items())
    if len(call_args) > 80:
        call_args = (
            "\n"
            + "\n".join(f"    {key}={value}," for key, value in arguments.items())
            + "\n"
        )
    awaited = "await " if isinstance(method, ast.AsyncFunctionDef) else ""
    returns_none = (
        isinstance(method.returns, ast.Constant) and method.returns.value is None
    )
    assignment = "" if returns_none else "result = "
    return prefix + f"{assignment}{awaited}mm.{method.name}({call_args})"


def _graphql(method):
    strings = [
        node.args[0].value
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "gql"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    if not strings:
        return None, None, [], []
    if len(strings) != 1:
        raise ValueError(
            f"{method.name}: multiple GraphQL documents need explicit documentation"
        )
    source = textwrap.dedent(strings[0]).strip()
    document = parse(source)
    operations = [
        node
        for node in document.definitions
        if isinstance(node, OperationDefinitionNode)
    ]
    if len(operations) != 1:
        raise ValueError(f"{method.name}: expected one GraphQL operation")
    operation = operations[0]
    variables = [
        {
            "name": var.variable.name.value,
            "type": print_ast(var.type),
            "required": isinstance(var.type, NonNullTypeNode)
            and var.default_value is None,
        }
        for var in operation.variable_definitions or []
    ]
    fragments = {
        node.name.value: node
        for node in document.definitions
        if isinstance(node, FragmentDefinitionNode)
    }
    fields = []

    def visit(selection_set, prefix="", stack=()):
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                name = (selection.alias or selection.name).value
                path = f"{prefix}.{name}" if prefix else name
                if selection.selection_set:
                    visit(selection.selection_set, path, stack)
                elif name != "__typename":
                    fields.append(path)
            elif isinstance(selection, InlineFragmentNode):
                visit(selection.selection_set, prefix, stack)
            elif isinstance(selection, FragmentSpreadNode):
                name = selection.name.value
                if name in stack:
                    raise ValueError(f"{method.name}: cyclic GraphQL fragment {name}")
                visit(fragments[name].selection_set, prefix, stack + (name,))

    visit(operation.selection_set)
    return source, operation, variables, list(dict.fromkeys(fields))


def _literal(node, environment):
    """Evaluate only a small, side-effect-free expression vocabulary."""
    if isinstance(node, ast.Name):
        return environment[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_literal(item, environment) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _literal(key, environment): _literal(value, environment)
            for key, value in zip(node.keys, node.values)
        }
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_literal(node.operand, environment)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and len(node.args) == 1
        and not node.keywords
    ):
        value = _literal(node.args[0], environment)
        if node.func.id in {"str", "int", "float", "bool"}:
            return {"str": str, "int": int, "float": float, "bool": bool}[node.func.id](
                value
            )
        if node.func.id == "_to_iso_date" and (isinstance(value, str) or value is None):
            return value
    raise ValueError("Expression is not a static JSON example")


def _request_body(method, parameters, source, operation, constants):
    if source is None:
        return None
    calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "gql_call"
    ]
    if len(calls) != 1:
        return None
    variable_node = next(
        (keyword.value for keyword in calls[0].keywords if keyword.arg == "variables"),
        None,
    )
    if variable_node is None:
        return {
            "operationName": operation.name.value if operation.name else None,
            "query": source,
            "variables": {},
        }
    environment = dict(constants)
    for parameter in parameters:
        try:
            environment[parameter["name"]] = (
                _placeholder(parameter["name"], parameter["type"])
                if parameter["required"]
                else _literal(
                    ast.parse(parameter["default"], mode="eval").body, environment
                )
            )
        except (ValueError, KeyError, TypeError):
            pass
    # Conditional changes and mutations cannot be represented by the initial dict.
    dependencies = {
        node.id for node in ast.walk(variable_node) if isinstance(node, ast.Name)
    }
    assignments = [node for node in method.body if isinstance(node, ast.Assign)]
    for statement in reversed(assignments):
        if any(
            isinstance(target, ast.Name) and target.id in dependencies
            for target in statement.targets
        ):
            dependencies.update(
                node.id
                for node in ast.walk(statement.value)
                if isinstance(node, ast.Name)
            )
    for node in ast.walk(method):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
            if any(
                isinstance(child, ast.Name)
                and child.id in dependencies
                and isinstance(child.ctx, ast.Store)
                for child in ast.walk(node)
            ):
                return None
            if any(
                isinstance(child, ast.Subscript)
                and isinstance(child.ctx, ast.Store)
                and any(
                    isinstance(part, ast.Name) and part.id in dependencies
                    for part in ast.walk(child.value)
                )
                for child in ast.walk(node)
            ):
                return None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"update", "pop", "append", "extend", "setdefault"}
        ):
            if any(
                isinstance(part, ast.Name) and part.id in dependencies
                for part in ast.walk(node.func.value)
            ):
                return None
    try:
        for statement in assignments:
            if len(statement.targets) == 1 and isinstance(
                statement.targets[0], ast.Name
            ):
                try:
                    environment[statement.targets[0].id] = _literal(
                        statement.value, environment
                    )
                except (ValueError, KeyError, TypeError):
                    pass
        variables = _literal(variable_node, environment)
        json.dumps(variables)
    except (ValueError, KeyError, TypeError):
        return None
    return {
        "operationName": operation.name.value if operation.name else None,
        "query": source,
        "variables": variables,
    }


def _json_type(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _schema(values):
    """Describe observed values without asserting required fields or nullability."""
    nonnull = [value for value in values if value is not None]
    if not nonnull:
        return (
            {"description": "Only null was observed; the non-null type is unknown."}
            if values
            else {}
        )
    kinds = {_json_type(value) for value in nonnull}
    if len(kinds) > 1:
        choices = [
            _schema([value for value in nonnull if _json_type(value) == kind])
            for kind in sorted(kinds)
        ]
        if len(nonnull) < len(values):
            choices.append({"type": "null"})
        return {"anyOf": choices}
    kind = next(iter(kinds))
    result = {"type": kind}
    if len(nonnull) < len(values):
        result["type"] = [kind, "null"]
    if kind == "object":
        keys = dict.fromkeys(key for value in nonnull for key in value)
        result["properties"] = {
            key: _schema([value[key] for value in nonnull if key in value])
            for key in keys
        }
    elif kind == "array":
        result["items"] = _schema([item for value in nonnull for item in value])
    return result


def _example_schema(example, source):
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **_schema([example]),
        "description": "Example-derived shape only. Fields, value types, and nullability are not an API contract.",
        "x-schema-source": source,
    }


def _project_response(value, fields):
    """Keep selected response paths, including aliases, through objects and arrays."""
    selection = {}
    for path in fields:
        branch = selection
        parts = path.split(".")
        for name in parts[:-1]:
            branch = branch.setdefault(name, {})
        branch[parts[-1]] = None

    def project(item, branch):
        # A leaf may itself be a JSON scalar containing a dict or list. Its
        # contents are not a GraphQL selection, so preserve them unchanged.
        if branch is None:
            return item
        if isinstance(item, list):
            return [project(child, branch) for child in item]
        if isinstance(item, dict):
            return {
                name: project(child, branch[name])
                for name, child in item.items()
                if name in branch
            }
        return item

    return project(value, selection)


def _trim(value):
    if isinstance(value, dict):
        return {key: _trim(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_trim(item) for item in value[:1]]
    return value


def _mock_examples(root):
    """Only literal execute_async mocks in tests calling one public client method."""
    path = root / "tests/test_monarchmoney.py"
    if not path.exists():
        return {}
    examples = {}
    for test in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(test, FUNCTIONS) or not test.name.startswith("test_"):
            continue
        if not any(
            isinstance(node, ast.Constant) and node.value == "execute_async"
            for decorator in test.decorator_list
            for node in ast.walk(decorator)
        ):
            continue
        called = {
            node.func.attr
            for node in ast.walk(test)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "monarch_money"
            and not node.func.attr.startswith("_")
        }
        if len(called) != 1:
            continue
        method = next(iter(called))
        environment = {}
        for statement in test.body:
            if not isinstance(statement, ast.Assign):
                continue
            try:
                value = _literal(statement.value, environment)
            except (ValueError, KeyError, TypeError):
                continue
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    environment[target.id] = value
                elif (
                    isinstance(target, ast.Attribute)
                    and target.attr == "return_value"
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "mock_execute_async"
                ):
                    examples.setdefault(
                        method, (value, f"tests/test_monarchmoney.py:{test.lineno}")
                    )
    return examples


def _annotation_schema(annotation, model_names):
    if annotation is None:
        return {}
    if isinstance(annotation, ast.Constant) and annotation.value is None:
        return {"type": "null"}
    if isinstance(annotation, ast.Name):
        if annotation.id in model_names:
            return {"$ref": "#/$defs/" + annotation.id}
        return (
            {
                "type": {
                    "str": "string",
                    "int": "integer",
                    "float": "number",
                    "bool": "boolean",
                    "dict": "object",
                    "list": "array",
                }[annotation.id]
            }
            if annotation.id in {"str", "int", "float", "bool", "dict", "list"}
            else (
                {
                    "type": "string",
                    "format": "date-time",
                    "description": "Python datetime attribute.",
                }
                if annotation.id == "datetime"
                else {}
            )
        )
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        kind = annotation.value.id
        items = (
            list(annotation.slice.elts)
            if isinstance(annotation.slice, ast.Tuple)
            else [annotation.slice]
        )
        if kind in {"List", "list"}:
            return {"type": "array", "items": _annotation_schema(items[0], model_names)}
        if kind in {"Dict", "dict"}:
            return {
                "type": "object",
                "additionalProperties": _annotation_schema(items[-1], model_names),
            }
        if kind in {"Optional", "Union"}:
            choices = [_annotation_schema(item, model_names) for item in items]
            if kind == "Optional":
                choices.append({"type": "null"})
            return {"anyOf": choices}
    return {}


def _typed_schema(module, annotation):
    classes = {
        node.name: node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name != "TypedMonarchMoney"
    }
    helpers = {
        node.name: node.returns for node in module.body if isinstance(node, FUNCTIONS)
    }
    definitions = {}
    for name, model in classes.items():
        properties = {}
        initializer = next(
            (
                node
                for node in model.body
                if isinstance(node, FUNCTIONS) and node.name == "__init__"
            ),
            None,
        )
        if initializer is None:
            continue
        for node in ast.walk(initializer):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target] if isinstance(node, ast.AnnAssign) else []
            )
            for target in targets:
                if (
                    not isinstance(target, ast.Attribute)
                    or not isinstance(target.value, ast.Name)
                    or target.value.id != "self"
                    or target.attr.startswith("_")
                ):
                    continue
                schema = (
                    _annotation_schema(node.annotation, classes)
                    if isinstance(node, ast.AnnAssign)
                    else {}
                )
                value = node.value
                if (
                    not schema
                    and isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                ):
                    schema = _annotation_schema(ast.Name(id=value.func.id), classes)
                    if not schema and value.func.id in helpers:
                        schema = _annotation_schema(helpers[value.func.id], classes)
                if (
                    not schema
                    and isinstance(value, ast.Constant)
                    and value.value is not None
                ):
                    schema = _schema([value.value])
                if not schema:
                    schema = {
                        "description": "Public Python attribute; type is not annotated."
                    }
                properties[target.attr] = schema
        for node in model.body:
            if isinstance(node, FUNCTIONS) and any(
                isinstance(item, ast.Name) and item.id == "property"
                for item in node.decorator_list
            ):
                properties[node.name] = {
                    **_annotation_schema(node.returns, classes),
                    "readOnly": True,
                }
        definitions[name] = {
            "type": "object",
            "properties": properties,
            "description": f"Public attributes of {name}; this is a Python object, not a JSON response.",
        }
    result = _annotation_schema(annotation, classes)
    needed = set()

    def references(value):
        if isinstance(value, dict):
            if "$ref" in value:
                name = value["$ref"].rsplit("/", 1)[-1]
                if name not in needed:
                    needed.add(name)
                    references(definitions[name])
            for item in value.values():
                references(item)
        elif isinstance(value, list):
            for item in value:
                references(item)

    references(result)
    result.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "x-schema-source": "Python annotations and model assignments",
        }
    )
    if needed:
        result["$defs"] = {name: definitions[name] for name in sorted(needed)}
    return result


def build_catalog(root: Path) -> dict:
    """Return all public methods plus exact requests and clearly sourced examples."""
    root = Path(root)
    override_path = root / "docs/data/method-examples.json"
    overrides = (
        json.loads(override_path.read_text(encoding="utf-8"))
        if override_path.exists()
        else {}
    )
    mock_examples = _mock_examples(root)
    methods = []
    for client, source_path in CLIENTS:
        module = ast.parse((root / source_path).read_text(encoding="utf-8"))
        constants = {}
        for node in module.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                try:
                    constants[node.targets[0].id] = _literal(node.value, constants)
                except (ValueError, KeyError, TypeError):
                    pass
        for method in _public_methods(module, client):
            name = method.name
            parameters = _parameters(method)
            source, operation, variables, fields = _graphql(method)
            return_type = (
                ast.unparse(method.returns)
                if method.returns is not None
                else "Not annotated"
            )
            entry = {
                "id": f"{client}.{name}",
                "name": name,
                "client": client,
                "group": _group(name),
                "kind": _kind(client, name, operation),
                "summary": _summary(method),
                "signature": _signature(method),
                "parameters": parameters,
                "python_example": _python_example(method, parameters, client),
                "return_type": return_type,
                "response_example": None,
                "response_schema": None,
                "response_fields": fields,
                "response_note": (
                    "No response example is recorded. Selected GraphQL fields do not establish field types or nullability."
                    if source
                    else "No response example is recorded. See the Python return type and source."
                ),
                "graphql": source,
                "graphql_variables": variables,
                "request_body": _request_body(
                    method, parameters, source, operation, constants
                ),
                "source_path": source_path,
                "source_line": method.lineno,
            }
            passthrough = any(
                isinstance(node, ast.Return)
                and isinstance(node.value, ast.Await)
                and isinstance(node.value.value, ast.Call)
                and isinstance(node.value.value.func, ast.Attribute)
                and node.value.value.func.attr == "gql_call"
                for node in method.body
            )
            example = None
            provenance = None
            fixture_path = root / "tests" / f"{name}.json"
            if client == "MonarchMoney" and passthrough:
                if fixture_path.exists():
                    example = json.loads(fixture_path.read_text(encoding="utf-8"))
                    provenance = f"tests/{name}.json"
                elif name in mock_examples:
                    example, provenance = mock_examples[name]
                if provenance:
                    if source is not None:
                        example = _project_response(example, fields)
                    entry.update(
                        response_example=_trim(example),
                        response_schema=_example_schema(example, provenance),
                        response_note=f"Example from {provenance}, limited to selected fields; arrays are shortened. Schema describes example values, not a complete API contract.",
                    )
            if return_type == "None":
                entry.update(
                    response_schema={
                        "type": "null",
                        "description": "This Python method returns None.",
                    },
                    response_note="Returns None on success; no response body.",
                )
            elif return_type == "bool":
                entry.update(
                    response_example=True,
                    response_schema={"type": "boolean"},
                    response_fields=[],
                    response_note="Illustrative successful Python return value. The client returns a boolean, not the raw GraphQL response.",
                )
            if name == "get_all_holdings" and client == "MonarchMoney":
                holding_path = root / "tests/get_account_holdings.json"
                if holding_path.exists():
                    example = {
                        "accounts": [
                            {
                                "id": "YOUR_ACCOUNT_ID",
                                "displayName": "Example brokerage",
                                "holdings": json.loads(
                                    holding_path.read_text(encoding="utf-8")
                                ),
                            }
                        ]
                    }
                    entry.update(
                        response_example=_trim(example),
                        response_schema=_example_schema(
                            example,
                            "Python wrapper and tests/get_account_holdings.json",
                        ),
                        response_note="Python wrapper shape with an illustrative account and shortened holdings fixture. Each account contains its full get_account_holdings result.",
                    )
            if name == "get_account_history":
                entry["response_fields"] = [
                    field.removeprefix("snapshots.")
                    for field in fields
                    if field.startswith("snapshots.")
                ] + ["accountId", "accountName"]
                entry["response_schema"] = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "accountId": {"type": "string"},
                            "accountName": {},
                        },
                    },
                    "description": "Python list wrapper. Snapshot field types are unspecified; accountId is converted to str by the client.",
                    "x-schema-source": "Python implementation; snapshot types unknown",
                }
                entry["response_note"] = (
                    "Returns a list of snapshots with accountId and accountName added. The source annotation says Dict[str, Any], but the implementation returns a list; its exact item schema is not recorded. GraphQL includes additional fields that are not returned."
                )
            if client == "TypedMonarchMoney":
                entry.update(
                    response_schema=_typed_schema(module, method.returns),
                    response_note="Returns Python model objects. Schema describes annotations and public attributes; unannotated attribute types remain unspecified. This is not a raw GraphQL response or automatic JSON serialization.",
                )
            override = overrides.get(entry["id"], {})
            for key in ("python_example", "response_example", "response_note"):
                if key in override:
                    entry[key] = override[key]
            if (
                "response_example" in override
                and client == "MonarchMoney"
                and return_type not in {"bool", "None"}
            ):
                entry["response_schema"] = _example_schema(
                    override["response_example"], "docs/data/method-examples.json"
                )
            if "request_body" in override:
                if source is None:
                    raise ValueError(
                        f"{entry['id']}: request body has no directly declared GraphQL operation"
                    )
                body = override["request_body"]
                operation_name = operation.name.value if operation.name else None
                if body.get("operationName") != operation_name:
                    raise ValueError(
                        f"{entry['id']}: example operation does not match source"
                    )
                if not {var["name"] for var in variables if var["required"]}.issubset(
                    body.get("variables", {})
                ):
                    raise ValueError(
                        f"{entry['id']}: example omits required GraphQL variables"
                    )
                entry["request_body"] = {**body, "query": source}
            methods.append(entry)
    unknown = set(overrides) - {entry["id"] for entry in methods}
    if unknown:
        raise ValueError(f"Examples refer to unknown methods: {sorted(unknown)}")
    return {"methods": methods}
