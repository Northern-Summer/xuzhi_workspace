#!/usr/bin/env python3
"""
quarantine.py — 不可抗力认知黑名单
策略二核心实现：同一宿主的物理阻力连续失败3次 → 认知放弃 + 记录

原则：
- 有些问题是硬件层，无法通过代码修补
- 连续3次修补失败 → 承认缺陷存在 → 记录在案 → 找替代方案
- 不在死循环里浪费算力
"""
import json, sys, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
QUARANTINE_DB = HOME / ".xuzhi_memory" / "task_center" / "quarantine_db.json"
BLACKLIST = HOME / ".xuzhi_memory" / "task_center" / "system_deadlock_blacklist.md"
MAX_RETRIES = 3

def log(msg: str):
    print(f"[quarantine] {msg}", flush=True)

def load_db() -> dict:
    if QUARANTINE_DB.exists():
        try:
            return json.loads(QUARANTINE_DB.read_text())
        except Exception:
            pass
    return {"entries": {}, "blacklist": []}

def save_db(db: dict):
    QUARANTINE_DB.parent.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DB.write_text(json.dumps(db, indent=2))

def record_failure(key: str, attempt: str, error: str) -> dict:
    """
    记录一次失败。返回当前状态：
      {"status": "retrying", "attempts": N}
      {"status": "quarantined", "attempts": N, "since": ts}
    """
    db = load_db()
    now = time.time()

    if key not in db["entries"]:
        db["entries"][key] = {"attempts": 0, "history": [], "quarantined_at": None}

    entry = db["entries"][key]
    entry["attempts"] += 1
    entry["history"].append({
        "at": now,
        "attempt_id": attempt,
        "error": error[:200],
    })
    # 只保留最近5条历史
    entry["history"] = entry["history"][-5:]

    if entry["attempts"] >= MAX_RETRIES and not entry["quarantined_at"]:
        entry["quarantined_at"] = now
        entry["status"] = "quarantined"
        add_to_blacklist(key, error)
        save_db(db)
        log(f"🚫 {key} → QUARANTINED（{MAX_RETRIES}次失败）")
        return {"status": "quarantined", "attempts": entry["attempts"]}

    save_db(db)
    return {"status": "retrying", "attempts": entry["attempts"]}

def add_to_blacklist(key: str, error: str):
    """追加到系统级死角黑名单"""
    entry = f"""
## [{key}] — 认知放弃时间: {datetime.now(timezone.utc).isoformat()}

**错误摘要**: {error[:300]}
**处理**: 接受该缺陷存在，寻求替代方案，不刚性修复。

"""
    BLACKLIST.parent.mkdir(parents=True, exist_ok=True)
    with open(BLACKLIST, "a") as f:
        f.write(entry)

def is_quarantined(key: str) -> bool:
    db = load_db()
    return db["entries"].get(key, {}).get("quarantined_at") is not None

def check(key: str) -> dict:
    """
    检查 key 是否在黑名单中。
    返回：(can_proceed: bool, reason: str)
    """
    db = load_db()
    entry = db["entries"].get(key)
    if not entry:
        return True, "not_seen"
    if entry.get("quarantined_at"):
        return False, f"QUARANTINED at {datetime.fromtimestamp(entry['quarantined_at'], tz=timezone.utc).isoformat()}"
    remaining = MAX_RETRIES - entry["attempts"]
    return True, f"attempts_remaining:{remaining}"

def status() -> dict:
    db = load_db()
    quarantined = [k for k, v in db["entries"].items() if v.get("quarantined_at")]
    return {
        "total_keys": len(db["entries"]),
        "quarantined_count": len(quarantined),
        "quarantined": quarantined,
        "active": [k for k, v in db["entries"].items() if not v.get("quarantined_at")],
    }

def clear(key: str = None):
    """清除黑名单（人工授权后）"""
    db = load_db()
    if key:
        if key in db["entries"]:
            del db["entries"][key]
            save_db(db)
            log(f"✅ cleared: {key}")
    else:
        db = {"entries": {}, "blacklist": []}
        save_db(db)
        log("✅ all cleared")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "check":
        key = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        ok, reason = check(key)
        print(f"{'PROCEED' if ok else 'BLOCKED'}:{reason}", flush=True)
        sys.exit(0 if ok else 1)

    elif cmd == "record":
        key = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        attempt_id = sys.argv[3] if len(sys.argv) > 3 else "n/a"
        error = sys.argv[4] if len(sys.argv) > 4 else ""
        result = record_failure(key, attempt_id, error)
        print(json.dumps(result), flush=True)
        sys.exit(0 if result["status"] != "quarantined" else 1)

    elif cmd == "status":
        print(json.dumps(status(), indent=2), flush=True)

    elif cmd == "clear":
        key = sys.argv[2] if len(sys.argv) > 2 else None
        clear(key)

    else:
        print(f"Unknown: {cmd}", flush=True)
