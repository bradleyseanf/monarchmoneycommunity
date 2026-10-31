from monarchmoney.read_types import JSONObject


from tests._fixtures import ReadFixture


class TestActivityRead(ReadFixture):

    async def test_activity_page_preserves_cursor_and_unread_state(self) -> None:
        expected: JSONObject = {
            "activityEvents": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [{"node": {"id": "event-1", "readAt": None, "eventData": {}}}],
            }
        }
        self.execute.return_value = expected

        result = await self.client.get_activity_events(25, "prior-event", [])

        self.assertIs(result, expected)
        query = self.assert_request(
            "Common_GetNotificationCenter",
            {
                "first": 25,
                "afterCursor": "prior-event",
                "excludeEventTypes": [],
            },
        )
        for field in (
            "pageInfo",
            "hasNextPage",
            "endCursor",
            "readAt",
            "dismissedAt",
            "eventData",
        ):
            self.assertIn(field, query)
        self.assertNotIn("mutation", query)
