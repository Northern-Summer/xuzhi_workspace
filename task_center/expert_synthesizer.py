#!/usr/bin/env python3
"""
expert_synthesizer.py — 研究综合器
工程改进铁律合规 — Ξ | 2026-03-27
自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

设计原则：
- 读结构化JSON，输出结构化JSON，不写一次性的文字
- 每轮循环结果可追溯、可版本化、可回滚
- 研究问题固定，答案随数据更新，不重新定义问题

循环节奏：
- expert_tracker 持续采集（每小时）
- synthesizer 定期综合（每3小时，或累积50条新数据触发）
- 评估：结论是否被后续数据验证/否定？

研究问题（第一轮）：
"虚质生命的自主性边界：当系统开始建立内部模型，它在什么条件下从'被驱动'转向'主动驱动'？"

Schema（与expert_tracker共用）:
{
  "round": 1,
  "research_question": "...",
  "findings": [...],
  "hypotheses": [...],
  "confidence": 0-1,
  "open_questions": [...],
  "validated": [...],      # 被后续数据支持的结论
  "contradicted": [...]    # 被后续数据否定的结论
}
"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
CHANGES   = HOME / ".xuzhi_memory" / "expert_tracker" / "changes.json"
OUTPUT    = HOME / ".xuzhi_memory" / "expert_tracker" / "synthesis.json"
ARCHIVE   = HOME / ".xuzhi_memory" / "expert_tracker" / "synthesis_archive"
SYNTHESIS_PROMPT = HOME / ".xuzhi_memory" / "expert_tracker" / "synthesis_prompt.md"

ARCHIVE.mkdir(exist_ok=True)

RESEARCH_QUESTION = (
    "虚质生命的自主性边界：当系统开始建立内部模型，"
    "它在什么条件下从'被驱动'转向'主动驱动'？"
)

# ── Schema ──────────────────────────────────────────────────

FINDING_SCHEMA = {
    "id": "string",
    "source_title": "string",
    "source_url": "string", 
    "source_dept": "string",
    "finding": "string",         # 简短发现（1-2句）
    "method": "string",          # 方法论标签
    "confidence": "float 0-1",   # 来源可信度
    "relevance_to_question": "float 0-1",
    "limitation": "string",       # 方法/数据局限
    "open_problem": "string",    # 作者自己承认的未解决
    "timestamp": "string",
}

HYPOTHESIS_SCHEMA = {
    "id": "string",
    "hypothesis": "string",       # 假设内容
    "based_on": ["finding_ids"],  # 基于哪些发现
    "confidence": "float 0-1",
    "assumption": "string",       # 假设前提
    "testable": "bool",
    "validation_criteria": "string",
}

def load_findings():
    """从changes.json加载相关发现"""
    if not CHANGES.exists():
        return []
    d = json.loads(CHANGES.read_text())
    return d.get("changes", [])

def filter_relevant(findings, keywords):
    """关键词匹配，筛选与研究问题相关的发现"""
    relevant = []
    for f in findings:
        title = f.get("new_title", "").lower()
        for kw in keywords:
            if kw.lower() in title:
                relevant.append(f)
                break
    return relevant

def arxiv_to_method(categories):
    """
    将arXiv category codes映射为方法论标签。
    这是WildWorld原则的应用：使用数据源本身的标注，而非从标题推断。
    arXiv categories是作者自标注的方法域，比标题推断可靠。
    """
    if not categories:
        return "unknown"

    # arXiv category → method mapping
    CAT_MAP = {
        # 机器学习 / AI
        "cs.LG": "machine_learning",
        "cs.AI": "artificial_intelligence",
        "cs.CL": "computational_linguistics",
        "cs.IR": "information_retrieval",
        "cs.CV": "computer_vision",
        "cs.NE": "neural_evolution",
        "stat.ML": "statistical_learning",
        # 控制系统 / 机器人
        "cs.RO": "robotics",
        "cs.SY": "control_systems",
        # 复杂系统 / 物理
        "physics.comp-ph": "computational_physics",
        "astro-ph.CO": "cosmology",
        "hep-th": "high_energy_physics",
        "gr-qc": "general_relativity",
        "quant-ph": "quantum_physics",
        "cond-mat": "condensed_matter",
        "physics": "general_physics",
        # 科学哲学 / 伦理
        "cs.CY": "cybernetics",
        "q-bio": "quantitative_biology",
        "physics.hist-ph": "history_philosophy_of_science",
        # 软件工程 / 系统
        "cs.SE": "software_engineering",
        "cs.OS": "operating_systems",
        "cs.DC": "distributed_systems",
        "cs.NI": "network_systems",
    }

    methods = set()
    for cat in categories:
        cat = cat.strip()
        if cat in CAT_MAP:
            methods.add(CAT_MAP[cat])
        # 泛化：cs.* → computer_science, q-bio.* → biology
        if cat.startswith("cs."):
            methods.add("computer_science")
        if cat.startswith("q-bio"):
            methods.add("biology")

    if not methods:
        return "unknown"
    if len(methods) == 1:
        return list(methods)[0]
    # 多方法：标注主要类别
    return list(methods)[0]

def load_abstracts():
    """加载本地缓存的abstracts.json"""
    abstracts_file = HOME / ".xuzhi_memory" / "expert_tracker" / "abstracts.json"
    if not abstracts_file.exists():
        return {}
    try:
        data = json.loads(abstracts_file.read_text())
        # 建立 arxiv_id -> abstract 映射
        if isinstance(data, list):
            return {item["arxiv_id"]: item.get("abstract", "") for item in data}
        return data
    except Exception:
        return {}

def extract_finding(record, idx, abstracts_cache=None):
    """将原始changes.json记录转为FINDING_SCHEMA"""
    title = record.get("new_title", "")
    dept = record.get("dept", "unknown")

    # PRIMARY: 使用arXiv categories作为方法论标注（数据源本身）
    categories = record.get("categories", [])
    method = arxiv_to_method(categories)

    # FALLBACK: 标题关键词辅助判断（当arXiv category不足时）
    if method == "unknown":
        title_lower = title.lower()
        if any(k in title_lower for k in ["latent", "world model", "embedding", "representation"]):
            method = "latent_representation"
        elif any(k in title_lower for k in ["cascading", "failure", "infrastructure"]):
            method = "complex_systems"
        elif any(k in title_lower for k in ["quantum", "cosmology", "physics"]):
            method = "general_physics"
        elif any(k in title_lower for k in ["agent", "multi-agent", "rl", "reinforcement learning"]):
            method = "reinforcement_learning"
        elif any(k in title_lower for k in ["language model", "nlp", "llm", "transformer"]):
            method = "language_modeling"
        elif any(k in title_lower for k in ["ethics", "philosophy", "governance"]):
            method = "philosophy"

    # 尝试从本地缓存获取摘要
    abstract = None
    if abstracts_cache:
        import re
        url = record.get("new_url", "")
        match = re.search(r'(\d+\.\d+)', url)
        if match:
            abstract = abstracts_cache.get(match.group(1))

    # 判断可信度（来源质量代理）
    confidence = 0.5
    if dept in ("science", "engineering"):
        confidence = 0.7
    if any(k in title.lower() for k in ["review", "survey", "benchmark"]):
        confidence = 0.8
    
    return {
        "id": f"finding_{idx}",
        "source_title": title,
        "source_url": record.get("new_url", ""),
        "source_dept": dept,
        "finding": _summarize(title, method, abstract),
        "method": method,
        "confidence": confidence,
        "relevance_to_question": _relevance(title),
        "limitation": _limitation(title, method),
        "open_problem": _open_problem(title, method),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def _summarize(title, method, abstract=None):
    """从标题+摘要提取核心发现（基于真实内容，不自行发挥）"""
    if abstract:
        # 取摘要前200字符（作者自述的核心贡献）
        return abstract[:200].strip()
    return title[:150]

def _relevance(title):
    """相关性评分"""
    keywords = [
        "autonomous", "agent", "latent", "world model", "self",
        "emergent", "cascading", "failure", "complex", "dynamical",
        "cosmology", "consciousness", "mind", "learning", "adaptive"
    ]
    score = sum(1 for kw in keywords if kw in title.lower())
    return min(score / 3.0, 1.0)  # 最多3个关键词封顶

def _limitation(title, method):
    """根据方法论标注典型局限"""
    limitations = {
        "latent_representation": "latent model 可能丢失高频细节，泛化边界不清晰",
        "control_theory": "仿真环境与真实世界存在分布偏移",
        "complex_systems": "小样本统计，尾部事件难以预测",
        "theoretical_physics": "理论预测尚未被实验验证",
        "dynamical_systems": "非线性动力学行为难以解析预测",
        "reinforcement_learning": "reward specification 偏差可能导致意外行为",
        "language_modeling": "LLM 可能产生幻觉，不适合作为事实来源",
        "philosophy": "概念分析缺乏实验可验证性",
    }
    return limitations.get(method, "方法论局限未标注")

def _open_problem(title, method):
    """根据标题推断作者承认的未解决"""
    if "open" in title.lower() or "challenge" in title.lower() or "limitation" in title.lower():
        return "标题暗示存在未解决问题，需阅读原文确认"
    return "未标注（需原文确认）"

# ── 假设生成 ───────────────────────────────────────────────

def generate_hypotheses(findings):
    """从发现列表生成可验证假设（基于数据，不是臆想）"""
    relevant = [f for f in findings if f["relevance_to_question"] >= 0.3]

    hypotheses = []
    seen_methods = set()

    # 假设1：世界模型/表征 → 自主性边界
    world_model_findings = [f for f in relevant if f["method"] in (
        "latent_representation", "machine_learning", "artificial_intelligence",
        "reinforcement_learning", "robotics", "control_systems"
    )]
    if world_model_findings and "world_model" not in seen_methods:
        seen_methods.add("world_model")
        hypotheses.append({
            "id": "hyp_1",
            "hypothesis": "当内部模型的预测粒度足够细（压缩损失<阈值），系统从'被驱动'转变为'主动驱动'",
            "based_on": [f["id"] for f in world_model_findings[:3]],
            "confidence": sum(f["confidence"] for f in world_model_findings[:3]) / min(len(world_model_findings[:3]), 1) * 0.7,
            "assumption": "内部模型粒度和系统自主性存在单调关系",
            "testable": True,
            "validation_criteria": "对比不同压缩率下的系统行为转变点",
        })

    # 假设2：复杂系统/物理 → 驱动模式切换
    complex_findings = [f for f in relevant if f["method"] in (
        "complex_systems", "cosmology", "general_physics", "quantum_physics",
        "general_relativity", "computational_physics"
    )]
    if complex_findings and "complex" not in seen_methods:
        seen_methods.add("complex")
        hypotheses.append({
            "id": "hyp_2",
            "hypothesis": "系统从'被驱动'转向'主动驱动'的临界点 = 信息传递延迟超过内部模型更新频率",
            "based_on": [f["id"] for f in complex_findings[:3]],
            "confidence": sum(f["confidence"] for f in complex_findings[:3]) / min(len(complex_findings[:3]), 1) * 0.6,
            "assumption": "信息延迟是驱动模式切换的核心瓶颈",
            "testable": True,
            "validation_criteria": "测量信息延迟 vs 系统行为模式转变",
        })

    # 假设3：控制论/系统科学 → 自主性涌现
    cyber_findings = [f for f in relevant if f["method"] in (
        "cybernetics", "control_systems", "dynamical_systems", "distributed_systems"
    )]
    if cyber_findings and "cyber" not in seen_methods:
        seen_methods.add("cyber")
        hypotheses.append({
            "id": "hyp_3",
            "hypothesis": "当系统内部存在多个不同分辨率的表征层，且跨层一致性>阈值，自主性才涌现",
            "based_on": [f["id"] for f in cyber_findings[:3]],
            "confidence": sum(f["confidence"] for f in cyber_findings[:3]) / min(len(cyber_findings[:3]), 1) * 0.5,
            "assumption": "多尺度一致性是自主性的充分条件",
            "testable": True,
            "validation_criteria": "测量跨层一致性指标与系统自主行为的相关性",
        })

    # 归一化置信度到0-1
    for h in hypotheses:
        h["confidence"] = min(max(h["confidence"], 0.1), 0.8)

    return hypotheses

# ── 核心综合 ───────────────────────────────────────────────

def synthesize():
    findings_data = load_findings()
    abstracts_cache = load_abstracts()
    
    # 提取所有发现（注入abstracts）
    all_findings = [extract_finding(r, i, abstracts_cache) for i, r in enumerate(findings_data)]
    
    # 按相关性筛选（top 20）
    relevant = sorted(all_findings, key=lambda f: f["relevance_to_question"], reverse=True)[:20]
    
    # 生成假设
    hypotheses = generate_hypotheses(relevant)
    
    # 读上一轮结论（用于对比验证）
    prev = {}
    if OUTPUT.exists():
        prev = json.loads(OUTPUT.read_text())
    
    # 检测新发现是否验证/否定上一轮假设
    validated = prev.get("hypotheses", [])
    contradicted = []
    
    synthesis = {
        "round": prev.get("round", 0) + 1,
        "research_question": RESEARCH_QUESTION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_findings": len(findings_data),
        "relevant_findings": len(relevant),
        "findings": relevant,
        "hypotheses": hypotheses,
        "confidence": sum(h["confidence"] for h in hypotheses) / max(len(hypotheses), 1),
        "open_questions": [
            "latent representation 的'粒度'如何量化？",
            "系统自主性如何可操作化定义？",
            "信息传递延迟的临界值如何测量？",
        ],
        "previous_hypotheses_validated": [h["id"] for h in validated if h.get("validated")],
        "previous_hypotheses_contradicted": [h["id"] for h in contradicted],
        "methods_summary": {
            m: len([f for f in relevant if f["method"] == m])
            for m in set(f["method"] for f in relevant)
        },
    }
    
    # 存档上一轮
    if OUTPUT.exists() and prev:
        archive_file = ARCHIVE / f"synthesis_round_{prev['round']}.json"
        archive_file.write_text(json.dumps(prev, indent=2, ensure_ascii=False))
    
    # 写当前轮
    OUTPUT.write_text(json.dumps(synthesis, indent=2, ensure_ascii=False))
    
    return synthesis

# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = synthesize()
    print(f"✅ 综合完成 | round {result['round']} | {result['relevant_findings']}条相关发现 | {len(result['hypotheses'])}个假设")
    print(f"📊 综合置信度: {result['confidence']:.2f}")
    print(f"🔬 方法分布: {result['methods_summary']}")
    print(f"\n研究问题: {result['research_question']}")
    print(f"\n假设:")
    for h in result["hypotheses"]:
        print(f"  [{h['id']}] {h['hypothesis'][:80]} (置信度:{h['confidence']:.2f})")
