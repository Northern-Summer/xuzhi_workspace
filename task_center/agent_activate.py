#!/usr/bin/env python3
"""
agent_push.py — Agent 激活时自动 push 状态到共享广播层
每个 agent 被 watchdog 激活后调用此脚本，将自己的状态写入 agent_reports.json。
这是星形拓扑的 push 端：每个 agent 只写自己的，不读别人的。
"""
import json
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
REPORTS = HOME / ".xuzhi_memory" / "agent_reports.json"
LOG    = HOME / ".xuzhi_memory" / "task_center" / "agent_push.log"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"{ts} [push] {msg}\n")

def push_status(agent_symbol):
    """将 agent 状态写入共享 reports 文件"""
    reports = {}
    if REPORTS.exists():
        try:
            reports = json.loads(REPORTS.read_text())
        except:
            pass

    now = datetime.now(timezone.utc).isoformat()

    # 读取 agent 自己的 memory 文件获取近况
    memory_file = HOME / f".xuzhi_memory/memory/{agent_symbol.lower()}.md"
    recent_work = ""
    if memory_file.exists():
        try:
            lines = memory_file.read_text().splitlines()
            # 取最后20行作为近期工作总结
            recent_work = "\n".join(lines[-20:]).strip()
        except:
            pass

    reports[agent_symbol] = {
        "pushed_at": now,
        "status": "active",
        "recent_work": recent_work[-300:] if recent_work else "",
        "next_action": "read changes.json and process expert learning tasks",
    }

    REPORTS.write_text(json.dumps(reports, indent=2, ensure_ascii=False))
    log(f"✅ {agent_symbol} pushed to shared reports")

def pull_changes():
    """从共享 changes.json pull expert 数据"""
    changes_file = HOME / ".xuzhi_memory/expert_tracker/changes.json"
    if not changes_file.exists():
        return None
    try:
        return json.loads(changes_file.read_text())
    except:
        return None

def main():
    import sys
    agent_symbol = sys.argv[1] if len(sys.argv) > 1 else "?"
    log(f"=== {agent_symbol} Push Start ===")
    push_status(agent_symbol)

    # pull expert changes
    changes = pull_changes()
    if changes:
        recent = changes.get("changes", [])
        log(f"Pulled {len(recent)} expert changes from shared layer")
    else:
        log("No expert changes available")

    log(f"=== {agent_symbol} Push Complete ===")

if __name__ == "__main__":
    import sys
    main()
