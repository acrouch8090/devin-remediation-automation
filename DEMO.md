# End-to-end demo

This walks through the full flow against a real issue in
`acrouch8090/superset`, dispatching a **real** Devin session. Do this only when
you intend to trigger a live session.

> The repo already has issues labeled `devin-fix` (e.g. #1, #2, #3).

## 0. Prerequisites

- Python 3.11 (or Docker).
- Your `DEVIN_API_KEY` (org secret).
- Optional: a `GITHUB_TOKEN` (classic, `repo` scope) so `simulate.py` can fetch
  issues without hitting the unauthenticated GitHub rate limit.

## 1. Configure

```bash
cp .env.example .env
# Edit .env and set:
#   DEVIN_API_KEY=<your key>
#   TARGET_REPO=acrouch8090/superset
#   GITHUB_TOKEN=<optional, for simulate.py>
```

## 2. Start the service

**Option A — local:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --port 8000
```

**Option B — Docker:**

```bash
docker compose up --build
```

Verify it's up:

```bash
curl -s localhost:8000/healthz      # -> {"status":"ok"}
```

Open the dashboard: <http://localhost:8000/dashboard> (empty to start).

## 3. Trigger a remediation from a real issue

In a second terminal (with the same env loaded so `GITHUB_TOKEN` is available to
`simulate.py`):

```bash
# Replace 1 with the issue number you want to remediate.
python simulate.py 1 --repo acrouch8090/superset --action labeled
```

Expected output:

```
Fetching issue #1 from acrouch8090/superset ...
POSTing simulated 'labeled' event to http://localhost:8000/webhook/github ...
HTTP 200
{
  "triggered": true,
  "issue_number": 1,
  "session_id": "...",
  "session_url": "https://app.devin.ai/sessions/..."
}
```

This calls the **real** Devin API and creates a live session.

> Tip: preview the payload first without creating a session by adding
> `--dry-run` (prints the webhook JSON and exits).

## 4. Watch progress

- Refresh the dashboard: <http://localhost:8000/dashboard>. The background poller
  updates the session status every `POLL_INTERVAL_SECONDS` (default 30s) and
  fills in the **Pull Request** link once Devin opens the PR.
- Or open the **Devin Session** link from the dashboard to watch Devin work.
- The resulting PR will target `master` and reference the issue (`Fixes #<n>`).

## 5. Verify

- Confirm a new PR appears in `acrouch8090/superset` from branch
  `devin/issue-<number>` and references the issue.
- The dashboard row shows status `finished`/`completed` and a PR link.

## Notes

- Re-running `simulate.py` for the same issue while its session is still active is
  a **no-op** (idempotent) — the response will say `"already in progress"`.
- To demo the `opened` trigger instead of `labeled`, use `--action opened`
  (the issue must already carry the `devin-fix` label).
