#!/usr/bin/env python3
"""
expert_watchdog.py — Expert Learning 闭环 watchdog
每轮 unified_cron 后运行，验证 expert learning 链是否断了。
如果断了，自动触发修复或告警。
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

HOME = Path.home()
CHANGES   = HOME / ".xuzhi_memory" / "expert_tracker" / "changes.json"
ACTIVITY  = HOME / ".xuzhi_memory" / "expert_tracker" / "activity.json"
LEARNER   = HOME / ".xuzhi_memory" / "task_center" / "expert_learner.py"
EXECUTOR  = HOME / ".xuzhi_memory" / "task_executor.py"
TASKS     = HOME / ".openclaw" / "tasks" / "tasks.json"
LOG       = HOME / ".xuzhi_memory" / "expert_tracker" / "watchdog.log"
STATE     = HOME / ".xuzhi_memory" / "task_center" / "expert_watchdog_state.json"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} [expert-wd] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def check_expert_tracker():
    """检查 expert_tracker 是否在跑"""
    changes = load_json(CHANGES, {})
    last = changes.get("last_run", "")
    if not last:
        return False, "changes.json无last_run"
    try:
        dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        return age_h < 8, f"最后运行: {age_h:.1f}h前"
    except:
        return False, "last_run格式错误"

def check_changes_fresh():
    """检查是否有新 changes"""
    changes = load_json(CHANGES, {})
    recent = changes.get("changes", [])
    if not recent:
        return False, "无changes记录"
    latest = recent[-1].get("discovered_at", "")
    return True, f"最后change: {latest}"

def check_learning_tasks():
    """检查 expert learning 任务状态"""
    tasks = load_json(TASKS, [])
    if not isinstance(tasks, list):
        tasks = tasks.get("tasks", [])
    learn = [t for t in tasks if isinstance(t.get("id"), int) and 130 <= t.get("id", 0) <= 160]
    if not learn:
        return False, "无learning任务"
    waiting = sum(1 for t in learn if t.get("status") == "等待")
    done = sum(1 for t in learn if t.get("status") == "完成")
    doing = sum(1 for t in learn if t.get("status") == "进行")
    return True, f"完成={done} 进行={doing} 等待={waiting}"

def check_memory_updated():
    """检查 agent memory 是否被更新（expert learning 结果）"""
    memory_dir = HOME / ".xuzhi_memory" / "memory"
    if not memory_dir.exists():
        return False, "memory目录不存在"
    agents = ["lambda", "delta", "phi", "omega", "gamma", "theta", "psi"]
    updated = []
    for agent in agents:
        fp = memory_dir / f"{agent}.md"
        if fp.exists():
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
            age_h = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            if age_h < 24:
                updated.append(f"{agent}({age_h:.1f}h)")
    if updated:
        return True, f"最近更新: {', '.join(updated)}"
    return False, "24h内无memory更新"

def trigger_recovery(action):
    """触发修复"""
    import subprocess
    if action == "expert_learner":
        log("→ 触发 expert_learner...")
        r = subprocess.run(["python3", str(LEARNER)],
                          capture_output=True, text=True, timeout=60)
        return r.returncode == 0, r.stdout.strip()[:100]
    elif action == "task_executor":
        log("→ 触发 task_executor...")
        r = subprocess.run(["python3", str(EXECUTOR)],
                          capture_output=True, text=True, timeout=30)
        return r.returncode == 0, r.stdout.strip()[:100]

def main():
    log("=== Expert Watchdog 开始 ===")

    results = {}
    results["tracker"] = check_expert_tracker()
    results["changes"] = check_changes_fresh()
    results["tasks"] = check_learning_tasks()
    results["memory"] = check_memory_updated()

    for k, (ok, msg) in results.items():
        status = "✅" if ok else "❌"
        log(f"  {status} {k}: {msg}")

    state = load_json(STATE, {"stall_count": 0, "last_recovery": None})

    # 判断是否需要修复
    needs_fix = not results["tasks"][0] or not results["memory"][0]

    if needs_fix:
        state["stall_count"] += 1
        log(f"⚠️  链断裂第 {state['stall_count']} 次")
        if state["stall_count"] >= 2:
            # 触发 expert_learner
            ok, msg = trigger_recovery("expert_learner")
            if ok:
                log(f"✅ expert_learner 触发成功: {msg}")
                state["stall_count"] = 0
                state["last_recovery"] = datetime.now(timezone.utc).isoformat()
            else:
                log(f"❌ expert_learner 触发失败: {msg}")
    else:
        if state["stall_count"] > 0:
            log(f"✅ 链恢复（之前断裂{state['stall_count']}次）")
        state["stall_count"] = 0

    save_json(STATE, state)
    log(f"=== Watchdog 完成 ===")

if __name__ == "__main__":
    main()
