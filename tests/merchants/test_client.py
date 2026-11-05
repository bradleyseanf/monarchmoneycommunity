from unittest.mock import patch

from gql import Client


from tests._fixtures import MonarchFixture


class TestMerchantsClient(MonarchFixture):

    @patch.object(Client, "execute_async")
    async def test_delete_merchant_same_id_raises(self, mock_execute_async):
        """
        delete_merchant refuses to merge a merchant into itself.
        """

        with self.assertRaises(ValueError):
            await self.monarch_money.delete_merchant(
                "170000000000000001", move_to_merchant_id="170000000000000001"
            )

        mock_execute_async.assert_not_called()
