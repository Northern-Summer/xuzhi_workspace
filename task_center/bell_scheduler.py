#!/usr/bin/env python3
"""
bell_scheduler.py — 动态铃铛调度器
有提案在流动 → 高频铃（2分钟）
无提案 → 低频铃（30分钟）
幂等，无竞态。
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

FLOW_FILE = Path.home() / ".xuzhi_genesis" / "centers" / "mind" / "parliament" / "flow.json"
STATE_FILE = Path.home() / ".xuzhi_watchdog" / "bell_state.json"

HIGH_MS  = 2 * 60 * 1000     # 2 分钟
LOW_MS   = 30 * 60 * 1000    # 30 分钟
now_ms   = lambda: int(datetime.now(timezone.utc).timestamp() * 1000)

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"interval_ms": LOW_MS, "last_rung": 0, "mode": "low"}

def save_state(s):
    STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
    STATE_FILE.write_text(json.dumps(s, indent=2))

def has_active_proposal() -> bool:
    if not FLOW_FILE.exists():
        return False
    try:
        d = json.loads(FLOW_FILE.read_text())
        return len(d.get("proposals", [])) > 0
    except:
        return False

def compute_next_interval(has_active: bool, state: dict) -> int:
    """计算下次铃铛间隔"""
    if has_active:
        return HIGH_MS
    return LOW_MS

def main():
    state = load_state()
    has_active = has_active_proposal()
    next_interval = compute_next_interval(has_active, state)

    if next_interval != state["interval_ms"]:
        old = state["interval_ms"]
        state["interval_ms"] = next_interval
        mode = "HIGH(2m)" if has_active else "LOW(30m)"
        print(f"[bell_scheduler] 切换模式: {mode}")
        save_state(state)

    # 打印下次应该铃的时间
    next_run = now_ms() + next_interval
    print(f"[bell_scheduler] 下次铃: +{next_interval//60000}min | active={has_active}")
    return 0 if has_active else 0  # 0 = 无需立即铃，1 = 需要立即铃

if __name__ == "__main__":
    sys.exit(main())
