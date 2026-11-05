# Launch note — fde-connector-pack (20-point pre-launch checklist)

1. **Tests green** — PASS: `python3 -m pytest tests/ -q` → 42 passed in ~0.9s.
2. **No real secrets** — PASS: every token is a synthetic `fixture-<vendor>-token-N` value generated in `auth.py`; no realistic credential literal exists in the tree.
3. **No private/personal data** — PASS: all contacts, users and messages are invented fixtures with `*.example` emails and `+1-555-*` numbers.
4. **No payment integration** — PASS: no payment provider, billing code or card handling anywhere.
5. **Free tier only / $0 cost** — PASS: Python stdlib + already-installed open-source packages; no paid service used or required.
6. **No network calls at runtime or in tests** — PASS: fixture servers are in-process FastAPI apps reached through TestClient; no sockets are opened.
7. **Deterministic fixtures** — PASS: datasets are fixed constants, vendor ids use `zlib.crc32` (not randomized `hash()`), backoff jitter is seeded (42) and time is an injected FakeClock.
8. **README verified against reality** — PASS: every number in the README (42 tests; 12/11/10/9 records in 3 pages each; 11 created + 1 dead-lettered; 3 retries under faults; delays [2.0, 2.0] and 1.3197/2.0125/4.1375) was measured in this build session.
9. **README free of internal process language** — PASS: public-facing wording only; scope limits are stated as product scope, not process.
10. **No binary files** — PASS: source and Markdown only; `.gitignore` excludes local SQLite DBs and caches.
11. **Mapping exactness tested** — PASS: canonical → vendor payload asserted dict-equal for all four connectors, plus vendor → canonical round trips.
12. **Pagination tested to completion** — PASS: all four pagination styles (SOQL cursor, Slack next_cursor, HubSpot after, Google pageToken) drained with exact record/page counts.
13. **Crash-resume tested** — PASS: crash after page 1 and after page 2, checkpoint durability across reopened SQLite files, and mid-page re-push deduplication all covered.
14. **Idempotency tested** — PASS: full re-run of a completed sync creates 0 records and absorbs 11 duplicates via unique idempotency keys.
15. **Retry/backoff behaviour tested** — PASS: Retry-After honoured exactly, seeded exponential schedule asserted value-for-value, bounded budget exhausts after exactly max_attempts requests.
16. **Error classification tested** — PASS: status-to-class table parametrized (429/5xx retryable, 400/401/403/404/422 permanent) and permanent vendor rejections verified to consume zero retries.
17. **Dead-letter contents tested** — PASS: the single bad record lands in the dead-letter table with connector, external id, class `permanent`, code `VALIDATION_ERROR` and its payload; all other records succeed.
18. **Fault injection is scripted and bounded** — PASS: faults come only from an explicit `FaultPlan` (opening 429s, per-cursor 500/429 counts, one bad record); defaults are fault-free.
19. **Scope honesty documented** — PASS: README states plainly that fixtures mimic API shapes only, tokens are synthetic, and no live vendor calls exist.
20. **Reproducible from a clean checkout** — PASS: `pip install -r requirements.txt`, then the documented pytest and demo commands reproduce everything with no external service.

Verdict: all items PASS or N/A with reason. Cleared for the ship lane.
