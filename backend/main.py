from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    AuthenticatedUser,
    CurrentUser,
    authenticate_user,
    clear_session_cookie,
    public_user,
    set_session_cookie,
    validate_auth_configuration,
)
from .agent_review import executive_review_events
from .config import ROOT, find_headcount_workbook, find_workbook
from .database import connect, initialize_database, load_attachment, load_visualization, utc_now
from .exports import attachment_path
from .query_engine import QueryError, answer_question

APP_STATE: dict[str, object] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_auth_configuration()
    workbook = find_workbook()
    headcount_workbook = find_headcount_workbook()
    APP_STATE.update(initialize_database(workbook, headcount_workbook))
    APP_STATE["workbook"] = workbook.name
    APP_STATE["headcount_workbook"] = headcount_workbook.name if headcount_workbook else None
    yield


app = FastAPI(title="Synergy Learning Intelligence", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    chat_id: str | None = None
    message: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=4096)


def _chat_row(row) -> dict:
    return {"id": row["id"], "title": row["title"], "created_at": row["created_at"], "updated_at": row["updated_at"]}


def _message_row(row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "visualization": load_visualization(row["visualization"]),
        "attachment": load_attachment(row["attachment"]),
        "created_at": row["created_at"],
    }


def _chat_title(message: str) -> str:
    return " ".join(message.split())


def _start_chat_message(
    request: ChatRequest,
    user: AuthenticatedUser,
) -> tuple[str, list[dict[str, str]]]:
    chat_id = request.chat_id or str(uuid.uuid4())
    now = utc_now()
    message = request.message.strip()
    with connect() as db:
        chat = db.execute(
            "SELECT * FROM chats WHERE id = ? AND user_id = ?",
            (chat_id, user.id),
        ).fetchone()
        if not chat:
            if request.chat_id:
                raise HTTPException(status_code=404, detail="Chat not found")
            db.execute(
                "INSERT INTO chats(id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user.id, _chat_title(message), now, now),
            )
        elif chat["title"] == "New analysis":
            db.execute(
                "UPDATE chats SET title = ? WHERE id = ? AND user_id = ?",
                (_chat_title(message), chat_id, user.id),
            )
        history_rows = db.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at",
            (chat_id,),
        ).fetchall()
        history = [
            {"role": row["role"], "content": row["content"]}
            for row in history_rows
        ]
        db.execute(
            "INSERT INTO messages(id, chat_id, role, content, created_at) VALUES (?, ?, 'user', ?, ?)",
            (str(uuid.uuid4()), chat_id, message, now),
        )
    return chat_id, history


def _persist_assistant_result(
    chat_id: str,
    user: AuthenticatedUser,
    result: dict,
) -> dict:
    assistant_id = str(uuid.uuid4())
    answered_at = utc_now()
    with connect() as db:
        db.execute(
            "INSERT INTO messages(id, chat_id, role, content, visualization, attachment, created_at) VALUES (?, ?, 'assistant', ?, ?, ?, ?)",
            (
                assistant_id,
                chat_id,
                result["content"],
                json.dumps(result["visualization"]) if result.get("visualization") else None,
                json.dumps(result.get("attachment")) if result.get("attachment") else None,
                answered_at,
            ),
        )
        db.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ? AND user_id = ?",
            (answered_at, chat_id, user.id),
        )
    return {
        "chat_id": chat_id,
        "message": {
            "id": assistant_id,
            "role": "assistant",
            "content": result["content"],
            "visualization": result.get("visualization"),
            "attachment": result.get("attachment"),
            "created_at": answered_at,
        },
    }


@app.get("/healthz", include_in_schema=False)
def deployment_health():
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(request: LoginRequest, response: Response):
    user = authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    set_session_cookie(response, user)
    return public_user(user)


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)


@app.get("/api/auth/me")
def current_user(user: CurrentUser):
    return public_user(user)


@app.get("/api/health")
def health(_: CurrentUser):
    return {"status": "ok", **APP_STATE}


@app.get("/api/chats")
def list_chats(user: CurrentUser):
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM chats WHERE user_id = ? ORDER BY updated_at DESC",
            (user.id,),
        ).fetchall()
    return [_chat_row(row) for row in rows]


@app.post("/api/chats")
def create_chat(user: CurrentUser):
    chat_id = str(uuid.uuid4())
    now = utc_now()
    with connect() as db:
        db.execute(
            "INSERT INTO chats(id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, user.id, "New analysis", now, now),
        )
        row = db.execute(
            "SELECT * FROM chats WHERE id = ? AND user_id = ?",
            (chat_id, user.id),
        ).fetchone()
    return _chat_row(row)


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str, user: CurrentUser):
    with connect() as db:
        chat = db.execute(
            "SELECT * FROM chats WHERE id = ? AND user_id = ?",
            (chat_id, user.id),
        ).fetchone()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        messages = db.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at", (chat_id,)).fetchall()
    return {**_chat_row(chat), "messages": [_message_row(row) for row in messages]}


@app.delete("/api/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str, user: CurrentUser):
    with connect() as db:
        attachment_rows = db.execute(
            """
            SELECT m.attachment
            FROM messages AS m
            JOIN chats AS c ON c.id = m.chat_id
            WHERE m.chat_id = ? AND c.user_id = ? AND m.attachment IS NOT NULL
            """,
            (chat_id, user.id),
        ).fetchall()
        db.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user.id))
    for row in attachment_rows:
        path = attachment_path(load_attachment(row["attachment"]) or {})
        if path and path.is_file():
            path.unlink()


@app.get("/api/exports/{export_id}")
def download_export(export_id: str, user: CurrentUser):
    attachment = None
    with connect() as db:
        rows = db.execute(
            """
            SELECT m.attachment
            FROM messages AS m
            JOIN chats AS c ON c.id = m.chat_id
            WHERE c.user_id = ? AND m.attachment IS NOT NULL
            ORDER BY m.created_at DESC
            """,
            (user.id,),
        ).fetchall()
    for row in rows:
        candidate = load_attachment(row["attachment"])
        if candidate and candidate.get("id") == export_id:
            attachment = candidate
            break
    if not attachment:
        raise HTTPException(status_code=404, detail="Export not found")

    path = attachment_path(attachment)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found")
    media_types = {
        "csv": "text/csv; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    media_type = media_types.get(attachment["format"], "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=attachment["filename"])


@app.post("/api/chat")
def chat(request: ChatRequest, user: CurrentUser):
    chat_id, history = _start_chat_message(request, user)

    try:
        result = answer_question(request.message.strip(), history=history)
    except QueryError as exc:
        result = {"content": str(exc), "visualization": None, "attachment": None, "debug": None}
    return _persist_assistant_result(chat_id, user, result)


@app.post("/api/agent-review")
def agent_review(request: ChatRequest, user: CurrentUser):
    chat_id, history = _start_chat_message(request, user)

    def stream():
        try:
            for event in executive_review_events(request.message.strip(), history):
                if event.get("event") == "result":
                    event = {
                        "event": "result",
                        "result": _persist_assistant_result(chat_id, user, event["result"]),
                    }
                yield json.dumps(event, ensure_ascii=False, default=str) + "\n"
        except QueryError as exc:
            yield json.dumps({"event": "error", "message": str(exc)}, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps(
                {
                    "event": "error",
                    "message": f"Analysis failed: {type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        requested = FRONTEND_DIST / path
        if path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")
