# devin-remediation-automation

An event-driven service that turns GitHub issues into Devin-authored pull
requests. When an issue in [`acrouch8090/superset`](https://github.com/acrouch8090/superset)
is labeled **`devin-fix`**, this service automatically dispatches a
[Devin](https://devin.ai) session scoped to fix that issue and open a PR against
`master`.

```
GitHub issue labeled `devin-fix`
        │  (webhook: issues event)
        ▼
POST /webhook/github  ──►  filter (opened/labeled + devin-fix?)
        │ yes
        ▼
translation layer  ──►  scoped Devin prompt (repo, branch, criteria, "open a PR")
        │
        ▼
Devin API client  ──►  POST /v1/sessions          ┐
        │                                          │ state persisted in SQLite
        ▼                                          │ (issue → session → status → PR)
background poller ──► GET /v1/session/{id} ────────┘
        │
        ▼
GET /dashboard  (issue · title · status · session link · PR link)
```

## Features

- **`POST /webhook/github`** — accepts GitHub `issues` webhook payloads and
  triggers when an issue is **opened with** or **labeled** `devin-fix`.
- **Translation layer** — converts an issue's title/body into a well-scoped Devin
  prompt: target repo, `devin/issue-<number>` branch convention, extracted
  acceptance criteria, and an instruction to open a PR against `master` that
  references the issue (`Fixes #<number>`).
- **Devin API client** — creates sessions via `POST /v1/sessions` (Bearer auth
  with `DEVIN_API_KEY`) and polls `GET /v1/session/{session_id}` for status/PR.
- **Persistent state store** — SQLite mapping issue number → session id, status,
  timestamps, and PR URL.
- **`GET /dashboard`** — minimal HTML page listing each remediation.
- **`GET /healthz`** — liveness probe.
- **`simulate.py`** — fetches a real issue from the GitHub API and POSTs an
  equivalent webhook payload locally, so the demo works without a public webhook.
- **Docker / docker-compose** and a documented **`.env.example`**.
- **Unit tests** for the translation layer and webhook filtering, with the Devin
  API fully mocked.

## Project layout

```
app/
  config.py        # env-driven settings (pydantic-settings)
  models.py        # GitHub webhook + internal record models
  webhook.py       # pure should_remediate() filtering logic
  translation.py   # issue -> Devin prompt
  devin_client.py  # async Devin API client (+ PR URL extraction)
  store.py         # SQLite state store
  service.py       # orchestration (filter -> translate -> dispatch -> poll)
  dashboard.py     # server-rendered HTML
  main.py          # FastAPI app factory + routes + background poller
simulate.py        # replay a real issue as a webhook
tests/             # translation + webhook filtering (Devin mocked)
```

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DEVIN_API_KEY` | yes (runtime) | — | Bearer token for the Devin API. Provided as an org secret. Not needed for tests. |
| `DEVIN_API_BASE` | no | `https://api.devin.ai/v1` | Devin API base URL. |
| `GITHUB_TOKEN` | no | — | Used only by `simulate.py` to fetch issues (raises rate limits / private repos). |
| `TARGET_REPO` | no | `acrouch8090/superset` | Repo Devin should fix. |
| `TRIGGER_LABEL` | no | `devin-fix` | Label that triggers remediation. |
| `DEFAULT_BASE_BRANCH` | no | `master` | Base branch for generated PRs. |
| `DATABASE_PATH` | no | `data/remediation.db` | SQLite file path. |
| `POLL_INTERVAL_SECONDS` | no | `30` | Background poll cadence. |

## Setup & run (local)

Requires Python 3.11.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # runtime + test deps
cp .env.example .env                        # then fill in DEVIN_API_KEY
export $(grep -v '^#' .env | xargs)         # or use your own env loader

uvicorn app.main:app --reload --port 8000
```

Then open <http://localhost:8000/dashboard>.

## Run with Docker

```bash
cp .env.example .env   # fill in DEVIN_API_KEY
docker compose up --build
```

The dashboard is served on <http://localhost:8000/dashboard>. The SQLite
database is persisted in the `remediation-data` named volume.

## Testing

Tests never hit the real Devin API (it is mocked) and never create sessions:

```bash
pip install -r requirements-dev.txt
python -m pytest        # 21 tests
ruff check .            # lint
```

## End-to-end demo

See [`DEMO.md`](DEMO.md) for exact step-by-step instructions to run the full
flow against a real `acrouch8090/superset` issue using your `DEVIN_API_KEY`.

## How the webhook would be wired in production

In a real deployment you'd add a GitHub webhook (repo Settings → Webhooks) for
the **Issues** event pointing at `https://<your-host>/webhook/github`. This repo
ships `simulate.py` so the flow can be demonstrated locally without exposing a
public endpoint.

## Design decisions

- **App factory + dependency injection** (`create_app(...)`). The Devin client
  and store are injectable, which is what lets tests run with a `FakeDevinClient`
  and an in-memory SQLite DB — no network, no real sessions.
- **Pure filtering function** (`should_remediate`). Keeping the trigger rules
  side-effect free makes them trivial to unit test and reason about.
- **Record-intent-first.** The webhook persists a `pending` remediation *before*
  calling Devin, so the dashboard reflects in-flight work and failures are
  visible (status flips to `error`) rather than lost.
- **Idempotency per issue.** A second `devin-fix` event for an issue that already
  has an active session is a no-op, preventing duplicate sessions.
- **Background poller** rather than webhooks-from-Devin: a single async loop
  refreshes non-terminal sessions every `POLL_INTERVAL_SECONDS`, updating status
  and the PR URL. This keeps the integration one-directional and simple.
- **SQLite** for the state store: zero external infra, persists across restarts
  via a Docker volume, and is sufficient for this low-throughput workload.
- **Tolerant PR-URL extraction** (`extract_pr_url`) checks the common response
  shapes (`pull_request.url`, `structured_output.pr_url`, …) so it keeps working
  across Devin API variations.

## Limitations

- **No webhook signature verification.** A production deployment should verify
  the `X-Hub-Signature-256` header against a shared secret. Omitted here to keep
  the demo simple.
- **In-process poller / single instance.** State and the poll loop live in one
  process. Running multiple replicas would need a shared DB and a leader/locking
  mechanism (or moving to Devin-side callbacks).
- **Best-effort status mapping.** Session status strings are passed through from
  the API; terminal-state detection uses a known set and may need updating if the
  API's vocabulary changes.
- **No auth on the dashboard / webhook** beyond what a reverse proxy would add.
- The translation layer extracts acceptance criteria heuristically (markdown
  "Acceptance Criteria" / "Definition of Done" headings); free-form issues fall
  back to instructing Devin to infer criteria.
