from __future__ import annotations

import argparse
import getpass
import sqlite3
import uuid

from .auth import hash_password
from .database import _create_application_tables, connect, utc_now


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Enter a valid email address.")
    return normalized


def create_user(
    email: str,
    name: str,
    password: str,
    *,
    claim_existing_chats: bool = False,
) -> dict[str, str]:
    normalized_email = normalize_email(email)
    normalized_name = " ".join(name.split())
    if not normalized_name:
        raise ValueError("Name is required.")
    user_id = str(uuid.uuid4())
    now = utc_now()
    with connect() as db:
        _create_application_tables(db)
        try:
            db.execute(
                "INSERT INTO users(id, email, name, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, normalized_email, normalized_name, hash_password(password), now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"A user with email {normalized_email} already exists.") from exc
        if claim_existing_chats:
            db.execute("UPDATE chats SET user_id = ? WHERE user_id IS NULL", (user_id,))
    return {"id": user_id, "email": normalized_email, "name": normalized_name}


def set_password(email: str, password: str) -> None:
    normalized_email = normalize_email(email)
    with connect() as db:
        cursor = db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE email = ? COLLATE NOCASE",
            (hash_password(password), utc_now(), normalized_email),
        )
        if not cursor.rowcount:
            raise ValueError(f"No user exists with email {normalized_email}.")


def set_active(email: str, active: bool) -> None:
    normalized_email = normalize_email(email)
    with connect() as db:
        cursor = db.execute(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE email = ? COLLATE NOCASE",
            (int(active), utc_now(), normalized_email),
        )
        if not cursor.rowcount:
            raise ValueError(f"No user exists with email {normalized_email}.")


def list_users() -> list[dict[str, str | bool]]:
    with connect() as db:
        _create_application_tables(db)
        rows = db.execute("SELECT id, email, name, is_active FROM users ORDER BY email").fetchall()
    return [
        {"id": row["id"], "email": row["email"], "name": row["name"], "is_active": bool(row["is_active"])}
        for row in rows
    ]


def _prompt_password() -> str:
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision Synergy users directly in SQLite.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a user")
    add_parser.add_argument("--email", required=True)
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--claim-existing-chats", action="store_true")

    password_parser = subparsers.add_parser("set-password", help="Replace a user's password")
    password_parser.add_argument("--email", required=True)

    for command in ("activate", "deactivate"):
        command_parser = subparsers.add_parser(command, help=f"{command.title()} a user")
        command_parser.add_argument("--email", required=True)

    subparsers.add_parser("list", help="List provisioned users")
    args = parser.parse_args()

    try:
        if args.command == "add":
            user = create_user(
                args.email,
                args.name,
                _prompt_password(),
                claim_existing_chats=args.claim_existing_chats,
            )
            print(f"Created {user['email']} ({user['id']}).")
        elif args.command == "set-password":
            set_password(args.email, _prompt_password())
            print(f"Updated password for {normalize_email(args.email)}.")
        elif args.command in {"activate", "deactivate"}:
            set_active(args.email, args.command == "activate")
            print(f"{args.command.title()}d {normalize_email(args.email)}.")
        else:
            for user in list_users():
                status = "active" if user["is_active"] else "inactive"
                print(f"{user['email']}\t{user['name']}\t{status}")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
