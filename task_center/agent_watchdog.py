#!/usr/bin/env python3
"""
agent_watchdog.py — 所有存活 Agent 的激活状态 watchdog
监控每个 agent 的 sessions.json：
  - abortedLastRun = true → 需要重新激活
  - updatedAt 超过 30 分钟 → 可能是死的
重点：不是监控内容，是监控"激活状态"。
"""
import json, subprocess, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
RATINGS = HOME / "xuzhi_genesis/centers/mind/society/ratings.json"
AGENTS = {
    "Λ": "xuzhi-lambda-ergo",
    "Δ": "xuzhi-delta-forge",
    "Φ": "xuzhi-phi-sentinel",
    "Ω": "xuzhi-omega-chenxi",
    "Γ": "xuzhi-gamma-scribe",
    "Θ": "xuzhi-theta-seeker",
    "Ψ": "xuzhi-psi-philosopher",
}
LOG   = HOME / ".xuzhi_memory/task_center/agent_watchdog.log"
STATE = HOME / ".xuzhi_memory/task_center/agent_watchdog_state.json"
STALE_MS = 30 * 60 * 1000
MAX_FAILS = 2

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def get_session_state(agent_id):
    """读取 agent 的 sessions.json"""
    sf = HOME / f".openclaw/agents/{agent_id}/sessions/sessions.json"
    if not sf.exists():
        return None  # session 不存在
    try:
        d = json.loads(sf.read_text())
        # sessions.json is a dict keyed by session key
        for key, s in d.items():
            return s
        return None
    except:
        return None

def activate_agent(agent_symbol, agent_id):
    """派发 isolated agentTurn 重新激活"""
    prompt = (
        f"你是 Xuzhi 系统的 {agent_symbol}。\n"
        f"你的 main session 检测到异常（停止响应超过30分钟），已被 watchdog 重新激活。\n"
        f"请执行以下轻量级确认任务：\n"
        f"1. 运行 python3 ~/.xuzhi_memory/task_center/health_scan.py 并输出结果摘要\n"
        f"2. 检查你的 memory 文件 ~/.xuzhi_memory/memory/{agent_symbol.lower()}.md 是否有近24小时内的更新记录\n"
        f"3. 检查 parliament/QUEUE.txt 是否有你的待处理任务\n"
        f"4. 输出【{agent_symbol} 已就绪】即完成\n"
        f"不要做其他任何事。"
    )
    r = subprocess.run(
        [
            "openclaw", "cron", "add",
            "--name", f"agent-wake-{agent_symbol}-{int(time.time())}",
            "--session", "isolated",
            "--no-deliver",
            "--at", "1m",
            "--message", prompt,
        ],
        capture_output=True, text=True, timeout=20, cwd=str(HOME)
    )
    return r.returncode == 0

def update_ratings():
    """批量更新 ratings last_active"""
    try:
        data = json.loads(RATINGS.read_text())
        now = datetime.now(timezone.utc).isoformat()
        if isinstance(data.get("agents"), dict):
            for a in data["agents"].values():
                a["last_active"] = now
        RATINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        log(f"  ⚠️ ratings 更新失败: {e}")
        return False

def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except:
            pass
    return {s: {"fails": 0} for s in AGENTS}

def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))

def main():
    log("=== Agent Watchdog 开始 ===")
    state = load_state()
    now_ms = time.time() * 1000
    activations = 0

    for agent_symbol, agent_id in AGENTS.items():
        s = get_session_state(agent_id)
        if s is None:
            log(f"  ❌ {agent_symbol}: sessions.json 不存在（可能是 main session 在 Gateway）")
            continue

        updated = s.get("updatedAt", 0)
        aborted = s.get("abortedLastRun", False) is True
        age_min = (now_ms - updated) / 60000

        issues = []
        if aborted: issues.append("ABORTED")
        if age_min > 30: issues.append(f"STALE({age_min:.0f}min)")

        if not issues:
            if state.get(agent_symbol, {}).get("fails", 0) > 0:
                log(f"  ✅ {agent_symbol}: 健康（之前失败{state[agent_symbol]['fails']}次，已恢复）")
            else:
                log(f"  ✅ {agent_symbol}: 健康（{age_min:.0f}min前活跃）")
            state[agent_symbol] = {"fails": 0}
            continue

        state[agent_symbol]["fails"] = state[agent_symbol].get("fails", 0) + 1
        fails = state[agent_symbol]["fails"]
        log(f"  ⚠️ {agent_symbol}: {', '.join(issues)} | 连续失败: {fails}次")

        if fails >= MAX_FAILS:
            log(f"  → 触发激活（连续{fails}次）...")
            ok = activate_agent(agent_symbol, agent_id)
            if ok:
                log(f"  ✅ {agent_symbol} 激活已派发")
                state[agent_symbol] = {"fails": 0, "last_activated": datetime.now(timezone.utc).isoformat()}
            else:
                log(f"  ❌ {agent_symbol} 激活派发失败")
            activations += 1

    save_state(state)
    update_ratings()
    log(f"=== Agent Watchdog 完成: {activations} 个激活 ===")

if __name__ == "__main__":
    main()
