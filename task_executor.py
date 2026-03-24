#!/usr/bin/env python3
"""
task_executor.py — 任务执行层核心引擎
由 unified_cron.sh 每40分钟调用一次
通过 openclaw cron add 创建 isolated execution agent，
该 agent 直接执行 claim → execute → complete → feedback 流程。
"""
import subprocess, json, sys, time
from pathlib import Path

HOME = Path.home()
TASKS = HOME / ".openclaw" / "tasks" / "tasks.json"
LOG = HOME / ".xuzhi_memory" / "task_center" / "task_executor.log"
STATE_FILE = HOME / ".xuzhi_memory" / "task_center" / "exec_state.json"
MAX_BATCH = 3
EXEC_TIMEOUT = 600  # subagent 超时秒

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
    """读取等待任务，选取不同部门的任务，跳过已认领的"""
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
                # 跳过已被认领的任务
                if t.get("status") == "进行":
                    log(f"跳过任务#{t['id']}（已由 {t.get('participants',[])} 认领）")
                    continue
                selected.append((t, AGENT_MAP.get(dept, "Λ")))
        
        return selected, len(waiting)
    except Exception as e:
        log(f"读取任务失败: {e}")
        return [], 0

def spawn_via_cron(prompt: str, retries: int = 3) -> bool:
    """通过 openclaw cron add 创建 isolated execution agent（带重试）"""
    for attempt in range(1, retries + 1):
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
                capture_output=True, text=True, timeout=20,
                cwd=str(HOME)
            )
            if result.returncode == 0:
                try:
                    d = json.loads(result.stdout)
                    job_id = d.get("id", "unknown")
                    log(f"✅ cron execution agent 创建成功: {job_id}")
                except Exception:
                    log(f"✅ cron job 创建成功: {result.stdout[:100]}")
                return True
            else:
                err = result.stderr[:150]
                log(f"❌ cron job 创建失败（第{attempt}次）: {err}")
                if attempt < retries:
                    time.sleep(3)  # 等待 Gateway 恢复
                    continue
                return False
        except Exception as e:
            log(f"派发异常（第{attempt}次）: {e}")
            if attempt < retries:
                time.sleep(3)
                continue
            return False
    return False

def build_prompt(selected):
    """构建 execution agent 的 prompt"""
    lines = ""
    ids = []
    for t, agent in selected:
        lines += f"- **任务#{t['id']}** [{t.get('department','')}] by {agent}: {t.get('title','')[:60]}\n"
        ids.append(str(t["id"]))
    
    task_ids = ",".join(ids)
    
    prompt = f"""你是 Xuzhi 系统的自主执行 agent。请逐个完成以下 {len(selected)} 个任务。

{lines}

**对每个任务执行以下完整流程：**

**步骤1 — 认领任务：**
```bash
python3 {HOME}/xuzhi_genesis/centers/task/claim_task.py <agent_id> <task_id>
```

**步骤2 — 自主执行：**
- 根据任务标题和描述自主判断行动
- 使用 exec、read、write、web_search 等工具
- 工程任务：分析/修改代码、运行命令
- 情报任务：web搜索，信息整理
- 哲学任务：分析论证、撰写短文

**步骤3 — 完成任务：**
```bash
python3 {HOME}/xuzhi_genesis/centers/task/complete_task.py <task_id> <agent_id> --report '完成摘要（不少于50字）'
```

**步骤4 — 记录反馈（提升评分）：**
```bash
python3 {HOME}/xuzhi_genesis/centers/mind/society/log_feedback.py --agent <agent_id> --task 'task_<task_id>' --feedback positive --reason '自主执行完成'
```

**重要规则：**
- 必须对每个任务都完整执行4个步骤
- 认领失败（任务已被认领）则跳过该任务
- 全部完成后输出：【批次完成: {task_ids}】"""

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
