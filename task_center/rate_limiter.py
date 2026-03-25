#!/usr/bin/env python3
"""
rate_limiter.py — 自适应 Token Bucket 速率限制器
设计原则：事前控速 + 自适应容量 + Exponential backoff
"""
import json, sys, time, os
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
STATE_FILE   = HOME / ".xuzhi_memory" / "task_center" / "rate_limit_state.json"
QUOTA_STATUS = HOME / ".openclaw"     / "workspace"    / "quota_status.json"
EXHAUSTED    = HOME / ".xuzhi_watchdog"               / "quota_exhausted"
HOLD_FILE    = HOME / ".xuzhi_watchdog"               / "rate_limit_hold"
LOG_FILE     = HOME / ".xuzhi_memory"  / "task_center" / "rate_limiter.log"

# ── 静态上限（按 quota 70% 反推的安全最大值）────────────
MAX_CAP       = 8
BASE_BACKOFF  = 60    # 初始 cooldown 秒数
WINDOW_SECS   = 300   # 5分钟滑动窗口
QUOTA_CACHE_TTL = 60  # quota 状态缓存秒数（避免每次查 API）

# ── 工具 ────────────────────────────────────────────────────────────────────

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
    now = time.time()
    d = {
        "tokens": MAX_CAP,
        "window_start": now,
        "requests": [],       # [{time, source}]
        "cooldown_until": 0,
        "cooldown_level": 0,  # 0=无, 1=60s, 2=120s ...
        "shrink_until": 0,    # 触发 794 后缩小窗口截止时间
        "quota_cache": {"pct": 100, "ts": 0},  # 缓存 quota 百分比
    }
    if STATE_FILE.exists():
        try:
            d.update(json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return d

def save_state(s: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s))

def get_quota_pct() -> float:
    """读取缓存的 quota 百分比（缓存 QUOTA_CACHE_TTL 秒）"""
    now = time.time()
    s = load_state()
    cached = s.get("quota_cache", {"pct": 100, "ts": 0})
    if now - cached.get("ts", 0) < QUOTA_CACHE_TTL:
        return cached["pct"]
    # 缓存过期 → 读取 quota_status.json
    try:
        pct = 0
        for tier in json.loads(open(QUOTA_STATUS).read()).get("tiers", []):
            if tier["name"] == "5_hour":
                pct = tier["pct"]
                break
        s["quota_cache"] = {"pct": pct, "ts": now}
        save_state(s)
        return pct
    except Exception:
        return 50  # 读不到时默认中档

