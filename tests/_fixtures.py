import json
import os
import pickle
import unittest
from monarchmoney import MonarchMoney


class MonarchFixture(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """
        Set up any necessary data or variables for the tests here.
        This method will be called before each test method is executed.
        """
        with open("temp_session.pickle", "wb") as fh:
            session_data = {
                "cookies": {"test_cookie": "test_value"},
                "token": "test_token",
            }
            pickle.dump(session_data, fh)
        self.monarch_money = MonarchMoney()
        self.monarch_money.load_session("temp_session.pickle")

    @classmethod
    def loadTestData(cls, filename) -> dict:
        filename = f"{os.path.dirname(os.path.realpath(__file__))}/{filename}"
        with open(filename, "r") as file:
            return json.load(file)

    def tearDown(self):
        """
        Tear down any necessary data or variables for the tests here.
        This method will be called after each test method is executed.
        """
        self.monarch_money.delete_session("temp_session.pickle")


from unittest.mock import AsyncMock, patch
from gql import Client
from graphql import print_ast
from monarchmoney.read_types import JSONObject


class ReadFixture(unittest.IsolatedAsyncioTestCase):

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.client: MonarchMoney = MonarchMoney()
        self.execute: AsyncMock = AsyncMock()

    def setUp(self) -> None:
        patcher = patch.object(Client, "execute_async", self.execute)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_request(self, operation: str, variables: JSONObject) -> str:
        self.execute.assert_awaited_once()
        awaited = self.execute.await_args
        assert awaited is not None
        kwargs = awaited.kwargs
        self.assertEqual(kwargs["operation_name"], operation)
        self.assertEqual(kwargs["variable_values"], variables)
        return print_ast(kwargs["request"].document)
