from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.database import initialize_database
from backend.query_engine import (
    QueryError,
    QueryPlan,
    _answer_from_rows,
    _conversation_context,
    _execute,
    _explicit_chart_type,
    _openrouter_client,
    _plan_with_openrouter,
    _planner_prompt,
    _read_only_authorizer,
    _summarize_with_openrouter,
    _validate_sql,
    answer_question,
)
from tests.fixtures import TEST_RECORDS, create_test_workbook


class QueryEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        root = Path(cls.temp_directory.name)
        cls.database_patch = patch("backend.database.DATABASE_PATH", root / "test.db")
        cls.database_patch.start()
        initialize_database(create_test_workbook(root / "test.xlsx"))

    @classmethod
    def tearDownClass(cls):
        cls.database_patch.stop()
        cls.temp_directory.cleanup()

    def test_unique_employee_count(self):
        plan = QueryPlan(
            "SELECT COUNT(DISTINCT employee_id) AS value FROM learning_records",
            "answer",
            "Unique employees",
        )
        with patch("backend.query_engine._plan_with_openrouter", return_value=plan):
            result = answer_question("How many unique employees are there?")
        self.assertEqual(result["content"], "6")

    def test_status_pie_chart(self):
        plan = QueryPlan(
            "SELECT status AS label, COUNT(*) AS value FROM learning_records GROUP BY status ORDER BY value DESC",
            "chart",
            "Learning status",
            "pie",
        )
        with (
            patch("backend.query_engine._plan_with_openrouter", return_value=plan),
            patch("backend.query_engine._summarize_with_openrouter", return_value="Most assignments have not started."),
        ):
            result = answer_question("Show status as a pie chart")
        chart = result["visualization"]
        self.assertEqual(chart["type"], "pie")
        self.assertEqual(sum(item["value"] for item in chart["data"]), len(TEST_RECORDS))

    def test_mutating_sql_is_rejected(self):
        with self.assertRaises(QueryError):
            _validate_sql("DROP TABLE learning_records")

    def test_harmless_action_label_is_not_treated_as_mutation(self):
        sql = "SELECT 'Create a recovery plan' AS action FROM learning_records LIMIT 1"
        self.assertEqual(_validate_sql(sql), sql)

    def test_multiple_statements_are_rejected_but_semicolon_in_text_is_allowed(self):
        allowed = "SELECT 'Start; then complete' AS action FROM learning_records LIMIT 1"
        self.assertEqual(_validate_sql(allowed), allowed)
        with self.assertRaises(QueryError):
            _validate_sql("SELECT * FROM learning_records; DROP TABLE learning_records")

    def test_database_authorizer_denies_writes(self):
        self.assertEqual(
            _read_only_authorizer(sqlite3.SQLITE_DELETE, None, None, None, None),
            sqlite3.SQLITE_DENY,
        )

    def test_openrouter_client_has_no_timeout(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            client = _openrouter_client()
        self.assertIsNone(client.timeout)

    def test_openrouter_uses_high_reasoning_for_planning_and_synthesis(self):
        create = MagicMock()
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "sql": "SELECT COUNT(*) AS value FROM learning_records",
                                "mode": "answer",
                                "title": "Records",
                                "chart_type": None,
                                "explanation": "Count all records.",
                            }
                        )
                    )
                )
            ]
        )
        with patch("backend.query_engine._openrouter_client", return_value=client):
            plan = _plan_with_openrouter("How many records are there?")
        self.assertEqual(create.call_args.kwargs["extra_body"], {"reasoning": {"effort": "high"}})

        create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="There are 7,206 records."))]
        )
        with patch("backend.query_engine._openrouter_client", return_value=client):
            _summarize_with_openrouter(
                "Summarize the records",
                plan,
                [{"label": "All", "value": 7206}],
            )
        self.assertEqual(create.call_args.kwargs["extra_body"], {"reasoning": {"effort": "high"}})
        system_prompt = create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("plain text only", system_prompt)

    def test_context_and_query_results_are_not_truncated(self):
        history = [
            {"role": "user" if index % 2 == 0 else "assistant", "content": f"{index}:" + "x" * 900}
            for index in range(12)
        ]
        context = json.loads(_conversation_context(history))
        self.assertEqual(context, history)
        self.assertNotIn("at most 50 rows", _planner_prompt("Show every record", history))
        self.assertEqual(len(_execute("SELECT employee_id FROM learning_records")), len(TEST_RECORDS))

    def test_generic_chart_request_is_left_for_the_model_to_choose(self):
        self.assertIsNone(_explicit_chart_type("Visualize completion status in the best chart"))

    def test_query_repairs_are_not_limited_to_one_retry(self):
        invalid = QueryPlan("SELECT missing_column FROM learning_records", "answer", "Broken")
        valid = QueryPlan("SELECT COUNT(*) AS value FROM learning_records", "answer", "Records")
        with patch(
            "backend.query_engine._plan_with_openrouter",
            side_effect=[invalid, invalid, valid],
        ) as planner:
            result = answer_question("How many records are there?")
        self.assertEqual(result["content"], "10")
        self.assertEqual(planner.call_count, 3)

    def test_advisory_questions_use_model_plan_and_model_answer(self):
        question = "I'm the manager. Find patterns and give me actionable tasks to improve my KPI."
        plan = QueryPlan(
            "SELECT status AS label, COUNT(*) AS value FROM learning_records GROUP BY status",
            "table",
            "Management analysis",
        )
        with (
            patch("backend.query_engine._plan_with_openrouter", return_value=plan) as planner,
            patch("backend.query_engine._summarize_with_openrouter", return_value="Model-generated action plan.") as summarizer,
        ):
            result = answer_question(question)
        self.assertEqual(result["content"], "Model-generated action plan.")
        planner.assert_called_once_with(question, None)
        summarizer.assert_called_once()

    def test_tables_receive_model_synthesis(self):
        plan = QueryPlan("SELECT 1 FROM learning_records", "table", "Status summary")
        rows = [{"label": "Not Started", "value": 5172}, {"label": "Completed", "value": 1886}]
        with patch("backend.query_engine._summarize_with_openrouter", return_value="Prioritize the Not Started backlog."):
            answer = _answer_from_rows("What should I know?", plan, rows)
        self.assertEqual(answer, "Prioritize the Not Started backlog.")

    def test_follow_up_context_is_passed_to_model(self):
        history = [
            {"role": "user", "content": "How many unique employees are in this report?"},
            {"role": "assistant", "content": "2,474"},
        ]
        plan = QueryPlan(
            "SELECT status AS label, COUNT(DISTINCT employee_id) AS value FROM learning_records GROUP BY status",
            "chart",
            "Employee learning status",
            "pie",
        )
        with (
            patch("backend.query_engine._plan_with_openrouter", return_value=plan) as planner,
            patch("backend.query_engine._summarize_with_openrouter", return_value="Employee status breakdown."),
        ):
            result = answer_question("Show their status breakdown as a pie chart", history=history)
        planner.assert_called_once_with("Show their status breakdown as a pie chart", history)
        chart = result["visualization"]
        values = {row["label"]: row["value"] for row in chart["data"]}
        self.assertEqual(values["Completed"], 4)


if __name__ == "__main__":
    unittest.main()
