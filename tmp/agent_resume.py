#!/usr/bin/env python3
"""
agent_resume.py — 通用自动唤醒 & 断点续跑引擎
==============================================
放入 tmp/，所有 Agent 共享使用。

用法（Agent启动时调用）：
    from agent_resume import AutoResume
    
    ar = AutoResume("xuzhi-engineer", "workspace-xuzhi-engineer")
    resumed, task_id, step = ar.check_and_resume(
        task_type="autorra_research",
        total_steps=5,
        description="AutoRA Research Cycle"
    )
    if resumed:
        print(f"从 step={step} 恢复任务 {task_id}")
        # 接着 step 继续执行...
"""

import json
import os
import sys
import time
import subprocess
import hashlib
from pathlib import Path
from typing import Optional

# 追加 tmp 到 path（保证 agent_resume 可被 import）
_SELF_DIR = Path(__file__).parent
sys.path.insert(0, str(_SELF_DIR))

# 导入共享的 checkpoint 引擎
try:
    from checkpoint import CheckpointEngine, TaskStatus, get_agent_workspace
except ImportError:
    # fallback: 内联简化版
    CheckpointEngine = None


# ============================================================================
# 断点续跑核心类
# ============================================================================

class AutoResume:
    """
    自动唤醒 & 断点续跑引擎
    
    设计原则：
    1. Agent启动时立即调用 check_and_resume()
    2. 引擎自动判断：是否有未完成的任务？
       - 有 → 返回 (True, task_id, current_step) → 从断点继续
       - 无 → 返回 (False, new_task_id, 0) → 开始新任务
    3. 每个关键步骤调用 step() 保存进度
    4. 任务完成调用 complete()，失败调用 fail()
    
    中断恢复场景：
    - Gateway 崩溃 → cron 触发唤醒 → resume 检测到 running 状态 → 续跑
    - Rate Limit 429 → wait → 重试 → 续跑（不需要重启）
    - 长时间任务 → 分步保存 → 中断后从 step=N 继续
    """
    
    def __init__(self, agent_id: str, workspace_name: str = None):
        self.agent_id = agent_id
        
        if workspace_name:
            self.workspace = Path.home() / ".openclaw" / workspace_name
        else:
            ws = get_agent_workspace(agent_id)
            self.workspace = Path(ws)
        
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        if CheckpointEngine:
            self._eng = CheckpointEngine(agent_id, str(self.workspace))
        else:
            self._eng = None
    
    # --------------------------------------------------------------------------
    # 核心 API
    # --------------------------------------------------------------------------
    
    def check_and_resume(self, task_type: str, description: str,
                          total_steps: int = 1,
                          context: dict = None,
                          force_new: bool = False) -> tuple[bool, Optional[str], int]:
        """
        检查是否需要恢复中断的任务。
        
        Returns:
            (is_resuming, task_id, current_step)
            - is_resuming=True → 发现中断任务，从断点继续
            - is_resuming=False → 无中断任务或任务已结束，开始新任务
        """
        if force_new or not self._eng:
            # 无checkpoint引擎，降级为直接新建
            task_id = f"{task_type}_{int(time.time())}"
            return False, task_id, 0
        
        task_id, is_resuming = self._eng.resume_or_start(
            task_type=task_type,
            description=description,
            total_steps=total_steps,
            context=context
        )
        
        task = self._eng.get_current_task()
        step = task.current_step if task else 0
        
        return is_resuming, task_id, step
    
    def step(self, step: int, label: str = "", context: dict = None) -> None:
        """每个关键步骤完成后调用"""
        if self._eng:
            self._eng.step_checkpoint(step, label, context)
    
    def complete(self, result: any = None) -> None:
        """任务正常完成"""
        if self._eng:
            self._eng.complete(result)
    
    def fail(self, error: str = "") -> None:
        """任务失败"""
        if self._eng:
            self._eng.fail(error)
    
    def heartbeat(self) -> None:
        """发送心跳"""
        if self._eng:
            self._eng.heartbeat()
    
    def get_progress(self) -> dict:
        """获取当前进度"""
        if self._eng:
            return self._eng.get_progress()
        return {"status": "no_checkpoint"}
    
    # --------------------------------------------------------------------------
    # 辅助方法
    # --------------------------------------------------------------------------
    
    def get_task_context(self) -> dict:
        """获取保存的上下文（用于恢复执行状态）"""
        task = self._eng.get_current_task() if self._eng else None
        return task.context if task else {}
    
    def is_task_stale(self, max_age_seconds: int = None) -> bool:
        """检查当前任务是否已过期（超过max_age未更新）"""
        if not self._eng:
            return False
        prog = self._eng.get_progress()
        if max_age_seconds is None:
            max_age_seconds = 3 * 3600
        return prog.get("age_seconds", 0) > max_age_seconds


