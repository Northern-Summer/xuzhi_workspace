#!/usr/bin/env python3
"""
research_loop.py — 研究循环引擎
工程改进铁律合规 — Ξ | 2026-03-27
自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

设计原则：
- 信息不枯竭：expert_tracker持续供数据
- 信息不爆炸：上限截旧，进出平衡
- 流程不阻塞：每步独立，错了只影响当前轮
- 推送自动化：综合完成后主动推WeChat

循环：
  expert_tracker（采集）→ changes.json（max 50）→ expert_synthesizer（综合）→ WeChat推送

触发条件（满足任一）：
  1. 距离上次综合 > 3小时
  2. 自上次综合后新增 >= 15条发现
"""
import json, subprocess, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
CHANGES    = HOME / ".xuzhi_memory" / "expert_tracker" / "changes.json"
SYNTHESIS  = HOME / ".xuzhi_memory" / "expert_tracker" / "synthesis.json"
SYN_LOCK   = HOME / ".xuzhi_memory" / "expert_tracker" / ".synthesis.lock"
LOG        = HOME / ".xuzhi_memory" / "expert_tracker" / "research_loop.log"
WE_CHAT_ID = "o9cq80z9eorqjasg6hb1w-cc4-po@im.wechat"

TRIGGER_NEW_COUNT = 15  # 新增15条触发
TRIGGER_HOURS     = 3  # 超过3小时触发

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def load_json(path, fallback=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback

def should_synthesize():
    """检查是否需要运行综合"""
    synthesis = load_json(SYNTHESIS, {})
    changes   = load_json(CHANGES, [])

    total   = len(changes.get("changes", []))
    last_at = synthesis.get("generated_at", "")

    # 上次综合后新增多少条
    if last_at:
        try:
            last_dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
            new_count = sum(
                1 for c in changes.get("changes", [])
                if c.get("discovered_at", "") > last_at[:10]
            )
        except Exception:
            new_count = total
    else:
        new_count = total

    # 时间触发
    if last_at:
        try:
            last_dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
            hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
            time_triggered = hours_since >= TRIGGER_HOURS
        except Exception:
            time_triggered = True
    else:
        time_triggered = True

    log(f"检查: total={total} new_since_last={new_count} time_triggered={time_triggered}")
    return new_count >= TRIGGER_NEW_COUNT or time_triggered

def push_to_wechat(synthesis):
    """综合完成后推送到WeChat"""
    round_n   = synthesis.get("round", "?")
    conf      = synthesis.get("confidence", 0)
    hyps      = synthesis.get("hypotheses", [])
    rq        = synthesis.get("research_question", "")
    methods   = synthesis.get("methods_summary", {})
    total     = synthesis.get("total_findings", 0)
    relevant  = synthesis.get("relevant_findings", 0)

    hyp_lines = []
    for h in hyps:
        hyp_lines.append(f"• {h['hypothesis'][:60]} (置信{h['confidence']:.0%})")

    msg = f"""📊 研究 Round {round_n} | {datetime.now(timezone.utc).strftime('%m-%d %H:%M')}

❓ {rq[:60]}{'…' if len(rq)>60 else ''}

📐 方法分布: {methods}
🔬 相关: {relevant}/{total}条 | 置信度: {conf:.0%}

🎯 假设:
{chr(10).join(hyp_lines[:3])}

✅ 综合完成"""
    try:
        result = subprocess.run([
            "openclaw", "message", "send",
            "--channel", "openclaw-weixin",
            "--target", WE_CHAT_ID,
            "--message", msg
        ], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            log("✅ 推送WeChat成功")
        else:
            log(f"⚠️ 推送WeChat失败: {result.stderr[-100:]}")
    except Exception as e:
        log(f"⚠️ 推送异常: {e}")

def run(force=False):
    log("=== 研究循环引擎启动 ===")

    if SYN_LOCK.exists():
        log("跳过：上次运行尚未结束")
        return

    if not force and not should_synthesize():
        log("无需综合：数据量或时间未达触发阈值")
        return

    if force:
        log("force模式：强制综合")

    SYN_LOCK.write_text(datetime.now(timezone.utc).isoformat())

    try:
        log("运行synthesizer...")
        result = subprocess.run(
            ["python3", str(HOME / "xuzhi_workspace" / "task_center" / "expert_synthesizer.py")],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            log(f"⚠️ synthesizer失败: {result.stderr[-200:]}")
            return

        synthesis = load_json(SYNTHESIS)
        if synthesis:
            push_to_wechat(synthesis)
            log(f"✅ 循环完成: round {synthesis.get('round')} conf={synthesis.get('confidence',0):.2f}")
        else:
            log("⚠️ 综合结果为空")

    finally:
        if SYN_LOCK.exists():
            SYN_LOCK.unlink()

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    run(force=force)
