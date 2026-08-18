from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.database import initialize_database
from backend.main import _resolve_frontend_file, app
from backend.query_engine import QueryPlan
from backend.users import create_user
from tests.fixtures import TEST_RECORDS, create_test_headcount_workbook, create_test_workbook


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        root = Path(cls.temp_directory.name)
        cls.root = root
        cls.workbook = create_test_workbook(root / "test.xlsx")
        cls.headcount_workbook = create_test_headcount_workbook(root / "headcount.xlsx")
        cls.database_patch = patch("backend.database.DATABASE_PATH", root / "test.db")
        cls.workbook_patch = patch("backend.main.find_workbook", return_value=cls.workbook)
        cls.headcount_patch = patch(
            "backend.main.find_headcount_workbook",
            return_value=cls.headcount_workbook,
        )
        cls.database_patch.start()
        cls.workbook_patch.start()
        cls.headcount_patch.start()
        initialize_database(cls.workbook, cls.headcount_workbook)
        cls.email = "analyst@example.test"
        cls.password = "correct-horse-battery-staple"
        create_user(cls.email, "Test Analyst", cls.password)
        cls.second_email = "second@example.test"
        cls.second_password = "another-correct-password"
        create_user(cls.second_email, "Second Analyst", cls.second_password)

    @classmethod
    def tearDownClass(cls):
        cls.headcount_patch.stop()
        cls.workbook_patch.stop()
        cls.database_patch.stop()
        cls.temp_directory.cleanup()

    def login(self, client: TestClient, *, second_user: bool = False):
        response = client.post(
            "/api/auth/login",
            json={
                "email": self.second_email if second_user else self.email,
                "password": self.second_password if second_user else self.password,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_authentication_flow_and_no_signup(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/healthz").json(), {"status": "ok"})
            self.assertEqual(client.get("/api/health").status_code, 401)
            self.assertEqual(client.get("/api/chats").status_code, 401)
            self.assertEqual(
                client.post(
                    "/api/auth/login",
                    json={"email": self.email, "password": "wrong-password"},
                ).status_code,
                401,
            )
            login = self.login(client)
            cookie = login.headers["set-cookie"]
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=strict", cookie)
            self.assertNotIn(self.password, cookie)
            self.assertEqual(client.get("/api/auth/me").json()["email"], self.email)
            self.assertEqual(client.post("/api/auth/register", json={}).status_code, 405)
            self.assertEqual(client.post("/api/auth/logout").status_code, 204)
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            client.cookies.set("synergy_session", "invalid-token", path="/api")
            self.assertEqual(client.get("/api/auth/me").status_code, 401)

    def test_frontend_file_resolution_cannot_escape_distribution_directory(self):
        with self.assertRaises(HTTPException) as context:
            _resolve_frontend_file("../../requirements.txt")
        self.assertEqual(context.exception.status_code, 404)
        self.assertIsNone(_resolve_frontend_file("missing-client-route"))

    def test_chat_lifecycle(self):
        plan = QueryPlan(
            "SELECT ROUND(100.0 * SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) / COUNT(*), 1) AS value FROM learning_records",
            "answer",
            "Completion rate",
        )
        with TestClient(app) as client, patch("backend.query_engine._plan_with_openrouter", return_value=plan):
            self.login(client)
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["records"], len(TEST_RECORDS))
            self.assertEqual(health.json()["headcount_records"], 8)
            self.assertEqual(health.json()["headcount_employees"], 7)

            answer = client.post("/api/chat", json={"message": "What is the completion rate?"})
            self.assertEqual(answer.status_code, 200)
            payload = answer.json()
            self.assertEqual(payload["message"]["content"], "50.0%")

            chat_id = payload["chat_id"]
            loaded = client.get(f"/api/chats/{chat_id}")
            self.assertEqual(len(loaded.json()["messages"]), 2)

            deleted = client.delete(f"/api/chats/{chat_id}")
            self.assertEqual(deleted.status_code, 204)

    def test_follow_up_receives_conversation_history(self):
        first_result = {"content": "2,474", "visualization": None, "debug": None}
        with TestClient(app) as client, patch("backend.main.answer_question", return_value=first_result):
            self.login(client)
            first = client.post("/api/chat", json={"message": "How many unique employees are there?"}).json()
            chat_id = first["chat_id"]
            fake_result = {"content": "Context received.", "visualization": None, "debug": None}
            with patch("backend.main.answer_question", return_value=fake_result) as mocked:
                follow_up = client.post(
                    "/api/chat",
                    json={"chat_id": chat_id, "message": "How many of those completed training?"},
                )
            self.assertEqual(follow_up.status_code, 200)
            history = mocked.call_args.kwargs["history"]
            self.assertEqual(history[0]["content"], "How many unique employees are there?")
            self.assertEqual(history[1]["role"], "assistant")
            client.delete(f"/api/chats/{chat_id}")

    def test_long_questions_and_complete_history_are_preserved(self):
        fake_result = {"content": "Recorded.", "visualization": None, "debug": None}
        long_question = "Explain this fully: " + "x" * 2500
        with TestClient(app) as client, patch("backend.main.answer_question", return_value=fake_result) as mocked:
            self.login(client)
            first = client.post("/api/chat", json={"message": long_question})
            self.assertEqual(first.status_code, 200)
            chat_id = first.json()["chat_id"]
            self.assertEqual(mocked.call_args.args[0], long_question)

            for index in range(5):
                client.post("/api/chat", json={"chat_id": chat_id, "message": f"Follow-up {index}"})

            loaded = client.get(f"/api/chats/{chat_id}").json()
            self.assertEqual(loaded["title"], long_question)
            self.assertEqual(len(mocked.call_args.kwargs["history"]), 10)
            self.assertEqual(mocked.call_args.kwargs["history"][0]["content"], long_question)
            client.delete(f"/api/chats/{chat_id}")

    def test_csv_attachment_is_persisted_downloadable_and_removed_with_chat(self):
        plan = QueryPlan(
            "SELECT status, COUNT(*) AS assignments FROM learning_records GROUP BY status ORDER BY status",
            "table",
            "Learning status",
        )
        export_directory = self.root / "exports"
        with (
            TestClient(app) as client,
            patch("backend.query_engine._plan_with_openrouter", return_value=plan),
            patch("backend.query_engine._summarize_with_openrouter", return_value="The export is ready."),
            patch("backend.exports.EXPORTS_PATH", export_directory),
        ):
            self.login(client)
            response = client.post(
                "/api/chat",
                json={"message": "Show status and download it as CSV"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            attachment = payload["message"]["attachment"]
            self.assertEqual(attachment["format"], "csv")
            self.assertEqual(attachment["row_count"], 3)

            download = client.get(attachment["url"])
            self.assertEqual(download.status_code, 200)
            self.assertIn("text/csv", download.headers["content-type"])
            self.assertIn(attachment["filename"], download.headers["content-disposition"])

            chat_id = payload["chat_id"]
            loaded = client.get(f"/api/chats/{chat_id}").json()
            self.assertEqual(loaded["messages"][-1]["attachment"]["id"], attachment["id"])
            path = export_directory / f'{attachment["id"]}.csv'
            self.assertTrue(path.is_file())

            client.delete(f"/api/chats/{chat_id}")
            self.assertFalse(path.exists())
            self.assertEqual(client.get(attachment["url"]).status_code, 404)

    def test_chats_are_private_to_their_owner(self):
        fake_result = {"content": "Private answer.", "visualization": None, "debug": None}
        with TestClient(app) as owner, patch("backend.main.answer_question", return_value=fake_result):
            self.login(owner)
            created = owner.post("/api/chat", json={"message": "Private question"}).json()
            chat_id = created["chat_id"]

            with TestClient(app) as other_user:
                self.login(other_user, second_user=True)
                self.assertNotIn(chat_id, {chat["id"] for chat in other_user.get("/api/chats").json()})
                self.assertEqual(other_user.get(f"/api/chats/{chat_id}").status_code, 404)
                self.assertEqual(
                    other_user.post(
                        "/api/chat",
                        json={"chat_id": chat_id, "message": "Try to access it"},
                    ).status_code,
                    404,
                )
            owner.delete(f"/api/chats/{chat_id}")


if __name__ == "__main__":
    unittest.main()
