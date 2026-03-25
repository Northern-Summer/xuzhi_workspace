#!/usr/bin/env python3
"""
task_executor.py — 任务执行层核心引擎
由 unified_cron.sh 每40分钟调用一次
通过 openclaw cron add 创建 isolated execution agent，
该 agent 直接执行 claim → execute → complete → feedback 流程。
"""
import subprocess, json, sys, time
from pathlib import Path
import subprocess

HOME = Path.home()
TASKS_JSON = HOME / ".openclaw" / "tasks" / "tasks.json"
CLAIM_SCRIPT = HOME / "xuzhi_genesis" / "centers" / "task" / "claim_task.py"
COMPLETE_SCRIPT = HOME / "xuzhi_genesis" / "centers" / "task" / "complete_task.py"
FEEDBACK_SCRIPT = HOME / "xuzhi_genesis" / "centers" / "mind" / "society" / "log_feedback.py"
LOG = HOME / ".xuzhi_memory" / "task_center" / "task_executor.log"
STATE_FILE = HOME / ".xuzhi_memory" / "task_center" / "exec_state.json"
MAX_BATCH = 3
EXEC_TIMEOUT = 600  # subagent 超时秒（10分钟）

AGENT_MAP = {
    "engineering": "Λ",
    "intelligence": "Θ",
    "mind": "Ω",
    "philosophy": "Ψ",
}

RL = HOME / "xuzhi_workspace" / "task_center" / "rate_limiter.py"


def rate_limit_acquire(source: str) -> bool:
    """主动控速：获取 token，成功返回 True，失败 False（失败时放行，不阻塞）"""
    try:
        result = subprocess.run(
            ["python3", str(RL), "acquire", source],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


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
        d = json.load(open(TASKS_JSON))
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


def spawn_via_cron(prompt: str, task_ids: str = "", retries: int = 3) -> bool:
    """通过 openclaw cron add 创建 isolated execution agent（一次性，不重复）"""
    for attempt in range(1, retries + 1):
        # ── Rate Limiter：主动控速 ─────────────────────────────────────────
        if not rate_limit_acquire(f"task_exec:{task_ids}"):
            log(f"Rate limiter 禁止派发（窗口满或冷却中）")
            return False

        try:
            # 使用 --at +Xs 而不是 --every Xs，保证只执行一次
            result = subprocess.run(
                [
                    "openclaw", "cron", "add",
                    "--name", f"task-exec-{int(time.time())}",
                    "--session", "isolated",
                    "--no-deliver",
                    "--at", "10m",
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
                # 检测 794 / 速率限制错误 → 触发 cooldown
                if "794" in err or "rate limit" in err.lower() or "1000" in err:
                    log(f"⚠️ 速率错误({err[:80]})，触发 cooldown")
                    subprocess.run(
                        ["python3", str(RL), "cooldown", err, "task_executor"],
                        capture_output=True, text=True, timeout=5
                    )
                    return False
                log(f"❌ cron job 创建失败（第{attempt}次）: {err}")
                if attempt < retries:
                    time.sleep(3)
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
    """构建 execution agent 的 prompt（使用绝对路径，避免 ~ 展开问题）"""
    lines = ""
    ids = []
    for t, agent in selected:
        lines += f"- **任务#{t['id']}** [{t.get('department','')}] by {agent}: {t.get('title','')[:60]}\n"
        ids.append(str(t["id"]))

    task_ids = ",".join(ids)

    # 全部使用绝对路径
    claim = str(CLAIM_SCRIPT)
    complete = str(COMPLETE_SCRIPT)
    feedback = str(FEEDBACK_SCRIPT)

    prompt = f"""你是 Xuzhi 系统的自主执行 agent。请逐个完成以下 {len(selected)} 个任务。

{lines}

**对每个任务执行以下完整流程：**

**步骤1 — 认领任务：**
```bash
python3 {claim} <agent_id> <task_id>
```
例如：python3 {claim} Λ task_55

**步骤2 — 自主执行：**
- 根据任务标题和描述自主判断行动
- 使用 exec、read、write、web_search 等工具
- 工程任务：分析/修改代码、运行命令
- 情报任务：web搜索，信息整理
- 哲学任务：分析论证、撰写短文

**步骤3 — 完成任务：**
```bash
python3 {complete} <task_id> <agent_id> --report '完成摘要（不少于50字）'
```
例如：python3 {complete} task_55 Λ --report '该任务分析了...完成'

**步骤4 — 记录反馈（提升评分）：**
```bash
python3 {feedback} --agent <agent_id> --task 'task_<task_id>' --feedback positive --reason '自主执行完成'
```
例如：python3 {feedback} --agent Λ --task 'task_55' --feedback positive --reason '自主执行完成'

**重要规则：**
- 必须对每个任务都完整执行4个步骤
- 认领失败（任务已被认领）则跳过该任务
- 所有任务完成后输出：【批次完成: {task_ids}】
- 完成后 **不要输出其他任何内容**"""

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

    # ── Rate Limiter：整体批次检查 ───────────────────────────────────────
    task_ids_str = ",".join(str(t["id"]) for t, _ in selected)
    if not rate_limit_acquire(f"task_exec_batch:{task_ids_str}"):
        log(f"Rate limiter 禁止批次派发（窗口满或冷却中）")
        return

    prompt = build_prompt(selected)

    ok = spawn_via_cron(prompt, task_ids_str)

    if ok:
        state["last_spawn_at"] = int(time.time())
        STATE_FILE.write_text(json.dumps(state, indent=2))

    log("=== 执行器完成 ===" if ok else "=== 执行器失败 ===")


if __name__ == "__main__":
    main()
