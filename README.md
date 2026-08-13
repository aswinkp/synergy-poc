# Synergy Learning Intelligence

Synergy is a one-page conversational analytics application for Excel learning reports. Users ask questions in plain English and receive the answer format that best fits the request: a direct value, a written analysis, a table, or a dynamically rendered chart.

The application imports an environment-provided workbook into a local SQLite database, uses OpenRouter to translate questions into read-only SQL, and stores multiple chat threads locally. The source workbook is never modified.

## What it supports

- Natural-language questions across the complete learning report
- Follow-up questions using the full conversation history
- Direct answers, analytical summaries, tables, and charts
- Bar, pie, line, and area charts rendered in React with Recharts
- Multiple persistent chat threads in the sidebar
- Automatic SQLite refresh when the source workbook changes
- Read-only SQL validation and SQLite write protection for model-generated queries
- OpenRouter model configuration through environment variables

## Technology

- Backend: Python, FastAPI, SQLite, OpenPyXL, OpenAI-compatible SDK
- Frontend: React, TypeScript, Vite, Recharts
- AI gateway: OpenRouter
- Default model: `openai/gpt-5.6-luna` with `high` reasoning

See [Architecture](docs/ARCHITECTURE.md) for the request and data flow.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- An OpenRouter API key
- A compatible Excel workbook supplied locally or through a mounted path

## Configure the environment

Copy the example file:

```bash
cp .env.example .env
```

Set these values in `.env`:

```dotenv
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=openai/gpt-5.6-luna
EXCEL_PATH=/absolute/path/to/learning-report.xlsx
DATABASE_PATH=./data/learning_chat.db
```

`OPENROUTER_API_KEY` and a workbook are required. `OPENROUTER_MODEL`, `EXCEL_PATH`, and `DATABASE_PATH` have defaults:

- Without `EXCEL_PATH`, the application uses the first `.xlsx` file in the repository root.
- Without `DATABASE_PATH`, SQLite is created at `data/learning_chat.db`.
- Relative paths are resolved from the repository root.

The `.env` file, Excel workbooks, and SQLite databases are intentionally ignored by Git. Keep API keys and customer data outside the repository.

## Workbook contract

The importer reads the active worksheet, treats rows 1–4 as report metadata/header rows, and begins importing data at row 5. Columns are positional and must match the schema in [backend/schema.py](backend/schema.py), beginning with:

`Employee ID`, `Employee Name`, `Gender`, `Date Of Joining`, `Email ID`, `Learning Category`, `Course Name`, `Status`, and the remaining fields declared in the schema.

Supported status values are `Completed`, `Not Started`, and `In Progress`.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend ci
```

## Run in development

Start the API:

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start Vite:

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to FastAPI on port 8000.

## Run as a single production-style application

```bash
npm --prefix frontend run build
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. FastAPI serves the compiled frontend when `frontend/dist` exists.

## Test

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
npm --prefix frontend run build
```

Tests create an isolated synthetic workbook and SQLite database in a temporary directory. They do not require or read customer data.

## Runtime behavior

- Every analytical question is planned by the configured OpenRouter model.
- Planning and synthesis use `high` reasoning.
- The application sets no response-token cap, analytical timeout, conversation truncation, or result-row cap.
- Invalid SQL is returned to the model for repair until a valid read-only query is produced.
- Scalar results are returned directly; richer results are synthesized by the model.
- The frontend renders visualization payloads independently from the written response.

## API

- `GET /api/health` — application and workbook status
- `GET /api/chats` — list chat threads
- `POST /api/chats` — create an empty chat
- `GET /api/chats/{chat_id}` — load a chat and its messages
- `DELETE /api/chats/{chat_id}` — delete a chat
- `POST /api/chat` — ask a question in a new or existing chat

## Repository layout

```text
backend/                 FastAPI API, workbook import, SQLite, AI query engine
frontend/src/            React chat interface and visualization rendering
tests/                   Isolated backend and API tests with synthetic data
docs/ARCHITECTURE.md     System design and trust boundaries
.env.example             Environment variable template without secrets
```

## Data and security notes

- Never commit `.env`, workbooks, databases, exports, or customer-derived files.
- Model-generated SQL is restricted to one read-only `SELECT` or common-table-expression query against `learning_records`.
- SQLite authorizer rules deny mutation and schema-changing operations during analytical queries.
- Chat history and imported workbook data remain in the configured local SQLite database.
- Report rows are sent to the configured OpenRouter model when needed to synthesize non-scalar answers. Review your provider and organizational data-handling requirements before using sensitive data.
