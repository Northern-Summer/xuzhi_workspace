#!/usr/bin/env python3
"""
expert_watchdog.py — Expert Tracker 链健康检查
每 2 小时运行一次，检测 Expert Tracker 生命周期是否断裂。
断裂时触发修复。
"""
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
STATE_FILE = HOME / ".xuzhi_watchdog" / "expert_wd_state.json"
LOG_FILE   = HOME / ".xuzhi_watchdog" / "expert_watchdog.log"
TASKS      = HOME / ".xuzhi_memory" / "expert_tracker" / "activity.json"
CHANGES    = HOME / ".xuzhi_memory" / "expert_tracker" / "changes.json"
LEARNER    = HOME / ".xuzhi_workspace" / "bin" / "expert_learner.py"
EXECUTOR   = HOME / ".xuzhi_workspace" / "task_center" / "task_executor.py"
MEM_DIR    = HOME / ".xuzhi_memory" / "memory"

import sys
sys.path.insert(0, str(HOME / "xuzhi_workspace" / "task_center"))
from memory_api import add_episode

# ─── 日志 ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def record(agent, task_type, inp, out, status):
    """双重输出：stdout + L2 SQLite"""
    log(f"{agent}: {out}")
    try:
        add_episode(agent, task_type, inp[:200], out[:200], status)
    except Exception as e:
        log(f"L2 写入失败: {e}")

# ─── 检查 ───────────────────────────────────────────────────────────────────

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def check_tracker():
    """检查 expert_tracker 是否活跃（有活动记录且最近更新）"""
    data = load_json(TASKS, {"activities": {}, "last_update": None})
    activities = data.get("activities", {})
    last_update = data.get("last_update", "")
    has_activities = len(activities) > 0
    if last_update:
        try:
            from datetime import datetime, timezone
            lu = datetime.fromisoformat(last_update)
            age_h = (datetime.now(timezone.utc) - lu).total_seconds() / 3600
            recent = age_h < 48
        except:
            recent = False
    else:
        recent = False
    ok = has_activities and recent
    msg = f"activities={len(activities)}, last_update={last_update[:16] if last_update else 'none'}"
    return ok, msg

def check_changes():
    data = load_json(CHANGES, {"discoveries": []})
    recent = data.get("discoveries", [])[-3:]
    if not recent:
        return False, "无changes记录"
    latest = recent[-1].get("discovered_at", "")
    return True, f"最后change: {latest}"

def check_learning_tasks():
    tasks_data = load_json(TASKS, [])
    if isinstance(tasks_data, list):
        tasks = tasks_data
    else:
        tasks = tasks_data.get("tasks", [])
    learn = [t for t in tasks if isinstance(t.get("id"), int) and 130 <= t.get("id", 0) <= 160]
    if not learn:
        return False, "无learning任务"
    waiting = sum(1 for t in learn if t.get("status") == "等待")
    done    = sum(1 for t in learn if t.get("status") == "完成")
    doing   = sum(1 for t in learn if t.get("status") == "进行")
    return True, f"完成={done} 进行={doing} 等待={waiting}"

def check_memory_updated():
    if not MEM_DIR.exists():
        return False, "memory目录不存在"
    agents = ["lambda", "delta", "phi", "omega", "gamma", "theta", "psi"]
    updated = []
    for agent in agents:
        fp = MEM_DIR / f"{agent}.md"
        if fp.exists():
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
            age_h = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            if age_h < 24:
                updated.append(f"{agent}({age_h:.1f}h)")
    if updated:
        return True, f"最近更新: {', '.join(updated)}"
    return False, "24h内无memory更新"

def trigger(action):
    if action == "expert_learner":
        r = subprocess.run(["python3", str(LEARNER)],
                          capture_output=True, text=True, timeout=60)
        return r.returncode == 0, r.stdout.strip()[:100] if r.returncode == 0 else r.stderr.strip()[:100]
    elif action == "task_executor":
        r = subprocess.run(["python3", str(EXECUTOR)],
                          capture_output=True, text=True, timeout=30)
        return r.returncode == 0, r.stdout.strip()[:100] if r.returncode == 0 else r.stderr.strip()[:100]
    return False, "unknown action"

def main():
    state = load_json(STATE_FILE, {"stall_count": 0, "chain_broken": False})
    log("=== Expert Watchdog 开始 ===")

    checks = [
        ("expert_watchdog", "tracker_check",   check_tracker),
        ("expert_watchdog", "changes_check",   check_changes),
        ("expert_watchdog", "learning_tasks", check_learning_tasks),
        ("expert_watchdog", "memory_updated", check_memory_updated),
    ]

    broken = False
    for agent, task, fn in checks:
        ok, msg = fn()
        record(agent, task, task, msg, "success" if ok else "failure")
        if not ok:
            broken = True

    if broken:
        state["stall_count"] += 1
        state["chain_broken"] = True
        log(f"⚠️  链断裂第 {state['stall_count']} 次")

        if state["stall_count"] >= 2:
            ok1, msg1 = trigger("expert_learner")
            record("expert_watchdog", "recovery_learner", "触发修复", msg1,
                   "success" if ok1 else "failure")
            if ok1:
                ok2, msg2 = trigger("task_executor")
                record("expert_watchdog", "recovery_executor", "触发执行", msg2,
                       "success" if ok2 else "failure")
                if ok2:
                    state["stall_count"] = 0
                    state["chain_broken"] = False
                    log(f"✅ 链恢复")
    else:
        if state["chain_broken"]:
            log(f"✅ 链恢复（之前断裂{state['stall_count']}次）")
        state["stall_count"] = 0
        state["chain_broken"] = False

    save_state(state)
    log(f"=== Watchdog 完成 ===")

if __name__ == "__main__":
    main()