# ============================================================================
# 外部调用接口（供 cron/脚本 使用）
# ============================================================================

def resume_agent(agent_id: str, task_type: str, prompt_template: str,
                 workspace_name: str = None, total_steps: int = 1) -> dict:
    """
    外部调用：从断点恢复指定Agent的任务
    
    用于 cron watchdog 检测到某 Agent 状态异常时，
    自动触发恢复。
    
    Returns:
        dict with keys: success, resumed, task_id, current_step, agent_id
    """
    import subprocess
    
    ar = AutoResume(agent_id, workspace_name)
    resumed, task_id, step = ar.check_and_resume(
        task_type=task_type,
        description=f"Auto-resumed task: {task_type}",
        total_steps=total_steps
    )
    
    if not resumed and step == 0:
        # 任务已完成或无任务
        return {
            "success": True,
            "resumed": False,
            "task_id": task_id,
            "current_step": 0,
            "agent_id": agent_id,
            "reason": "no_task_to_resume"
        }
    
    # 构建恢复提示词（注入上下文）
    context = ar.get_task_context()
    
    # 替换模板中的占位符
    prompt = prompt_template.format(
        task_id=task_id,
        step=step,
        context=json.dumps(context, ensure_ascii=False)
    )
    
    # 触发 isolated session
    try:
        result = subprocess.run([
            "openclaw", "sessions", "spawn",
            "--agent-id", agent_id,
            "--runtime", "subagent",
            "--task", prompt,
            "--mode", "run"
        ], capture_output=True, text=True, timeout=30)
        
        return {
            "success": result.returncode == 0,
            "resumed": resumed,
            "task_id": task_id,
            "current_step": step,
            "agent_id": agent_id,
            "output": result.stdout[:500] if result.stdout else ""
        }
    except Exception as e:
        return {
            "success": False,
            "resumed": resumed,
            "task_id": task_id,
            "current_step": step,
            "agent_id": agent_id,
            "error": str(e)
        }


# ============================================================================
# 自唤醒 watchdog（主循环）
# ============================================================================

