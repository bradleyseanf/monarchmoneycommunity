"""Every extracted document retains the pre-refactor GraphQL AST."""

import hashlib
import json
import unittest
from pathlib import Path
from graphql import parse, print_ast

from monarchmoney.monarchmoney import _query, _LEGACY_QUERIES

BASE = Path(__file__).resolve().parents[1]
QUERIES = BASE.parent / "monarchmoney" / "queries"


class TestResources(unittest.TestCase):
    def test_extracted_documents_match_171(self):
        expected = json.loads((BASE / "refactor_query_baseline.json").read_text())
        for name, digest in expected.items():
            with self.subTest(name=name):
                content = (QUERIES / (name + ".graphql")).read_text()
                self.assertEqual(
                    hashlib.sha256(print_ast(parse(content)).encode()).hexdigest(),
                    digest,
                )
                self.assertEqual(_query(name).document, parse(content))
        self.assertEqual(len(expected), 63)

    def test_legacy_resource_names_still_load(self):
        self.assertEqual(len(_LEGACY_QUERIES), 9)
        for old, new in _LEGACY_QUERIES.items():
            with self.subTest(old=old):
                self.assertEqual(_query(old).document, _query(new).document)
