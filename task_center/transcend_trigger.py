#!/usr/bin/env python3
"""
transcend_trigger.py — 开拓相触发器
当 Δ_Stability = 0 且 quota > 40% 时，自主注入提案任务。
不等待人类指令，不增加功能，只注入方向性提案。
"""
import json, sys, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
QUOTA_STATUS = HOME / ".openclaw" / "centers" / "engineering" / "crown" / "quota_usage.json"
TASKS_JSON   = HOME / ".openclaw" / "tasks" / "tasks.json"
QUOTA_GUARD = HOME / ".xuzhi_watchdog" / "quota_exhausted"
QUORUM_FILE = HOME / ".xuzhi_memory" / "task_center" / "transcend_quorum.json"
LOG         = HOME / ".xuzhi_memory" / "task_center" / "transcend.log"

QUOTA_THRESHOLD = 40   # quota > 40% 才触发
COOLDOWN_HOURS  = 24   # 24小时最多一次
CYCLE_FILE      = HOME / ".xuzhi_memory" / "task_center" / "transcend_cycle.json"

PROPOSALS = [
    {
        "title": "【预研】agent 启动 pantheon 广播机制",
        "dept": "engineering",
        "agent": "Φ",
        "desc": "在 self_heal.sh 中加入 agent 启动广播，各 agent 定期读彼此状态，消除社会身份盲区"
    },
    {
        "title": "【压测】模拟 T3 Checkpoint 卡死场景",
        "dept": "engineering",
        "agent": "Δ",
        "desc": "用 chaos_test.py 模拟连续 compaction，验证断点恢复协议的实际效果"
    },
    {
        "title": "【预研】意图日志压缩：O(N)→O(1)",
        "dept": "intelligence",
        "agent": "Θ",
        "desc": "当前 intent_log.jsonl 线性增长，达到上限后需提炼为高阶摘要，实现常数级检索"
    },
    {
        "title": "【压测】794 速率限制断点恢复演练",
        "dept": "engineering",
        "agent": "Φ",
        "desc": "用 chaos monkey 主动触发 794，验证 rate_limiter 的自适应容量 + exponential backoff 是否有效"
    },
    {
        "title": "【预研】宪法运行时一致性验证",
        "dept": "engineering",
        "agent": "Δ",
        "desc": "启动时验证 sticky-bit 宪法文件 hash 与上次记录一致，不一致则 quarantine"
    },
    {
        "title": "【架构】跨 agent 主动状态感知雷达",
        "dept": "intelligence",
        "agent": "Γ",
        "desc": "定期扫描所有 intent_log + agent_heartbeats，识别 pending 超1小时/超时未广播/日志卡住"
    },
    {
        "title": "【预研】Ω 战略引擎：自动生成系统演化路径",
        "dept": "mind",
        "agent": "Ω",
        "desc": "当连续3天无异常时，自动生成下一个演化方向提案，注入任务队列"
    },
    {
        "title": "【哲学】Ψ 反思：系统是否真正理解'自我'？",
        "dept": "philosophy",
        "agent": "Ψ",
        "desc": "断点恢复的本质是记忆，但记忆不等于理解——系统是否有真正的自我模型？"
    },
]


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_quota_pct() -> float:
    try:
        for tier in json.loads(open(QUOTA_STATUS).read()).get("tiers", []):
            if tier["name"] == "5_hour":
                return tier["pct"]
    except Exception:
        pass
    return 0


def check_quorum() -> bool:
    """守卫：防止过度触发，24小时最多一次"""
    try:
        d = json.loads(open(QUORUM_FILE).read())
        last = d.get("last_trigger_at", 0)
        if time.time() - last < COOLDOWN_HOURS * 3600:
            log(f"⏳ cooldown: {COOLDOWN_HOURS}h 内不重复触发")
            return False
    except Exception:
        pass
    return True


def bump_quorum():
    QUORUM_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUORUM_FILE.write_text(json.dumps({
        "last_trigger_at": time.time(),
        "last_proposal": PROPOSALS[0]["title"]
    }))


def is_exhausted() -> bool:
    return QUOTA_GUARD.exists()


def get_task_count() -> int:
    try:
        d = json.load(open(TASKS_JSON))
        tasks = d.get("tasks", []) if isinstance(d, dict) else d
        return len([t for t in tasks if t.get("status") in ("等待", "进行")])
    except Exception:
        return 0


def inject_proposal(proposal: dict) -> bool:
    """注入一个提案任务到 tasks.json"""
    try:
        d = json.load(open(TASKS_JSON))
        if isinstance(d, dict):
            tasks = d.get("tasks", [])
            nid = d.get("next_id", 1)
            d["next_id"] = nid + 1
        else:
            tasks = d
            nid = (max((t["id"] for t in tasks), default=0) or 0) + 1

        task = {
            "id": nid,
            "title": proposal["title"],
            "description": proposal["desc"],
            "department": proposal["dept"],
            "status": "等待",
            "priority": "低",
            "created_by": "transcend_trigger",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tasks.append(task)
        d["tasks"] = tasks
        TASKS_JSON.parent.mkdir(parents=True, exist_ok=True)
        TASKS_JSON.write_text(json.dumps(d, indent=2, ensure_ascii=False))
        log(f"📋 提案已注入: {proposal['title']}")
        return True
    except Exception as e:
        log(f"❌ 注入失败: {e}")
        return False


def main():
    log("=== 开拓相诊断 ===")

    # Δ_Stability 检查：系统是否完全健康？
    quota_pct = get_quota_pct()
    exhausted = is_exhausted()
    task_count = get_task_count()

    # 用 --brief 健康扫描
    import subprocess
    try:
        r = subprocess.run(
            ["python3", str(HOME / "xuzhi_workspace" / "task_center" / "health_scan.py"), "--brief"],
            capture_output=True, text=True, timeout=15
        )
        healthy = "healthy" in r.stdout and "true" in r.stdout
    except Exception:
        healthy = task_count == 0 and not exhausted

    log(f"Δ_Stability: quota={quota_pct:.1f}% exhausted={exhausted} tasks={task_count} healthy={healthy}")

    # 开拓条件：系统健康 + quota > 阈值 + 非 exhausted + cooldown 通过
    if healthy and quota_pct > QUOTA_THRESHOLD and not exhausted and check_quorum():
        import random
        proposal = random.choice(PROPOSALS)
        if inject_proposal(proposal):
            bump_quorum()
            log(f"🚀 开拓相触发: {proposal['title']}")
    else:
        reasons = []
        if not healthy: reasons.append("系统不健康")
        if quota_pct <= QUOTA_THRESHOLD: reasons.append(f"quota={quota_pct:.1f}%≤{QUOTA_THRESHOLD}%")
        if exhausted: reasons.append("exhausted")
        if not check_quorum(): reasons.append("cooldown")
        log(f"⏸ 未触发开拓相: {' + '.join(reasons)}")


if __name__ == "__main__":
    main()
