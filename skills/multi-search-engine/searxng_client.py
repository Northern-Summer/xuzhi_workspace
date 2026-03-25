#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES
"""
searxng_client.py — SearXNG JSON API 封装
提供简洁的搜索接口，替代 Brave/Google API 调用
支持 --toon 输出（节省30-60% token，供 Agent 使用）
"""

import json
import sys
import urllib.request
import urllib.parse
import time
from pathlib import Path

SEARXNG_URL = "http://127.0.0.1:8080"


def json_to_toon(data):
    """JSON → TOON 格式（零外部依赖，内联实现）"""
    if isinstance(data, list):
        if data and all(isinstance(item, dict) for item in data):
            keys = []
            for item in data:
                for k in item:
                    if k not in keys:
                        keys.append(k)
            if all(set(item.keys()) == set(keys) for item in data if item):
                header = f"[{len(data)}]{{{','.join(keys)}}}"
                rows = []
                for item in data:
                    row = ",".join(str(item.get(k, "")) for k in keys)
                    rows.append(row)
                return f"{header}:\n" + "\n".join(f"  {r}" for r in rows)
        lines = [json_to_toon(item) for item in data]
        return "[\n" + ",\n".join("  " + l for l in lines) + "\n]"
    if isinstance(data, dict):
        if not data:
            return "{}"
        lines = []
        for k, v in data.items():
            v_str = json_to_toon(v)
            if isinstance(v, (dict, list)):
                lines.append(f"  {k}: {v_str}")
            else:
                lines.append(f"  {k}: {repr(v) if isinstance(v, str) else v}")
        return "{\n" + ",\n".join(lines) + "\n}"
    if isinstance(data, str):
        return repr(data)
    return str(data)


def search(query, engines=None, timeout=30, max_results=10, toon=False):
    """
    搜索接口

    参数:
        query: 搜索词
        engines: list of engine names, None = all available
        timeout: 超时秒数
        max_results: 最大结果数
        toon: True → 返回TOON格式字符串（供Agent/LLM使用，省token）

    返回:
        toon=False: {"results": [...], "count": int, ...}
        toon=True:  TOON格式字符串
    """
    params = {
        "q": query,
        "format": "json",
        "engines": ",".join(engines) if engines else None,
    }
    params = {k: v for k, v in params.items() if v}
    url = SEARXNG_URL + "/search?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for r in data.get("results", [])[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "engine": r.get("engine", ""),
                "snippet": r.get("content", ""),
            })

        unresponsive = data.get("unresponsive_engines", [])

        payload = {
            "results": results,
            "count": len(results),
            "query": query,
            "unresponsive": [u[0] for u in unresponsive] if unresponsive else [],
            "engines_used": [e for e in (engines or []) if e not in (unresponsive or [])],
        }

        if toon:
            # TOON: 结果列表用表格格式，主数据用JSON兼容结构
            toon_payload = {
                "query": query,
                "count": len(results),
                "engines_used": payload["engines_used"],
                "unresponsive": payload["unresponsive"],
                "results": results,
            }
            return json_to_toon(toon_payload)

        return payload

    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "results": [],
            "count": 0,
        }


def main():
    argv = sys.argv[1:]
    toon = "--toon" in argv or "-t" in argv
    argv = [a for a in argv if a not in ("--toon", "-t")]

    if len(argv) < 1:
        print("用法: python3 searxng_client.py '<搜索词>' [engines] [--toon|-t]")
        print("  --toon: 输出TOON格式（节省token，供Agent使用）")
        print("例: python3 searxng_client.py 'hello world' bing,ddg")
        sys.exit(1)

    query = argv[0]
    engines = argv[1].split(",") if len(argv) > 1 else None

    start = time.time()
    result = search(query, engines, toon=toon)
    elapsed = time.time() - start

    if "error" in result and not toon:
        print(f"错误: {result['error']}")
        sys.exit(1)

    if toon:
        # Agent输出: 纯TOON，无装饰
        print(result)
    else:
        print(f"查询: {result['query']} ({result['count']} 条结果, {elapsed:.2f}s)")
        if result.get("unresponsive"):
            print(f"引擎无响应: {', '.join(result['unresponsive'])}")
        print()
        for r in result["results"]:
            print(f"[{r['engine']}] {r['title']}")
            print(f"  {r['url']}")
            if r["snippet"]:
                print(f"  {r['snippet'][:100]}...")
            print()


if __name__ == "__main__":
    main()
