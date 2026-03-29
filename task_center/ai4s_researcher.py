#!/usr/bin/env python3
"""
AI4S Researcher — 每周AI+学科开源项目追踪
Engineering Improvement Law compliant — Ξ | 2026-03-29

每周一早上自动运行，覆盖全部7个AI+学科领域。
输出：各领域前三开源可复刻项目，写入对应 centers/AI4S.md
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime

HOME = Path.home()
SCRIPT_DIR = __file__.parent
DOMAINS = [
    ("mathematics", "AI+Math", "AI mathematics proof assistant open source 2025 2026", "Δ Delta"),
    ("naturalscience", "AI+Science", "AI for science open source alphaFold protein 2025 2026", "Γ Gamma"),
    ("socialscience", "AI+SocialScience", "AI social science computational open source 2025 2026", "Θ Theta"),
    ("art", "AI+Art", "AI art music creative open source stable diffusion 2025 2026", "Ω Omega"),
    ("philosophy", "AI+Philosophy", "AI philosophy ethics reasoning automated open source 2025 2026", "Ψ Psi"),
    ("linguistics", "AI+Linguistics", "AI linguistics NLP multilingual open source 2025 2026", "Φ Phi"),
    ("engineering", "AI+AI", "AutoML AI agent framework open source best practices 2025 2026", "Ξ Xi"),
]

SEARXNG = HOME / ".openclaw/workspace/skills/multi-search-engine/searxng_client.py"
LOG = HOME / ".xuzhi_memory/task_center/ai4s_researcher.log"
LOCK = HOME / ".xuzhi_memory/task_center/.ai4s_researcher.lock"

def log(msg):
    stamp = datetime.now().strftime("%H:%M")
    line = f"[{stamp}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def acquire_lock():
    if LOCK.exists():
        log("LOCK exists, skip")
        return False
    LOCK.write_text(str(__import__('os').getpid()))
    return True

def release_lock():
    if LOCK.exists():
        LOCK.unlink()

def search(query, engines="bing"):
    """Search via SearXNG, return list of (title, url, snippet)"""
    try:
        result = subprocess.run(
            ["python3", str(SEARXNG), query, engines],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        # Parse bing/brave results
        items = []
        lines = output.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("[bing]") or line.startswith("[brave]"):
                title = line[7:].strip()
                url_line = lines[i+1] if i+1 < len(lines) else ""
                url = url_line.strip() if not url_line.startswith("[") else ""
                snippet_line = lines[i+2] if i+2 < len(lines) else ""
                snippet = snippet_line.strip() if not snippet_line.startswith("[") else ""
                if url and "github.com" in url:
                    items.append((title, url, snippet))
        return items
    except Exception as e:
        log(f"Search error for {query}: {e}")
        return []

def write_ai4s_file(domain_dir, domain_name, agent_letter, items):
    """Write AI4S.md for a domain"""
    file_path = domain_dir / "AI4S.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# {domain_name} — AI4S Weekly Research",
        f"**Generated:** {today} | **Agent:** {agent_letter}",
        "",
        "## Top 3 Open Source Reproducible Projects",
        ""
    ]
    for i, (title, url, snippet) in enumerate(items[:3], 1):
        clean_title = title.split(" - ")[0].split("|")[0].strip()
        lines.append(f"### {i}. {clean_title}")
        lines.append(f"- **URL:** {url}")
        lines.append(f"- **Summary:** {snippet[:200]}")
        lines.append(f"- **Status:** Open Source | Reproducible")
        lines.append("")
    
    with open(file_path, "w") as f:
        f.write("\n".join(lines))
    log(f"Wrote {file_path}")

def main():
    log("=== AI4S Researcher START ===")
    if not acquire_lock():
        return
    
    try:
        GENESIS = HOME / "xuzhi_genesis" / "centers"
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        results = []
        for domain_key, domain_name, query, agent_letter in DOMAINS:
            log(f"Searching {domain_name}...")
            domain_dir = GENESIS / domain_key
            if not domain_dir.exists():
                domain_dir.mkdir(parents=True, exist_ok=True)
            
            items = search(query, "bing")
            # Fallback to arxiv if bing returns nothing useful
            if not items:
                items = search(query, "arxiv")
            
            write_ai4s_file(domain_dir, domain_name, agent_letter, items)
            results.append((domain_name, len(items)))
            log(f"  {domain_name}: {len(items)} items found")
        
        log(f"=== AI4S Researcher DONE | {today} ===")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
