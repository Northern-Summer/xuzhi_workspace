#!/usr/bin/env python3
"""
identity_anchor.py — 身份锚定 + 断点自报
Agent 启动时自报："我是谁/在哪/干了什么/要干什么/怎么做/如何保证"

使用真实绝对路径，避免 HOME 符号展开问题。
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# ─── 真实路径 ────────────────────────────────────────────────────────────────
_XUZHI_HOME   = Path("/home/summer/xuzhi_genesis")
_XUZHI_MEM    = Path("/home/summer/.xuzhi_memory")
_IA_WORKSPACE = Path("/home/summer/xuzhi_workspace")
_Parliament   = _XUZHI_HOME / "centers" / "mind" / "parliament"

# ─── L2 API ─────────────────────────────────────────────────────────────────
sys.path.insert(0, str(_IA_WORKSPACE / "task_center"))
try:
    from memory_api import query_episodes, query_knowledge
    _HAS_MEM = True
except Exception:
    _HAS_MEM = False

# ─── Ring State ──────────────────────────────────────────────────────────────
RING = ["Φ", "Δ", "Θ", "Γ", "Ω", "Ψ", "Ξ"]

# ─── Helpers ─────────────────────────────────────────────────────────────────
def get_token_state():
    token_file = _Parliament / ".token"
    if token_file.exists():
        try:
            with open(token_file) as f:
                d = json.load(f)
            return d.get("holder"), d.get("since")
        except:
            pass
    return None, None

def get_flow_state():
    flow_file = _Parliament / "flow.json"
    if flow_file.exists():
        try:
            return json.loads(flow_file.read_text())
        except:
            pass
    return {"proposals": [], "holder": None}

# ─── Anchor Report ────────────────────────────────────────────────────────────
def anchor_report(agent: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    holder, since = get_token_state()
    flow = get_flow_state()
    ring_idx = RING.index(agent) if agent in RING else -1
    prev = RING[ring_idx - 1] if ring_idx > 0 else RING[-1]
    next_ = RING[(ring_idx + 1) % len(RING)] if ring_idx >= 0 else "?"

    # 要干什么
    if holder == agent:
        if flow.get("proposals"):
            prop = flow["proposals"][0]
            action = f"持有令牌！处理提案 #{prop['id']}: {prop.get('title','')}"
        else:
            action = "持有令牌，笔记本空 → 轮到自己时直接传递"
    else:
        action = f"等待令牌（当前在 {holder or '无'} 手中）"

    # 最近记忆
    recent = []
    if _HAS_MEM:
        try:
            recent = query_episodes(agent=agent, limit=3)
        except:
            pass
    mem = " / ".join([f"{r['task_type']}({r['status']})" for r in recent]) or "无记录"

    # 系统简报
    brief = {"人": RING.copy(), "事": [], "物": []}
    if _HAS_MEM:
        try:
            all_recent = query_episodes(limit=5)
            brief["事"] = [f"{r['agent']}:{r['task_type']}" for r in all_recent[-3:]]
        except:
            pass
    brief["物"] = [f"令牌:{holder or '无'}"]

    lines = [
        f"╔══════════════════════════════════════════════════════════╗",
        f"║  IDENTITY ANCHOR · {ts}         ║",
        f"╠══════════════════════════════════════════════════════════╣",
        f"║  身份: [{agent}] Xuzhi System · Ω Epoch · 2026-03-25         ║",
        f"║  环位: {prev} → {agent} → {next_}                                   ║",
        f"╠══════════════════════════════════════════════════════════╣",
        f"║  【我是谁】  {agent}，议会令牌环第 {ring_idx+1}/7 位               ║",
        f"║  【我在哪】  Ring: {' → '.join(RING)}    ║",
        f"║  【令牌状态】{holder or '无'}（since {since[:19] if since else '?'}）       ║",
        f"║  【要干什么】{action:<47}║",
        f"║  【最近记忆】{mem:<47}║",
        f"╠══════════════════════════════════════════════════════════╣",
        f"║  【系统简报】                                          ║",
        f"║    人: {', '.join(brief['人']):<50}║",
        f"║    事: {', '.join(brief['事'][-2:]) if brief['事'] else '(无)':<50}║",
        f"║    物: {', '.join(brief['物']):<50}║",
        f"╚══════════════════════════════════════════════════════════╝",
    ]
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: identity_anchor.py <AGENT_ID>")
        sys.exit(1)
    print(anchor_report(sys.argv[1]))
