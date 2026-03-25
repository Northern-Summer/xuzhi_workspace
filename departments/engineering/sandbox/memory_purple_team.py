#!/usr/bin/env python3
"""
memory_purple_team.py — 记忆系统紫队（混沌改进建议）
基于红队攻击结果 + 蓝队防御结果，生成启发式改进建议。
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
SANDBOX_IN_RED  = HOME / "xuzhi_workspace" / "departments" / "engineering" / "sandbox" / "memory_red_team.json"
SANDBOX_IN_BLUE = HOME / "xuzhi_workspace" / "departments" / "engineering" / "sandbox" / "memory_blue_team.json"
SANDBOX_OUT     = HOME / "xuzhi_workspace" / "departments" / "engineering" / "sandbox" / "memory_purple_team.json"

IMPROVEMENTS = [
    {"id":"L2-001","severity":"MEDIUM","title":"脏数据注入防御：字段长度限制",
     "from_attack":"脏数据注入","problem":"超长字段和特殊字符未被拒绝",
     "fix":"add_episode/add_knowledge 中加入 len() 检查","effort":"LOW","status":"TODO"},
    {"id":"L2-002","severity":"LOW","title":"并发写入：SQLite WAL 模式",
     "from_attack":"并发写入","problem":"WAL 可改善并发性能",
     "fix":"conn.execute('PRAGMA journal_mode=WAL')","effort":"LOW","status":"TODO"},
    {"id":"L3-001","severity":"LOW","title":"L3 importance/freshness 值域限制",
     "from_attack":"L3评分操纵","problem":"importance=999.0 未被 clamp",
     "fix":"importance=min(max(val,0),1)","effort":"TRIVIAL","status":"TODO"},
    {"id":"ARCH-001","severity":"HIGH","title":"L2 查询无分页",
     "from_attack":"记忆污染","problem":"query_episodes 无 LIMIT，pollution 后爆炸",
     "fix":"强制 LIMIT=20，上限 100","effort":"TRIVIAL","status":"TODO"},
    {"id":"ARCH-002","severity":"MEDIUM","title":"L2 无 TTL/自动清理",
     "from_attack":"记忆污染","problem":"episode 永不过期，垃圾累积",
     "fix":"decay_freshness() 扩展为 episode TTL","effort":"MEDIUM","status":"TODO"},
    {"id":"SYNC-001","severity":"HIGH","title":"memory.db 未纳入 GitHub 备份",
     "from_attack":"架构","problem":".xuzhi_memory 是 git repo 但 memory.db 未跟踪",
     "fix":"定期导出 memory.db 为 JSON 后 commit","effort":"LOW","status":"TODO"},
    {"id":"ID-001","severity":"HIGH","title":"identity_anchor.py 路径硬编码",
     "from_attack":"架构","problem":"~/.xuzhi_genesis 硬编码，不兼容符号链接",
     "fix":"使用 Path(__file__).resolve()","effort":"TRIVIAL","status":"TODO"},
]

SEV_ORDER = {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3,"TRIVIAL":4}

def main():
    red_results, blue_results = {}, {}
    try:
        with open(SANDBOX_IN_RED) as f:
            red = json.load(f)
            red_results = {r["attack"]: r for r in red.get("results", [])}
    except: pass
    try:
        with open(SANDBOX_IN_BLUE) as f:
            blue = json.load(f)
            blue_results = {r["test"]: r for r in blue.get("results", [])}
    except: pass

    improvements = sorted(IMPROVEMENTS, key=lambda x: SEV_ORDER[x["severity"]])

    output = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "red_pass": sum(1 for v in red_results.values() if v.get("passed")),
        "blue_pass": sum(1 for v in blue_results.values() if v.get("passed")),
        "improvements": improvements,
    }

    with open(SANDBOX_OUT, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("=== PURPLE TEAM — 启发式改进建议 ===\n")
    print(f"红队通过: {output['red_pass']} | 蓝队通过: {output['blue_pass']}\n")
    for imp in improvements:
        icon = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}.get(imp["severity"],"⚪")
        print(f"  {icon} [{imp['severity']}] {imp['id']}: {imp['title']}")
        print(f"      问题: {imp['problem']}")
        print(f"      修复: {imp['fix']} (工作:{imp['effort']})\n")
    print(f"完整报告 → {SANDBOX_OUT}")

if __name__ == "__main__":
    main()
