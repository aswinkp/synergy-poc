# Architecture

## Overview

Synergy is a single-screen React application backed by FastAPI. The backend owns authentication, two-workbook ingestion, employee identity resolution, user-scoped chat persistence, AI planning, guarded SQL execution, export generation, and response construction. The browser receives a typed response containing text, an optional visualization payload, and an optional download attachment.

## Authentication flow

```text
Browser starts
    |
    +--> GET /api/auth/me with HttpOnly cookie
            |
            +--> valid signed token + active database user -> workspace
            |
            +--> missing/invalid/expired token -> login screen

Login form -> POST /api/auth/login -> Argon2 password verification
                                      |
                                      +--> signed JWT stored in HttpOnly SameSite cookie
```

`pwdlib[argon2]` handles password hashing and `PyJWT` signs session tokens. The cookie is unavailable to frontend JavaScript, uses `SameSite=strict`, is scoped to `/api`, and is marked `Secure` when `AUTH_COOKIE_SECURE=true`. Token subjects contain only the database user ID. Every protected request also confirms that the user still exists and is active, so deactivation takes effect immediately.

No register route exists. `backend.users` is the administrative provisioning interface and writes Argon2 hashes directly to SQLite. Authentication failures use the same response for unknown users, wrong passwords, and inactive accounts; an Argon2 dummy verification reduces user-enumeration timing differences.

## Request flow

```text
User question
    |
    v
React chat interface
    |
    v
POST /api/agent-review (newline-delimited event stream)
    |
    +--> Verify signed session and active database user
    |
    +--> Load complete chat history from SQLite
    |
    +--> OpenRouter planning call (high reasoning)
    |       returns SQL + answer mode + chart metadata
    |
    +--> Validate and execute read-only SQL
    |       invalid query -> model repair -> validate again
    |
    +--> Direct scalar response or streaming OpenRouter synthesis call
    |
    +--> Explicit CSV/Excel/PowerPoint request? Generate from the same result rows
    |
    +--> Persist assistant response, visualization, and attachment metadata in SQLite
    |
    v
React progressively renders answer text, then the final table or Recharts visualization and optional download card
```

## Streaming agent execution

Every frontend question calls `POST /api/agent-review`. This is a bounded execution shell around the same prompt-driven query engine available through the non-streaming compatibility endpoint, not a separate fixed analysis recipe. It streams newline-delimited JSON events over the authenticated HTTP response:

```text
Create or reuse the user-owned chat
    |
    +--> Show "understanding the request" while GPT-5.6 Luna plans from the question and schema
    +--> Stream the model-selected analysis title and execute its guarded read-only SQL
    +--> Stream the model-selected written answer as it is generated
    +--> Produce the model-selected table or chart from those result rows
    +--> Create CSV, Excel, or PowerPoint only when that format is requested
    +--> For an explicit email action, use the deterministic demo response: "email is sent"
    |
    v
Persist one ordinary assistant message with text, chart, and attachment
```

No workforce segment, tenure bucket, manager ranking, SQL statement, chart choice, or keyword-based execution route is embedded in this path. Those come from the current question and the model's validated query plan. Only the operational tool contract and safety boundary are fixed. Each `running`, `complete`, or answer-content event wraps actual work; the frontend does not simulate progress or add artificial delays. Step state and partial text are transient, while the final assistant response uses the existing chat persistence and ownership boundary. If the stream fails, it emits a structured error event and does not persist a partial assistant answer.

## Data lifecycle

On startup, `backend.config.find_workbook` resolves `EXCEL_PATH` and `find_headcount_workbook` resolves `HEADCOUNT_EXCEL_PATH`. When variables are absent, filename-aware discovery keeps the headcount export from being mistaken for the learning report. `backend.database.initialize_database` fingerprints both workbooks using path, size, and modification time.

If either fingerprint changed, both active worksheets are validated and imported in one SQLite transaction. Chat tables remain intact across workbook refreshes.

`Employee ID` is normalized and used as the identity key. The import creates:

- `employees` — canonical union of headcount and learning employees, keyed by `employee_id`
- `employee_headcount` — every raw headcount row, including duplicates
- `learning_records` — assignments with a foreign key to `employees.employee_id`
- `employee_learning_summary` — employee profiles plus assignment and completion metrics

The current headcount source contains duplicate employee IDs. Raw rows are preserved; the first exported row is the canonical profile and `headcount_record_count` exposes duplicate coverage. Learning-only employees remain joinable with `is_in_headcount = 0`, while headcount employees without assignments have `has_learning_records = 0`.

The workbook and database are runtime inputs. They are not repository assets and are excluded by `.gitignore`.

## AI contract

The query planner receives:

- The user question
- Complete prior conversation history
- The declared schemas, table grain, and employee relationship
- Any SQL validation or execution error from the previous attempt

