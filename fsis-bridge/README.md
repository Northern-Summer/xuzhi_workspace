# FSIS Minute Bridge

Purpose: provide FSIS with a machine-readable, auditable A-share 1-minute snapshot without requiring the ChatGPT Web runtime to make arbitrary outbound HTTP calls.

Architecture:

`GitHub Actions scheduler -> East Money public HTTP K-line endpoint -> normalized JSON -> fsis-data branch -> FSIS Web retrieval`

The bridge is deliberately a data transport layer, not a trading engine. FSIS must still validate freshness, point-in-time date, continuity, missing/duplicate bars, security mapping, and source provenance before live admission.

Current cadence: every 5 minutes during the A-share daytime window (UTC 01:00-07:59, Monday-Friday), plus manual dispatch. This is a snapshot bridge, not a tick feed. It must not be described as sub-minute or exchange-direct.

The default universe is a small liquid ETF/benchmark/theme set. Runtime requests are stored in `bridge/request.json` on the durable `fsis-data` branch and are bounded to 25 symbols with expiry validation.

Data publication invariants:

- Only snapshots with `status=OK` and `live_eligible=true` may replace `bridge/latest.json`.
- Partial/failed fetches update canonical `bridge/status.json` but never overwrite the last-known-good `latest.json`.
- Writes to `fsis-data` are excluded from the workflow's own push trigger, preventing recursive self-triggering.
- Concurrency does not cancel an in-flight run; overlapping schedule/push triggers serialize instead.
- `fsis-data` is the durable data branch; it is not itself a competing FSIS workflow authority.

Important: GitHub Actions scheduling can be delayed. The `fetched_at_bj`, `latest_bar_ts`, and session date in `bridge/status.json` are authoritative for freshness checks. If freshness is outside the registered FSIS tolerance, the data is DATA/EXECUTION-CONSTRAINED.