def run_watchdog_loop(agent_id: str, workspace_name: str = None,
                       interval_seconds: int = 300,
                       max_consecutive_failures: int = 3):
    """
    守护进程主循环：监控并自动恢复中断的任务
    
    通常由 cron 每5分钟触发一次。
    也可以长期运行（debug模式）。
    """
    import signal, sys
    
    ar = AutoResume(agent_id, workspace_name)
    consecutive_failures = 0
    
    def signal_handler(sig, frame):
        print(f"[watchdog] 收到退出信号，优雅退出")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"[watchdog] 启动 watchdog for {agent_id}, 间隔 {interval_seconds}s")
    
    while True:
        try:
            task = ar._eng.get_current_task() if ar._eng else None
            
            if task and task.status in (TaskStatus.RUNNING, TaskStatus.STEPPING):
                age = time.time() - task.updated_at
                
                if age > 3 * 3600:  # 3小时未更新 = 中断
                    print(f"[watchdog] 检测到中断任务 {task.task_id}（已中断 {int(age/60)}min），尝试恢复...")
                    
                    resumed, tid, step = ar.check_and_resume(
                        task_type=task.task_type,
                        description=task.description,
                        total_steps=task.total_steps,
                        context=task.context
                    )
                    
                    if resumed:
                        print(f"[watchdog] ✓ 已触发恢复，step={step}")
                        consecutive_failures = 0
                    else:
                        print(f"[watchdog] ⚠ 恢复失败或无需恢复")
                        consecutive_failures += 1
                
                ar.heartbeat()
            else:
                # 空闲状态，只发心跳
                if ar._eng:
                    ar._eng.heartbeat()
            
            consecutive_failures = 0
            
        except Exception as e:
            print(f"[watchdog] 异常: {e}")
            consecutive_failures += 1
            
            if consecutive_failures >= max_consecutive_failures:
                print(f"[watchdog] 连续失败{max_consecutive_failures}次，退出")
                break
        
        time.sleep(interval_seconds)


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Resume Engine")
    parser.add_argument("action", choices=["status", "resume", "watchdog", "test"])
    parser.add_argument("--agent", default="main", help="Agent ID")
    parser.add_argument("--workspace", help="Workspace name (e.g. workspace-xuzhi-researcher)")
    parser.add_argument("--task-type", default="general", help="任务类型")
    parser.add_argument("--steps", type=int, default=1, help="总分步数")
    parser.add_argument("--interval", type=int, default=300, help="Watchdog间隔(秒)")
    
    args = parser.parse_args()
    
    if args.action == "status":
        ar = AutoResume(args.agent, args.workspace)
        prog = ar.get_progress()
        print(json.dumps(prog, indent=2))
        
        if ar._eng:
            cp = ar._eng._load()
            if cp and cp.completed_tasks:
                print(f"\n最近完成的任务 ({len(cp.completed_tasks)}条):")
                for t in cp.completed_tasks[-3:]:
                    print(f"  - {t['task_type']} | step={t['current_step']}/{t['total_steps']} | {t['status']}")
    
    elif args.action == "resume":
        # 演示resume流程
        ar = AutoResume(args.agent, args.workspace)
        resumed, tid, step = ar.check_and_resume(
            task_type=args.task_type,
            description=f"测试任务 {args.task_type}",
            total_steps=args.steps
        )
        print(f"resumed={resumed}, task_id={tid}, step={step}")
        
        if resumed:
            print("→ 从断点继续执行...")
            ar.step(step + 1, f"步骤{step+1}完成", {"resumed_from": step})
            ar.complete({"resumed": True, "original_step": step})
        else:
            print("→ 开始新任务...")
            ar.step(1, "第一步完成")
            ar.complete()
    
    elif args.action == "watchdog":
        run_watchdog_loop(args.agent, args.workspace, args.interval)
    
    elif args.action == "test":
        # 完整测试
        print("=== AutoResume Test ===")
        
        import tempfile, shutil
        test_ws = tempfile.mkdtemp(prefix="test_ar_")
        
        ar1 = AutoResume("test-agent", test_ws)
        resumed, tid1, step1 = ar1.check_and_resume("autorra_test", "测试AutoRA任务", total_steps=5)
        print(f"[1] 新任务: resumed={resumed}, tid={tid1[:20]}..., step={step1}")
        
        ar1.step(2, "步骤2完成")
        ar1.step(3, "步骤3完成")
        
        # 模拟重启
        ar2 = AutoResume("test-agent", test_ws)
        resumed2, tid2, step2 = ar2.check_and_resume("autorra_test", "测试AutoRA任务", total_steps=5)
        print(f"[2] 恢复: resumed={resumed2}, tid={tid2[:20]}..., step={step2}")
        assert resumed2 == True, "应该检测到恢复！"
        assert step2 == 3, f"应该从step=3恢复，实际={step2}"
        
        ar2.complete({"test": "passed"})
        
        # 测试完成后新任务
        ar3 = AutoResume("test-agent", test_ws)
        resumed3, tid3, step3 = ar3.check_and_resume("autorra_test", "测试AutoRA任务", total_steps=5)
        print(f"[3] 新任务: resumed={resumed3}, tid={tid3[:20]}..., step={step3}")
        assert resumed3 == False, "完成后应该开始新任务！"
        
        shutil.rmtree(test_ws, ignore_errors=True)
        print("\n✓ 所有测试通过")
