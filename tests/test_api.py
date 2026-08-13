from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.query_engine import QueryPlan
from tests.fixtures import TEST_RECORDS, create_test_workbook


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        root = Path(cls.temp_directory.name)
        cls.workbook = create_test_workbook(root / "test.xlsx")
        cls.database_patch = patch("backend.database.DATABASE_PATH", root / "test.db")
        cls.workbook_patch = patch("backend.main.find_workbook", return_value=cls.workbook)
        cls.database_patch.start()
        cls.workbook_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.workbook_patch.stop()
        cls.database_patch.stop()
        cls.temp_directory.cleanup()

    def test_chat_lifecycle(self):
        plan = QueryPlan(
            "SELECT ROUND(100.0 * SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) / COUNT(*), 1) AS value FROM learning_records",
            "answer",
            "Completion rate",
        )
        with TestClient(app) as client, patch("backend.query_engine._plan_with_openrouter", return_value=plan):
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["records"], len(TEST_RECORDS))

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


if __name__ == "__main__":
    unittest.main()
