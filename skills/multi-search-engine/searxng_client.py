#!/usr/bin/env python3
"""
searxng_client.py — SearXNG JSON API 封装
提供简洁的搜索接口，替代 Brave/Google API 调用
"""

import json
import sys
import urllib.request
import urllib.parse
import time

SEARXNG_URL = "http://127.0.0.1:8080"


def search(query, engines=None, timeout=30, max_results=10):
    """
    搜索接口
    
    参数:
        query: 搜索词
        engines: list of engine names, None = all available
        timeout: 超时秒数
        max_results: 最大结果数
    
    返回:
        {"results": [{"title": "", "url": "", "engine": "", "snippet": ""}], "count": int}
    """
    params = {
        "q": query,
        "format": "json",
        "engines": ",".join(engines) if engines else None,
    }
    # 移除 None 值
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

        return {
            "results": results,
            "count": len(results),
            "query": query,
            "unresponsive": [u[0] for u in unresponsive] if unresponsive else [],
            "engines_used": [e for e in (engines or []) if e not in (unresponsive or [])],
        }

    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "results": [],
            "count": 0,
        }


def main():
    if len(sys.argv) < 2:
        print("用法: python3 searxng_client.py '<搜索词>' [engines]")
        print("例: python3 searxng_client.py 'hello world' bing,ddg")
        sys.exit(1)

    query = sys.argv[1]
    engines = sys.argv[2].split(",") if len(sys.argv) > 2 else None

    start = time.time()
    result = search(query, engines)
    elapsed = time.time() - start

    if "error" in result:
        print(f"错误: {result['error']}")
        sys.exit(1)

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
