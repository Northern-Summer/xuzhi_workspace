#!/usr/bin/env python3
"""
agent_watchdog.py — 所有存活 Agent 的激活状态 watchdog
重点：不是监控内容，是监控"激活状态"。
防止并发：文件锁确保同一时刻只有一个实例运行。
冷却机制：最近10分钟内已激活 → 跳过。
"""
import json, subprocess, time, os
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
LOCKFILE = HOME / ".xuzhi_memory/task_center/.agent_watchdog.lock"
LOG      = HOME / ".xuzhi_memory/task_center/agent_watchdog.log"
STATE    = HOME / ".xuzhi_memory/task_center/agent_watchdog_state.json"
STALE_MS = 30 * 60 * 1000   # 30 min
COOLDOWN_S = 600             # 10 min cooldown
MAX_FAILS  = 2

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def acquire_lock():
    """文件锁——防止并发执行"""
    try:
        os.makedirs(str(LOCKFILE.parent), exist_ok=True)
        os.mkdir(str(LOCKFILE))
        return True
    except FileExistsError:
        return False

def release_lock():
    try:
        os.rmdir(str(LOCKFILE))
    except:
        pass

def get_session_state(agent_id):
    """读取最新 session（按 updatedAt 排序）"""
    sf = HOME / f".openclaw/agents/{agent_id}/sessions/sessions.json"
    if not sf.exists():
        return None
    try:
        d = json.loads(sf.read_text())
        sessions = [(k, s) for k, s in d.items() if s.get("updatedAt")]
        if not sessions:
            return None
        sessions.sort(key=lambda x: x[1].get("updatedAt", 0), reverse=True)
        return sessions[0][1]
    except:
        return None

def is_recently_activated(last_activated_str):
    """最近10分钟内已激活 → 跳过"""
    if not last_activated_str:
        return False
    try:
        last = last_activated_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(last)
        return (datetime.now(timezone.utc) - dt).total_seconds() < COOLDOWN_S
    except:
        return False

def activate_agent(agent_symbol, agent_id):
    """
    用文件信号激活 agent（零新 session，零递归 spawn）。
    直接 sessions_send 到目标 agent，main session 处理唤醒逻辑。
    """
    # Map agent_symbol to session key
    session_map = {
        "Φ": "agent:phi:main",
        "Δ": "agent:delta:main",
        "Θ": "agent:theta:main",
        "Γ": "agent:gamma:main",
        "Ω": "agent:omega:main",
        "Ψ": "agent:psi:main",
    }
    session_key = session_map.get(agent_symbol)
    if not session_key:
        log(f"未知 agent: {agent_symbol}")
        return False

    prompt = (
        f"【{agent_symbol} 唤醒信号】
"
        f"执行激活流程：
"
        f"1. 检查 ~/.xuzhi_watchdog/wake_signals/wake_{agent_symbol}.json
"
        f"2. 运行 health_scan 或等效检查
"
        f"3. 更新 ratings.json 的 last_active 时间戳
"
        f"4. 输出【{agent_symbol} 已就绪】
"
        f"不要 spawn 新的 agent，不要调用 cron add。"
    )
    r = subprocess.run(
        ["openclaw", "sessions", "send",
         "--session", session_key,
         "--message", prompt,
         "--timeout", "30"],
        capture_output=True, text=True, timeout=30, cwd=str(HOME)
    )
    if r.returncode == 0:
        log(f"✅ {agent_symbol} 唤醒信号已发送")
        return True
    else:
        log(f"❌ {agent_symbol} 唤醒失败: {r.stderr[:100]}")
        return False

def update_ratings():
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
    return {}

def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))

def main():
    if not acquire_lock():
        log("跳过（已有实例运行）")
        return

    try:
        log("=== Agent Watchdog 开始 ===")
        state = load_state()
        now_ms = time.time() * 1000
        activations = 0

        for agent_symbol, agent_id in AGENTS.items():
            s = get_session_state(agent_id)

            if s is None:
                # 无 isolated sessions.json → 检查 ratings.last_active 作为代理
                try:
                    data = json.loads(RATINGS.read_text())
                    agents = data.get("agents", {})
                    if isinstance(agents, dict):
                        agent_data = agents.get(agent_symbol) or agents.get(agent_id)
                    else:
                        agent_data = None
                    if agent_data:
                        last_active = agent_data.get("last_active", "")
                        if last_active:
                            dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                            age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
                            is_stale = age_min > 30
                        else:
                            is_stale = True
                    else:
                        is_stale = False
                except:
                    is_stale = False

                if is_stale:
                    state.setdefault(agent_symbol, {"fails": 0})
                    state[agent_symbol]["fails"] = state[agent_symbol].get("fails", 0) + 1
                    fails = state[agent_symbol]["fails"]
                    log(f"  ⚠️ {agent_symbol}: NO_SESSION + STALE(>30min) | fails={fails}")
                    if fails >= MAX_FAILS:
                        last_act = state.get(agent_symbol, {}).get("last_activated", "")
                        if not is_recently_activated(last_act):
                            ok = activate_agent(agent_symbol, agent_id)
                            log(f"  {'✅' if ok else '❌'} {agent_symbol} 激活{'成功' if ok else '失败'}")
                            state[agent_symbol] = {"fails": 0, "last_activated": datetime.now(timezone.utc).isoformat()}
                            activations += 1
                        else:
                            log(f"  ⏳ {agent_symbol}: 冷却中（{COOLDOWN_S//60}min内已激活），跳过")
                else:
                    log(f"  ✅ {agent_symbol}: 健康（ratings.last_active 正常）")
                    state[agent_symbol] = {"fails": 0}
                continue

            updated = s.get("updatedAt", 0)
            aborted = s.get("abortedLastRun", False) is True
            age_min = (now_ms - updated) / 60000

            issues = []
            if aborted: issues.append("ABORTED")
            if age_min > 30: issues.append(f"STALE({age_min:.0f}min)")

            if not issues:
                fails = state.get(agent_symbol, {}).get("fails", 0)
                if fails > 0:
                    log(f"  ✅ {agent_symbol}: 健康（之前{fails}次失败，已恢复）")
                state[agent_symbol] = {"fails": 0}
                continue

            state.setdefault(agent_symbol, {"fails": 0})
            state[agent_symbol]["fails"] = state[agent_symbol].get("fails", 0) + 1
            fails = state[agent_symbol]["fails"]
            log(f"  ⚠️ {agent_symbol}: {', '.join(issues)} | fails={fails}")

            if fails >= MAX_FAILS:
                last_act = state.get(agent_symbol, {}).get("last_activated", "")
                if not is_recently_activated(last_act):
                    log(f"  → 触发激活...")
                    ok = activate_agent(agent_symbol, agent_id)
                    if ok:
                        log(f"  ✅ {agent_symbol} 激活成功")
                        state[agent_symbol] = {"fails": 0, "last_activated": datetime.now(timezone.utc).isoformat()}
                    else:
                        log(f"  ❌ {agent_symbol} 激活失败")
                    activations += 1
                else:
                    log(f"  ⏳ {agent_symbol}: 冷却中，跳过")

        save_state(state)
        update_ratings()
        log(f"=== Agent Watchdog 完成: {activations} 个激活 ===")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
