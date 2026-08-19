# FSIS Minute Bridge

Purpose: provide FSIS with a machine-readable, auditable A-share 1-minute snapshot without requiring the ChatGPT Web runtime to make arbitrary outbound HTTP calls.

Architecture:

`GitHub Actions scheduler -> full-market discovery -> bounded candidate generation -> 1m depth fetch -> PIT validation -> fsis-data branch -> FSIS Web retrieval`

Full-market discovery is provider-heterogeneous. EastMoney is the preferred source when reachable; Tencent Finance is an explicit full-market fallback. The bridge does not treat any single public endpoint as authoritative.

The bridge is a data transport and admission layer, not a trading engine. FSIS must still validate freshness, point-in-time date, continuity, missing/duplicate bars, security mapping, and source provenance before using data for live decisions.

Current cadence: every 5 minutes during the A-share daytime window (UTC 01:00-07:59, Monday-Friday), plus manual dispatch. This is a snapshot bridge, not a tick feed, and it is not exchange-direct.

Market discovery currently targets the complete Shanghai/Shenzhen/Beijing A-share universe, with a runtime sanity floor of 3,500 securities. A healthy run has recently produced roughly 5,800 securities and then generates at most 120 minute-deep candidates. Candidate generation is intentionally redundant across price, change, amplitude, turnover, speed, and capital-flow fields so provider schema drift does not collapse a valid universe to zero candidates.

Runtime requests are stored on the control plane at `bridge/request.json` on `master`; an empty symbol list means full-market discovery. The durable data plane is `fsis-data`.

Data publication invariants:

- Only snapshots with `status=OK` and `live_eligible=true` may replace `bridge/latest.json`.
- Partial or failed fetches update canonical `bridge/status.json` but never overwrite the last-known-good `latest.json`.
- Writes to `fsis-data` are excluded from the workflow's push trigger, preventing recursive self-triggering.
- Workflow runs in the same concurrency group are serialized; an in-flight snapshot is not cancelled by a later schedule/push event.
- `fsis-data` is the durable data branch and is protected from inverse-entropy reclamation.
- Market-data degradation is a state, not a workflow crash. The system must publish auditable degraded state and retain last-known-good data.
- Runtime code is checked out at the exact triggering commit so the runner cannot silently execute a mutable older revision.
- Provider access is bounded: EastMoney hosts are probed concurrently, then only one healthy host is paginated; Tencent pagination is bounded and used as heterogeneous fallback. This avoids provider-host fan-out that can amplify rate limits or connection failures.

Freshness authority is the published `fetched_at_bj`, `latest_bar_max` / `pit_cutoff_bar`, `stale_success_count`, and session date in `bridge/status.json`. A run is tradeable-live only when both full-market admission and minute-layer PIT admission are live. If freshness falls outside the registered FSIS tolerance, treat the data as DATA/EXECUTION-CONSTRAINED.
