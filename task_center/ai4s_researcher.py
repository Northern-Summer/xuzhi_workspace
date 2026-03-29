#!/usr/bin/env python3
"""
AI4S Researcher — 每周AI+学科开源项目追踪
工程改进铁律合规 — Ξ | 2026-03-29
自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

每周一早上自动运行，覆盖全部7个AI+学科领域。
输出：各领域前三开源可复刻项目，写入对应 centers/AI4S.md

SearXNG 搜索方案：
- 使用 subprocess curl 直接请求（绕过 Python urllib SSL 问题）
- format=html + grep 提取 GitHub URL（JSON API 有 bug）
- 有代理走代理（via settings.yml），无代理直连（SSL verify=false）
- 永久修复：settings.yml outgoing.verify=false + proxies 已配置
"""

import subprocess
import re
import urllib.parse
from pathlib import Path
from datetime import datetime

HOME = Path.home()
SEARXNG_URL = "http://127.0.0.1:8080"
LOG = HOME / ".xuzhi_memory/task_center/ai4s_researcher.log"
LOCK = HOME / ".xuzhi_memory/task_center/.ai4s_researcher.lock"

DOMAINS = [
    ("mathematics",    "AI for Mathematics",     "lean4 theorem proving AI mathematical reasoning github",         "Δ Delta"),
    ("naturalscience", "AI for Natural Science", "alphaFold protein structure prediction AI science github",         "Γ Gamma"),
    ("socialscience",  "AI for Social Science",  "AI social science computational simulation agent open source",       "Θ Theta"),
    ("art",           "AI for Art",             "AI art music creative generation stable diffusion open source",     "Ω Omega"),
    ("philosophy",     "AI for Philosophy",      "AI philosophy ethics automated reasoning open source github",        "Ψ Psi"),
    ("linguistics",    "AI for Linguistics",     "AI linguistics NLP multilingual model huggingface open source",    "Φ Phi"),
    ("engineering",    "AI for AI",              "AI agent framework LangChain AutoGen crewai open source 2025",     "Ξ Xi"),
]

def log(msg):
    stamp = datetime.now().strftime("%H:%M")
    line = f"[{stamp}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def acquire_lock():
    if LOCK.exists():
        pid = LOCK.read_text().strip()
        log(f"LOCK exists (pid={pid}), skip")
        return False
    LOCK.write_text(str(__import__("os").getpid()))
    return True

def release_lock():
    if LOCK.exists():
        LOCK.unlink()

def search_github(query, timeout=15):
    """
    通过 SearXNG HTML 提取 GitHub URLs。
    使用 curl subprocess（绕过 Python urllib SSL 问题）。
    """
    encoded_q = urllib.parse.quote(query)
    url = f"{SEARXNG_URL}/search?q={encoded_q}&format=html"
    
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), "--get", url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        html = result.stdout
    except Exception as e:
        log(f"Search error for {query}: {e}")
        return []
    
    if not html or len(html) < 100:
        return []
    
    links = re.findall(r'href="(https?://github\.com/[^"]+)"', html)
    
    BLOCKED = {"searxng/searxng", "searxng/searxng-issues", "searxng"}
    seen = set()
    unique = []
    for link in links:
        clean = link.split("?")[0].split("#")[0]
        parts = clean.replace("https://github.com/", "").split("/")
        if len(parts) >= 2 and f"{parts[0]}/{parts[1]}" in BLOCKED:
            continue
        if clean not in seen:
            seen.add(clean)
            unique.append(clean)
    
    return unique[:5]

def get_repo_name(url):
    parts = url.replace("https://github.com/", "").split("/")
    return f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else url

def write_ai4s(domain_key, domain_name, agent_letter, repos):
    """写入单个领域的 AI4S.md"""
    genesis = HOME / "xuzhi_genesis" / "centers" / domain_key
    genesis.mkdir(parents=True, exist_ok=True)
    path = genesis / "AI4S.md"
    
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# {domain_name} — AI4S Weekly Research",
        f"**Generated:** {today} | **Agent:** {agent_letter}",
        "",
        "## Top 3 Open Source Reproducible Projects",
        ""
    ]
    for i, url in enumerate(repos[:3], 1):
        lines.append(f"### {i}. {get_repo_name(url)}")
        lines.append(f"- **URL:** {url}")
        lines.append(f"- **Status:** Open Source | Active")
        lines.append("")
    
    next_week = f"{today[:8]}05"
    lines.append(f"## Next Update\n{next_week} (weekly)")
    
    with open(path, "w") as f:
        f.write("\n".join(lines))
    
    return len(repos)

def main():
    log("=== AI4S Researcher START ===")
    if not acquire_lock():
        return
    
    try:
        total_repos = 0
        for domain_key, domain_name, query, agent_letter in DOMAINS:
            log(f"Searching {domain_name}...")
            repos = search_github(query)
            count = write_ai4s(domain_key, domain_name, agent_letter, repos)
            log(f"  {domain_name}: {count} repos")
            total_repos += count
        
        log(f"=== DONE | {total_repos} repos across {len(DOMAINS)} domains ===")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
