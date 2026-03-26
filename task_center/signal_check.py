#!/usr/bin/env python3
"""
signal_check.py — 检查并处理发给自己的 wake 信号
每个 agent 的心跳时自动调用。
幂等：N 次调用 = 1 次效果。
修复：ACK后还要dispatch（spawn session或写入待处理队列）
"""
import json, sys, subprocess, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
SIGNAL_DIR = HOME / ".xuzhi_watchdog" / "wake_signals"
WAKEUP_SH  = HOME / "xuzhi_genesis" / "centers" / "engineering" / "crown" / "wakeup_agent.sh"

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

def dispatch_wake(agent: str, reason: str) -> bool:
    """
    根据reason分发唤醒。
    watchdog_activate → 调用wakeup_agent.sh激活agent认领任务
    """
    if reason == "watchdog_activate":
        # 调用wakeup_agent.sh，幂等
        if not WAKEUP_SH.exists():
            print(f"[{agent}] wakeup_agent.sh not found at {WAKEUP_SH}")
            return False
        try:
            result = subprocess.run(
                ["bash", str(WAKEUP_SH), agent],
                capture_output=True, text=True, timeout=60,
                cwd=str(HOME)
            )
            if result.returncode == 0:
                print(f"[{agent}] ✅ wakeup dispatched")
                return True
            else:
                print(f"[{agent}] ❌ wakeup failed: {result.stderr[:100]}")
                return False
        except Exception as e:
            print(f"[{agent}] ❌ exception: {e}")
            return False
    else:
        print(f"[{agent}] unknown reason: {reason}, skipping dispatch")
        return False

def main():
    AGENT = sys.argv[1] if len(sys.argv) > 1 else None
    if not AGENT:
        print("用法: signal_check.py <AGENT_SYMBOL>")
        sys.exit(1)

    sig = check_and_ack(AGENT)
    if sig:
        reason = sig.get("reason", "")
        print(f"【{AGENT} 已收到唤醒信号】reason={reason} ts={sig.get('ts')}")
        # 真正dispatch
        ok = dispatch_wake(AGENT, reason)
        print(f"  dispatch={'✅' if ok else '❌'}")
    else:
        print(f"[{AGENT}] 无待处理信号")

if __name__ == "__main__":
    main()
