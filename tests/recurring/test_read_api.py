from monarchmoney.read_types import JSONObject


from tests._fixtures import ReadFixture


class TestRecurringRead(ReadFixture):

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
