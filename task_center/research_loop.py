#!/usr/bin/env python3
"""
research_loop.py — 研究循环引擎
工程改进铁律合规 — Ξ | 2026-03-27

流程: expert_tracker → peer_review → expert_synthesizer

触发条件:
  1. 自上次综合后新增 >= 15条发现
  2. 距离上次综合 > 3小时
"""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
CHANGES    = HOME / ".xuzhi_memory" / "expert_tracker" / "changes.json"
REVIEWED  = HOME / ".xuzhi_memory" / "expert_tracker" / "reviewed_changes.json"
SYNTHESIS = HOME / ".xuzhi_memory" / "expert_tracker" / "synthesis.json"
LOOP_LOCK = HOME / ".xuzhi_memory" / "expert_tracker" / ".loop.lock"
LOG       = HOME / ".xuzhi_memory" / "expert_tracker" / "research_loop.log"
PEER      = HOME / "xuzhi_workspace" / "task_center" / "peer_review.py"
SYNTH     = HOME / "xuzhi_workspace" / "task_center" / "expert_synthesizer.py"
TRIGGER_NEW  = 15
TRIGGER_HOURS = 3

def _log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def _check_stale_lock():
    """清理超过1小时的stale lock（防止进程崩溃后永久卡死）"""
    if LOOP_LOCK.exists():
        try:
            lock_age = (datetime.now(timezone.utc) - datetime.fromisoformat(
                LOOP_LOCK.read_text().strip().replace("Z", "+00:00")
            )).total_seconds()
            if lock_age > 3600:  # 超过1小时
                _log(f"⚠️ 发现 stale lock ({lock_age/3600:.1f}h)，自动清理")
                LOOP_LOCK.unlink()
        except Exception:
            try:
                LOOP_LOCK.unlink()  # 读不出就删
            except Exception:
                pass

def load_json(path, fallback=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback

def should_run():
    syn = load_json(SYNTHESIS, {})
    chg = load_json(CHANGES, [])
    changes = chg if isinstance(chg, list) else (chg.get("changes", []) if isinstance(chg, dict) else [])
    total = len(changes)
    last_at = syn.get("generated_at", "")

    new_count = 0
    if last_at:
        cutoff = last_at[:10]
        new_count = sum(1 for c in changes if c.get("discovered_at", "") > cutoff)
    else:
        new_count = total

    time_triggered = False
    if last_at:
        try:
            last_dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
            hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
            time_triggered = hours >= TRIGGER_HOURS
        except Exception:
            time_triggered = True
    else:
        time_triggered = True

    _log(f"检查: new={new_count}/{TRIGGER_NEW} time={time_triggered}")
    return new_count >= TRIGGER_NEW or time_triggered

def run(force=False):
    _log("=== research_loop 开始 ===")

    _check_stale_lock()  # 先检查并清理 stale lock

    if LOOP_LOCK.exists():
        _log("跳过：上次运行尚未结束")
        return
    LOOP_LOCK.write_text(datetime.now(timezone.utc).isoformat())
    try:
        if not force and not should_run():
            _log("无需运行")
            return

        # 0. peer_review
        if PEER.exists():
            _log("0. peer_review...")
            r = subprocess.run(["python3", str(PEER)], capture_output=True, text=True, timeout=90)
            if r.returncode == 0:
                _log("✅ peer_review 完成")
            else:
                _log(f"⚠️ peer_review 失败")

        # 1. expert_synthesizer
        if SYNTH.exists():
            _log("1. expert_synthesizer...")
            r = subprocess.run(["python3", str(SYNTH)], capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                _log("✅ synthesizer 完成")
            else:
                _log(f"⚠️ synthesizer 失败")

        syn_data = load_json(SYNTHESIS)
        if syn_data:
            _log(f"✅ 循环完成: round {syn_data.get('round')} conf={syn_data.get('confidence',0):.2f}")
        else:
            _log("⚠️ 无综合结果")
    finally:
        if LOOP_LOCK.exists():
            LOOP_LOCK.unlink()

if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        _log("force 模式")
    run(force=force)
