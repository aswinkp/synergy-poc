from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.auth import authenticate_user
from backend.database import _create_application_tables, connect, utc_now
from backend.users import create_user, set_active, set_password


class UserProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_patch = patch(
            "backend.database.DATABASE_PATH",
            Path(self.temp_directory.name) / "users.db",
        )
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.temp_directory.cleanup()

    def test_user_is_created_with_argon2_hash_and_can_authenticate(self):
        user = create_user(
            "Analyst@Example.Test",
            "Test Analyst",
            "correct-horse-battery-staple",
        )
        self.assertEqual(user["email"], "analyst@example.test")
        with connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        self.assertTrue(row["password_hash"].startswith("$argon2"))
        self.assertNotIn("correct-horse", row["password_hash"])
        self.assertEqual(
            authenticate_user("analyst@example.test", "correct-horse-battery-staple").id,
            user["id"],
        )
        self.assertIsNone(authenticate_user("analyst@example.test", "wrong-password"))

    def test_password_changes_and_inactive_users_cannot_login(self):
        create_user("analyst@example.test", "Test Analyst", "first-secure-password")
        set_password("analyst@example.test", "second-secure-password")
        self.assertIsNone(authenticate_user("analyst@example.test", "first-secure-password"))
        self.assertIsNotNone(authenticate_user("analyst@example.test", "second-secure-password"))
        set_active("analyst@example.test", False)
        self.assertIsNone(authenticate_user("analyst@example.test", "second-secure-password"))

    def test_short_passwords_and_duplicate_emails_are_rejected(self):
        with self.assertRaises(ValueError):
            create_user("analyst@example.test", "Test Analyst", "too-short")
        create_user("analyst@example.test", "Test Analyst", "long-enough-password")
        with self.assertRaises(ValueError):
            create_user("ANALYST@example.test", "Duplicate", "another-long-password")

    def test_existing_chats_are_claimed_only_when_explicitly_requested(self):
        now = utc_now()
        with connect() as db:
            _create_application_tables(db)
            db.execute(
                "INSERT INTO chats(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("legacy-chat", "Legacy", now, now),
            )
        user = create_user(
            "owner@example.test",
            "Legacy Owner",
            "long-enough-password",
            claim_existing_chats=True,
        )
        with connect() as db:
            owner_id = db.execute(
                "SELECT user_id FROM chats WHERE id = 'legacy-chat'"
            ).fetchone()["user_id"]
        self.assertEqual(owner_id, user["id"])


if __name__ == "__main__":
    unittest.main()
