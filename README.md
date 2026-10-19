# Project Atlas - Report Copilot

A FastAPI service that answers market-research questions from a client's purchased reports. It never reveals content the client has not bought, shows conflicting sources side by side, labels derived numbers, and hands low-confidence questions to a human analyst.

Everything lives under `src/`. SQLite stands in for MySQL (same tables). There are two chat pages: a CodeIgniter 3 (PHP) portal page in `src/php` and a plain page served by FastAPI at `/`.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
touch .env
.venv/bin/uvicorn src.main:app --port 8000
```

The defaults work without any `.env`. To change settings create a `.env` file with lines such as `CONFIDENCE_THRESHOLD=0.5` or the LLM variables below.

Open http://localhost:8000 and chat; pick the client in the first box (C-01 bought R-101 and R-103, C-02 bought R-103). No keys are needed by default. To turn client authentication on, set `API_KEYS=key1:C-01,key2:C-02` (each key is tied to one client); the chat page then shows a key box. The admin page and admin endpoints never ask for a key, so only run this on a trusted machine or put it behind your own network controls.

First start downloads a 79 MB embedding model and ingests the six reports (about 40 s); later starts are instant. If the download fails the service falls back to hashed embeddings and says so in `/health`.

Docker (API, embedded Chroma vector store, SQLite volume and the CodeIgniter 3 portal):

```bash
docker compose up --build
```

- CodeIgniter 3 chat page: http://localhost:8080
- API and its own chat page: http://localhost:8000

Defaults come from `docker-compose.yml`; override them with a `.env` file next to it (never commit it; `.env*` is git-ignored). Authentication is off by default and the admin endpoints are always open; keep the ports on your own machine or behind your own network controls. The first start waits for the embedding model download, so the portal comes up after the API is healthy.

Tests and evaluation:

```bash
.venv/bin/python -m pytest src/tests -q
.venv/bin/python -m src.eval.runner
```

LLM is optional. With `LLM_PROVIDER=none` (default) answers are composed deterministically. The `LLM_PROVIDER` variable in `.env` picks the backend; the writer then rewrites the draft and the SQL planner can translate free-form aggregate questions.

Each provider has its own variables, so you can keep several configured and switch with `LLM_PROVIDER` alone:

| `LLM_PROVIDER` | Its own variables | Notes |
|---|---|---|
| `bedrock` | `BEDROCK_MODEL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (`AWS_SESSION_TOKEN` if temporary) | Bedrock Converse API; without keys it uses the standard AWS credential chain (profile, IAM role) |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.5-flash`) | |
| `ollama` | `OLLAMA_MODEL` (default `llama3.1`), `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) | local, no key; from Docker use `http://host.docker.internal:11434/v1` |
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`) | |
| `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | |
| `custom` | `LLM_BASE_URL`, `LLM_MODEL`, optional `LLM_API_KEY` | any OpenAI-compatible endpoint |
| `none` | nothing | no LLM |

The older generic `LLM_API_KEY`, `LLM_MODEL` and `LLM_BASE_URL` still work as a fallback when a provider's own variable is empty. Shared settings: `LLM_MAX_TOKENS`, `LLM_TIMEOUT_S`, `REQUEST_TOKEN_CAP`, `LLM_PRICE_IN_PER_M`, `LLM_PRICE_OUT_PER_M`.

`/health` shows `llm_enabled`. Every LLM draft passes the critic; a draft with an unsupported number is discarded and the deterministic answer is used.

## Managing reports from the browser

Open http://localhost:8000/admin (link on the chat page), and you can:

- **Add a report**: fill in title, publisher, date and sector, choose a `.md`, `.txt` or `.pdf` file, tick the clients who may see it, and optionally add figures (market size, CAGR, regional share) so people can ask for numbers. It is indexed straight away, no restart.
- **Share or hide a report**: tick or untick a client next to any paid report.
- **Delete a report**: removes its file, search data, figures and access. Cached answers are cleared.
- **Re-ingest all**: rebuilds the search data from the files.
- **See what is stored**: a summary bar (reports, text chunks in the vector database, figures in the SQL tables, reports not indexed, embeddings, LLM on/off), status chips on each report (`not in search index`, `source file missing`, `no figures`) and a **View** button that lists the exact chunks the search uses, with any text aimed at an AI flagged.

In `.md` and `.txt` files start each page with `[[page 1]]`, `[[page 2]]`... so citations show page numbers; without markers pages are split automatically. Scanned (image-only) PDFs are rejected because they have no text. Deleting a built-in report is permanent: the seed data is only loaded into a new database.

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /chat` | client key if `API_KEYS` is set | `{client_id, message, conversation_id?}` returns `answer, citations[], confidence, conflicts[], derived_values[], escalated` plus `intent, flags, sql_queries, message_id` |
| `POST /feedback` | client key if `API_KEYS` is set | thumbs up/down on a message |
| `POST /ingest` | none | (re)ingest reports from `src/data/reports` |
| `GET /escalations` | none | open analyst tickets |
| `GET /admin/reports` | none | reports with chunk counts, figures and which clients can see each |
| `POST /admin/reports` | none | multipart upload of a `.md`, `.txt` or `.pdf` report with its details, optional figures and client access |
| `PUT /admin/reports/{id}/access` | none | choose which clients can see a paid report |
| `DELETE /admin/reports/{id}` | none | remove the report, its file, search data, figures and access |
| `GET /health` | none | status, chunk count, embedding backend |

## Architecture

```
CI3 portal page (PHP)            plain page / API clients
      |  session -> client_id, key held server side
 CI3 controller + Atlas_client library (timeouts, fallbacks)
      |  X-API-Key (bound to one client_id)
   FastAPI routes -> ChatService (cache, conversation log, usage + cost log)
                          |
                    LangGraph agent
   router -> retriever -> calculator -> writer -> critic -> escalation
      \__ refusal ______________^         ^__ retry once, deterministic
