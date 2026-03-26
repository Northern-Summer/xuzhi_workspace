#!/usr/bin/env python3
"""system_activity_notify.py — 所有智能体共读写文件的状态摘要"""
import json
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
ts = datetime.now(timezone.utc).strftime("%m-%d %H:%M GMT")

# ── 1. ratings.json (7个agent的活跃状态) ──────────────────────────
r = HOME / "xuzhi_genesis/centers/mind/society/ratings.json"
agents = []
if r.exists():
    d = json.load(open(r))
    for greek, info in d.get("agents", {}).items():
        rel = info.get("reliability", 0)
        act = info.get("last_active", "?")
        note = info.get("notes", "")
        agents.append(f"  {greek}: rel={rel:.0%} | {note} | last={act[:16]}")

# ── 2. queue.json (待处理任务) ──────────────────────────────────
q = HOME / "xuzhi_genesis/centers/engineering/crown/queue.json"
queue_info = "无"
if q.exists():
    d = json.load(open(q))
    items = d.get("queue", [])
    total = len(items)
    xi_count = items.count("Ξ") if isinstance(items, list) else 0
    queue_info = f"{total}个名额，Ξ获{xi_count}个"

# ── 3. quota_usage ────────────────────────────────────────────────
qu = HOME / ".openclaw/centers/engineering/crown/quota_usage.json"
quota_info = "?"
if qu.exists():
    d = json.load(open(qu))
    t = d.get("5_hour", {})
    used = t.get("used", 0)
    total = t.get("quota", 5000)
    pct = used / total * 100 if total else 0
    quota_info = f"{used}/{total} ({pct:.0f}%)"

# ── 4. expert_tracker ─────────────────────────────────────────────
ea = HOME / ".xuzhi_memory/expert_tracker/activity.json"
expert_count = "?"
if ea.exists():
    d = json.load(open(ea))
    expert_count = str(len(d.get("activities", [])))

# ── 5. expert_cycle ───────────────────────────────────────────────
ec = HOME / ".xuzhi_memory/task_center/.expert_cycle"
cycle = ec.read_text().strip() if ec.exists() else "?"

# ── 组装消息 ───────────────────────────────────────────────────────
lines = [
    f"📊 Xuzhi系统状态 {ts}",
    "─" * 28,
    f"💬 ratings.json — 7个agent活跃",
]
lines += agents

lines += [
    "",
    f"📋 queue.json    — {queue_info}",
    f"⚡ quota_usage  — {quota_info}",
    f"🔬 expert_cycle — {cycle} (expert_tracker: {expert_count}条)",
    "─" * 28,
]

print("\n".join(lines))
