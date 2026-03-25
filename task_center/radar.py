#!/usr/bin/env python3
"""
radar.py — 跨 Agent 主动状态感知雷达
定期扫描所有 intent_log + agent_heartbeats，识别：
1. pending 超过 1 小时的意图
2. 超时未广播心跳的 agent
3. 日志卡住（长时间无新条目）的 agent
输出结构化报告。
"""
import json, sys, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
HEARTBEAT_DIR = HOME / ".xuzhi_memory" / "task_center" / "agent_heartbeats"
INTENT_DIR = HOME / ".xuzhi_memory" / "agents"
RADAR_LOG = HOME / ".xuzhi_memory" / "task_center" / "radar.log"
REPORT_FILE = HOME / ".xuzhi_memory" / "task_center" / "radar_report.json"

# 所有注册 agent
ALL_AGENTS = ["xi", "phi", "delta", "theta", "gamma", "omega", "psi"]

# 阈值
PENDING_THRESHOLD_HOURS = 1
HEARTBEAT_THRESHOLD_SECS = 7200  # 2小时未广播 → 失踪
LOG_STALE_THRESHOLD_SECS = 14400  # 4小时无新条目 → 卡住

OUTPUT_MODE = "brief"  # 默认 brief，可选 full


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        RADAR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(RADAR_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_intent_log(agent_id: str) -> list:
    """读取 intent log，返回所有条目（最新优先）"""
    path = INTENT_DIR / agent_id / "intent_log.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text().strip().splitlines()
        entries = []
        for line in lines[-100:]:  # 只读最近100条
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
        return entries
    except Exception:
        return []


def read_heartbeat(agent_id: str) -> dict:
    """读取心跳文件"""
    path = HEARTBEAT_DIR / f"{agent_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def parse_ts(ts_str: str) -> float:
    """解析时间戳字符串为 Unix float"""
    if not ts_str:
        return 0
    try:
        if isinstance(ts_str, (int, float)):
            return float(ts_str)
        t = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return t.timestamp()
    except Exception:
        return 0


def analyze_agent(agent_id: str) -> dict:
    """分析单个 agent 的状态"""
    result = {
        "agent": agent_id,
        "status": "alive",
        "issues": [],
        "pending_intent": None,
        "last_heartbeat": None,
        "last_heartbeat_age_secs": None,
        "last_log_entry": None,
        "last_log_age_secs": None,
    }

    now = time.time()

    # 心跳检查
    hb = read_heartbeat(agent_id)
    if hb:
        result["last_heartbeat"] = hb.get("alive_at")
        ts = parse_ts(hb.get("alive_at", ""))
        result["last_heartbeat_age_secs"] = now - ts if ts else None
        if result["last_heartbeat_age_secs"] and result["last_heartbeat_age_secs"] > HEARTBEAT_THRESHOLD_SECS:
            result["status"] = "missing"
            result["issues"].append(f"心跳超时 {result['last_heartbeat_age_secs']/3600:.1f}h")
    else:
        result["status"] = "no_heartbeat"
        result["issues"].append("从未广播心跳")

    # Intent log 检查
    entries = read_intent_log(agent_id)
    if entries:
        last = entries[-1]
        result["last_log_entry"] = last.get("ts")
        ts = parse_ts(last.get("ts", ""))
        result["last_log_age_secs"] = now - ts if ts else None

        # pending 检查
        for entry in reversed(entries):
            if entry.get("status") == "pending":
                pending_ts = parse_ts(entry.get("ts", ""))
                age_hours = (now - pending_ts) / 3600
                result["pending_intent"] = entry.get("intent", "")[:80]
                if age_hours > PENDING_THRESHOLD_HOURS:
                    result["issues"].append(f"pending超{age_hours:.1f}h: {result['pending_intent']}")
                break

        # 日志陈旧检查
        if result["last_log_age_secs"] and result["last_log_age_secs"] > LOG_STALE_THRESHOLD_SECS:
            result["issues"].append(f"日志陈旧 {result['last_log_age_secs']/3600:.1f}h")
    elif result["status"] == "alive":
        result["status"] = "no_intent_log"
        result["issues"].append("无 intent_log")

    return result


def generate_report() -> dict:
    """生成全局雷达报告"""
    agents = {}
    total_issues = 0

    for agent_id in ALL_AGENTS:
        analysis = analyze_agent(agent_id)
        agents[agent_id] = analysis
        if analysis["issues"]:
            total_issues += len(analysis["issues"])

    overall = "healthy" if total_issues == 0 else f"{total_issues}_issues"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "total_agents": len(ALL_AGENTS),
        "alive_count": sum(1 for a in agents.values() if a["status"] == "alive"),
        "missing_count": sum(1 for a in agents.values() if a["status"] in ("missing", "no_heartbeat")),
        "total_issues": total_issues,
        "agents": agents,
    }

    # 摘要行
    summary_parts = []
    if report["missing_count"] > 0:
        missing = [a for a, d in agents.items() if d["status"] in ("missing", "no_heartbeat")]
        summary_parts.append(f"失踪:{','.join(missing)}")
    pending_overdue = [(a, d["pending_intent"]) for a, d in agents.items() if any("pending超" in i for i in d["issues"])]
    if pending_overdue:
        summary_parts.append(f"pending积压:{len(pending_overdue)}个")
    stale = [a for a, d in agents.items() if any("日志陈旧" in i for i in d["issues"])]
    if stale:
        summary_parts.append(f"日志陈旧:{','.join(stale)}")

    report["summary"] = " | ".join(summary_parts) if summary_parts else "全部正常"

    return report


def format_brief(report: dict) -> str:
    """人类可读的简短摘要"""
    lines = [
        f"🔭 Radar @ {report['generated_at'][11:19]}",
        f"   存活: {report['alive_count']}/{report['total_agents']} | 失踪: {report['missing_count']} | 问题: {report['total_issues']}",
    ]
    if report["summary"] != "全部正常":
        lines.append(f"   ⚠️ {report['summary']}")
    else:
        lines.append("   ✅ 全系统正常")
    return "\n".join(lines)


def format_full(report: dict) -> str:
    """详细报告"""
    lines = [f"🔭 全局雷达 @ {report['generated_at']}", f"总体: {report['overall']}", ""]
    for agent_id in ALL_AGENTS:
        d = report["agents"][agent_id]
        status_icon = {"alive": "🟢", "missing": "🔴", "no_heartbeat": "🟡", "no_intent_log": "⚪"}.get(d["status"], "⚪")
        lines.append(f"{status_icon} {agent_id}: {d['status']}")
        if d["issues"]:
            for issue in d["issues"]:
                lines.append(f"   ⚠️ {issue}")
    return "\n".join(lines)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "brief"
    report = generate_report()

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    if mode == "full":
        print(format_full(report))
    else:
        # JSON brief: 核心数据
        brief = {
            "healthy": report["overall"] == "healthy",
            "alive": report["alive_count"],
            "missing": report["missing_count"],
            "issues": report["total_issues"],
            "summary": report["summary"],
        }
        print(json.dumps(brief, ensure_ascii=False), flush=True)

    sys.exit(0 if report["overall"] == "healthy" else 1)
