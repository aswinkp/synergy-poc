from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from backend.schema import COLUMNS


TEST_RECORDS = [
    ("E001", "Alex", "Male", "2024-01-01", "alex@example.test", "Core", "Safety", "Completed"),
    ("E001", "Alex", "Male", "2024-01-01", "alex@example.test", "Core", "Security", "Not Started"),
    ("E002", "Blair", "Female", "2023-06-01", "blair@example.test", "Core", "Safety", "Completed"),
    ("E002", "Blair", "Female", "2023-06-01", "blair@example.test", "Core", "Security", "In Progress"),
    ("E003", "Casey", "Female", "2025-02-01", "casey@example.test", "Role", "Safety", "Not Started"),
    ("E003", "Casey", "Female", "2025-02-01", "casey@example.test", "Role", "Leadership", "Not Started"),
    ("E004", "Dev", "Male", "2022-03-01", "dev@example.test", "Role", "Safety", "Completed"),
    ("E004", "Dev", "Male", "2022-03-01", "dev@example.test", "Role", "Leadership", "Completed"),
    ("E005", "Emery", "Female", "2021-08-01", "emery@example.test", "Core", "Security", "Not Started"),
    ("E006", "Flynn", "Male", "2020-05-01", "flynn@example.test", "Role", "Leadership", "Completed"),
]


def create_test_workbook(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Learning Report"
    sheet.append(["Synthetic test workbook"])
    sheet.append([])
    sheet.append([])
    sheet.append([label for _, label, _ in COLUMNS])

    for seed in TEST_RECORDS:
        row = list(seed) + [None] * (len(COLUMNS) - len(seed))
        row[14] = "Test Company"
        row[15] = "Test Business Unit"
        row[19] = "Test Department"
        row[27] = "Test Manager"
        row[28] = "Active"
        sheet.append(row)

    workbook.save(path)
    return path
