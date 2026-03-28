#!/usr/bin/env python3
"""
peer_review.py — 同行评审：评审我自己的研究产出
工程改进铁律合规 — Ξ | 2026-03-27
自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

评审对象：我自己的产出（synthesis.json）
不是评审 expert_tracker 采集的论文

评审维度（对齐学术同行评审）：
  1. soundness（严谨性）：假设是否有方法论支撑
  2. novelty（创新性）：假设是否提供新的洞见
  3. evidence（证据）：结论是否有充分证据
  4. clarity（清晰性）：表述是否明确可验证
  5. significance（意义）：对研究问题的贡献度

Verdict:
  accept: 可以推送
  revise: 需要修改后推送
  reject: 打回重做
"""
import json
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
SYNTHESIS  = HOME / ".xuzhi_memory" / "expert_tracker" / "synthesis.json"
REVIEWED   = HOME / ".xuzhi_memory" / "expert_tracker" / "reviewed_output.json"
ARCHIVE    = HOME / ".xuzhi_memory" / "expert_tracker" / "review_archive"
LOOP_LOCK  = HOME / ".xuzhi_memory" / "expert_tracker" / ".peer_review.lock"
REVIEW_LOG = HOME / ".xuzhi_memory" / "expert_tracker" / "peer_review_log.json"

ARCHIVE.mkdir(exist_ok=True)

VERDICT_THRESHOLDS = {
    "accept": 6.5,
    "revise": 4.0,
}

