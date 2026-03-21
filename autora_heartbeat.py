#!/usr/bin/env python3
"""AutoRA Heartbeat - 在 main session 运行，直接调用 web_search 工具"""
import json, sys
from pathlib import Path
from datetime import datetime

GENESIS  = Path.home() / "xuzhi_genesis"
INTELLIGENCE = GENESIS / "centers" / "intelligence"
QUEUE_FILE = INTELLIGENCE / "autora_task_queue.json"
STATE_FILE = INTELLIGENCE / "autora_state.json"
RESULTS_FILE = INTELLIGENCE / "autora_logs" / "research_results.md"
LOG_DIR  = INTELLIGENCE / "autora_logs"

LOG_DIR.mkdir(exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    (LOG_DIR / f"heartbeat_{datetime.now().strftime('%Y-%m-%d')}.log").open("a").write(line + "\n")

def load_queue():
    if not QUEUE_FILE.exists():
        return []
    try:
        return json.loads(QUEUE_FILE.read_text())
    except:
        return []

def get_pending(limit=3):
    tasks = load_queue()
    pending = [t for t in tasks if t.get("status") == "pending"]
    return pending[:limit]

def mark_done(query):
    if not QUEUE_FILE.exists():
        return
    try:
        tasks = json.loads(QUEUE_FILE.read_text())
        for t in tasks:
            if t.get("query") == query and t.get("status") == "pending":
                t["status"] = "done"
        QUEUE_FILE.write_text(json.dumps(tasks, indent=2))
    except:
        pass

def write_result(query, result_text):
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    lines = [
        f"\n## 搜索: {query}",
        f"时间: {datetime.now().isoformat()}",
        f"结果: {result_text[:500]}"
    ]
    RESULTS_FILE.open("a").write("\n".join(lines) + "\n")

def main():
    log("=" * 40)
    log("HEARTBEAT AutoRA 启动")
    pending = get_pending(limit=3)
    log(f"待处理任务: {len(pending)}")
    
    for i, task in enumerate(pending):
        q = task.get("query", "")
        log(f"[{i+1}/{len(pending)}] 搜索: {q[:60]}")
        # 注意：这里的输出会被解析用于提取 web_search 指令
        print(f"[[WEB_SEARCH]] {q}", flush=True)
        mark_done(q)
        write_result(q, "(web_search 已调用，结果待 main session 捕获)")
    
    log(f"处理完成: {len(pending)} 任务")

if __name__ == "__main__":
    main()