```

| Node | Job |
|---|---|
| Router | rule-based intent: factual, comparison, calculation, aggregate, trust, escalate, out of scope, unsafe. Unsafe, write and exfiltration requests are refused and logged before anything is retrieved |
| Retriever | entitlement filter first, then vector search (Chroma) with a lexical re-rank, structured metric lookup, conflict detection and the read-only SQL tool |
| Calculator | CAGR projections with formula, assumptions and both base-year readings |
| Writer | builds the answer and citations; optional LLM rewrite |
| Critic | every number must appear in a citation, a derived value or the SQL result; scores confidence |
| Escalation | writes a ticket to `escalations` when confidence is below `CONFIDENCE_THRESHOLD` or a rule forces it |

Layers: `api/` (routes, auth) -> `services/` (business logic) -> `repositories/` (SQL) -> `db/`. `core/container.py` wires every class.

## CodeIgniter 3 portal

`src/php/application` holds the controller (`Chat`), the `Atlas_client` library (cURL with 3 s connect and 35 s total timeouts) and the chat view. The Docker image installs the framework with Composer and overlays this folder.

- The signed-in client lives in the CI3 session and the API key never reaches the browser, so a user cannot ask as another client. The page has a demo client switcher.
- CSRF protection is on for every POST; the page sends the token with each request. All server-rendered values go through `html_escape` and the script writes responses with `textContent`.
- Timeouts, an unreachable service and upstream errors return a clear message with 504, 503 and 502; the page shows it instead of failing.
- Thumbs up/down and the conversation are stored by the API service (SQLite `messages` and `feedback` tables), keyed by the CI3 session's conversation id.

## How the hard parts are handled

- **Conflicting sources**: metrics are grouped by sector, measure, region and period. Differing values are returned in `conflicts[]` with each report's scope note and are never averaged.
- **Derived numbers**: only the calculator produces them, labelled `derived_values[]` with formula and assumptions. R-101 states a 2024 size but a 2025-2030 CAGR, so both 6-period and 5-period readings are shown. Years beyond a report's forecast window are not extrapolated; the question escalates.
- **Prompt injection**: retrieved text is sanitised sentence by sentence (the R-102 p.14 footnote is dropped, the rest of the page is kept), the attempt is written to `injection_log`, and the response carries `injection_detected`. Facts come from structured metrics, so injected text cannot steer a figure.
- **Entitlements**: access is purchased reports plus public-excerpt reports (R-102). The vector filter runs before text reaches any model. A locked report may be named with an upgrade path; its figures and scope notes are never shown. The SQL sandbox only contains entitled metric rows.
- **SQL safety**: each query runs in a fresh in-memory copy holding `reports` metadata and the client's entitled `market_metrics` rows. SELECT-only validation, a single statement, an authorizer that allows only those two tables, `query_only`, a row limit and a timeout. The `clients` table is not in the sandbox at all.
- **Out of scope and sensitive**: politics, other clients' purchases and personal data are refused politely. Outbound answers have email addresses redacted.
- **Latency and cost**: exact-match cache, per-request token cap, per-request tokens and cost in `usage_log` and in structured JSON logs. Typical answers take well under a second without an LLM.

## Design decisions and trade-offs

- When `API_KEYS` is set, each key is bound to one `client_id`, so a client cannot ask as another client. With no keys configured there is no authentication and the caller chooses the `client_id`; entitlements still filter what each client sees.
- Public-excerpt reports are visible to every client in full; the spec does not define what an excerpt contains.
- Metrics live in `market_metrics` and carry a `page` column so every figure cites its page.
- The router and the critic are deterministic on purpose: they are testable and cannot be talked into anything. The cost is brittleness on unusual phrasing (see `src/eval/ANALYSIS.md`).
- SQLite instead of MySQL: same schema, zero setup. The read-only guarantee comes from the sandbox, not database grants.

## Evaluation and notes

- Evaluation report with the results table and every failure analysed: [src/eval/ANALYSIS.md](src/eval/ANALYSIS.md) (generated table and answers: [src/eval/REPORT.md](src/eval/REPORT.md)). 62 questions, all pass now, after three rounds of failures that were found and fixed; the analysis explains why that number should not be over-trusted.
- What I would do with one more week: [ONE_MORE_WEEK.md](ONE_MORE_WEEK.md).

## What was cut

MySQL (SQLite is used and no MySQL container runs), the demo video, Langfuse/LangSmith (structured logs instead), streaming, and full multi-turn memory (only short follow-ups such as "and for APAC?" are supported). The Docker files and the CI3 image have not been built here (no Docker access); the CI3 app itself was exercised against the real framework on a local PHP server.

## AI-assistant disclosure

An AI coding assistant was used throughout this project: to scaffold the structure, write most of the Python code, the CodeIgniter 3 portal, the chat and admin pages, the tests and the evaluation harness, to draft the six synthetic reports in `src/data/reports`, to write the evaluation questions, and to draft this README and the notes. I ran the tests and the evaluation, and I am able to explain the code. All figures, clients and reports are fictional.
