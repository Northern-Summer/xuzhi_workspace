#!/usr/bin/env python3
"""
heartbeat_tasks.py — 任务派发心跳
由 heartbeat_runner.py 每30分钟调用
与 unified_cron.sh 的 task_executor.py 共享逻辑，但这里是快速检查版本
"""
import subprocess, json, sys, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
LOG = HOME / ".xuzhi_memory" / "task_center" / "heartbeat_tasks.log"
TASKS_JSON = HOME / ".openclaw" / "tasks" / "tasks.json"
RL = HOME / "xuzhi_workspace" / "task_center" / "rate_limiter.py"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def quota_check():
    """快速quota检查（纯文件，不走HTTP）"""
    qfile = HOME / ".openclaw" / "centers" / "engineering" / "crown" / "quota_usage.json"
    if not qfile.exists():
        return False, "quota_guard: NO_FILE", 0
    try:
        d = json.loads(qfile.read_text())
        tier = d.get("5_hour", {})
        quota = tier.get("quota", 5000)
        used = tier.get("used", 0)
        pct = used / quota * 100 if quota > 0 else 0
        return True, f"quota_guard: OK ({pct:.1f}%)", pct
    except Exception as e:
        return False, f"quota_guard: ERROR {e}", 0

def rate_limit_acquire(source: str) -> bool:
    try:
        r = subprocess.run(["python3", str(RL), "acquire", source],
            capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except:
        return False

def get_waiting_tasks(limit=3):
    if not TASKS_JSON.exists():
        return []
    try:
        d = json.loads(TASKS_JSON.read_text())
        tasks = d if isinstance(d, list) else d.get("tasks", [])
        waiting = [t for t in tasks if t.get("status") == "等待"]
        return waiting[:limit]
    except:
        return []

def spawn_task_via_cron(task_id: int, prompt: str) -> bool:
    """派发单个任务到 isolated agent"""
    try:
        result = subprocess.run(
            [
                "openclaw", "cron", "add",
                "--session", "isolated",
                "--no-deliver",
                "--name", f"htask-{task_id}-{int(time.time())}",
                "--at", "10m",
                "--message", prompt,
            ],
            capture_output=True, text=True, timeout=20, cwd=str(HOME)
        )
        if result.returncode == 0:
            try:
                j = json.loads(result.stdout)
                log(f"✅ task #{task_id}: cron job {j.get('id','?')} created")
            except:
                log(f"✅ task #{task_id}: spawned (output: {result.stdout[:80]})")
            return True
        else:
            err = result.stderr.strip() or result.stdout.strip()
            log(f"❌ task #{task_id}: spawn failed — {err[:100]}")
            return False
    except Exception as e:
        log(f"❌ task #{task_id}: exception — {e}")
        return False

def check_wake_signals():
    """检查所有wake信号并dispatch"""
    SIGNAL_DIR = HOME / ".xuzhi_watchdog" / "wake_signals"
    SC = HOME / "xuzhi_workspace" / "task_center" / "signal_check.py"
    if not SIGNAL_DIR.exists():
        return
    dispatched = 0
    for sf in sorted(SIGNAL_DIR.glob("wake_*.json")):
        try:
            sig = json.loads(sf.read_text())
            if sig.get("status") != "pending":
                continue
            agent = sig.get("agent", "?")
            reason = sig.get("reason", "")
            log(f"[wake] {agent} signal pending: {reason}")
            result = subprocess.run(
                ["python3", str(SC), agent],
                capture_output=True, text=True, timeout=30
            )
            out = result.stdout.strip()
            if out:
                log(f"[wake] {agent}: {out}")
            dispatched += 1
        except Exception as e:
            pass
    if dispatched:
        log(f"[wake] dispatched {dispatched} wake signal(s)")

def main():
    log("=== heartbeat_tasks: 开始 ===")
    
    # 1. Quota检查
    ok, msg, pct = quota_check()
    log(f"Quota 检查通过: [{datetime.now(timezone.utc).isoformat()}] {msg}")
    if not ok:
        log("Quota 不可用，跳过派发")
        log("=== heartbeat_tasks: 派发 0 个任务 ===")
        # 仍然检查wake signals
        check_wake_signals()
        return
    
    # 2. 获取等待任务
    waiting = get_waiting_tasks(limit=3)
    log(f"等待任务: {len(waiting)} 个")
    
    if not waiting:
        log("=== heartbeat_tasks: 派发 0 个任务 ===")
        check_wake_signals()
        return
    
    # 3. 逐个派发
    dispatched = 0
    for task in waiting:
        tid = task.get("id", "?")
        title = task.get("title", "")[:50]
        dept = task.get("department", "engineering")
        
        if not rate_limit_acquire(f"heartbeat_task:{tid}"):
            log(f"Rate limiter 禁止派发（窗口满或冷却中）")
            break
        
        prompt = (
            f"执行任务 #{tid}: {title}\n"
            f"部门: {dept}\n"
            f"描述: {task.get('description','')}\n"
            f"验收标准: {task.get('acceptance_criteria','')}\n"
            f"完成后调用: python3 {HOME}/xuzhi_genesis/centers/task/complete_task.py {tid}"
        )
        
        ok = spawn_task_via_cron(tid, prompt)
        if ok:
            dispatched += 1
        time.sleep(2)  # 避免gateway过载
    
    log(f"=== heartbeat_tasks: 派发 {dispatched} 个任务 ===")
    
    # 4. 检查wake signals
    check_wake_signals()

if __name__ == "__main__":
    main()
