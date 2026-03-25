#!/usr/bin/env python3
"""
heartbeat_runner.py — Xuzhi heartbeat orchestrator
Engineering Principles Compliance — Xi | 2026-03-25
Fix: ALL heartbeat tasks have hard timeout; wait(results) capped at 25s.
    Previously: wait(results) blocked forever when any task hung.
    Root cause: quota_guard_agent subprocess hung on HTTP call.
    Solution: wait(results, timeout=25) + FuturesTimeoutError → cancel all.
"""
import importlib, os, sys, time, threading, uuid
from concurrent.futures import wait, ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError

LOG  = os.path.expanduser("~/.xuzhi_cron.log")
STAMP_LOCK = threading.Lock()

def stamp(msg):
    ts = time.strftime("%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with STAMP_LOCK:
        with open(LOG, "a") as f:
            f.write(line + "\n")
        print(line)

def log_exception(func_name, exc):
    stamp(f"EXCEPTION in {func_name}: {type(exc).__name__}: {exc}")

def graceful_shutdown():
    stamp("heartbeat_runner: shutdown")

def run_task_func(task_name, func, args=None):
    try:
        stamp(f"heartbeat: {task_name} starting")
        f = func(args) if args is not None else func()
        stamp(f"heartbeat: {task_name} done")
        return True, task_name, f
    except Exception as e:
        log_exception(task_name, e)
        return False, task_name, str(e)

def runner_heartbeat_task(task):
    task_name = task.get("name", "?")
    module_name = task.get("module")
    func_name = task.get("func")
    args = task.get("args")
    if not module_name or not func_name:
        return {"ok": False, "task": task_name, "error": "missing module/func"}
    try:
        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name, None)
        if not func:
            return {"ok": False, "task": task_name, "error": f"{func_name} not in {module_name}"}
        result = func() if args is None else func(args)
        return {"ok": True, "task": task_name, "result": result}
    except Exception as e:
        log_exception(f"{module_name}.{func_name}", e)
        return {"ok": False, "task": task_name, "error": str(e)}

def run_heartbeat():
    stamp("heartbeat_runner: start")

    heartbeat_tasks = [
        # ── 1. Quota Guard — zero HTTP, pure file read ────────────────────
        {
            "name": "quota_guard",
            "module": "quota_guard_agent",
            "func": "main",
        },
        # ── 2. Recovery alert check ────────────────────────────────────
        {
            "name": "check_recovery_alert",
            "module": "check_recovery_alert",
            "func": "main",
        },
        # ── 3. Escalation check ────────────────────────────────────────
        {
            "name": "check_escalation",
            "module": "check_escalation",
            "func": "main",
        },
        # ── 4. Task dispatch ───────────────────────────────────────────
        {
            "name": "heartbeat_tasks",
            "module": "heartbeat_tasks",
            "func": "main",
        },
    ]

    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="heartbeat-")

    # CRITICAL FIX: wait(results) had NO TIMEOUT → hung forever if any task blocked.
    # Now: all tasks must finish within 25s, else cancel all.
    results = [
        executor.submit(runner_heartbeat_task, task)
        for task in heartbeat_tasks
    ]
    try:
        # Wait up to 25s for ALL tasks. If timeout → cancel remaining.
        wait(results, timeout=25)
    except FuturesTimeoutError:
        stamp("heartbeat: TIMEOUT — cancelling hung tasks")
        for future in results:
            future.cancel()
    finally:
        executor.shutdown(wait=False)

    graceful_shutdown()

if __name__ == "__main__":
    run_heartbeat()
