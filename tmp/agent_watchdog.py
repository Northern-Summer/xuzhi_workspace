#!/usr/bin/env python3
"""
agent_watchdog.py — 全局 Agent 自唤醒 & 断点续跑 Watchdog
==========================================================
放入 tmp/，通过 cron 每5分钟触发一次。

功能：
1. 扫描所有 Agent 的 .checkpoint.json
2. 发现 stale（>3h未更新）且 status=running/stepping → 判定为中断
3. 自动触发该 Agent 的 isolated session，从断点续跑
4. 记录恢复事件到日志

设计原则：
- 轻量级（systemEvent，不启动LLM）
- 幂等（可重复运行，结果一致）
- 外部通过 agent_resume.py 的 resume_agent() 函数触发恢复
"""

import json
import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# 添加 tmp 到 path
_SELF_DIR = Path(__file__).parent
sys.path.insert(0, str(_SELF_DIR))

try:
    from checkpoint import CheckpointEngine, get_agent_workspace, TaskStatus
except ImportError:
    CheckpointEngine = None
    print("[watchdog] checkpoint.py 不可用，仅报告模式", file=sys.stderr)


# ============================================================================
# 配置
# ============================================================================

# 超时阈值（秒）：超过此时间未更新 = 判定为中断
STALE_THRESHOLD = 3 * 3600  # 3小时

# 连续 stale 次数阈值：超过此次数才触发恢复（避免误判）
STALE_COUNT_THRESHOLD = 1

# Agent → 恢复时使用的 task_type（用于 check_and_resume）
AGENT_TASK_TYPES = {
    "main":                   "main_session",
    "xuzhi-researcher":       "autorra_research",
    "xuzhi-engineer":         "engineering_daily",
    "xuzhi-philosopher":      "philosophy_exploration",
    "xuzhi-chenxi":           "strategic_planning",
    "scientist":              "science_exploration",
    "engineer":               "system_construction",
    "philosopher":            "meaning_exploration",
}

# Agent → workspace 名称映射
AGENT_WORKSPACES = {
    "main":                   "workspace",
    "xuzhi-researcher":       "workspace-xuzhi-researcher",
    "xuzhi-engineer":        "workspace-xuzhi-engineer",
    "xuzhi-philosopher":      "workspace-xuzhi-philosopher",
    "xuzhi-chenxi":           "workspace-xuzhi",
    "scientist":             "workspace-scientist",
    "engineer":              "workspace-engineer",
    "philosopher":           "workspace-philosopher",
}

LOG_FILE = Path(__file__).parent / "watchdog_log.jsonl"


# ============================================================================
# 核心逻辑
# ============================================================================

def get_all_agent_ids() -> list[str]:
    """从 openclaw agents list 获取所有注册 Agent ID"""
    try:
        result = subprocess.run(
            ["openclaw", "agents", "list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            import re
            ids = re.findall(r'^\s*-\s+(\S+)', result.stdout, re.MULTILINE)
            return ids if ids else list(AGENT_WORKSPACES.keys())
    except:
        pass
    return list(AGENT_WORKSPACES.keys())


def scan_agent_checkpoint(agent_id: str) -> dict:
    """扫描单个 Agent 的检查点状态"""
    workspace_name = AGENT_WORKSPACES.get(agent_id, f"workspace-{agent_id}")
    workspace = Path.home() / ".openclaw" / workspace_name
    checkpoint_file = workspace / ".checkpoint.json"
    
    if not checkpoint_file.exists():
        return {
            "agent_id": agent_id,
            "status": "no_checkpoint",
            "healthy": True,
            "workspace": str(workspace)
        }
    
    try:
        with open(checkpoint_file) as f:
            data = json.load(f)
        
        task = data.get("current_task")
        heartbeat = data.get("heartbeat_at", 0)
        age = time.time() - heartbeat
        stale = age > STALE_THRESHOLD
        
        if task:
            status_str = task.get("status", "unknown")
            try:
                status_enum = TaskStatus(status_str)
            except:
                status_enum = TaskStatus.PENDING
            
            # healthy = 有检查点且非stale的任务在运行；idle 和 no_checkpoint 都是 healthy
            healthy = not stale and status_enum in (TaskStatus.RUNNING, TaskStatus.STEPPING)
            
            return {
                "agent_id": agent_id,
                "status": status_str,
                "task_type": task.get("task_type", ""),
                "task_id": task.get("task_id", ""),
                "step": f"{task.get('current_step', 0)}/{task.get('total_steps', 1)}",
                "age_seconds": int(age),
                "stale": stale,
                "healthy": healthy,
                "workspace": str(workspace),
                "last_heartbeat": datetime.fromtimestamp(heartbeat).isoformat()
            }
        else:
            return {
                "agent_id": agent_id,
                "status": "idle",
                "age_seconds": int(age),
                "healthy": True,
                "workspace": str(workspace)
            }
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return {
            "agent_id": agent_id,
            "status": "error",
            "healthy": False,
            "workspace": str(workspace)
        }


def try_resume_agent(agent_id: str, task_info: dict) -> dict:
    """尝试恢复指定 Agent 的中断任务"""
    workspace_name = AGENT_WORKSPACES.get(agent_id, f"workspace-{agent_id}")
    
    try:
        # 导入 AutoResume
        sys.path.insert(0, str(_SELF_DIR))
        from agent_resume import AutoResume
        
        ar = AutoResume(agent_id, workspace_name)
        
        task_type = task_info.get("task_type", "general")
        task_id = task_info.get("task_id", "")
        current_step = 0
        
        # 从检查点文件获取当前 step
        ws = Path.home() / ".openclaw" / workspace_name
        cp_file = ws / ".checkpoint.json"
        if cp_file.exists():
            with open(cp_file) as f:
                data = json.load(f)
            task = data.get("current_task", {})
            current_step = task.get("current_step", 0)
            task_type = task.get("task_type", task_type)
            task_id = task.get("task_id", task_id)
        
        print(f"[watchdog] 尝试恢复 {agent_id}: task_type={task_type}, step={current_step}",
              file=sys.stderr)
        
        # 触发 isolated session（使用 sessions_spawn）
        # 注意：这需要通过主会话的 API 触发，这里用命令行方式
        result = subprocess.run([
            "openclaw", "sessions", "spawn",
            "--agent-id", agent_id,
            "--runtime", "subagent",
            "--mode", "run",
            "--task", f"[Auto-Resume] 断点续跑任务 {task_id}，从 step={current_step} 继续执行。上下文：{task_info.get('task_type', 'general')}"
        ], capture_output=True, text=True, timeout=60)
        
        return {
            "agent_id": agent_id,
            "action": "resumed",
            "task_id": task_id,
            "step": current_step,
            "success": result.returncode == 0,
            "output": result.stdout[:200] if result.stdout else "",
            "error": result.stderr[:200] if result.stderr else ""
        }
        
    except Exception as e:
        return {
            "agent_id": agent_id,
            "action": "error",
            "error": str(e)
        }


def log_event(event: dict):
    """记录事件到日志文件"""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "datetime": datetime.now().isoformat(),
                **event
            }, ensure_ascii=False) + "\n")
    except:
        pass


