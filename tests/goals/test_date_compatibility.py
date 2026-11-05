import unittest
from datetime import datetime
from unittest.mock import patch

from monarchmoney import MonarchMoney


class FrozenDateTime(datetime):
    @classmethod
    def now(cls):
        return cls(2026, 2, 15, 12, 0)


class TestDateCompatibility(unittest.TestCase):
    def test_facade_datetime_patch_reaches_goal_helpers(self):
        client = MonarchMoney()
        with patch("monarchmoney.monarchmoney.datetime", FrozenDateTime):
            self.assertEqual(client._get_current_date(), "2026-02-15")
            self.assertEqual(client._get_start_of_current_month(), "2026-02-01")
            self.assertEqual(client._get_end_of_current_month(), "2026-02-28")
