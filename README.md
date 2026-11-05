# fde-connector-pack

A customer connector pack for a SaaS product: outbound integration
connectors for **Salesforce, Slack, HubSpot and Google Workspace**, a
common connector framework underneath them, and an idempotent sync
engine that moves records between systems without duplicating them —
including across a crash.

Everything runs against **local fixture servers**: in-process FastAPI
apps that mimic each vendor's API shape, pagination style and error
format. There are no live vendor calls, no vendor accounts and no real
credentials anywhere in this project.

## The framework

- **One connector interface.** Every connector implements
  `fetch(cursor) -> Page`, `push(record) -> PushResult` and `health()`,
  over canonical objects (`Contact`, `Account`, `Message`,
  `DirectoryUser`). Each connector maps its canonical object to and from
  the vendor's payload shape.
- **Resilient HTTP layer.** All calls pass through one request wrapper
  that attaches an OAuth-style fixture bearer token (with refresh on
  virtual expiry), classifies errors as **retryable** (429, 5xx) or
  **permanent** (400/401/403/404/422), honours `Retry-After` on 429s,
  and retries retryable failures with exponential backoff plus jitter —
  bounded by a configurable attempt budget, after which the failure is
  raised as exhausted instead of looping.
- **Deterministic time.** Backoff uses an injected clock and a seeded
  RNG. Tests assert the exact retry counts and delay values from the
  seeded schedule (default seed 42: delays 1.3197s, 2.0125s, 4.1375s),
  never wall-clock time. A `Retry-After: 2` header overrides the
  schedule with exactly 2.0s.
- **Idempotent sync with durable checkpoints.** The sync engine pages
  through a source, pushes each record to the destination under an
  idempotency key (`<source>:<external_id>`, unique in SQLite), and
  commits the next cursor to a checkpoint table after every page. A
  crash between pages resumes from the checkpoint; a crash mid-page
  re-fetches that page and the duplicate pushes are absorbed by the
  idempotency keys.
- **Dead letters, not silent drops.** A record the destination
  permanently rejects (or whose retries are exhausted) is written to a
  dead-letter table with its source, external id, error class, vendor
  error code, message, attempt count and payload — while every other
  record in the sync still completes.

## The four connectors

| Connector | Canonical object | Pagination style | Vendor shapes mimicked |
|---|---|---|---|
| Salesforce | `Contact` | SOQL-style query cursor (`nextRecordsUrl`) | `FirstName/LastName/Email/AccountId` records, list-shaped error bodies with `errorCode` |
| Slack | `Message` | `response_metadata.next_cursor` | `chat.postMessage`, `conversations.history/list`, `{"ok": false, "error": ...}` errors, `Retry-After` rate limits |
| HubSpot | `Contact` | CRM `paging.next.after` cursor | `properties{...}` objects, single + batch create, `category: VALIDATION_ERROR` errors |
| Google Workspace | `DirectoryUser` | Directory `nextPageToken` | `primaryEmail` + `name{givenName, familyName}` users, nested `error.errors[].reason` bodies |

Each fixture server also supports **scripted fault injection**: a fixed
number of opening 429s, a chosen page cursor that fails twice with 500
(or is rate-limited once) before succeeding, and one permanently bad
record (an invalid email on the last Salesforce page) that validating
destinations reject with a 400.

## Run it

```bash
pip install -r requirements.txt

# Test suite (42 tests, fully in-process, no network, no sockets)
python3 -m pytest tests/ -q

# Demo: Salesforce -> HubSpot-validated store sync with a page that
# fails twice, a simulated crash after page 1, and a resume
PYTHONPATH=src python3 -m fde_connector_pack.demo
```

## Measured results

All numbers below were measured in this build (pytest 9, Python 3.12):

- **42 tests pass** covering per-connector mapping (exact payload
  shapes), pagination to completion, retry/backoff, error
  classification, crash-resume, dead letters and fault injection.
- **Pagination:** Salesforce 12 contacts in 3 pages, HubSpot 11 in 3,
  Google Workspace 10 in 3, Slack 9 messages in 3 — each drained to
  completion with no gaps or repeats.
- **Clean sync:** Salesforce → store (HubSpot-validated): 12 fetched,
  11 created, exactly 1 dead-lettered (the invalid-email record,
  class `permanent`, code `VALIDATION_ERROR`).
- **Fault-injected sync:** with page 2 failing twice (500) and page 3
  rate-limited once (429), the same sync still completes with exactly
  3 retries, 11 created and 1 dead-lettered.
- **Crash-resume:** crashing after page 1 leaves 5 records durable and
  the checkpoint at the page-2 cursor; resuming fetches only the
  remaining 7, creates 6, and produces **0 duplicates**. A full re-run
  of a completed sync creates 0 and reports 11 duplicates absorbed.
  Checkpoints survive reopening the SQLite database.
- **Rate limiting:** a fixture that 429s its first two requests is
  fetched successfully with retry delays of exactly `[2.0, 2.0]`
  seconds (the `Retry-After` value), and an always-429 fixture
  exhausts a 3-attempt budget after exactly 3 requests — never more.

## Scope honesty

The fixture servers mimic vendor API *shapes* — routes, payload fields,
pagination and error formats — with small invented datasets. They are
not production vendor SDKs: there is no real OAuth flow (tokens are
synthetic `fixture-*` values), no live vendor endpoint is contacted,
rate limits and faults are scripted rather than observed, and the sync
engine's destination in the demo is a local SQLite store with an
optional validating vendor-connector push in front of it. The point of
the project is the connector framework engineering — mapping,
pagination, resilience, checkpointing, idempotency and dead letters —
exercised end to end without any external dependency.
