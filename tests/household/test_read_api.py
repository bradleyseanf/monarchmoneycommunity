from tests._fixtures import ReadFixture


class TestHouseholdRead(ReadFixture):

    async def test_profile_household_and_reports_preserve_selected_objects(
        self,
    ) -> None:
        cases = (
            (
                "get_user_profile",
                "Common_GetMe",
                {"me": {"profile": {"webUiThemePreference": None}}},
                (
                    "UserFields",
                    "mobileUiThemePreference",
                    "activeSupportAccountAccessGrant",
                ),
            ),
            (
                "get_household_preferences",
                "Common_GetHouseholdPreferences",
                {
                    "householdPreferences": {"aiAssistantEnabled": False},
                    "budgetSystem": None,
                    "insightTopics": [],
                },
                (
                    "HouseholdPreferencesFields",
                    "HouseholdBudgetSettingsFields",
                    "disabledInsightTopics",
                ),
            ),
            (
                "get_report_configurations",
                "Common_GetReportConfigurations",
                {
                    "reportConfigurations": [
                        {"id": "report-1", "transactionFilterSet": {}, "reportView": {}}
                    ]
                },
                (
                    "ownershipSet",
                    "businessEntitySet",
                    "excludedSavingsGoals",
                    "chartCalculation",
                    "timeframePeriod",
                ),
            ),
        )
        for method_name, operation, expected, fields in cases:
            with self.subTest(method=method_name):
                self.execute.reset_mock()
                self.execute.return_value = expected

                result = await getattr(self.client, method_name)()

                self.assertIs(result, expected)
                query = self.assert_request(operation, {})
                for field in fields:
                    self.assertIn(field, query)
