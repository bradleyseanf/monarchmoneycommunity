"""Generate the method directory from source without importing the API client."""

import ast
import importlib.util
import json
from pathlib import Path

from mkdocs.structure.files import File


def on_files(files, config):
    root = Path(config.config_file_path).parent
    # Load the neighboring generator without changing sys.path or importing clients.
    spec = importlib.util.spec_from_file_location(
        "api_catalog", root / "scripts/api_catalog.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = module.build_catalog(root)
    files.append(
        File.generated(
            config,
            "assets/api-catalog.json",
            content=json.dumps(catalog, indent=2, ensure_ascii=False),
        )
    )
    return files


CLIENTS = (
    ("MonarchMoney", "monarchmoney/monarchmoney.py", "client.md"),
    ("TypedMonarchMoney", "typedmonarchmoney/monarchmoney_typed.py", "typed.md"),
)


def method_directory(root: Path) -> str:
    sections = []
    for class_name, source_path, reference in CLIENTS:
        module = ast.parse((root / source_path).read_text(encoding="utf-8"))
        client = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        methods = sorted(
            (
                node
                for node in client.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
                and not any(
                    isinstance(decorator, ast.Name) and decorator.id == "property"
                    for decorator in node.decorator_list
                )
            ),
            key=lambda node: node.name,
        )
        sections.append(f"## {class_name}\n")
        if class_name == "TypedMonarchMoney":
            sections.append(
                "Overrides and convenience methods are listed below. Other methods "
                "are inherited from `MonarchMoney`.\n"
            )
        sections.append("| Method | Call | Description |\n| --- | --- | --- |")
        module_path = source_path.removesuffix(".py").replace("/", ".")
        for method in methods:
            docstring = ast.get_docstring(method) or ""
            summary = " ".join(docstring.split("\n\n", 1)[0].split())
            summary = summary.replace("|", "\\|") or "See signature and source."
            call = "`await`" if isinstance(method, ast.AsyncFunctionDef) else "sync"
            target = f"{reference}#{module_path}.{class_name}.{method.name}"
            sections.append(f"| [`{method.name}`]({target}) | {call} | {summary} |")
        sections.append("")
    return "\n".join(sections)


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri == "reference/index.md":
        root = Path(config.config_file_path).parent
        return markdown.replace("<!-- method-directory -->", method_directory(root))
    return markdown
