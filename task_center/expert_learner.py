#!/usr/bin/env python3
"""
expert_learner.py — Expert Tracker → Agent 学习闭环
从 changes.json 读取专家最新动态，生成"方法分析任务"写入 tasks.json。
Agent 完成任务后，产出【方法改进建议】存入各自的 memory/ 目录。
整个过程：全自动，零人工介入。
"""
import json, subprocess
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
TRACKER = HOME / ".xuzhi_memory" / "expert_tracker"
EXPERTS = TRACKER / "experts.json"
CHANGES = TRACKER / "changes.json"
TASKS   = HOME  / ".openclaw" / "tasks" / "tasks.json"
AGENTS  = ["Ξ", "Φ", "Δ", "Θ", "Γ", "Ω", "Ψ"]

# Agent → 对应部门
AGENT_DEPT = {
    "Ξ": "engineering", "Φ": "engineering", "Δ": "engineering", "Ω": "mind",
    "Γ": "intelligence", "Θ": "intelligence", "Ψ": "philosophy",
}

# Agent → memory 文件
AGENT_MEMORY = {
    "Ξ": HOME / ".xuzhi_memory" / "memory" / "xi.md",
    "Δ": HOME / ".xuzhi_memory" / "memory" / "delta.md",
    "Φ": HOME / ".xuzhi_memory" / "memory" / "phi.md",
    "Ω": HOME / ".xuzhi_memory" / "memory" / "omega.md",
    "Γ": HOME / ".xuzhi_memory" / "memory" / "gamma.md",
    "Θ": HOME / ".xuzhi_memory" / "memory" / "theta.md",
    "Ψ": HOME / ".xuzhi_memory" / "memory" / "psi.md",
}

def load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return default

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def load_tasks():
    return json.loads(TASKS.read_text())

def save_tasks(tasks):
    TASKS.write_text(json.dumps(tasks, indent=2, ensure_ascii=False))

def get_task_title_for_change(change):
    """根据专家动态生成任务标题"""
    expert = change.get("expert", "")
    title = change.get("new_title", "")[:60]
    dept = change.get("dept", "")
    dept_label = {"engineering": "工程", "science": "科学", "mind": "心灵",
                   "philosophy": "哲学", "intelligence": "情报"}.get(dept, dept)
    return f"[{dept_label}] {expert}: {title}"

def create_tasks_from_changes():
    """读取 changes.json，为未处理的新变化生成分析任务"""
    changes_db = load(CHANGES, {"changes": []})
    tasks = load_tasks()
    now = datetime.now(timezone.utc).isoformat()

    # 已有的学习任务（按 change_key 去重）
    existing_keys = set()
    for t in tasks.get("tasks", []):  # tasks 是 dict {"tasks": [...]}
        ref = t.get("completion_report", "") or ""
        if "expert_learn:" in ref:
            # 提取 change key
            key = ref.split("expert_learn:")[-1].split()[0]
            existing_keys.add(key)

    created = 0
    new_task_ids = []

    for change in changes_db.get("changes", []):
        key = f"{change['dept']}:{change['expert']}:{change['new_title'][:30]}"
        if key in existing_keys:
            continue

        task_title = get_task_title_for_change(change)

        # 找对应的 agent
        dept = change.get("dept", "")
        agent = next((a for a, d in AGENT_DEPT.items() if d == dept), "Ξ")

        new_task = {
            "id": max((t["id"] for t in tasks.get("tasks", []) if isinstance(t["id"], int)), default=0) + 1,
            "title": task_title,
            "type": "简单",
            "department": dept,
            "mode": "竞争",
            "description": (
                "你是 Xuzhi 系统的 " + agent + "，请分析以下专家最新动态：\n\n"
                "专家: " + change.get('expert', '') + "\n"
                "机构: " + change.get('affiliation', '未知') + "\n"
                "新论文: " + change.get('new_title', '') + "\n"
                "URL: " + change.get('new_url', '') + "\n\n"
                "请完成：\n"
                "1. 如果有URL，尝试用web_search/web_fetch阅读论文\n"
                "2. 识别其中可应用于你工作流程的方法/工具/思想\n"
                "3. 将具体改进建议追加写入 ~/.xuzhi_memory/memory/" + agent.lower() + ".md\n\n"
                "完成后用 complete_task.py 标记完成，报告格式: expert_learn:" + key
            ),
            "acceptance_criteria": "改进建议已写入对应Agent的memory文件",
            "created": now,
            "deadline": (datetime.now(timezone.utc)).isoformat(),
            "status": "等待",
            "participants": [],
            "participant_times": {},
            "completed_by": [],
            "completion_time": None,
            "completion_report": "",
            "evaluations": {},
            "score_processed": False,
            "last_updated": now,
        }

        tasks["tasks"].append(new_task)
        new_task_ids.append(new_task["id"])
        created += 1

    if created > 0:
        save_tasks(tasks)
        print(f"[learner] 生成了 {created} 个学习任务: {new_task_ids}")
    else:
        print("[learner] 无新学习任务")

    return created

def main():
    print("=== Expert Learner 开始 ===")
    created = create_tasks_from_changes()
    print(f"=== Expert Learner 完成: {created} 个任务 ===")

if __name__ == "__main__":
    main()
