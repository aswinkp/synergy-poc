from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from backend.exports import attachment_path, create_export


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.export_directory = Path(self.temp_directory.name) / "exports"
        self.path_patch = patch("backend.exports.EXPORTS_PATH", self.export_directory)
        self.path_patch.start()
        self.rows = [
            {"employee": "Alex", "assignments": 2, "note": "=SUM(1,1)"},
            {"employee": "Blair", "assignments": 1, "note": "Complete"},
        ]

    def tearDown(self):
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def test_csv_export_is_excel_friendly_and_formula_safe(self):
        attachment = create_export(self.rows, "Employee assignments", "csv")
        path = attachment_path(attachment)
        self.assertIsNotNone(path)
        self.assertTrue(path.is_file())
        self.assertEqual(attachment["row_count"], 2)
        self.assertEqual(path.read_bytes()[:3], b"\xef\xbb\xbf")

        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["employee"], "Alex")
        self.assertEqual(rows[0]["assignments"], "2")
        self.assertEqual(rows[0]["note"], "'=SUM(1,1)")

    def test_xlsx_export_has_headers_filters_and_safe_values(self):
        attachment = create_export(self.rows, "Employee assignments", "xlsx")
        path = attachment_path(attachment)
        self.assertIsNotNone(path)

        workbook = load_workbook(path, data_only=False)
        try:
            sheet = workbook.active
            self.assertEqual([cell.value for cell in sheet[1]], ["employee", "assignments", "note"])
            self.assertEqual(sheet.freeze_panes, "A2")
            self.assertEqual(sheet.auto_filter.ref, "A1:C3")
            self.assertEqual(sheet["C2"].value, "'=SUM(1,1)")
            self.assertEqual(sheet["C2"].data_type, "s")
        finally:
            workbook.close()


if __name__ == "__main__":
    unittest.main()
