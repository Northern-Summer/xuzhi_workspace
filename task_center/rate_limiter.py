#!/usr/bin/env python3
"""
rate_limiter.py — Token Bucket 速率限制器（主动控速）
设计原则：
- 事前控速，不事后重试
- 滑动时间窗口（5分钟）
- 容量可配置（默认10个 agentTurn/窗口）
- 跨 task_executor + heartbeat_tasks 共享状态

调用方式：
  python3 rate_limiter.py acquire <source>  # 获取 token，返回 (ok, remaining, wait_seconds)
  python3 rate_limiter.py status             # 查看当前状态
  python3 rate_limiter.py reset              # 重置窗口（仅人工触发）
"""
import json
import sys
import time
import os
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
STATE_FILE = HOME / ".xuzhi_memory" / "task_center" / "rate_limit_state.json"
HOLD_FILE  = HOME / ".xuzhi_watchdog"  / "rate_limit_hold"
LOG_FILE   = HOME / ".xuzhi_memory"    / "task_center" / "rate_limiter.log"

# ── 配置 ──────────────────────────────────────────────────────────────────────
WINDOW_SECS  = 300   # 5分钟滑动窗口
CAPACITY     = 10    # 每窗口最多 N 个 agentTurn（可按 quota 调低）
BURST_PAD    = 2     # 保留 buffer，防止瞬间耗尽
SAFE_CAP     = max(1, CAPACITY - BURST_PAD)  # 实际可用 = 8

# 冷却参数（发现 794 后用）
COOLDOWN_SECS = 60   # 触发 794 后冷却 60s
RETRY_INTERVAL = 15  # 无 token 时重试间隔

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state() -> dict:
    """加载或初始化状态"""
    now = time.time()
    default = {
        "tokens": SAFE_CAP,       # 当前可用 token 数
        "window_start": now,       # 窗口起始时间
        "requests": [],            # {time, source} 历史（用于滑动窗口）
        "cooldown_until": 0,       # 794 触发后的冷却截止时间
        "last_refill": now,
    }
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            # 校验必要字段
            for k in ["tokens", "window_start", "requests", "cooldown_until"]:
                if k not in state:
                    state[k] = default[k]
            return state
        except Exception:
            pass
    return default


def save_state(state: dict):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        log(f"⚠️ 状态写入失败: {e}")


def refill_tokens(state: dict) -> dict:
    """滑动窗口重置：清空超过 WINDOW_SECS 的历史请求，补充 token"""
    now = time.time()
    window_elapsed = now - state["window_start"]

    if window_elapsed < WINDOW_SECS:
        # 窗口未过期，只补充按时间流逝的比例 token
        # 精确保补：每 WINDOW_SECS 完全补充 SAFE_CAP
        fraction = window_elapsed / WINDOW_SECS
        elapsed_tokens = int((SAFE_CAP - state["tokens"]) * fraction)
        # 不在这里补，等窗口过期
        return state

    # 窗口过期 → 滑动重置
    state["tokens"] = SAFE_CAP
    state["window_start"] = now
    state["requests"] = []
    state["last_refill"] = now
    log(f"🔄 Token window refilled: {SAFE_CAP} tokens (window reset)")
    return state


def sliding_window_update(state: dict) -> dict:
    """清理过期请求记录"""
    now = time.time()
    cutoff = now - WINDOW_SECS
    state["requests"] = [r for r in state["requests"] if r["time"] > cutoff]
    return state


def acquire_token(source: str) -> tuple:
    """
    尝试获取 1 个 token。
    返回 (ok: bool, remaining: int, wait_seconds: float)
    - ok=True: 获取成功
    - ok=False: 触发冷却或窗口满，需等待 wait_seconds
    """
    now = time.time()
    state = load_state()

    # ── 1. 冷却检查 ─────────────────────────────────────────────────────────
    if now < state["cooldown_until"]:
        wait = state["cooldown_until"] - now
        log(f"⏸️ [{source}] 冷却中: {wait:.0f}s remaining")
        return False, 0, wait

    # ── 2. Token 补充（窗口滑动）──────────────────────────────────────────
    state = refill_tokens(state)
    state = sliding_window_update(state)

    # ── 3. 配额检查 ────────────────────────────────────────────────────────
    if state["tokens"] <= 0:
        # 计算到窗口过期还需多久
        wait = WINDOW_SECS - (now - state["window_start"])
        log(f"🚫 [{source}] 窗口满: {state['tokens']} tokens, 等待 {wait:.0f}s")
        return False, 0, max(0.1, wait)

    # ── 4. 消耗 token ──────────────────────────────────────────────────────
    state["tokens"] -= 1
    state["requests"].append({"time": now, "source": source})
    save_state(state)

    log(f"✅ [{source}] token acquired: {state['tokens']}/{SAFE_CAP} remaining")
    return True, state["tokens"], 0


def trigger_cooldown(source: str, error_msg: str = ""):
    """收到 794 或类似速率错误时，触发冷却期"""
    state = load_state()
    now = time.time()
    state["cooldown_until"] = now + COOLDOWN_SECS
    save_state(state)
    log(f"⚠️ [{source}] 速率错误触发冷却 {COOLDOWN_SECS}s: {error_msg[:80]}")
    HOLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    HOLD_FILE.write_text(
        json.dumps({
            "reason": "rate_limit",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "cooldown_until": state["cooldown_until"],
            "source": source,
            "error": error_msg[:200],
        })
    )


def release_hold():
    """冷却结束，释放 hold 文件"""
    if HOLD_FILE.exists():
        HOLD_FILE.unlink()
        log("🔓 rate_limit_hold released")


def get_status() -> dict:
    """获取当前速率限制状态"""
    state = load_state()
    now = time.time()
    return {
        "tokens": state["tokens"],
        "capacity": SAFE_CAP,
        "window_start": state["window_start"],
        "window_elapsed": now - state["window_start"],
        "window_secs": WINDOW_SECS,
        "in_cooldown": now < state["cooldown_until"],
        "cooldown_until": state["cooldown_until"],
        "cooldown_remaining": max(0, state["cooldown_until"] - now),
        "requests_in_window": len(state["requests"]),
        "last_refill": state["last_refill"],
    }


# ── CLI 入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "acquire":
        if len(sys.argv) < 3:
            print("Usage: rate_limiter.py acquire <source>")
            sys.exit(1)
        source = sys.argv[2]
        ok, remaining, wait = acquire_token(source)
        if ok:
            print(f"OK:{remaining}")
            sys.exit(0)
        else:
            print(f"HOLD:{wait:.0f}")
            sys.exit(1)

    elif cmd == "cooldown":
        # 外部检测到 794 时调用
        reason = sys.argv[2] if len(sys.argv) > 2 else ""
        source = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        trigger_cooldown(source, reason)
        sys.exit(0)

    elif cmd == "release":
        release_hold()
        sys.exit(0)

    elif cmd == "status":
        s = get_status()
        print(json.dumps(s, indent=2))
        sys.exit(0)

    elif cmd == "reset":
        state = load_state()
        now = time.time()
        state["tokens"] = SAFE_CAP
        state["window_start"] = now
        state["requests"] = []
        state["cooldown_until"] = 0
        save_state(state)
        release_hold()
        print("RESET")
        sys.exit(0)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
