from monarchmoney.read_types import JSONObject


from tests._fixtures import ReadFixture


class TestTransactionsRead(ReadFixture):

    async def test_retail_page_preserves_cursor_filters_items_and_order(self) -> None:
        filters: JSONObject = {"search": "synthetic"}
        expected: JSONObject = {
            "retailTransactionsConnection": {
                "pageInfo": {"hasNextPage": True, "endCursor": "next-retail"},
                "edges": [
                    {
                        "node": {
                            "id": "retail-1",
                            "lineItems": [{"id": "item-1", "category": None}],
                            "retailOrder": {"id": "order-1", "grandTotal": 0},
                        }
                    }
                ],
            }
        }
        self.execute.return_value = expected

        result = await self.client.get_retail_transactions(25, "prior-retail", filters)

        self.assertIs(result, expected)
        query = self.assert_request(
            "Common_RetailTransactionsConnection",
            {
                "first": 25,
                "afterCursor": "prior-retail",
                "filters": filters,
            },
        )
        for field in (
            "pageInfo",
            "hasNextPage",
            "endCursor",
            "lineItems",
            "retailOrder",
            "splitTransactions",
            "category",
            "vendorOrderId",
        ):
            self.assertIn(field, query)
        self.assertEqual(filters, {"search": "synthetic"})
