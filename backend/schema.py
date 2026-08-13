from __future__ import annotations

# Explicit names avoid losing either of the two Excel columns named "Category".
COLUMNS: list[tuple[str, str, str]] = [
    ("employee_id", "Employee ID", "TEXT"),
    ("employee_name", "Employee Name", "TEXT"),
    ("gender", "Gender", "TEXT"),
    ("date_of_joining", "Date Of Joining", "TEXT"),
    ("email_id", "Email ID", "TEXT"),
    ("learning_category", "Learning Category", "TEXT"),
    ("course_name", "Course Name", "TEXT"),
    ("status", "Status", "TEXT"),
    ("start_date", "Start Date", "TEXT"),
    ("completed_date", "Completed Date", "TEXT"),
    ("overdue", "Overdue", "INTEGER"),
    ("duration", "Duration", "TEXT"),
    ("refresher_course", "Refresher Course", "TEXT"),
    ("certificate", "Certificate", "TEXT"),
    ("company", "Company", "TEXT"),
    ("business_unit", "Business Unit", "TEXT"),
    ("synergy_division", "Synergy Division", "TEXT"),
    ("job_level", "Job Level", "TEXT"),
    ("functional_area", "Functional Area", "TEXT"),
    ("current_department", "Current Department", "TEXT"),
    ("contribution_level", "Contribution Level", "TEXT"),
    ("designation", "Designation", "TEXT"),
    ("current_office_area", "Current Office Area", "TEXT"),
    ("employee_category", "Employee Category", "TEXT"),
    ("tmsa_type", "TMSA Type", "TEXT"),
    ("tmsa_guidelines", "TMSA Guidelines", "TEXT"),
    ("manager_id", "Manager ID", "TEXT"),
    ("manager_name", "Manager Name", "TEXT"),
    ("active_status", "Active Status", "TEXT"),
    ("lwd", "LWD", "TEXT"),
]

COLUMN_LABELS = {name: label for name, label, _ in COLUMNS}

SCHEMA_PROMPT = "\n".join(f"- {name}: {label}" for name, label, _ in COLUMNS)
