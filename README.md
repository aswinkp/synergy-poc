# Synergy Learning Intelligence

Synergy is a one-page conversational analytics application for Excel learning and employee-headcount reports. Users ask questions in plain English and receive the answer format that best fits the request: a direct value, a written analysis, a table, or a dynamically rendered chart.

The application imports environment-provided workbooks into a relational SQLite database, joins learning assignments to canonical employee profiles through `Employee ID`, uses OpenRouter to translate questions into read-only SQL, and stores multiple chat threads locally. Source workbooks are never modified.

## What it supports

- Natural-language questions across the complete learning report
- Combined learning, workforce, demographic, tenure, role, and reporting-line analysis
- Follow-up questions using the full conversation history
- Direct answers, analytical summaries, tables, and charts
- Bar, pie, line, and area charts rendered in React with Recharts
- Prompt-driven analysis with live, truthful planning, query, response, answer-text, and export progress for every question
- A demo email action that responds exactly with `email is sent`
- On-demand CSV, Excel (`.xlsx`), and visually designed PowerPoint (`.pptx`) briefings generated only when explicitly requested
- Persistent download cards attached to the relevant assistant response
- Multiple persistent chat threads in the sidebar
- Database-provisioned login with no public signup
- Per-user chat history and export isolation
- Automatic SQLite refresh when either source workbook changes
- Read-only SQL validation and SQLite write protection for model-generated queries
- OpenRouter model configuration through environment variables

## Technology

- Backend: Python, FastAPI, SQLite, OpenPyXL, python-pptx, OpenAI-compatible SDK
- Frontend: React, TypeScript, Vite, Recharts
- AI gateway: OpenRouter
- Default model: `openai/gpt-5.6-luna` with `high` reasoning

See [Architecture](docs/ARCHITECTURE.md) for the request and data flow.
See [VPS deployment](docs/DEPLOYMENT.md) for the Docker Compose, HTTPS, BWS, backup, and operations runbook.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- An OpenRouter API key
- A randomly generated authentication signing secret
- A compatible learning workbook supplied locally or through a mounted path
- An optional compatible headcount workbook for employee enrichment

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
HEADCOUNT_EXCEL_PATH=/absolute/path/to/headcount-report.xlsx
DATABASE_PATH=./data/learning_chat.db
EXPORTS_PATH=./data/exports
AUTH_SECRET=replace-with-output-from-openssl-rand-hex-32
AUTH_TOKEN_TTL_HOURS=12
AUTH_COOKIE_SECURE=false
```

`OPENROUTER_API_KEY` and the learning workbook are required. The headcount workbook is optional but required for combined workforce analysis.

- Without `EXCEL_PATH`, the application uses the first repository-root `.xlsx` file whose name does not contain `headcount`.
- Without `HEADCOUNT_EXCEL_PATH`, the application uses the first repository-root `.xlsx` file whose name contains `headcount`, when available.
- Without `DATABASE_PATH`, SQLite is created at `data/learning_chat.db`.
- Without `EXPORTS_PATH`, generated downloads are written to `data/exports`.
- `AUTH_SECRET` is required and must contain at least 32 characters. Generate it with `openssl rand -hex 32`.
- `AUTH_COOKIE_SECURE` must be `true` when the application is served over HTTPS. Keep it `false` only for local HTTP development.
- Relative paths are resolved from the repository root.

The `.env` file, Excel workbooks, and SQLite databases are intentionally ignored by Git. Keep API keys and customer data outside the repository.

## Provision users

There is intentionally no signup endpoint or signup UI. Add users directly to the configured SQLite database with the administration command:

```bash
source .venv/bin/activate
python -m backend.users add --email analyst@company.com --name "Data Analyst"
```

The command prompts for the password without placing it in shell history and stores only an Argon2 hash. On the first authenticated deployment after upgrading an existing database, historical chats remain unassigned so they cannot leak to a new account. Assign them deliberately while creating their owner:

```bash
python -m backend.users add \
  --email owner@company.com \
  --name "Existing Chat Owner" \
  --claim-existing-chats
```

Other administration commands:

```bash
python -m backend.users list
python -m backend.users set-password --email analyst@company.com
python -m backend.users deactivate --email analyst@company.com
python -m backend.users activate --email analyst@company.com
```

Passwords must contain at least 12 characters. Deactivated users are rejected immediately, including when they still have an unexpired session cookie.

## Workbook contracts

### Learning report

The importer reads the active worksheet, treats rows 1–4 as report metadata/header rows, and begins importing assignments at row 5. Columns are positional and must match `COLUMNS` in [backend/schema.py](backend/schema.py), beginning with:

`Employee ID`, `Employee Name`, `Gender`, `Date Of Joining`, `Email ID`, `Learning Category`, `Course Name`, `Status`, and the remaining fields declared in the schema.

Supported status values are `Completed`, `Not Started`, and `In Progress`.

### Headcount report

The importer reads headers from row 1 and employee records from row 2. Columns must match `HEADCOUNT_COLUMNS` in [backend/schema.py](backend/schema.py). The report adds organization structure, employment status, effective date, date of birth, group joining date, generation, age, exit information, role type, and HRBP/QHSE/DOC reporting relationships.

`Employee ID` is the relational key. Because source headcount exports can contain duplicate employee IDs, SQLite stores:

- `employee_headcount` — every raw source row for auditability
- `employees` — one canonical row per employee ID across both workbooks
- `learning_records` — one row per employee-course assignment with a foreign key to `employees.employee_id`
- `employee_learning_summary` — one row per employee with assignment counts and completion rate

For duplicate headcount IDs, every row is preserved and the first exported row becomes the deterministic canonical profile. `headcount_record_count` identifies affected employees for data-quality review.

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

## Deploy with Docker

Production uses the included multi-stage image and Compose stack. FastAPI serves the compiled frontend, while Caddy provides automatic HTTPS and is the only container exposed on the host. Runtime workbooks and SQLite state are mounted from the VPS and are never included in the image.

```bash
docker compose \
  --env-file .env.production \
  -f compose.production.yml \
  up -d --build
