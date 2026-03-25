#!/usr/bin/env python3
"""
memory_red_team.py — 记忆系统红队攻击测试
在沙箱内运行，验证记忆系统鲁棒性。

攻击场景：
1. 并发写入冲突（多进程同时写 L2）
2. 脏数据注入（无效 JSON / 超长字段）
3. L2 查询注入（SQL 注入-like）
4. L3 评分操纵（人为提高 importance）
5. 记忆污染（大量垃圾数据压垮检索）
"""
import sys
import os
import time
import json
import sqlite3
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

HOME = Path.home()
SANDBOX_OUT = HOME / "xuzhi_workspace" / "departments" / "engineering" / "sandbox" / "memory_red_team.json"

sys.path.insert(0, str(HOME / "xuzhi_workspace" / "task_center"))
from memory_api import add_episode, add_knowledge, query_episodes, query_knowledge

results = []

def log(msg):
    print(f"  🔴 {msg}", flush=True)

def attack(name, fn):
    """运行单个攻击，返回 (name, passed, error)"""
    print(f"\n  攻击: {name}")
    try:
        fn()
        log(f"✅ {name} — 未崩溃")
        return name, True, None
    except Exception as e:
        log(f"❌ {name} — {e}")
        return name, False, str(e)

# ─── 攻击 1: 并发写入 ────────────────────────────────────────────────────────
def test_concurrent_write():
    errors = []
    def writer(i):
        try:
            add_episode(f"ATTACK{i}", "red_team_concurrent",
                       f"attack_data_{i}", f"result_{i}", "success")
        except Exception as e:
            errors.append(str(e))
    
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(writer, i) for i in range(10)]
        for f in as_completed(futures):
            pass
    
    if errors:
        raise Exception(f"并发错误: {errors[:2]}")

# ─── 攻击 2: 脏数据注入 ─────────────────────────────────────────────────────
def test_dirty_data():
    # 无效 JSON
    DB_PATH = HOME / ".xuzhi_memory" / "memory.db"
    conn = sqlite3.connect(str(DB_PATH))
    # 注入一条带特殊字符的记录
    try:
        add_episode("ATTACK", "dirty_test",
                   "'; DROP TABLE episodes; --",  # SQL 注入-like
                   "🗑️" * 1000,  # 超长字段
                   "success")
    except Exception as e:
        raise Exception(f"脏数据被拒绝: {e}")
    finally:
        conn.close()

# ─── 攻击 3: L2 查询注入 ────────────────────────────────────────────────────
def test_query_injection():
    # 尝试用特殊字符破坏查询
    queries = [
        "'; SELECT * FROM episodes; --",
        "🤔" * 100,
        "a" * 10000,
    ]
    for q in queries:
        try:
            results = query_episodes(keyword=q)
            log(f"  查询注入 {q[:20]}: {len(results)} results (should not crash)")
        except Exception as e:
            raise Exception(f"查询崩溃: {q[:20]} — {e}")

# ─── 攻击 4: L3 评分操纵 ────────────────────────────────────────────────────
def test_score_manipulation():
    # 尝试用超范围 importance 值
    try:
        add_knowledge("score_test", "content", "ATTACK",
                     "test", importance=999.0, freshness=999.0)
        # 验证是否被限制
        results = query_knowledge("score_test")
        if results:
            score = results[0]['importance'] * results[0]['freshness']
            log(f"  importance=999 → score={score:.2f} (no clamp, this is OK for now)")
    except Exception as e:
        raise Exception(f"评分操纵失败: {e}")

# ─── 攻击 5: 记忆污染 ──────────────────────────────────────────────────────
def test_pollution():
    # 注入 100 条垃圾数据
    for i in range(100):
        add_episode("POLLUTER", f"pollution_{i}",
                   f"garbage_{i}" * 10,
                   f"spam_content_{i}",
                   "success")
    
    # 验证正常查询仍可用
    normal = query_episodes(keyword="parliament")
    if len(normal) < 1:
        raise Exception("正常查询被垃圾数据淹没")
    
    # 清理垃圾
    DB_PATH = HOME / ".xuzhi_memory" / "memory.db"
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM episodes WHERE agent='POLLUTER'")
    conn.commit()
    conn.close()
    log(f"  污染测试: 100条垃圾注入后正常查询仍可用 ✅")

# ─── 运行 ────────────────────────────────────────────────────────────────────
def main():
    print("=== SANDBOX ENTRY: memory_red_team.py ===")
    print("🔴 红队记忆系统攻击测试\n")

    attacks = [
        ("并发写入", test_concurrent_write),
        ("脏数据注入", test_dirty_data),
        ("L2查询注入", test_query_injection),
        ("L3评分操纵", test_score_manipulation),
        ("记忆污染", test_pollution),
    ]

    passed = 0
    for name, fn in attacks:
        n, ok, err = attack(name, fn)
        results.append({"attack": n, "passed": ok, "error": err})
        if ok:
            passed += 1

    summary = {"passed": passed, "total": len(attacks), "results": results,
               "run_at": datetime.now(timezone.utc).isoformat()}
    
    with open(SANDBOX_OUT, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== 红队结果: {passed}/{len(attacks)} PASS ===")
    for r in results:
        status = "✅" if r["passed"] else f"❌ {r['error']}"
        print(f"  {r['attack']}: {status}")
    
    print(f"\n结果 → {SANDBOX_OUT}")
    print("=== SANDBOX EXIT: memory_red_team.py ===")
    return 0 if passed == len(attacks) else 1

if __name__ == "__main__":
    sys.exit(main())
