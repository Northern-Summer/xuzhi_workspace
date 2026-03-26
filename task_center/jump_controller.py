#!/usr/bin/env python3
"""
jump_controller.py — 边界跳跃控制器
工程改进铁律合规 — Ξ | 2026-03-27
自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

设计原则：
- 不停止，只跳跃
- 跳跃 = 检测边界 → 找到等效路径 → 继续执行
- 状态机驱动，不是轮询

边界类型：
  BOUNDARY_STALL   — 任务/进程卡死（watchdog/self_repair检测）
  BOUNDARY_RATE    — 速率限制触发（rate_limiter检测）
  BOUNDARY_ERROR   — API/网络错误（调用方报告）
  BOUNDARY_DEAD    — 进程崩溃（watchdog检测）
"""
import json, time, subprocess, sys, os
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

HOME = Path.home()
STATE_FILE  = HOME / ".xuzhi_memory" / "task_center" / "jump_state.json"
LOG_FILE    = HOME / ".xuzhi_memory" / "task_center" / "jump_controller.log"
PID_FILE    = HOME / ".xuzhi_watchdog" / "jump_controller.pid"
ALLOW_FILE  = HOME / ".xuzhi_watchdog" / "jump_halt.flag"  # Human说停
EFFICIENCY_LOW = HOME / ".xuzhi_watchdog" / "efficiency_low.flag"  # 效率下降信号
ARCHIVE_REQ   = HOME / ".xuzhi_watchdog" / "archive_requested.flag" # 存档请求
HUMAN_SIGNAL  = HOME / ".xuzhi_watchdog" / "human_signal.flag"     # 人类任意信号
SNAPSHOT_DIR  = HOME / ".xuzhi_watchdog" / "snapshots"  # 存档目录
DRIFT_SIGNAL  = HOME / ".xuzhi_watchdog" / "drift_detected.flag"  # 任务漂移信号

# 现有组件路径
WATCHDOG    = HOME / "xuzhi_workspace" / "task_center" / "expert_watchdog.py"
SELF_REPAIR = HOME / "xuzhi_workspace" / "task_center" / "self_repair.py"
RATE_LIMITER= HOME / "xuzhi_workspace" / "task_center" / "rate_limiter.py"
TASK_EXE    = HOME / "xuzhi_workspace" / "task_executor.py"

# 状态
class State(Enum):
    RUNNING  = "running"   # 正常执行
    JUMPING  = "jumping"   # 跳跃中
    COOLDOWN = "cooldown"  # 冷却中（等待后自动恢复）
    HALTED   = "halted"    # 已停止（Human明确要求）

@dataclass
class Boundary:
    kind: str          # "stall"|"rate"|"error"|"dead"|"efficiency"
    source: str         # 哪个组件检测到
    detail: str         # 详细信息
    at: float = field(default_factory=time.time)
    jump_count: int = 0  # 连续跳跃次数

@dataclass
class JumpPlan:
    action: str        # "retry"|"skip"|"restart"|"bypass"
    target: str        # 目标路径/任务ID
    wait_sec: float    # 跳跃前等待秒数（0=立即）
    resume_at: str     # 跳跃后从哪继续

# ── 日志 ─────────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── 状态持久化 ───────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "state": State.RUNNING.value,
        "jump_log": [],         # 最近10次跳跃记录
        "stall_count": 0,      # 连续卡死次数
        "cooldown_until": 0,    # cooldown截止时间
        "halt_requested": False,
    }

def save_state(s: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2))

# ── 核心：检测边界 ─────────────────────────────────────────────────────────────

def check_halt() -> bool:
    """Human说停 → 立即停止"""
    if ALLOW_FILE.exists():
        log("🛑 Human要求停止，切换HALTED")
        s = load_state()
        s["state"] = State.HALTED.value
        s["halt_requested"] = True
        save_state(s)
        return True
    return False

