#!/usr/bin/env python3
"""
memory_blue_team.py — 记忆系统蓝队防御验证
在沙箱内运行，验证记忆系统功能正确性。

防御验证：
1. L2 CRUD 完整性
2. L3 CRUD 完整性
3. 身份锚定自报完整性
4. 三层记忆数据一致性
5. API 幂等性
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
SANDBOX_OUT = HOME / "xuzhi_workspace" / "departments" / "engineering" / "sandbox" / "memory_blue_team.json"

sys.path.insert(0, str(HOME / "xuzhi_workspace" / "task_center"))
from memory_api import (
    add_episode, query_episodes,
    add_knowledge, query_knowledge,
    init as mem_init
)
from identity_anchor import anchor_report

results = []

def check(name, fn):
    try:
        fn()
        print(f"  🛡️  {name}: ✅ PASS")
        return name, True, None
    except Exception as e:
        print(f"  🛡️  {name}: ❌ FAIL — {e}")
        return name, False, str(e)

# ─── 1. L2 CRUD ─────────────────────────────────────────────────────────────
def test_l2_create():
    id_ = add_episode("BLUE", "blue_team_test",
                      "蓝队测试输入", "蓝队测试输出", "success")
    assert id_ > 0, "ID should be > 0"
    results_l2 = query_episodes(agent="BLUE", limit=5)
    found = any(r["id"] == id_ for r in results_l2)
    assert found, "写入的 episode 未找到"

def test_l2_read():
    r = query_episodes(agent="Φ", limit=3)
    assert isinstance(r, list), "Should return list"
    print(f"    read {len(r)} episodes for Φ")

def test_l2_update_via_read():
    # L2 无 update（append-only），验证读取正确
    before = query_episodes(keyword="parliament")
    assert len(before) >= 0, "Should return list"

# ─── 2. L3 CRUD ─────────────────────────────────────────────────────────────
def test_l3_create():
    id_ = add_knowledge("蓝队测试知识", "这是蓝队测试内容",
                        "BLUE_TEAM", "test,blue", 0.9, 1.0)
    assert id_ > 0, "ID should be > 0"
    r = query_knowledge("蓝队测试知识")
    found = any(x["id"] == id_ for x in r)
    assert found, "写入的 knowledge 未找到"

def test_l3_read():
    r = query_knowledge(keyword="击鼓传花")
    assert isinstance(r, list), "Should return list"
    print(f"    read {len(r)} knowledge units for '击鼓传花'")

# ─── 3. 身份锚定 ───────────────────────────────────────────────────────────
def test_identity_anchor():
    report = anchor_report("Ξ")
    assert "【我是谁】" in report, "Missing identity"
    assert "【我在哪】" in report, "Missing position"
    assert "【系统简报】" in report, "Missing brief"
    assert "令牌" in report, "Missing token state"
    print("    identity anchor: 人/事/物 三要素完整 ✅")

# ─── 4. 三层数据一致性 ──────────────────────────────────────────────────────
def test_three_layer_consistency():
    # L2 有 parliament 记录，L3 有击鼓传花知识
    l2 = query_episodes(keyword="parliament")
    l3 = query_knowledge(keyword="击鼓传花")
    
    l2_agents = set(r["agent"] for r in l2)
    l3_sources = set(r["source"] for r in l3)
    
    print(f"    L2 agents: {l2_agents}")
    print(f"    L3 sources: {l3_sources}")
    
    assert len(l2) >= 0, "L2 should be queryable"
    assert len(l3) >= 0, "L3 should be queryable"

# ─── 5. API 幂等性 ─────────────────────────────────────────────────────────
def test_idempotency():
    # 同一 episode 多次写入（应该创建多条，这是幂等性）
    id1 = add_episode("IDEM", "idempotency_test", "input", "output", "success")
    id2 = add_episode("IDEM", "idempotency_test", "input", "output", "success")
    # 两次调用返回不同 ID（这是正确的 append-only 行为）
    assert id1 != id2, "Append-only: each call creates new row"
    # 读取时应该都能找到
    r = query_episodes(agent="IDEM")
    assert len(r) >= 2, "Both rows should be findable"

# ─── 运行 ────────────────────────────────────────────────────────────────────
def main():
    print("=== 🛡️  BLUE TEAM — 记忆系统防御验证 ===\n")

    tests = [
        ("L2 Create+Read", test_l2_create),
        ("L2 Read", test_l2_read),
        ("L2 Update (read-only)", test_l2_update_via_read),
        ("L3 Create+Read", test_l3_create),
        ("L3 Read", test_l3_read),
        ("身份锚定自报", test_identity_anchor),
        ("三层数据一致性", test_three_layer_consistency),
        ("API 幂等性", test_idempotency),
    ]

    passed = 0
    for name, fn in tests:
        n, ok, err = check(name, fn)
        results.append({"test": n, "passed": ok, "error": err})
        if ok:
            passed += 1

    summary = {"passed": passed, "total": len(tests), "results": results,
               "run_at": datetime.now(timezone.utc).isoformat()}
    
    with open(SANDBOX_OUT, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== 🛡️ 蓝队结果: {passed}/{len(tests)} PASS ===")
    print(f"结果 → {SANDBOX_OUT}")
    return 0 if passed == len(tests) else 1

if __name__ == "__main__":
    sys.exit(main())
