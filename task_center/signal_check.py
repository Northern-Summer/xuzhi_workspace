#!/usr/bin/env python3
"""
signal_check.py — 检查并处理发给自己的 wake 信号
每个 agent 的心跳时自动调用。
幂等：N 次调用 = 1 次效果。
"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
AGENT = sys.argv[1] if len(sys.argv) > 1 else None
SIGNAL_DIR = HOME / ".xuzhi_watchdog" / "wake_signals"

def check_and_ack(agent: str) -> dict | None:
    """检查发给自己的信号，ack 并返回"""
    sig_file = SIGNAL_DIR / f"wake_{agent}.json"
    if not sig_file.exists():
        return None
    try:
        with open(sig_file) as f:
            sig = json.load(f)
        if sig.get("status") == "acknowledged":
            return None
        sig["status"] = "acknowledged"
        sig["acked_at"] = datetime.now(timezone.utc).isoformat()
        with open(sig_file, "w") as f:
            json.dump(sig, f, indent=2)
        return sig
    except Exception:
        return None

if __name__ == "__main__":
    if not AGENT:
        print("用法: signal_check.py <AGENT_SYMBOL>")
        sys.exit(1)
    sig = check_and_ack(AGENT)
    if sig:
        print(f"【{AGENT} 已收到唤醒信号】reason={sig.get('reason')} ts={sig.get('ts')}")
    else:
        print(f"[{AGENT}] 无待处理信号")
