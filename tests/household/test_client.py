from unittest.mock import patch

from gql import Client


from tests._fixtures import MonarchFixture


class TestHouseholdClient(MonarchFixture):

    @patch.object(Client, "execute_async")
    async def test_get_household_members(self, mock_execute_async):
        """
        Test the get_household_members method.
        """
        mock_execute_async.return_value = {
            "myHousehold": {
                "users": [
                    {
                        "id": "user-1",
                        "name": "Alex",
                        "displayName": "Alex",
                        "householdRole": "OWNER",
                    },
                    {
                        "id": "user-2",
                        "name": "Sam",
                        "displayName": "Sam",
                        "householdRole": "MEMBER",
                    },
                ]
            }
        }
        result = await self.monarch_money.get_household_members()
        mock_execute_async.assert_called_once()
        self.assertIsNotNone(result, "Expected result to not be None")
        users = result["myHousehold"]["users"]
        self.assertEqual(len(users), 2, "Expected 2 household members")
        self.assertEqual(users[0]["id"], "user-1")
        self.assertEqual(users[0]["name"], "Alex")
        self.assertEqual(users[0]["displayName"], "Alex")
        self.assertEqual(users[0]["householdRole"], "OWNER")
        self.assertEqual(users[1]["id"], "user-2")
        self.assertEqual(users[1]["householdRole"], "MEMBER")

    @patch.object(Client, "execute_async")
    async def test_get_household_members_empty(self, mock_execute_async):
        """
        Test the get_household_members method with no members.
        """
        mock_execute_async.return_value = {"myHousehold": {"users": []}}
        result = await self.monarch_money.get_household_members()
        mock_execute_async.assert_called_once()
        self.assertEqual(result["myHousehold"]["users"], [])
