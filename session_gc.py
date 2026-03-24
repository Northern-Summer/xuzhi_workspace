#!/usr/bin/env python3
"""
session_gc.py — 清理过期的 isolated subagent sessions
防止 subagent sessions 无限堆积
cron: 每30分钟调度
"""
import json, sys, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
LOG = HOME / ".xuzhi_memory" / "task_center" / "session_gc.log"
MAX_AGE_HOURS = 4  # 超过4小时的 completed/aborted sessions 删除
DRY_RUN = False  # 首次运行用 DRY_RUN，验证后改为 False

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [gc] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def get_sessions(agent_dir: Path):
    """读取 agent 的所有 sessions"""
    sessions_dir = agent_dir / "sessions"
    if not sessions_dir.exists():
        return []
    sessions = []
    for f in sessions_dir.iterdir():
        if f.suffix == ".jsonl" and not f.name.startswith("."):
            try:
                # 读取最后一行获取最后活跃时间
                lines = f.read_text().strip().split("\n")
                if lines:
                    last = json.loads(lines[-1])
                    ts = last.get("ts", last.get("timestamp", 0))
                    sessions.append({
                        "file": f,
                        "key": f.stem,
                        "last_ts": ts,
                        "age_hours": (time.time() - ts) / 3600 if ts else 999
                    })
            except Exception:
                pass
    return sessions

def gc_agent(agent_name: str, agent_dir: Path):
    sessions = get_sessions(agent_dir)
    old = [s for s in sessions if s["age_hours"] > MAX_AGE_HOURS]
    if not old:
        return 0
    deleted = 0
    for s in old:
        if DRY_RUN:
            log(f"  [DRY] 删除 {agent_name}/{s['key']} (age={s['age_hours']:.1f}h)")
        else:
            try:
                s["file"].unlink()
                deleted += 1
                log(f"  删除 {agent_name}/{s['key']} (age={s['age_hours']:.1f}h)")
            except Exception as e:
                log(f"  删除失败 {agent_name}/{s['key']}: {e}")
    return deleted

def main():
    log("=== Session GC 启动 ===")
    
    total_deleted = 0
    for agent_dir in sorted((HOME / ".openclaw" / "agents").iterdir()):
        if not agent_dir.is_dir():
            continue
        name = agent_dir.name
        # 只清理 subagent sessions（以 cron: 或 subagent: 开头）
        sessions = get_sessions(agent_dir)
        subagent = [s for s in sessions if ":" in s["key"] and ("cron" in s["key"] or "subagent" in s["key"])]
        old = [s for s in subagent if s["age_hours"] > MAX_AGE_HOURS]
        
        if old:
            log(f"{name}: {len(old)}/{len(subagent)} sessions 过期")
            total_deleted += gc_agent(name, agent_dir)
    
    if DRY_RUN:
        log(f"=== GC 完成（DRY RUN，验证模式）===")
    else:
        log(f"=== GC 完成，删除 {total_deleted} 个 sessions ===")

if __name__ == "__main__":
    main()