def run_watchdog(report_only: bool = False) -> dict:
    """
    运行 watchdog 主逻辑
    
    Args:
        report_only: True = 只报告，不执行恢复（用于调试）
    
    Returns:
        扫描结果摘要 dict
    """
    print(f"[watchdog] {'[REPORT ONLY]' if report_only else ''} 开始扫描 {datetime.now().isoformat()}",
          file=sys.stderr)
    
    agent_ids = get_all_agent_ids()
    results = {}
    recovered = []
    problems = []
    
    for agent_id in agent_ids:
        info = scan_agent_checkpoint(agent_id)
        results[agent_id] = info
        
        if info.get("stale") and info.get("status") in ("running", "stepping"):
            problems.append((agent_id, info))
            
            if not report_only:
                # 尝试恢复
                log_event({"type": "stale_detected", "agent_id": agent_id, **info})
                resume_result = try_resume_agent(agent_id, info)
                results[agent_id]["resume_result"] = resume_result
                log_event({"type": "resume_attempt", **resume_result})
                
                if resume_result.get("success"):
                    recovered.append(agent_id)
    
    # 定期健康报告（每10次 = 约50分钟）
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_agents": len(agent_ids),
        "healthy": sum(1 for r in results.values() if r.get("healthy")),
        "stale": len(problems),
        "recovered": recovered,
        "problems": [(aid, i.get("status"), int(i.get("age_seconds", 0)/60))
                     for aid, i in problems]
    }
    
    print(f"[watchdog] 结果: healthy={summary['healthy']}/{summary['total_agents']}, "
          f"stale={summary['stale']}, recovered={recovered}", file=sys.stderr)
    
    log_event({"type": "scan_summary", **summary})
    
    return summary


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Watchdog — 全局自唤醒引擎")
    parser.add_argument("--report", action="store_true", help="仅报告，不执行恢复")
    parser.add_argument("--agent", help="仅检查指定 Agent")
    parser.add_argument("--list", action="store_true", help="列出所有 Agent 状态")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    
    args = parser.parse_args()
    
    if args.list:
        summary = run_watchdog(report_only=True)
        for agent_id, info in summary.items():
            if agent_id in ("timestamp", "total_agents", "healthy", "stale"):
                continue
            healthy = "✅" if info.get("healthy") else "⚠️"
            stale = " [STALE]" if info.get("stale") else ""
            age = info.get("age_seconds", 0)
            age_str = f"{int(age//3600)}h{(int(age)%3600)//60}m" if age > 60 else f"{age}s"
            print(f"{healthy} {agent_id}: {info.get('status','?')} {stale} ({age_str})")
        sys.exit(0)
    
    if args.agent:
        info = scan_agent_checkpoint(args.agent)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        sys.exit(0)
    
    if args.json:
        print(json.dumps(run_watchdog(report_only=args.report), indent=2, ensure_ascii=False))
    else:
        summary = run_watchdog(report_only=args.report)
        if summary["problems"]:
            print("⚠️  发现问题:")
            for aid, status, age_min in summary["problems"]:
                print(f"  - {aid}: {status}（已中断 {age_min}min）")
        if summary["recovered"]:
            print("✅ 已尝试恢复:")
            for aid in summary["recovered"]:
                print(f"  - {aid}")
