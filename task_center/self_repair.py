#!/usr/bin/env python3
"""
Xuzhi 自动修复引擎 — 无 LLM 依赖
每次运行自动修复已知模式的问题，不消耗 POST。
"""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

HOME = Path.home()
TASKS = HOME / ".openclaw" / "tasks" / "tasks.json"
HEAL_LOG = HOME / ".xuzhi_memory" / "heal.log"
LOG = HOME / ".xuzhi_memory" / "task_center" / "self_repair.log"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} [repair] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def atomic_write(path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.rename(path)

def fix_tasks_dedup():
    """P1: tasks.json 去重"""
    try:
        with open(TASKS) as f:
            tasks = json.load(f)
    except Exception as e:
        log(f"P1 跳过（读取失败）: {e}")
        return False

    ids = [t["id"] for t in tasks]
    dupes = [k for k, v in Counter(ids).items() if v > 1]
    if not dupes:
        log(f"P1 ✅ 无重复ID")
        return False

    by_id = {}
    for t in tasks:
        by_id.setdefault(t["id"], []).append(t)

    STATUS_PRIORITY = {"进行": 0, "完成": 1, "等待": 2, "open": 3, "放弃": 4}
    deduped = []
    removed = 0
    for tid, items in by_id.items():
        if len(items) == 1:
            deduped.append(items[0])
        else:
            best = min(items, key=lambda t: STATUS_PRIORITY.get(t.get("status", "放弃"), 99))
            deduped.append(best)
            removed += len(items) - 1
            log(f"  去重 id={tid}: 保留 {best.get('status')}")

    log(f"P1 🔧 去重：{len(tasks)}→{len(deduped)}，删{removed}条")
    atomic_write(TASKS, deduped)
    return True

def fix_stale_tasks():
    """P3: 清理超2小时的'进行中'任务"""
    try:
        with open(TASKS) as f:
            tasks = json.load(f)
    except Exception as e:
        log(f"P3 跳过: {e}")
        return False

    now = datetime.now(timezone.utc)
    stale = []
    for t in tasks:
        if t.get("status") == "进行":
            claimed = t.get("participant_times", {})
            if claimed:
                last = list(claimed.values())[0]
                try:
                    dt_str = last.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt_str)
                    if (now - dt).total_seconds() > 7200:
                        stale.append(t["id"])
                        t["status"] = "放弃"
                        t["completion_report"] = "自动清理（超时>2h）"
                except Exception:
                    pass

    if stale:
        log(f"P3 🔧 清理{len(stale)}个卡死任务: {stale}")
        atomic_write(TASKS, tasks)
        return True
    log(f"P3 ✅ 无卡死任务")
    return False

def fix_heal_log():
    """P5: heal.log 截断（>500行→保留后200行）"""
    if not HEAL_LOG.exists():
        return False
    try:
        with open(HEAL_LOG) as f:
            lines = f.readlines()
    except Exception as e:
        log(f"P5 跳过: {e}")
        return False
    if len(lines) <= 500:
        log(f"P5 ✅ heal.log {len(lines)}行，无需截断")
        return False
    trimmed = lines[-200:]
    with open(HEAL_LOG, "w") as f:
        f.writelines(trimmed)
    log(f"P5 🔧 heal.log: {len(lines)}→{len(trimmed)}行")
    return True

def run():
    log("=== 自动修复开始 ===")
    fixed = 0
    fixed += 1 if fix_tasks_dedup() else 0
    fixed += 1 if fix_stale_tasks() else 0
    fixed += 1 if fix_heal_log() else 0
    log(f"=== 完成: {fixed} 项修复 ===")

if __name__ == "__main__":
    run()
