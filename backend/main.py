from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, find_workbook
from .database import connect, initialize_database, load_visualization, utc_now
from .query_engine import QueryError, answer_question

APP_STATE: dict[str, object] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    workbook = find_workbook()
    APP_STATE.update(initialize_database(workbook))
    APP_STATE["workbook"] = workbook.name
    yield


app = FastAPI(title="Synergy Learning Intelligence", version="1.0.0", lifespan=lifespan)
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


def _chat_row(row) -> dict:
    return {"id": row["id"], "title": row["title"], "created_at": row["created_at"], "updated_at": row["updated_at"]}


def _message_row(row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "visualization": load_visualization(row["visualization"]),
        "created_at": row["created_at"],
    }


def _chat_title(message: str) -> str:
    return " ".join(message.split())


@app.get("/api/health")
def health():
    return {"status": "ok", **APP_STATE}


@app.get("/api/chats")
def list_chats():
    with connect() as db:
        rows = db.execute("SELECT * FROM chats ORDER BY updated_at DESC").fetchall()
    return [_chat_row(row) for row in rows]


@app.post("/api/chats")
def create_chat():
    chat_id = str(uuid.uuid4())
    now = utc_now()
    with connect() as db:
        db.execute("INSERT INTO chats(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)", (chat_id, "New analysis", now, now))
        row = db.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    return _chat_row(row)


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    with connect() as db:
        chat = db.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        messages = db.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at", (chat_id,)).fetchall()
    return {**_chat_row(chat), "messages": [_message_row(row) for row in messages]}


@app.delete("/api/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str):
    with connect() as db:
        db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


@app.post("/api/chat")
def chat(request: ChatRequest):
    chat_id = request.chat_id or str(uuid.uuid4())
    now = utc_now()
    with connect() as db:
        chat = db.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        if not chat:
            title = _chat_title(request.message)
            db.execute("INSERT INTO chats(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)", (chat_id, title, now, now))
        elif chat["title"] == "New analysis":
            db.execute("UPDATE chats SET title = ? WHERE id = ?", (_chat_title(request.message), chat_id))
        history_rows = db.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at",
            (chat_id,),
        ).fetchall()
        history = [
            {"role": row["role"], "content": row["content"]}
            for row in history_rows
        ]
        user_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO messages(id, chat_id, role, content, created_at) VALUES (?, ?, 'user', ?, ?)",
            (user_id, chat_id, request.message.strip(), now),
        )

    try:
        result = answer_question(request.message.strip(), history=history)
    except QueryError as exc:
        result = {"content": str(exc), "visualization": None, "debug": None}

    assistant_id = str(uuid.uuid4())
    answered_at = utc_now()
    with connect() as db:
        db.execute(
            "INSERT INTO messages(id, chat_id, role, content, visualization, created_at) VALUES (?, ?, 'assistant', ?, ?, ?)",
            (assistant_id, chat_id, result["content"], json.dumps(result["visualization"]) if result["visualization"] else None, answered_at),
        )
        db.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (answered_at, chat_id))
    return {
        "chat_id": chat_id,
        "message": {
            "id": assistant_id,
            "role": "assistant",
            "content": result["content"],
            "visualization": result["visualization"],
            "created_at": answered_at,
        },
    }


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