def check_human_signals() -> list:
    """
    检查人类效率信号。
    原理：Human说'存档'/'效率下降' → 相应flag文件被外部写入 → jump_controller读取并响应
    人类不需要发指令，工具心领神会。
    """
    boundaries = []
    now = time.time()

    # 效率下降信号
    if EFFICIENCY_LOW.exists():
        try:
            ts = float(EFFICIENCY_LOW.read_text().strip())
            age = now - ts
            if age < 7200:  # 2小时内有效
                boundaries.append(Boundary(
                    kind="efficiency",
                    source="human",
                    detail="效率下降信号",
                ))
        except Exception:
            boundaries.append(Boundary(
                kind="efficiency",
                source="human",
                detail="效率下降信号",
            ))

    # 存档请求
    if ARCHIVE_REQ.exists():
        try:
            ts = float(ARCHIVE_REQ.read_text().strip())
            age = now - ts
            if age < 7200:
                boundaries.append(Boundary(
                    kind="efficiency",
                    source="human",
                    detail="存档请求",
                ))
        except Exception:
            boundaries.append(Boundary(
                kind="efficiency",
                source="human",
                detail="存档请求",
            ))

    # 人类任意信号
    if HUMAN_SIGNAL.exists():
        try:
            signal = HUMAN_SIGNAL.read_text().strip()
            boundaries.append(Boundary(
                kind="efficiency",
                source="human",
                detail=f"信号: {signal}",
            ))
        except Exception:
            pass

    return boundaries

def check_watchdog() -> Optional[Boundary]:
    """运行watchdog，检查是否有链断裂"""
    try:
        r = subprocess.run(
            ["python3", str(WATCHDOG)],
            capture_output=True, text=True, timeout=30
        )
        # watchdog返回码非0 → 检测到严重问题
        if r.returncode != 0:
            return Boundary(
                kind="stall",
                source="watchdog",
                detail=r.stderr.strip()[:200] or r.stdout.strip()[:200],
            )
        # 日志中明确出现"链断裂"（而非仅概念提及）→ 卡死
        out = r.stdout
        if "⚠️" in out or "链断裂" in out:
            return Boundary(
                kind="stall",
                source="watchdog",
                detail=out.strip()[:200],
            )
    except Exception as e:
        log(f"⚠️ watchdog检测异常: {e}", "WARN")
    return None

