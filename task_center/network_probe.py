#!/usr/bin/env python3
"""
network_probe.py — Xuzhi 网络连通性探测
自动检测所有数据源的可用性，不依赖任何外部 API key。
返回可用源清单，供其他模块直接使用。
"""
import urllib.request, urllib.error, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
PROBE_LOG = HOME / ".xuzhi_memory" / "task_center" / "network_probe.log"

RESULTS = {}  # 缓存探测结果

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{ts} {msg}")
    with open(PROBE_LOG, "a") as f:
        f.write(f"{ts} {msg}\n")

def probe(url, timeout=5, headers=None):
    """返回 (ok: bool, latency_ms: float, error: str)"""
    start = time.time()
    try:
        req = urllib.request.Request(url, headers=headers or {
            "User-Agent": "xuzhi-probe/1.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            latency = (time.time() - start) * 1000
            return True, latency, ""
    except Exception as e:
        return False, (time.time() - start) * 1000, str(e)[:60]

def probe_github():
    """GitHub Search API — 免费，无需 key（限速60次/h，对我们够用）"""
    ok, lat, err = probe(
        "https://api.github.com/search/code?q=stars:>1000+language:python&per_page=1",
        timeout=8,
        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "xuzhi-probe/1.0"}
    )
    return ok, lat, err

def probe_arxiv():
    """arXiv — 完全免费，无 key"""
    ok, lat, err = probe(
        "http://export.arxiv.org/api/query?id_list=2500.00001&max_results=1",
        timeout=10
    )
    return ok, lat, err

def probe_searxng():
    """SearXNG — 本地零成本"""
    for port in [8080, 8888, 8090]:
        ok, lat, err = probe(f"http://localhost:{port}/search?q=test&format=json", timeout=4)
        if ok:
            return ok, lat, f"localhost:{port}"
    return False, 0, "all ports failed"

def probe_s2():
    """Semantic Scholar — 免费 API，30次/5min"""
    ok, lat, err = probe(
        "https://api.semanticscholar.org/graph/v1/paper/search?query=AI&limit=1&fields=title",
        timeout=8
    )
    return ok, lat, err

def probe_brave():
    """Brave Search — 需要 key，没配则跳过"""
    key = ""
    for env in ["BRAVE_API_KEY", "OPENCLAW_BRAVE_API_KEY"]:
        import os
        key = os.environ.get(env, "")
        if key:
            break
    if not key:
        return False, 0, "no API key"
    ok, lat, err = probe(
        f"https://api.search.brave.com/res/v1/search?q=test",
        timeout=8,
        headers={"Accept": "application/json", "X-Subscription-Token": key}
    )
    return ok, lat, err

def run():
    log("=== 网络探测开始 ===")
    sources = {
        "github": probe_github,
        "arxiv": probe_arxiv,
        "searxng": probe_searxng,
        "semantic_scholar": probe_s2,
        "brave": probe_brave,
    }

    available = {}
    for name, fn in sources.items():
        ok, lat, err = fn()
        status = "✅" if ok else "❌"
        log(f"  {status} {name}: {lat:.0f}ms{(' — ' + err) if err else ''}")
        if ok:
            available[name] = lat

    log(f"=== 可用源: {list(available.keys())} ===")
    return available

if __name__ == "__main__":
    run()
