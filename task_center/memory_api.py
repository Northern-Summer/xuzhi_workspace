#!/usr/bin/env python3
"""
memory_api.py — Xuzhi 三层记忆系统 API
所有 agents 通过这个 API 读写记忆，不直接访问 DB。
无向量库依赖，零外部服务。

L2: 情景记忆（任务摘要）
L3: 语义记忆（知识单元）

使用：python3 memory_api.py <command> [args]
"""
import json
import sqlite3
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

HOME = Path.home()
DB_PATH = HOME / ".xuzhi_memory" / "memory.db"

# ─── Schema ─────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT    NOT NULL,        -- Φ/Δ/Θ/Γ/Ω/Ψ/Ξ
    task_type   TEXT    NOT NULL,        -- parliament/vote/health_scan/...
    input_sum   TEXT    NOT NULL,        -- 输入摘要（≤200字）
    output_sum  TEXT    NOT NULL,        -- 输出摘要（≤200字）
    status      TEXT    NOT NULL,        -- success/failure/pending
    ts          TEXT    NOT NULL         -- ISO8601
);

CREATE TABLE IF NOT EXISTS knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    content     TEXT    NOT NULL,        -- 知识单元正文
    source      TEXT    NOT NULL,        -- 来源（如 PRT-001）
    tags        TEXT    NOT NULL,        -- 逗号分隔标签
    importance  REAL    NOT NULL DEFAULT 0.5,
    freshness   REAL    NOT NULL DEFAULT 1.0,
    created_at  TEXT    NOT NULL
);

-- FTS5 for L2 keyword search
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    task_type, input_sum, output_sum, content=episodes, content_rowid=id
);

-- FTS5 for L3 keyword search
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    topic, content, tags, content=knowledge, content_rowid=id
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# ─── Init ───────────────────────────────────────────────────────────────────

def init():
    DB_PATH.parent.mkdir(exist_ok=True, parents=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('version', '1.0')")
    conn.commit()
    conn.close()
    print(f"✅ memory.db initialized: {DB_PATH}")

# ─── L2: Episodic Memory ────────────────────────────────────────────────────

def add_episode(agent: str, task_type: str, input_sum: str,
                output_sum: str, status: str) -> int:
    # 字段长度限制
    input_sum = str(input_sum)[:500]
    output_sum = str(output_sum)[:500]
    """写入任务摘要到 L2"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.execute(
        "INSERT INTO episodes (agent, task_type, input_sum, output_sum, status, ts) VALUES (?,?,?,?,?,?)",
        (agent, task_type, input_sum, output_sum, status,
         datetime.now(timezone.utc).isoformat())
    )
    rowid = cur.lastrowid
    # Sync to FTS
    conn.execute(
        "INSERT INTO episodes_fts(rowid, task_type, input_sum, output_sum) VALUES (?,?,?,?)",
        (rowid, task_type, input_sum, output_sum)
    )
    conn.commit()
    conn.close()
    return rowid

def query_episodes(keyword: str = "", agent: str = "", limit: int = 20) -> list:
    """检索 L2：关键词 LIKE + agent 过滤（中文友好）"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM episodes"
    params = []
    conditions = []
    if keyword:
        conditions.append("(task_type LIKE ? OR input_sum LIKE ? OR output_sum LIKE ?)")
        params.extend([f"%{keyword}%"] * 3)
    if agent:
        conditions.append("agent = ?")
        params.append(agent)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY ts DESC LIMIT ?"
    params.append(min(limit, 100))  # cap at 100
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─── L3: Semantic Memory ────────────────────────────────────────────────────

def add_knowledge(topic: str, content: str, source: str,
                  tags: str, importance: float = 0.5, freshness: float = 1.0) -> int:
    """写入知识单元到 L3"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    # Clamp values to valid range
    importance = min(max(float(importance), 0.0), 1.0)
    freshness = min(max(float(freshness), 0.0), 1.0)
    cur = conn.execute(
        "INSERT INTO knowledge (topic, content, source, tags, importance, freshness, created_at) VALUES (?,?,?,?,?,?,?)",
        (topic, content, source, tags, importance, freshness,
         datetime.now(timezone.utc).isoformat())
    )
    rowid = cur.lastrowid
    conn.execute(
        "INSERT INTO knowledge_fts(rowid, topic, content, tags) VALUES (?,?,?,?)",
        (rowid, topic, content, tags)
    )
    conn.commit()
    conn.close()
    return rowid

def query_knowledge(keyword: str = "", tags: str = "", limit: int = 10) -> list:
    """检索 L3：关键词 LIKE + 标签过滤 + importance×freshness 排序"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    query = "SELECT *, (importance * freshness) as score FROM knowledge"
    params = []
    conditions = []
    if keyword:
        conditions.append("(topic LIKE ? OR content LIKE ? OR tags LIKE ?)")
        params.extend([f"%{keyword}%"] * 3)
    if tags:
        conditions.append("tags LIKE ?")
        params.append(f"%{tags}%")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY score DESC LIMIT ?"
    params.append(min(limit, 100))  # cap at 100
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def decay_freshness(days: int = 7, decay: float = 0.9):
    """每日新鲜度衰减"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("UPDATE knowledge SET freshness = freshness * ?", (decay,))
    conn.commit()
    conn.close()

# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "init":
        init()

    elif cmd == "ep_add":
        # ep_add <agent> <task_type> <input_sum> <output_sum> <status>
        _, agent, task_type, input_sum, output_sum, status = sys.argv
        id_ = add_episode(agent, task_type, input_sum, output_sum, status)
        print(f"✅ Episode #{id_} added")

    elif cmd == "ep_query":
        # ep_query [keyword] [agent]
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        agent   = sys.argv[3] if len(sys.argv) > 3 else ""
        for r in query_episodes(keyword, agent):
            print(f"[{r['ts'][:10]}] {r['agent']} | {r['task_type']} | {r['status']} | {r['input_sum'][:60]}")

    elif cmd == "kb_add":
        # kb_add <topic> <content> <source> <tags> [importance] [freshness]
        _, topic, content, source, tags = sys.argv[:6]
        imp = float(sys.argv[6]) if len(sys.argv) > 6 else 0.5
        fr  = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
        id_ = add_knowledge(topic, content, source, tags, imp, fr)
        print(f"✅ Knowledge #{id_} added")

    elif cmd == "kb_query":
        # kb_query [keyword] [tags]
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        tags    = sys.argv[3] if len(sys.argv) > 3 else ""
        for r in query_knowledge(keyword, tags):
            print(f"[{r['source']}] {r['topic']} | score={r['importance']*r['freshness']:.2f}")
            print(f"  {r['content'][:100]}...")

    elif cmd == "decay":
        decay_freshness()
        print("✅ Freshness decayed")

    elif cmd == "help":
        print("""Xuzhi Memory API — 三层记忆系统
Usage:
  init          — 初始化数据库
  ep_add <agent> <task_type> <input_sum> <output_sum> <status>
               — 添加任务摘要到 L2
  ep_query [keyword] [agent]
               — 检索 L2 情景记忆
  kb_add <topic> <content> <source> <tags> [importance] [freshness]
               — 添加知识单元到 L3
  kb_query [keyword] [tags]
               — 检索 L3 语义记忆
  decay         — 新鲜度衰减
""")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
