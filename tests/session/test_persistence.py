import tempfile
import unittest
from pathlib import Path

from monarchmoney import LoginFailedException, MonarchMoney


class TestSessionPersistence(unittest.TestCase):
    def test_cookie_session_round_trip_and_delete(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / "nested" / "session.pickle"
            original = MonarchMoney(token="old-token", session_file=str(path))
            original.set_cookies({"session_id": "session", "csrftoken": "csrf"})
            original.save_session()

            restored = MonarchMoney(session_file=str(path))
            restored.load_session()
            self.assertEqual(restored._auth_mode, "cookie")
            self.assertEqual(restored._cookies["session_id"], "session")
            self.assertEqual(restored._headers["X-Csrftoken"], "csrf")
            self.assertNotIn("Authorization", restored._headers)
            restored.delete_session()
            self.assertFalse(path.exists())

    def test_features_jwt_is_rejected_before_creating_file(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / "session.pickle"
            client = MonarchMoney(
                token="header.payload.signature", session_file=str(path)
            )
            with self.assertRaises(LoginFailedException):
                client.save_session()
            self.assertFalse(path.exists())