```

Use [the complete VPS runbook](docs/DEPLOYMENT.md) for first-time setup. It covers DNS, UFW, BWS-backed environment creation, workbook placement, user provisioning, health verification, daily SQLite backups, operations, and rollback.

## Test

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
npm --prefix frontend run build
```

Tests create isolated synthetic learning and headcount workbooks plus SQLite in a temporary directory. They test duplicate headcount records, headcount-only employees, the employee relationship, and combined summaries without reading customer data.

## Runtime behavior

- Every analytical question is planned by the configured OpenRouter model.
- Workforce questions use the canonical `employees` table; combined questions join it to `learning_records` through `employee_id`.
- Planning and synthesis use `high` reasoning.
- The application sets no response-token cap, analytical timeout, conversation truncation, or result-row cap.
- Invalid SQL is returned to the model for repair until a valid read-only query is produced.
- Scalar results are returned directly; richer results are synthesized by the model.
- The frontend renders visualization payloads independently from the written response.
- The React client sends every question through the same streaming, model-planned, guarded query engine. Step labels, SQL analysis, response shape, and chart follow the user's actual question; there is no keyword-based route or injected workforce, tenure, generation, or manager analysis.
- The progress card first shows the slower model-planning operation, then names the model-selected analysis and answer format. Fast SQLite work may complete between browser paints, but every displayed state reflects completed work rather than a simulated delay.
- Rich written answers stream into the chat as the model generates them, then the completed answer, chart, and optional attachment are persisted together.
- Explicit email-action prompts bypass the model and return exactly `email is sent`; no email provider is contacted.
- CSV, Excel, or PowerPoint files are generated from the same validated result only when the prompt explicitly asks for that format. PowerPoint requests also steer the model toward a concise, slide-ready executive narrative, while the deterministic deck renderer applies the presentation design system, native charts, management takeaways, readable evidence tables, and additional briefing slides when the answer is too long for one slide. Asking for a chart, table, or ordinary answer does not create a file.
- Export metadata is stored with the assistant message, so its download card remains available when the chat is reopened. Deleting the chat also removes its generated files.
- Login uses `pwdlib` with Argon2 password hashing and `PyJWT` signed sessions in an HttpOnly, SameSite cookie. The frontend never reads or stores the token.
- Every chat, message history lookup, deletion, and export download is constrained to the authenticated owner.

## API

- `POST /api/auth/login` — authenticate a provisioned user and set the session cookie
- `POST /api/auth/logout` — clear the session cookie
- `GET /api/auth/me` — return the authenticated user
- `GET /api/health` — application and workbook status
- `GET /api/chats` — list chat threads
- `POST /api/chats` — create an empty chat
- `GET /api/chats/{chat_id}` — load a chat and its messages
- `DELETE /api/chats/{chat_id}` — delete a chat
- `POST /api/chat` — non-streaming compatibility endpoint for a question in a new or existing chat
- `POST /api/agent-review` — primary frontend endpoint; stream prompt-driven progress and answer text as newline-delimited JSON
- `GET /api/exports/{export_id}` — download an export referenced by a persisted assistant message

## Repository layout

```text
backend/                 FastAPI API, authentication, workbook import, SQLite, AI query engine, proactive review, exports
frontend/src/            React chat interface and visualization rendering
tests/                   Isolated backend and API tests with synthetic data
docs/ARCHITECTURE.md     System design and trust boundaries
docs/DEPLOYMENT.md       VPS provisioning, deployment, backup, and operations runbook
deploy/                  Caddy config, deployment scripts, and backup systemd units
Dockerfile               Multi-stage React and FastAPI production image
compose.production.yml   Private app network plus public HTTPS proxy
.env.example             Environment variable template without secrets
```

## Data and security notes

- Never commit `.env`, workbooks, databases, exports, or customer-derived files.
- CSV and XLSX writers neutralize formula-like source text before it reaches spreadsheet software.
- Model-generated SQL is restricted to one read-only `SELECT` or common-table-expression query against the imported analytics tables and summary view.
- SQLite authorizer rules deny mutation and schema-changing operations during analytical queries.
- Chat history and imported workbook data remain in the configured local SQLite database.
- Public signup does not exist. Passwords are never stored in plaintext, and user access is checked against the database on every protected request.
- Learning and employee rows are sent to the configured OpenRouter model when needed to synthesize non-scalar answers. Headcount fields can contain personal and organizational data; review provider and organizational data-handling requirements before use.
