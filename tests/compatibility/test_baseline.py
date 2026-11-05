"""Contracts recorded from the identical 1.7.1 dev/main tree."""

import inspect
import json
import re
import unittest
from pathlib import Path

from monarchmoney import MonarchMoney
from monarchmoney.monarchmoney import _UNSET
from monarchmoney.read_api import ReadApiMixin
from monarchmoney.read_types import MerchantPaginationError

BASE = Path(__file__).resolve().parents[1]


class TestBaseline(unittest.TestCase):
    def test_all_method_signatures_match_171(self):
        expected = json.loads((BASE / "refactor_signature_baseline.json").read_text())
        actual = {
            name: re.sub(
                r"datetime\.datetime\(\d{4}, [^)]*\)",
                "datetime.datetime(<import-time>)",
                re.sub(
                    r"object at 0x[0-9a-f]+",
                    "object at <address>",
                    str(inspect.signature(getattr(MonarchMoney, name))),
                ),
            )
            for name in expected
        }
        self.assertEqual(actual, expected)
        self.assertTrue(set(expected) <= set(MonarchMoney.__dict__))

    def test_legacy_identities_and_sentinel(self):
        self.assertIs(ReadApiMixin, MonarchMoney)
        self.assertEqual(MerchantPaginationError.__module__, "monarchmoney.read_types")
        self.assertIs(
            inspect.signature(MonarchMoney.update_transaction_rule)
            .parameters["set_category_id"]
            .default,
            _UNSET,
        )