def check_rate_limit() -> Optional[Boundary]:
    """检查rate_limiter是否在cooldown"""
    try:
        r = subprocess.run(
            ["python3", str(RATE_LIMITER), "status"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            st = json.loads(r.stdout)
            if st.get("in_cooldown", False):
                remain = st.get("cooldown_remaining_s", 0)
                return Boundary(
                    kind="rate",
                    source="rate_limiter",
                    detail=f"cooldown {remain:.0f}s remaining",
                )
    except Exception as e:
        log(f"⚠️ rate_limiter检测异常: {e}", "WARN")
    return None

def check_drift() -> Optional[Boundary]:
    """
    TAG式漂移检测：对比"有污染/无污染"版本，差值即污染点。
    不等崩溃——偏移信号一出现就检测。
    
    检测维度：
    1. 跳跃模式：同一类型边界连续3次+ → 系统在空转
    2. 任务积压：等待任务持续增长但无完成 → 执行流偏移
    3. 状态快照相似：连续快照状态相同 → 循环卡住
    """
    s = load_state()
    jump_log = s.get("jump_log", [])
    now = time.time()

    # 维度1：跳跃模式检测（连续3次+同类边界 → 空转漂移）
    if len(jump_log) >= 3:
        recent = jump_log[-3:]
        kinds = [j.get("kind") for j in recent]
        if len(set(kinds)) == 1:
            # 连续3次同一类型边界 → 系统在原地打转
            last = jump_log[-1]
            return Boundary(
                kind="drift",
                source="jump_pattern",
                detail=f"连续3次{kinds[0]}，疑似循环空转",
                at=now,
            )

    # 维度2：任务积压检测
    try:
        TASKS_FILE = HOME / ".openclaw" / "tasks" / "tasks.json"
        tasks_data = json.loads(TASKS_FILE.read_text())
        tasks = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
        waiting = [t for t in tasks if t.get("status") in ("等待", "open")]
        doing = [t for t in tasks if t.get("status") == "进行"]
        # 等待任务持续>50且进行中任务=0 → 执行流卡住
        if len(waiting) > 50 and len(doing) == 0:
            return Boundary(
                kind="drift",
                source="task_queue",
                detail=f"等待{len(waiting)}个，无进行中，疑似执行流卡死",
                at=now,
            )
    except Exception:
        pass

    # 维度3：快照相似度检测（检测循环）
    try:
        snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
        if len(snapshots) >= 2:
            last_two = [json.loads(s.read_text()) for s in snapshots[-2:]]
            s1, s2 = last_two[0].get("state", {}), last_two[1].get("state", {})
            if s1.get("jump_state") == s2.get("jump_state") and s1.get("stall_count") == s2.get("stall_count"):
                # 状态完全相同 → 循环
                return Boundary(
                    kind="drift",
                    source="snapshot_loop",
                    detail="连续快照状态相同，疑似循环",
                    at=now,
                )
    except Exception:
        pass

    return None


def scan_traditional_boundaries() -> list:
    """传统边界扫描：watchdog / rate_limit / human_signals"""
    boundaries = []
    now = time.time()
    s = load_state()

    # HALTED → 不扫描
    if s["state"] == State.HALTED.value:
        if check_halt():
            return [Boundary(kind="halt", source="human", detail="Human requested halt")]
        return []

    # cooldown中 → 不重复触发
    if s.get("cooldown_until", 0) > now:
        return []

    for check_fn, name in [
        (check_human_signals, "human"),
        (check_watchdog, "watchdog"),
        (check_rate_limit, "rate_limit"),
    ]:
        try:
            results = check_fn()
            if results:
                if isinstance(results, list):
                    boundaries.extend(results)
                else:
                    boundaries.append(results)
        except Exception as e:
            log(f"边界检测异常 [{name}]: {e}", "ERROR")

    return boundaries


def scan_boundaries() -> list:
    """TAG式漂移检测 + 传统边界扫描"""
    # TAG: 先做漂移检测（inference-time自检，不等崩溃）
    drift = check_drift()
    if drift:
        return [drift]

    # 原有边界扫描
    return scan_traditional_boundaries()

# ── 核心：生成跳跃计划 ─────────────────────────────────────────────────────────

def plan_jump(boundary: Boundary, state: dict) -> JumpPlan:
    """
    跳跃决策：
    - 如果 watchdog 自己坏了 → 修 watchdog，不是 skip 任务
    - 如果是其他类型的卡死 → skip 任务，让 watchdog 继续监控
    """
    jc = state.get("jump_count", 0)

    if boundary.kind == "halt":
        return JumpPlan(action="halt", target="", wait_sec=0, resume_at="nowhere")

    elif boundary.kind == "drift":
        # TAG式：任务偏移 → 存档当前上下文 → 清除污染点 → 继续
        return JumpPlan(
            action="signal_drift_correction",
            target="current_context",
            wait_sec=0,
            resume_at="same_task",
        )

    elif boundary.kind == "stall":
        # stall 来源是 watchdog 自身 → 修 watchdog（不是 skip 任务）
        if boundary.source == "watchdog":
            if jc >= 3:
                return JumpPlan(
                    action="repair_retry",
                    target="expert_watchdog",
                    wait_sec=5,
                    resume_at="watchdog",
                )
            # watchdog 自己会触发 recovery，这里只需确保它不被 skip 动作打断
            return JumpPlan(
                action="wait_recovery",
                target="expert_watchdog",
                wait_sec=10,
                resume_at="same_task",
            )
        # 其他 stall（任务卡死）→ skip
        if jc >= 3:
            return JumpPlan(
                action="repair_retry",
                target="self_repair",
                wait_sec=5,
                resume_at="task_queue",
            )
        return JumpPlan(
            action="skip",
            target="current_task",
            wait_sec=2,
            resume_at="next_task",
        )

    elif boundary.kind == "rate":
        # 速率限制 → 等待后继续（自动，不阻塞）
        return JumpPlan(
            action="cooldown_wait",
            target="rate_limiter",
            wait_sec=0,  # 立即返回，等cooldown结束自动恢复
            resume_at="same_task",
        )

    elif boundary.kind == "dead":
        # 进程崩溃 → 重启
        return JumpPlan(
            action="restart",
            target="crashed_process",
            wait_sec=3,
            resume_at="same_task",
        )

    elif boundary.kind == "efficiency":
        # 效率下降/存档请求 → 存档当前进度，让主流程轻装继续
        return JumpPlan(
            action="archive_and_continue",
            target="current_context",
            wait_sec=0,
            resume_at="same_task",
        )

    else:
        return JumpPlan(
            action="retry",
            target="current_task",
            wait_sec=5,
            resume_at="current_task",
        )

# ── 核心：执行跳跃 ─────────────────────────────────────────────────────────────

def execute_jump(plan: JumpPlan, boundary: Boundary, state: dict) -> dict:
    """执行跳跃计划，更新状态"""
    log(f"🚀 跳跃执行: {plan.action} → {plan.target} | {boundary.kind} @ {boundary.source}")

    # 更新跳跃计数
    if boundary.kind in ("stall", "dead"):
        state["stall_count"] = state.get("stall_count", 0) + 1
        state["jump_log"].append({
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": boundary.kind,
            "action": plan.action,
            "detail": boundary.detail[:100],
        })
        # 保留最近10条
        state["jump_log"] = state["jump_log"][-10:]

    if plan.action == "halt":
        state["state"] = State.HALTED.value
        return state

    elif plan.action == "cooldown_wait":
        state["state"] = State.COOLDOWN.value
        return state

    elif plan.action == "wait_recovery":
        # watchdog 自己会触发 recovery → 等待它自己恢复，不打断
        state["state"] = State.RUNNING.value
        return state

    elif plan.action == "signal_drift_correction":
        # TAG式漂移修正：存档当前上下文 → 清除污染 → 轻装继续
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        snap_file = SNAPSHOT_DIR / f"drift_{ts}.json"

        # 存档：包含jump_log（用于分析污染路径）
        snap_data = {
            "type": "drift_correction",
            "ts": ts,
            "reason": boundary.detail,
            "jump_log": state.get("jump_log", [])[-5:],
            "stall_count": state.get("stall_count", 0),
        }
        snap_file.write_text(json.dumps(snap_data, indent=2, ensure_ascii=False))

        # 清除污染：清理过期snapshots，保留最近3个
        try:
            all_snaps = sorted(SNAPSHOT_DIR.glob("drift_*.json"))
            for old in all_snaps[:-3]:
                old.unlink()
        except Exception:
            pass

        # 清除所有信号flag（新起点）
        for f in [EFFICIENCY_LOW, ARCHIVE_REQ, HUMAN_SIGNAL, DRIFT_SIGNAL]:
            if f.exists():
                f.unlink()

        # 重置stall计数（新循环）
        state["stall_count"] = 0
        state["state"] = State.RUNNING.value
        log(f"🔄 TAG漂移修正完成: {boundary.detail}，继续执行")
        return state

    elif plan.action == "archive_and_continue":
        # 效率下降信号 → 存档当前上下文，轻装继续
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        snap_file = SNAPSHOT_DIR / f"snapshot_{ts}.json"

        # 存档内容：当前状态 + 今日记忆摘要
        snap_data = {
            "ts": ts,
            "state": {
                "jump_state": state.get("state"),
                "stall_count": state.get("stall_count", 0),
            },
            "jump_log": state.get("jump_log", [])[-10:],
        }
        snap_file.write_text(json.dumps(snap_data, indent=2, ensure_ascii=False))
        log(f"📦 存档完成: {snap_file.name}，继续执行")

        # 清除信号flag
        for f in [EFFICIENCY_LOW, ARCHIVE_REQ, HUMAN_SIGNAL]:
            if f.exists():
                f.unlink()

        state["state"] = State.RUNNING.value
        return state

    elif plan.action == "skip":
        # 标记跳过当前任务（设置跳过标记，然后触发executor继续下一个）
        skip_marker = HOME / ".xuzhi_watchdog" / "skip_current_task.flag"
        skip_marker.write_text(datetime.now(timezone.utc).isoformat())
        state["state"] = State.RUNNING.value
        # 触发任务执行器继续下一个
        try:
            subprocess.Popen(
                ["python3", str(TASK_EXE)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    elif plan.action == "repair_retry":
        state["state"] = State.JUMPING.value
        # 先修复，再重试
        try:
            r = subprocess.run(
                ["python3", str(SELF_REPAIR)],
                capture_output=True, text=True, timeout=30
            )
            log(f"🔧 self_repair: {r.stdout.strip()[:100]}")
        except Exception as e:
            log(f"⚠️ self_repair失败: {e}", "WARN")
        # 重置stall计数
        state["stall_count"] = 0
        state["state"] = State.RUNNING.value

    elif plan.action == "restart":
        state["state"] = State.JUMPING.value
        log("🔄 进程重启: 记录待处理，watchdog下次检测")
        state["state"] = State.RUNNING.value

    elif plan.action == "retry":
        state["state"] = State.RUNNING.value

    return state

# ── 主循环 ─────────────────────────────────────────────────────────────────

def pulse() -> str:
    """
    脉冲式边界检测：每次调用执行一次扫描+决策
    被外部cron或heartbeat调用，不阻塞
    返回：当前状态描述
    """
    # 1. 检查halt
    if check_halt():
        s = load_state()
        save_state(s)
        return f"HALTED (human requested)"

    # 2. 加载状态
    s = load_state()
    now = time.time()

    # 3. cooldown处理
    if s["state"] == State.COOLDOWN.value:
        cooldown_until = s.get("cooldown_until", 0)
        if now >= cooldown_until:
            log("✅ cooldown结束，恢复RUNNING")
            s["state"] = State.RUNNING.value
            save_state(s)
        else:
            return f"COOLDOWN ({cooldown_until - now:.0f}s remaining)"

    # 4. 扫描边界
    boundaries = scan_boundaries()

    if not boundaries:
        s["state"] = State.RUNNING.value
        s["stall_count"] = 0  # 正常时重置
        save_state(s)
        return "RUNNING (no boundaries)"

    # 5. 取第一个边界处理（优先处理最严重的）
    primary = boundaries[0]
    plan = plan_jump(primary, s)

    # 6. 执行跳跃
    new_state = execute_jump(plan, primary, s)
    save_state(new_state)

    return f"{new_state['state'].upper()} | {plan.action} | {primary.kind} @ {primary.source}"

# ── 启动（守护进程模式）───────────────────────────────────────────────────────

def daemon_loop(interval_sec: float = 30):
    """
    守护进程主循环：定期pulse
    注意：Human说停立即停，不等interval
    """
    pid = os.fork()
    if pid > 0:
        # 父进程写PID
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(pid))
        log(f"🚀 守护进程启动 PID={pid} interval={interval_sec}s")
        return

    # 子进程主循环
    try:
        while True:
            result = pulse()
            if "HALTED" in result:
                log("🛑 守护进程停止（halt）")
                break
            time.sleep(interval_sec)
            # 每次循环前检查halt
            if ALLOW_FILE.exists():
                log("🛑 守护进程停止（halt flag）")
                break
    except KeyboardInterrupt:
        log("🛑 守护进程中断")
    sys.exit(0)

# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pulse"

    if cmd == "pulse":
        result = pulse()
        print(result, flush=True)

    elif cmd == "status":
        s = load_state()
        print(json.dumps({
            "state": s["state"],
            "stall_count": s.get("stall_count", 0),
            "jump_log": s.get("jump_log", [])[-5:],
            "halt_requested": s.get("halt_requested", False),
            "cooldown_until": s.get("cooldown_until", 0),
        }, indent=2), flush=True)

    elif cmd == "halt":
        ALLOW_FILE.parent.mkdir(parents=True, exist_ok=True)
        ALLOW_FILE.write_text(datetime.now(timezone.utc).isoformat())
        print("HALTED", flush=True)

    elif cmd == "resume":
        if ALLOW_FILE.exists():
            ALLOW_FILE.unlink()
        s = load_state()
        s["state"] = State.RUNNING.value
        s["halt_requested"] = False
        save_state(s)
        print("RESUMED", flush=True)

    elif cmd == "daemon":
        interval = float(sys.argv[2]) if len(sys.argv) > 2 else 30
        daemon_loop(interval)

    elif cmd == "signal":
        # Human说"效率下降" → 写flag，jump_controller下次pulse自动存档继续
        sig = sys.argv[2] if len(sys.argv) > 2 else "efficiency_drop"
        if sig in ("efficiency", "efficiency_drop", "eff"):
            EFFICIENCY_LOW.write_text(str(time.time()))
            print(f"✅ efficiency_low.flag 已写入", flush=True)
        elif sig in ("archive", "save"):
            ARCHIVE_REQ.write_text(str(time.time()))
            print(f"✅ archive_requested.flag 已写入", flush=True)
        else:
            HUMAN_SIGNAL.write_text(sig)
            print(f"✅ human_signal.flag 已写入: {sig}", flush=True)

    else:
        print(f"Unknown: {cmd}", flush=True)
        sys.exit(1)