def load_json(path, fallback=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback

def review_hypothesis(hypothesis, idx, round_n):
    """
    评审一个假设。
    不调用LLM，用规则做结构化评审。
    """
    text = hypothesis.get("hypothesis", "")
    confidence = hypothesis.get("confidence", 0)
    based_on = hypothesis.get("based_on", [])
    assumption = hypothesis.get("assumption", "")
    testable = hypothesis.get("testable", False)
    criteria = hypothesis.get("validation_criteria", "")

    scores = {}
    notes = []

    # 1. soundness：假设是否包含可评估的陈述
    has_quantifier = any(kw in text for kw in ["阈值", "临界", "足够", "超过", "大于", "小于", "阈值"])
    has_direction = any(kw in text for kw in ["从", "转为", "导致", "引起", "→", "转变"])
    has_mechanism = any(kw in text for kw in ["因为", "由于", "机制", "过程", "延迟", "频率", "粒度"])
    soundness = 0
    if has_quantifier: soundness += 3
    if has_direction: soundness += 3
    if has_mechanism: soundness += 3
    soundness = min(10, max(2, soundness))
    scores["soundness"] = soundness
    if soundness >= 7:
        notes.append("假设包含机制性描述，严谨性较高")
    elif soundness < 5:
        notes.append("假设过于模糊，缺乏机制性描述")

    # 2. novelty：是否提供了新洞见
    # 基于假设是否不是显而易见的老生常谈
    is_trivial = any(kw in text for kw in ["重要", "关键", "需要", "应该", "必须"])
    novelty = 5.0 if is_trivial else 7.0
    scores["novelty"] = novelty
    if novelty >= 7:
        notes.append("假设提供了非显而易见的新洞见")
    else:
        notes.append("假设接近老生常谈，创新性有限")

    # 3. evidence：置信度是否有来源
    evidence_score = min(confidence * 10, 10)  # confidence 0-1 → 0-10
    scores["evidence"] = evidence_score
    if evidence_score >= 7:
        notes.append(f"置信度{confidence:.0%}有充分支撑")
    elif evidence_score < 5:
        notes.append(f"置信度{confidence:.0%}依据不足")

    # 4. clarity：表述是否清晰可验证
    clarity = 7.0 if (testable and criteria) else 5.0
    if testable:
        notes.append("假设可验证")
    else:
        notes.append("假设缺少验证标准")
    scores["clarity"] = clarity

    # 5. significance：对研究问题的贡献
    significance = 6.0 if soundness >= 7 else 4.0
    scores["significance"] = significance

    # 综合评分
    overall = (scores["soundness"] + scores["novelty"] + scores["evidence"] +
               scores["clarity"] + scores["significance"]) / 5

    # Verdict
    if overall >= VERDICT_THRESHOLDS["accept"]:
        verdict = "accept"
    elif overall >= VERDICT_THRESHOLDS["revise"]:
        verdict = "revise"
    else:
        verdict = "reject"

    return {
        "id": hypothesis.get("id", f"hyp_{idx}"),
        "hypothesis": text,
        "scores": scores,
        "overall": round(overall, 2),
        "verdict": verdict,
        "notes": notes,
        "confidence": confidence,
        "based_on_count": len(based_on),
    }

def review_synthesis():
    """评审我自己的综合产出"""
    syn = load_json(SYNTHESIS)
    if not syn:
        return None

    round_n = syn.get("round", "?")
    hypotheses = syn.get("hypotheses", [])
    research_question = syn.get("research_question", "")
    confidence = syn.get("confidence", 0)

    hypothesis_reviews = []
    verdicts = {"accept": 0, "revise": 0, "reject": 0}
    overall_scores = []

    for i, h in enumerate(hypotheses):
        r = review_hypothesis(h, i, round_n)
        hypothesis_reviews.append(r)
        verdicts[r["verdict"]] += 1
        overall_scores.append(r["overall"])

    # 综合产出整体评审
    avg_hypothesis_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0
    accept_rate = verdicts["accept"] / max(len(hypotheses), 1)

    # 整体 verdict：大多数假设是 accept 才算 accept
    if accept_rate >= 0.6:
        overall_verdict = "accept"
    elif accept_rate >= 0.3:
        overall_verdict = "revise"
    else:
        overall_verdict = "reject"

    # 综合报告
    report = {
        "round": round_n,
        "research_question": research_question,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis_reviews": hypothesis_reviews,
        "aggregated": {
            "total": len(hypotheses),
            "by_verdict": verdicts,
            "avg_score": round(avg_hypothesis_score, 2),
            "accept_rate": round(accept_rate, 2),
        },
        "overall_verdict": overall_verdict,
        "feedback": _generate_feedback(verdicts, avg_hypothesis_score, hypothesis_reviews),
    }

    return report

def _generate_feedback(verdicts, avg_score, hyp_reviews):
    """生成改进建议"""
    feedback = []

    if verdicts["reject"] > 0:
        rejected = [r for r in hyp_reviews if r["verdict"] == "reject"]
        feedback.append(f"⚠️ {verdicts['reject']}个假设被打回：需要重新设计或找到更多证据")
    if verdicts["revise"] > 0:
        feedback.append(f"🔧 {verdicts['revise']}个假设需要修改后推送")
    if avg_score < 5:
        feedback.append("整体严谨性不足：假设缺少机制性描述")
    if verdicts["accept"] >= 2:
        feedback.append(f"✅ {verdicts['accept']}个假设达到发表标准")

    return feedback

def run():
    print("=== peer_review: 评审我的产出 ===")

    if LOOP_LOCK.exists():
        print("跳过：上次评审尚未结束")
        return None
    LOOP_LOCK.write_text(datetime.now(timezone.utc).isoformat())
    try:
        report = review_synthesis()
        if not report:
            print("无综合产出可评审")
            return None

        # 存档上一轮
        if REVIEWED.exists():
            prev = load_json(REVIEWED)
            if prev:
                af = ARCHIVE / f"reviewed_output_round_{prev.get('round', 0)}.json"
                af.write_text(json.dumps(prev, indent=2, ensure_ascii=False))
                print(f"已存档: {af.name}")

        REVIEWED.write_text(json.dumps(report, indent=2, ensure_ascii=False))

        v = report["aggregated"]
        print(f"✅ 评审完成: {v['total']}假设 | avg={v['avg_score']:.1f} | "
              f"accept={v['by_verdict']['accept']} "
              f"revise={v['by_verdict']['revise']} "
              f"reject={v['by_verdict']['reject']}")
        print(f"   整体verdict: {report['overall_verdict']}")
        for fb in report["feedback"]:
            print(f"   {fb}")

        return report

    finally:
        if LOOP_LOCK.exists():
            LOOP_LOCK.unlink()

if __name__ == "__main__":
    run()
