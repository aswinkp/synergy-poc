from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from backend.schema import COLUMNS, HEADCOUNT_COLUMNS


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

TEST_HEADCOUNT_PROFILES = [
    ("E001", "Alex", "Male", "Millennials", 32, "Individual contributor"),
    ("E002", "Blair", "Female", "Millennials", 35, "People manager"),
    ("E003", "Casey", "Female", "Gen Z", 27, "Individual contributor"),
    ("E004", "Dev", "Male", "Gen X", 44, "People manager"),
    ("E005", "Emery", "Female", "Gen X", 46, "Individual contributor"),
    ("E006", "Flynn", "Male", "Gen X", 48, "Individual contributor"),
    ("E007", "Gray", "Non-binary", "Gen Z", 25, "Individual contributor"),
]


def create_test_workbook(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Learning Report"
    sheet.append(["Synthetic test workbook"])
    sheet.append([])
    sheet.append([])
    headers = [label for _, label, _ in COLUMNS]
    headers[5] = "Category"
    headers[23] = "Category"
    sheet.append(headers)

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


def create_test_headcount_workbook(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Headcount"
    sheet.append([label for _, label, _ in HEADCOUNT_COLUMNS])
    indexes = {name: index for index, (name, _, _) in enumerate(HEADCOUNT_COLUMNS)}

    for employee_id, name, gender, generation, age, role_type in TEST_HEADCOUNT_PROFILES:
        row = [None] * len(HEADCOUNT_COLUMNS)
        values = {
            "employee_id": employee_id,
            "employee_name": name,
            "company": "Test Company",
            "business_unit": "Test Business Unit",
            "synergy_division": "Test Division",
            "functional_area": "Test Function",
            "current_department": "Test Department",
            "employee_category": "Employee",
            "contribution_level": "Individual",
            "job_level": "L2",
            "designation": "Specialist",
            "manager_id": "M001",
            "manager_name": "Test Manager",
            "employment_status": "Permanent",
            "effective_from": "2026-01-01",
            "email_id": f"{employee_id.casefold()}@example.test",
            "gender": gender,
            "date_of_joining": "2024-01-01",
            "generation": generation,
            "age": age,
            "role_type": role_type,
            "active_status": "Active",
        }
        for key, value in values.items():
            row[indexes[key]] = value
        sheet.append(row)

        if employee_id == "E002":
            duplicate = row.copy()
            duplicate[indexes["manager_id"]] = "M002"
            duplicate[indexes["manager_name"]] = "Alternate Manager"
            sheet.append(duplicate)

    workbook.save(path)
    return path
