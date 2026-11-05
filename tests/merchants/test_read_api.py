from monarchmoney.read_types import JSONObject


from tests._fixtures import ReadFixture


class TestMerchantsRead(ReadFixture):

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

    async def test_negative_merchant_offset_is_rejected_before_requests(self) -> None:
        with self.assertRaises(ValueError):
            await self.client.get_merchants(offset=-1)
        self.execute.assert_not_awaited()
