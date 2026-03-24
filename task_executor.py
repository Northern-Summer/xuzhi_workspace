#!/usr/bin/env python3
"""
task_executor.py — 任务执行层核心引擎
通过 openclaw cron add 创建 isolated execution agent，
该 agent 持有 sessions_spawn 工具，直接派发任务子 agent，
子 agent claim → execute → complete → feedback 全链路自主执行。
"""
import subprocess, json, sys, time
from pathlib import Path

HOME = Path.home()
TASKS = HOME / ".openclaw" / "tasks" / "tasks.json"
LOG = HOME / ".xuzhi_memory" / "task_center" / "task_executor.log"
STATE_FILE = HOME / ".xuzhi_memory" / "task_center" / "exec_state.json"
MAX_BATCH = 3
EXEC_TIMEOUT = 600  # 秒

AGENT_MAP = {
    "engineering": "Λ",
    "intelligence": "Θ",
    "mind": "Ω",
    "philosophy": "Ψ",
}

def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [exec] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def get_waiting_tasks():
    """读取等待任务，选取不同部门的任务"""
    try:
        d = json.load(open(TASKS))
        tasks = d if isinstance(d, list) else d.get("tasks", [])
        waiting = [t for t in tasks if t.get("status") == "等待"]
        
        by_dept = {}
        for t in waiting:
            dept = t.get("department", "engineering")
            if dept not in by_dept:
                by_dept[dept] = []
            by_dept[dept].append(t)
        
        selected = []
        for dept in ["engineering", "intelligence", "mind", "philosophy"]:
            if len(selected) >= MAX_BATCH:
                break
            if dept in by_dept and by_dept[dept]:
                t = by_dept[dept][0]
                selected.append((t, AGENT_MAP.get(dept, "Λ")))
        
        return selected, len(waiting)
    except Exception as e:
        log(f"读取任务失败: {e}")
        return [], 0

def spawn_via_cron(prompt: str) -> bool:
    """通过 openclaw cron add 创建 isolated execution agent"""
    try:
        result = subprocess.run(
            [
                "openclaw", "cron", "add",
                "--name", f"task-exec-{int(time.time())}",
                "--session", "isolated",
                "--no-deliver",
                "--every", "30s",
                "--message", prompt,
            ],
            capture_output=True, text=True, timeout=15,
            cwd=str(HOME)
        )
        if result.returncode == 0:
            try:
                d = json.loads(result.stdout)
                job_id = d.get("id", "unknown")
                log(f"✅ cron execution agent 创建成功: {job_id}")
                return True
            except Exception:
                log(f"✅ cron job 创建成功: {result.stdout[:100]}")
                return True
        else:
            log(f"❌ cron job 创建失败: {result.stderr[:150]}")
            return False
    except Exception as e:
        log(f"派发异常: {e}")
        return False

def build_prompt(selected):
    """构建 execution agent 的 prompt"""
    lines = ""
    ids = []
    for t, agent in selected:
        lines += f"- **任务#{t['id']}** [{t.get('department','')}] by {agent}: {t.get('title','')[:60]}\n"
        ids.append(str(t["id"]))
    
    task_ids = ",".join(ids)
    
    # execution agent 的任务：使用 sessions_spawn 派发子 agent 执行每个任务
    prompt = f"""你是 Xuzhi 系统的任务派发 agent。你需要使用 `sessions_spawn` 工具为每个任务派发独立的执行 subagent。

**你的任务列表：**
{lines}

**你需要做的事情：**
1. 对每个任务调用 `sessions_spawn` 工具，派发一个独立的 subagent 来执行该任务
2. 每个 subagent 的 `task` 参数应包含：
   - 认领任务: `python3 {HOME}/xuzhi_genesis/centers/task/claim_task.py <agent_id> <task_id>`
   - 执行任务（根据标题描述自主判断，用 web_search/exec 等工具）
   - 完成任务: `python3 {HOME}/xuzhi_genesis/centers/task/complete_task.py <task_id> <agent_id> --report '分析结论摘要'`
   - 记录反馈: `python3 {HOME}/xuzhi_genesis/centers/mind/society/log_feedback.py --agent <agent_id> --task 'task_<task_id>' --feedback positive --reason '自主执行完成'`

**sessions_spawn 调用示例（你需要对每个任务调用一次）：**
```
sessions_spawn(task="认领任务: python3 .../claim_task.py Λ 36\n然后执行任务...", runtime="subagent", mode="run", runTimeoutSeconds=300)
```

**重要规则：**
- 必须对每个任务都调用 `sessions_spawn` 派发子 agent
- 派发完成后，输出：【派发完成: {task_ids}】
- 不要尝试自己执行任务，派发给 subagent 即可"""

    return prompt

def main():
    log("=== 任务执行器启动 ===")
    
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    
    selected, total = get_waiting_tasks()
    
    if not selected:
        log(f"无待执行任务（等待总数: {total}）")
        return
    
    log(f"选取 {len(selected)} 个任务（等待总数: {total}）")
    
    prompt = build_prompt(selected)
    
    ok = spawn_via_cron(prompt)
    
    if ok:
        state["last_spawn_at"] = int(time.time())
        STATE_FILE.write_text(json.dumps(state, indent=2))
    
    log("=== 执行器完成 ===" if ok else "=== 执行器失败 ===")

if __name__ == "__main__":
    main()
