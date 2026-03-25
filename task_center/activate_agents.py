#!/usr/bin/env python3
"""
activate_agents.py — 轻量 agent 激活（零递归 spawn）
用文件信号替代 openclaw cron add，零新 session 创建。
"""
import json, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
SIGNAL_DIR = HOME / ".xuzhi_watchdog" / "wake_signals"
SIGNAL_DIR.mkdir(exist_ok=True, parents=True)

RATINGS = HOME / "xuzhi_genesis" / "centers" / "mind" / "society" / "ratings.json"
AGENTS = ["Φ", "Δ", "Θ", "Γ", "Ω", "Ψ"]


def activate_agent(agent_symbol):
    """
    向目标 agent 的 wake signal 文件写入激活信号。
    目标 agent 下次心跳时读到信号，自行处理。
    不创建新 session，不递归 spawn。
    """
    signal_file = SIGNAL_DIR / f"wake_{agent_symbol}.json"
    with open(signal_file, 'w') as f:
        json.dump({
            "agent": agent_symbol,
            "ts": datetime.now(timezone.utc).isoformat(),
            "reason": "watchdog_activate",
            "status": "pending"
        }, f)
    print(f"信号已写入: {signal_file}")
    return True


def check_signals(agent_symbol):
    """Agent 自己调用：检查是否有发给自己的 wake 信号"""
    signal_file = SIGNAL_DIR / f"wake_{agent_symbol}.json"
    if signal_file.exists():
        try:
            with open(signal_file) as f:
                sig = json.load(f)
            sig["status"] = "acknowledged"
            sig["acked_at"] = datetime.now(timezone.utc).isoformat()
            with open(signal_file, 'w') as f:
                json.dump(sig, f, indent=2)
            return sig
        except:
            signal_file.unlink()
            return None
    return None


def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: activate_agents.py <agent_symbol>")
        print("      activate_agents.py --check <agent_symbol>")
        sys.exit(1)

    if sys.argv[1] == "--check":
        agent = sys.argv[2]
        sig = check_signals(agent)
        if sig:
            print(f"收到唤醒信号: {sig}")
        else:
            print("无待处理唤醒信号")
        return

    agent = sys.argv[1]
    activate_agent(agent)


if __name__ == "__main__":
    main()
