# Architecture

## Overview

Synergy is a single-screen React application backed by FastAPI. The backend owns workbook ingestion, chat persistence, AI planning, guarded SQL execution, and response construction. The browser receives a typed response containing text and an optional visualization payload.

## Request flow

```text
User question
    |
    v
React chat interface
    |
    v
POST /api/chat
    |
    +--> Load complete chat history from SQLite
    |
    +--> OpenRouter planning call (high reasoning)
    |       returns SQL + answer mode + chart metadata
    |
    +--> Validate and execute read-only SQL
    |       invalid query -> model repair -> validate again
    |
    +--> Direct scalar response or OpenRouter synthesis call
    |
    +--> Persist assistant response and visualization in SQLite
    |
    v
React renders text, table, or Recharts visualization
```

## Data lifecycle

On startup, `backend.config.find_workbook` resolves `EXCEL_PATH` or locates the first repository-root `.xlsx` file. `backend.database.initialize_database` fingerprints the workbook using its path, size, and modification time.

If the fingerprint changed, the active worksheet is read from row 5 onward and imported into a replacement `learning_records` table. The replacement is built first and then renamed, so the application does not partially refresh the live table. Chat tables remain intact across workbook refreshes.

The workbook and database are runtime inputs. They are not repository assets and are excluded by `.gitignore`.

## AI contract

The query planner receives:

- The user question
- Complete prior conversation history
- The declared learning-report schema
- Any SQL validation or execution error from the previous attempt

It returns a JSON query plan containing a single SQL statement, response mode, title, chart type, and analytical context. Planning and synthesis use `high` reasoning through the OpenRouter OpenAI-compatible endpoint.

There are no application-level timeouts, response-token limits, conversation truncation, or result-row limits. Provider and model context limits still apply.

## SQL trust boundary

Model output is untrusted. Before execution, the backend:

1. Masks quoted values and SQL comments for structural checks.
2. Requires a single `SELECT` or common-table-expression statement.
3. Requires the query to use `learning_records`.
4. Enables SQLite `query_only` mode.
5. Installs an authorizer that denies writes, schema changes, attachment, and mutation-related pragmas.

The model can analyze report data but cannot modify the workbook or SQLite schema through the analytical path.

## Response contract

The backend returns an assistant message with plain text and an optional visualization object:

```json
{
  "content": "The completion rate is 50%.",
  "visualization": {
    "type": "pie",
    "title": "Completion status",
    "data": [{"label": "Completed", "value": 5}],
    "labelKey": "label",
    "valueKeys": ["value"]
  }
}
```

The frontend owns chart rendering. Model synthesis is instructed not to return Markdown charts, Mermaid, JSON, or text tables.

## Persistence

SQLite contains three application concerns:

- `learning_records` — imported workbook data
- `chats` — thread metadata
- `messages` — user/assistant messages and serialized visualizations

Deleting a chat cascades to its messages. Reimporting a workbook replaces only `learning_records`.

## Deployment assumptions

- The process needs read access to `EXCEL_PATH`.
- The process needs write access to the parent directory of `DATABASE_PATH`.
- The OpenRouter key is supplied at runtime and never baked into the frontend.
- A built `frontend/dist` directory lets FastAPI serve the application as one service.