It returns a JSON query plan containing a single SQL statement, response mode, title, chart type, and analytical context. Planning and synthesis use `high` reasoning through the OpenRouter OpenAI-compatible endpoint.

There are no application-level timeouts, response-token limits, conversation truncation, or result-row limits. Provider and model context limits still apply.

## SQL trust boundary

Model output is untrusted. Before execution, the backend:

1. Masks quoted values and SQL comments for structural checks.
2. Requires a single `SELECT` or common-table-expression statement.
3. Requires the query to use an approved analytics table or view.
4. Enables SQLite `query_only` mode.
5. Installs an authorizer that denies writes, schema changes, attachment, and mutation-related pragmas.

The model can analyze learning, employee, and combined data but cannot modify either workbook or the SQLite schema through the analytical path.

## Response contract

The backend returns an assistant message with plain text, an optional visualization object, and an optional attachment:

```json
{
  "content": "The completion rate is 50%.",
  "visualization": {
    "type": "pie",
    "title": "Completion status",
    "data": [{"label": "Completed", "value": 5}],
    "labelKey": "label",
    "valueKeys": ["value"]
  },
  "attachment": {
    "id": "c440457d-035d-4e62-9dd1-3c31813c85f7",
    "format": "xlsx",
    "filename": "completion-status.xlsx",
    "url": "/api/exports/c440457d-035d-4e62-9dd1-3c31813c85f7",
    "row_count": 3,
    "size_bytes": 5312,
    "title": "Completion status"
  }
}
```

The frontend owns chart rendering. Model synthesis is instructed not to return Markdown charts, Mermaid, JSON, or text tables. Export intent is detected deterministically from explicit `CSV`, `Excel`, `XLS`, `XLSX`, `PowerPoint`, `PPT`, or `PPTX` wording; the model cannot silently opt a normal response into file generation. CSV uses UTF-8 with a byte-order mark for Excel compatibility, XLSX includes a styled header, frozen row, filter, and practical widths, and formula-like text is neutralized in both formats. PowerPoint requests add a slide-ready executive-writing instruction to the model. The deterministic renderer then applies a branded 16:9 visual system, separates long narratives across readable briefing slides, builds a native chart with a management-takeaway rail when supported, and limits the evidence slide to a legible data sample. Explicit email-action language follows a separate deterministic demo path and returns exactly `email is sent` without contacting an external service.

## Persistence

SQLite contains these application concerns:

- `learning_records` — imported workbook data
- `employees` — canonical one-row-per-employee dimension
- `employee_headcount` — raw headcount export rows
- `employee_learning_summary` — combined employee learning view
- `chats` — thread metadata
- `users` — provisioned identities, Argon2 password hashes, and active status
- `chats.user_id` — owner boundary for chats, messages, and exports
- `messages` — user/assistant messages plus serialized visualizations and export attachment metadata

Generated files live under `EXPORTS_PATH` and are downloadable only while referenced by a persisted assistant message owned by the authenticated user. Deleting a chat cascades to its messages and removes its export files. Reimporting workbooks replaces the analytics tables and view while preserving users, chats, and their existing exports.

Existing databases receive nullable `chats.user_id` and `messages.attachment` columns through non-destructive startup migrations. Historical chats remain unassigned until an administrator deliberately claims them with `python -m backend.users add --claim-existing-chats`.

## Deployment assumptions

```text
Internet
   |
   | HTTPS :443 (HTTP :80 only for redirect/certificate issuance)
   v
Caddy container
   |
   | private Compose network
   v
FastAPI + compiled React container (one Uvicorn worker)
   |                         |
   v                         v
/opt/synergy-poc/data     /opt/synergy-poc/input (read-only)
SQLite + exports          learning.xlsx + headcount.xlsx
```

- Only Caddy publishes host ports. The application has no host port mapping.
- Caddy manages TLS certificates and forwards the original proxy headers to Uvicorn.
- The application runs as UID/GID `10001`, with a read-only container filesystem and writable `/app/data` bind mount.
- One application worker is required while SQLite is the system of record. Horizontal scaling requires a shared database and shared file storage.
- `/healthz` is intentionally unauthenticated and reveals only `{"status":"ok"}` for container and external availability checks. `/api/health` remains authenticated and exposes workbook/application details.
- Docker JSON log rotation limits local log growth. A systemd timer performs a daily online SQLite backup with 14-day local retention.

- The process needs read access to `EXCEL_PATH`.
- When configured, the process needs read access to `HEADCOUNT_EXCEL_PATH`.
- The process needs write access to the parent directory of `DATABASE_PATH`.
- The process needs write access to `EXPORTS_PATH` when users request downloads.
- `AUTH_SECRET` must be supplied at runtime; use a distinct random value in every environment.
- `AUTH_COOKIE_SECURE=true` is required behind production HTTPS.
- The OpenRouter key is supplied at runtime and never baked into the frontend.
- A built `frontend/dist` directory lets FastAPI serve the application as one service.
