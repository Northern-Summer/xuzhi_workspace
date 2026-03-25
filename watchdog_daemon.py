#!/usr/bin/env python3
"""
watchdog_daemon.py — Gateway 健康检查（一次性检查模式）
只做：健康检查 → 记录状态 → 连续 FAIL 次则重启
零 agent 通信，零 LLM 调用，幂等。

cron: * * * * * python3 .../watchdog_daemon.py
"""
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
CHECKPOINT = HOME / ".xuzhi_memory" / "watchdog_checkpoint.json"
STATE_FILE = HOME / ".xuzhi_watchdog" / "wd_state.json"
LOG       = HOME / ".xuzhi_watchdog" / "watchdog.log"
GATEWAY_URL = "http://localhost:18789/health"
OPENCLAW_CMD = "openclaw"
FAIL_THRESHOLD = 3  # 连续 3 次失败才重启（避免抖动）

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [wd] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(exist_ok=True, parents=True)
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
    CHECKPOINT.parent.mkdir(exist_ok=True, parents=True)
    with open(CHECKPOINT, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok" if ok else "fail"
        }, f)

def restart_gateway():
    log("🚨 连续失败达到阈值，执行 Gateway 重启")
    try:
        r = subprocess.run(
            [OPENCLAW_CMD, "gateway", "restart"],
            capture_output=True, text=True, timeout=30
        )
        log(f"✅ restart exit={r.returncode}")
    except Exception as e:
        log(f"❌ restart failed: {e}")

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"consecutive_fails": 0}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def tick():
    state = load_state()
    ok = check_gateway()
    write_checkpoint(ok)

    if ok:
        if state["consecutive_fails"] > 0:
            log(f"✅ 恢复（之前连续失败 {state['consecutive_fails']} 次）")
        state["consecutive_fails"] = 0
        log(f"✅ Gateway OK")
    else:
        state["consecutive_fails"] += 1
        log(f"❌ FAIL #{state['consecutive_fails']}")
        if state["consecutive_fails"] >= FAIL_THRESHOLD:
            restart_gateway()
            state["consecutive_fails"] = 0

    save_state(state)

if __name__ == "__main__":
    tick()