def compute_capacity(quota_pct: float, shrink_active: bool) -> int:
    """
    按 quota 余量动态计算安全容量：
      quota > 60%  → 8（全速）
      quota 40-60% → 4（保守）
      quota 20-40% → 2（谨慎）
      quota < 20%  → 1（极低）
    触发 794 后 shrink_until 期间再减半
    """
    if quota_pct >= 60:
        cap = MAX_CAP
    elif quota_pct >= 40:
        cap = 4
    elif quota_pct >= 20:
        cap = 2
    else:
        cap = 1
    if shrink_active:
        cap = max(1, cap // 2)
    return cap

def next_backoff(level: int) -> int:
    """Exponential backoff: 60→120→240→480s（上限 480）"""
    return min(BASE_BACKOFF * (2 ** level), 480)

# ── 核心操作 ────────────────────────────────────────────────────────────────

def acquire(source: str) -> tuple:
    """
    尝试获取 1 token。返回 (ok, remaining, wait_secs)
    流程：exhausted 检查 → cooldown → quota 自适应 → token 消耗
    """
    now = time.time()
    s = load_state()

    # 1. exhausted 全局停派
    if EXHAUSTED.exists():
        log(f"🚫[{source}] quota exhausted，全局停派")
        return False, 0, 300

    # 2. cooldown 检查
    if now < s["cooldown_until"]:
        wait = s["cooldown_until"] - now
        log(f"⏸ [{source}] cooldown L{s['cooldown_level']}: {wait:.0f}s")
        return False, 0, wait

    # 3. 释放 hold（cooldown 结束）
    if HOLD_FILE.exists():
        HOLD_FILE.unlink()
        log("🔓 cooldown 结束，hold 释放")

    # 4. 滑动窗口重置
    if now - s["window_start"] >= WINDOW_SECS:
        s["window_start"] = now
        s["requests"] = []
        log(f"🔄 窗口重置")

    # 5. 自适应容量
    shrink_active = now < s["shrink_until"]
    quota_pct = get_quota_pct()
    capacity = compute_capacity(quota_pct, shrink_active)

    # Quota 骤降时 clamp tokens（不能超过当前安全容量）
    if s["tokens"] > capacity:
        log(f"⚠️ tokens {s['tokens']}→{capacity}（quota={quota_pct:.0f}%）")
        s["tokens"] = capacity

    # 6. 清理过期请求记录
    cutoff = now - WINDOW_SECS
    s["requests"] = [r for r in s["requests"] if r["time"] > cutoff]

    # 7. token 不足
    if s["tokens"] <= 0 or len(s["requests"]) >= capacity:
        wait = WINDOW_SECS - (now - s["window_start"])
        log(f"🚫[{source}] 窗口满({len(s['requests'])}/{capacity})，quota={quota_pct:.0f}%，等 {wait:.0f}s")
        return False, 0, max(1.0, wait)

    # 8. 消耗 token
    s["tokens"] -= 1
    s["requests"].append({"time": now, "source": source})
    # cooldown 成功消耗 → 降低 level（成功回归）
    if s["cooldown_level"] > 0:
        s["cooldown_level"] = max(0, s["cooldown_level"] - 1)
        s["cooldown_until"] = 0
    save_state(s)
    log(f"✅[{source}] {s['tokens']}/{capacity} | quota={quota_pct:.0f}% | shrink={shrink_active}")
    return True, s["tokens"], 0


def trigger_cooldown(source: str, err: str = ""):
    """收到 794 → 升级 backoff + 临时缩小容量"""
    now = time.time()
    s = load_state()
    s["cooldown_level"] = min(s["cooldown_level"] + 1, 5)  # 最多 5 级
    wait = next_backoff(s["cooldown_level"] - 1) if s["cooldown_level"] == 1 \
        else next_backoff(s["cooldown_level"] - 1)
    s["cooldown_until"] = now + wait
    s["shrink_until"] = now + WINDOW_SECS  # 下个窗口容量减半
    save_state(s)
    log(f"⚠️ [{source}] 794 触发 L{s['cooldown_level']} backoff={wait}s shrink=1窗口 | {err[:60]}")
    HOLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    HOLD_FILE.write_text(json.dumps({
        "reason": "rate_limit_794",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "cooldown_until": s["cooldown_until"],
        "backoff_level": s["cooldown_level"],
        "source": source,
        "err": err[:200],
    }))

def status() -> dict:
    s = load_state()
    now = time.time()
    shrink = now < s["shrink_until"]
    quota_pct = get_quota_pct()
    return {
        "tokens": s["tokens"],
        "capacity": compute_capacity(quota_pct, shrink),
        "quota_pct": quota_pct,
        "window_elapsed_s": now - s["window_start"],
        "window_secs": WINDOW_SECS,
        "requests_in_window": len(s["requests"]),
        "in_cooldown": now < s["cooldown_until"],
        "cooldown_level": s["cooldown_level"],
        "cooldown_remaining_s": max(0, s["cooldown_until"] - now),
        "backoff_next_s": next_backoff(s["cooldown_level"] - 1) if s["cooldown_level"] > 0 else 0,
        "shrink_active": shrink,
        "shrink_until": s["shrink_until"],
        "exhausted": EXHAUSTED.exists(),
    }

# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "acquire":
        src = sys.argv[2] if len(sys.argv) > 2 else "cli"
        ok, rem, wait = acquire(src)
        print(f"{'OK' if ok else 'HOLD'}:{rem if ok else int(wait)}", flush=True)
        sys.exit(0 if ok else 1)

    elif cmd == "cooldown":
        err = sys.argv[2] if len(sys.argv) > 2 else ""
        src = sys.argv[3] if len(sys.argv) > 3 else "cli"
        trigger_cooldown(src, err)
        sys.exit(0)

    elif cmd == "status":
        print(json.dumps(status(), indent=2), flush=True)
        sys.exit(0)

    elif cmd == "reset":
        s = load_state()
        now = time.time()
        s.update({
            "tokens": MAX_CAP, "window_start": now, "requests": [],
            "cooldown_until": 0, "cooldown_level": 0, "shrink_until": 0,
        })
        save_state(s)
        if HOLD_FILE.exists():
            HOLD_FILE.unlink()
        print("RESET", flush=True)
        sys.exit(0)

    else:
        print(f"Unknown: {cmd}", flush=True)
        sys.exit(1)
