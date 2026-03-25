# HEARTBEAT.md — Zero-Blocking Pure Python Edition
## Engineering Principles Compliance — Xi | 2026-03-25
## 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES
## 修复：外部脚本调用 → 内联逻辑，零 subprocess，零阻塞，零 exec 占用

import json, os
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
WD   = HOME / ".openclaw" / "workspace"
WDOG = HOME / ".xuzhi_watchdog"
WDOG.mkdir(exist_ok=True)

QUOTA_HARD = 70.0
QUOTA_SOFT = 60.0
ts = datetime.now(timezone.utc).isoformat()

# ── 1. Quota Guard (inline, read file only) ─────────────────────────
quota_file = WD / "quota_status.json"
pct = None
if quota_file.exists():
    try:
        d = json.loads(quota_file.read_text())
        for t in d.get("tiers", []):
            if t.get("name") == "5_hour":
                pct = t.get("pct", 0)
                break
    except Exception:
        pass

exhausted_file = WDOG / "quota_exhausted"
rate_hold_file  = WDOG / "rate_limit_hold"

if pct is not None:
    if pct >= QUOTA_HARD:
        exhausted_file.write_text(f"{ts}\n")
        print(f"[{ts}] quota_guard: EXHAUSTED ({pct:.1f}%)")
    elif pct >= QUOTA_SOFT:
        rate_hold_file.write_text(f"{ts}\n")
        print(f"[{ts}] quota_guard: WARNING ({pct:.1f}%)")
    else:
        if exhausted_file.exists(): exhausted_file.unlink()
        if rate_hold_file.exists(): rate_hold_file.unlink()
        print(f"[{ts}] quota_guard: OK ({pct:.1f}%)")
else:
    print(f"[{ts}] quota_guard: QUOTA_FILE_UNREADABLE")

# ── 2. Gateway Recovery Alert (file check, zero wait) ──────────────
recovery_file = WDOG / "recovery_trigger"
if recovery_file.exists():
    content = recovery_file.read_text().strip()
    if content:
        print(f"[{ts}] RECOVERY_ALERT: {content}")

# ── 3. Restart Loop Escalation (file check, zero wait) ────────────────
escalation_file = WDOG / "escalation_alert"
if escalation_file.exists():
    content = escalation_file.read_text().strip()
    if content:
        print(f"[{ts}] ESCALATION: {content}")

# ── 4. Task State Check (read file only) ────────────────────────────
tasks_state = WD / ".tasks_state.json"
if tasks_state.exists():
    try:
        td = json.loads(tasks_state.read_text())
        pending = [t for t in td.get("tasks", []) if t.get("status") == "pending"]
        print(f"[{ts}] tasks: {len(pending)} pending")
    except Exception:
        pass

# ── Done ────────────────────────────────────────────────────────────
print(f"[{ts}] HEARTBEAT: OK")
