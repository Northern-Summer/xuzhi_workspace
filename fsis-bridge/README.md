# FSIS Minute Bridge

Purpose: provide FSIS with a machine-readable, auditable A-share 1-minute snapshot without requiring the ChatGPT Web runtime to make arbitrary outbound HTTP calls.

Architecture:

`GitHub Actions scheduler -> East Money public HTTP K-line endpoint -> normalized JSON -> GitHub repository -> FSIS Web retrieval`

The bridge is deliberately a data transport layer, not a trading engine. FSIS must still validate freshness, point-in-time date, continuity, missing/duplicate bars, security mapping, and source provenance before live admission.

Current cadence: every 5 minutes during the A-share daytime window (UTC 01:00-07:59, Monday-Friday), plus manual dispatch. This is a snapshot bridge, not a tick feed. It must not be described as sub-minute or exchange-direct.

The default universe is a small liquid ETF/benchmark/theme set. `FSIS_SYMBOLS` can be supplied as a workflow environment variable when a broader candidate universe is required.

Important: GitHub Actions scheduling can be delayed. The `fetched_at_bj`, `latest_bar_ts`, and session date in `bridge/status.json` are authoritative for freshness checks. If freshness is outside the registered FSIS tolerance, the data is DATA/EXECUTION-CONSTRAINED.
