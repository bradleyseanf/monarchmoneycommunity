from monarchmoney.read_types import JSONObject


from tests._fixtures import ReadFixture


class TestAccountsRead(ReadFixture):

    async def test_account_details_preserve_metadata_notes_and_snapshots(self) -> None:
        expected: JSONObject = {
            "account": {
                "id": "account-1",
                "notes": "Synthetic note",
                "hideInBudget": True,
                "useAvailableBalance": False,
                "deletedAt": None,
                "originalProviderData": {"apr": 0},
                "equityGrants": [{"id": "grant-1", "notes": "Synthetic grant"}],
            },
            "snapshotsForAccount": [{"date": "2026-01-01", "signedBalance": 0}],
        }
        self.execute.return_value = expected

        result = await self.client.get_account_details("account-1")

        self.assertIs(result, expected)
        query = self.assert_request("ExportAccountComplete", {"id": "account-1"})
        for field in (
            "notes",
            "originalProviderData",
            "equityGrants",
            "goalAllocations",
            "useAvailableBalance",
            "snapshotsForAccount",
            "deletedAt",
        ):
            self.assertIn(field, query)

    async def test_account_details_preserve_inaccessible_account(self) -> None:
        expected: JSONObject = {"account": None, "snapshotsForAccount": []}
        self.execute.return_value = expected

        result = await self.client.get_account_details(123)

        self.assertIs(result, expected)
        self.assert_request("ExportAccountComplete", {"id": "123"})

    async def test_account_history_keeps_existing_enriched_list_shape(self) -> None:
        self.execute.return_value = {
            "account": {
                "id": "123",
                "displayName": "Synthetic account",
                "notes": "Not returned",
            },
            "snapshots": [{"date": "2026-01-01", "signedBalance": 0}],
        }

        result = await self.client.get_account_history(123)

        self.assertEqual(
            result,
            [
                {
                    "date": "2026-01-01",
                    "signedBalance": 0,
                    "accountId": "123",
                    "accountName": "Synthetic account",
                }
            ],
        )

    async def test_account_roster_preserves_deleted_and_hidden_identities(self) -> None:
        expected: JSONObject = {
            "accounts": [
                {"id": "deleted-1", "deletedAt": "2026-01-01", "hideFromList": True},
            ]
        }
        self.execute.return_value = expected

        result = await self.client.get_account_roster()

        self.assertIs(result, expected)
        query = self.assert_request(
            "GetAccountRoster", {"includeDeleted": True, "includeHidden": True}
        )
        self.assertIn("includeDeleted: $includeDeleted", query)
        self.assertIn("includeHidden: $includeHidden", query)
        self.assertIn("deletedAt", query)

    async def test_account_roster_passes_false_flags(self) -> None:
        self.execute.return_value = {"accounts": []}

        await self.client.get_account_roster(
            include_deleted=False, include_hidden=False
        )

        self.assert_request(
            "GetAccountRoster", {"includeDeleted": False, "includeHidden": False}
        )
