#!/usr/bin/env python3
"""
watchdog_daemon.py — Xuzhi 系统看门狗（一次性检查模式）
crontab: * * * * * python3 ~/.xuzhi_memory/watchdog_daemon.py
每次运行执行一次检查，连续 FAIL_THRESHOLD 次失败则重启 Gateway。
"""
import sys
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
CHECKPOINT = HOME / ".xuzhi_memory" / "watchdog_checkpoint.json"
STATE_FILE = HOME / ".xuzhi_memory" / "task_center" / "wd_state.json"
LOG = HOME / ".xuzhi_memory" / "task_center" / "watchdog.log"

FAIL_THRESHOLD = 2   # 连续失败次数（达到则重启）
GATEWAY_URL = "http://localhost:18789/health"
OPENCLAW_CMD = "openclaw"

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [wd] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def check_gateway() -> bool:
    try:
        req = urllib.request.Request(GATEWAY_URL, headers={"User-Agent": "XuzhiWatchdog/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return '"ok"' in body or '"status"' in body or '"running"' in body
    except Exception:
        return False

def write_checkpoint(ok: bool):
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if ok else "fail",
        "check_interval_s": 60
    }
    with open(CHECKPOINT, "w") as f:
        json.dump(data, f)

def restart_gateway():
    log("🚨 连续失败达到阈值，执行 Gateway 重启")
    try:
        result = subprocess.run(
            [OPENCLAW_CMD, "gateway", "restart"],
            capture_output=True, text=True, timeout=30
        )
        log(f"✅ 重启命令已发送 (exit={result.returncode})")
    except Exception as e:
        log(f"❌ 重启失败: {e}")

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"consecutive_fails": 0}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def tick():
    state = load_state()
    ok = check_gateway()
    write_checkpoint(ok)

    if ok:
        if state["consecutive_fails"] > 0:
            log(f"✅ Gateway 恢复（之前连续失败 {state['consecutive_fails']} 次）")
        state["consecutive_fails"] = 0
        log(f"✅ Gateway 健康 (consecutive_fails=0)")
    else:
        state["consecutive_fails"] += 1
        log(f"❌ Gateway 检查失败 (连续第 {state['consecutive_fails']} 次)")
        if state["consecutive_fails"] >= FAIL_THRESHOLD:
            restart_gateway()
            state["consecutive_fails"] = 0

    save_state(state)

if __name__ == "__main__":
    tick()
