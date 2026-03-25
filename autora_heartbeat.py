#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES
"""
AutoRA Heartbeat - 在 main session 运行，直接调用 web_search 工具
支持精确匹配缓存：重复查询直接返回缓存结果，不触发 WEB_SEARCH。
缓存文件：~/.xuzhi_genesis/centers/intelligence/query_cache.json
"""
import json, sys, time, hashlib
from pathlib import Path
from datetime import datetime

GENESIS     = Path.home() / "xuzhi_genesis"
INTELLIGENCE = GENESIS / "centers" / "intelligence"
QUEUE_FILE  = INTELLIGENCE / "autora_task_queue.json"
CACHE_FILE  = INTELLIGENCE / "query_cache.json"
STATE_FILE  = INTELLIGENCE / "autora_state.json"
RESULTS_FILE = INTELLIGENCE / "autora_logs" / "research_results.md"
LOG_DIR     = INTELLIGENCE / "autora_logs"

LOG_DIR.mkdir(exist_ok=True)
CACHE_TTL_SECS = 7 * 86400  # 7天过期

# ── 缓存 ────────────────────────────────────────────────────────────────────

def _norm(q: str) -> str:
    """规范化查询：去除首尾空白，转小写，压缩空白"""
    return " ".join(q.strip().lower().split())


def _cache_key(q: str) -> str:
    """稳定哈希键（MD5，零随机性）"""
    return hashlib.md5(_norm(q).encode()).hexdigest()[:16]


def load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


def cache_get(query: str):
    """精确匹配缓存查询。命中有结果，无命中/过期返回 None。"""
    cache = load_cache()
    key = _cache_key(query)
    entry = cache.get(key)
    if not entry:
        return None
    # 检查过期
    try:
        age = time.time() - entry.get("cached_at", 0)
        if age > CACHE_TTL_SECS:
            return None
    except Exception:
        return None
    return entry.get("result")


def cache_set(query: str, result: str):
    """写入缓存（精确匹配）"""
    cache = load_cache()
    key = _cache_key(query)
    cache[key] = {
        "query": _norm(query),
        "result": result,
        "cached_at": time.time(),
    }
    save_cache(cache)


# ── 日志 ────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        (LOG_DIR / f"heartbeat_{datetime.now().strftime('%Y-%m-%d')}.log").open("a").write(line + "\n")
    except Exception:
        pass


def load_queue():
    if not QUEUE_FILE.exists():
        return []
    try:
        return json.loads(QUEUE_FILE.read_text())
    except Exception:
        return []


def get_pending(limit=3):
    tasks = load_queue()
    pending = [t for t in tasks if t.get("status") == "pending"]
    return pending[:limit]


def mark_done(query):
    if not QUEUE_FILE.exists():
        return
    try:
        tasks = json.loads(QUEUE_FILE.read_text())
        for t in tasks:
            if t.get("query") == query and t.get("status") == "pending":
                t["status"] = "done"
        QUEUE_FILE.write_text(json.dumps(tasks, indent=2))
    except Exception:
        pass


def write_result(query, result_text):
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    lines = [
        f"\n## 搜索: {query}",
        f"时间: {datetime.now().isoformat()}",
        f"结果: {result_text[:500]}"
    ]
    RESULTS_FILE.open("a").write("\n".join(lines) + "\n")


# ── 主逻辑 ──────────────────────────────────────────────────────────────────

def main():
    log("=" * 40)
    log("HEARTBEAT AutoRA 启动")
    pending = get_pending(limit=3)
    log(f"待处理任务: {len(pending)}")

    emitted = 0
    skipped = 0

    for i, task in enumerate(pending):
        q = task.get("query", "")
        if not q:
            continue

        cached = cache_get(q)
        if cached:
            log(f"  [{i+1}/{len(pending)}] CACHE HIT: {q[:60]}")
            write_result(q, f"[cached] {cached[:200]}")
            skipped += 1
        else:
            log(f"  [{i+1}/{len(pending)}] SEARCH: {q[:60]}")
            # Agent 输出格式：[[WEB_SEARCH]] <query>
            print(f"[[WEB_SEARCH]] {q}", flush=True)
            # 缓存占位：结果由 main session 回填
            # 标记任务完成（main session 会处理实际搜索）
            mark_done(q)
            emitted += 1

    log(f"处理完成: {emitted} 次搜索请求, {skipped} 次缓存命中")

if __name__ == "__main__":
    main()
