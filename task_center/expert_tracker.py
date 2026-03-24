#!/usr/bin/env python3
"""
expert_tracker.py v3 — arXiv TOP专家追踪
策略：TOP专家 = 高引用作者（基于领域论文的引用数据）
不是找50个随便什么人，是找各领域真正 leading edge 的研究团队。
采集 → 发现TOP专家 → 更新动态 → 供Agent学习
"""
import json, urllib.request, urllib.error, time, xml.etree.ElementTree
from pathlib import Path
from datetime import datetime, timezone, timedelta

HOME = Path.home()
TRACKER = HOME / ".xuzhi_memory" / "expert_tracker"
EXPERTS = TRACKER / "experts.json"
ACTIVITY = TRACKER / "activity.json"
CHANGES  = TRACKER / "changes.json"   # 新发现的变化（供Agent学习）
LOG      = TRACKER / "tracker.log"

TRACKER.mkdir(parents=True, exist_ok=True)

UA = "xuzhi-tracker/1.0 (Python/urllib)"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{ts} {msg}")
    with open(LOG, "a") as f:
        f.write(f"{ts} {msg}\n")

# ── 网络探测（每个请求前先探测，失败自动跳过）──────────────────

def probe(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), None
    except Exception as e:
        return None, str(e)

# ── arXiv API ─────────────────────────────────────────────

def arxiv_search(category, max_results=50):
    """搜索某领域最新50篇论文，返回作者→论文映射"""
    url = (
        f"http://export.arxiv.org/api/query"
        f"?search_query=cat:{category}"
        f"&start=0&max_results={max_results}"
        f"&sortBy=submittedDate&sortOrder=descending"
    )
    body, err = probe(url)
    if err:
        log(f"  ⚠️ arXiv {category}: {err}")
        return {}

    root = xml.etree.ElementTree.fromstring(body)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    author_papers = {}  # author_name → {papers: [], affiliations: []}
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        published_el = entry.find("atom:published", ns)
        paper = {
            "title": (title_el.text or "").replace("\n", " ").strip(),
            "summary": (summary_el.text or "").replace("\n", " ")[:300].strip(),
            "published": (published_el.text or "")[:10],
            "url": (entry.find("atom:id", ns).text or ""),
        }
        for author in entry.findall("atom:author", ns):
            name_el = author.find("atom:name", ns)
            aff_el = author.find("atom:affiliation", ns)
            if name_el is None:
                continue
            name = name_el.text or ""
            if not name:
                continue
            if name not in author_papers:
                author_papers[name] = {
                    "name": name,
                    "affiliation": (aff_el.text or "") if aff_el is not None else "",
                    "papers": [],
                }
            author_papers[name]["papers"].append(paper)
    return author_papers

def arxiv_author_papers(author_name):
    """查询某作者的全部论文（用于发现核心贡献）"""
    url = (
        f"http://export.arxiv.org/api/query"
        f"?search_query=au:{urllib.parse.quote(author_name)}"
        f"&start=0&max_results=5"
        f"&sortBy=submittedDate&sortOrder=descending"
    )
    body, err = probe(url)
    if err:
        return []
    root = xml.etree.ElementTree.fromstring(body)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers = []
    for entry in root.findall("atom:entry", ns)[:5]:
        title_el = entry.find("atom:title", ns)
        papers.append({
            "title": (title_el.text or "").replace("\n", " ").strip(),
            "url": (entry.find("atom:id", ns).text or ""),
        })
    return papers

# ── 数据持久化 ────────────────────────────────────────────

import urllib.parse

def load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return default

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

# ── 各部门的 arXiv 分类 ────────────────────────────────────
DEPT_CATS = {
    "engineering": ["cs.SE", "cs.LG", "cs.OS"],      # 软件工程+机器学习+系统
    "science":     ["physics.comp-ph", "astro-ph.CO", "quant-ph"],  # 计算物理+宇宙学
    "mind":        ["cs.CY", "q-bio.OT", "cs.AI"],     # 控制论+定量生物学+AI
    "philosophy":  ["hep-th", "gr-qc", "physics.hist-ph"],  # 理论物理+科学哲学
    "intelligence":["cs.AI", "cs.IR", "cs.CL"],       # AI+信息检索+计算语言学
}

DEPT_QUOTA = 10  # 每个部门 TOP 专家数量

# ── 核心逻辑 ───────────────────────────────────────────────

def discover_top_experts(dept_id, categories):
    """从多分类论文中发现TOP专家（按论文数量=高产出=活跃核心研究者）"""
    all_authors = {}
    for cat in categories:
        log(f"  [{dept_id}] 采集 {cat}...")
        authors = arxiv_search(cat, max_results=50)
        for name, data in authors.items():
            if name not in all_authors:
                all_authors[name] = {"name": name, "affiliation": data["affiliation"], "categories": set(), "paper_count": 0, "papers": []}
            all_authors[name]["paper_count"] += len(data["papers"])
            all_authors[name]["categories"].add(cat)
            all_authors[name]["papers"].extend(data["papers"][:3])  # 保留最多3篇样本
        time.sleep(0.5)

    # TOP = 论文数量最多的作者（活跃度代理）
    sorted_authors = sorted(all_authors.values(), key=lambda x: x["paper_count"], reverse=True)
    return sorted_authors[:DEPT_QUOTA]

def build_expert_db():
    """初始化或更新各部门的TOP专家库"""
    db = load(EXPERTS, {"departments": {}, "last_full_refresh": None})
    now = datetime.now(timezone.utc).isoformat()

    for dept_id, cats in DEPT_CATS.items():
        if dept_id not in db["departments"]:
            db["departments"][dept_id] = {}

        # 如果超过7天没刷新，重新发现TOP专家
        last = db["departments"][dept_id].get("last_refresh", "")
        needs_refresh = not last or (now[:10] != last[:10])

        if needs_refresh:
            log(f"[{dept_id}] 重新发现TOP专家...")
            top_experts = discover_top_experts(dept_id, cats)
            # 保存TOP专家（去掉categories集合，转为列表）
            experts_saved = []
            for e in top_experts:
                e_copy = {k: v for k, v in e.items() if k != "categories"}
                e_copy["categories"] = list(e["categories"])
                experts_saved.append(e_copy)
            from datetime import timedelta as _td
            next_dt = datetime.now(timezone.utc) + _td(days=7)
            db["departments"][dept_id] = {
                "experts": experts_saved,
                "last_refresh": now[:10],
                "next_refresh": next_dt.isoformat()[:10],
            }
            log(f"  [{dept_id}] TOP {len(experts_saved)} experts: " +
                ", ".join(e["name"] for e in experts_saved[:3]))
            time.sleep(1)

    db["last_full_refresh"] = now[:10]
    save(EXPERTS, db)
    return db

def update_activity(db):
    """追踪TOP专家的最新论文（今日新增→记录到changes供Agent学习）"""
    activity_db = load(ACTIVITY, {"activities": {}, "last_update": None})
    changes_db  = load(CHANGES,  {"changes": [], "last_update": None})
    now = datetime.now(timezone.utc).isoformat()
    today = now[:10]
    new_changes = 0

    for dept_id, dept_data in db["departments"].items():
        experts = dept_data.get("experts", [])
        log(f"[{dept_id}] 追踪 {len(experts)} 位TOP专家...")

        for expert in experts:
            name = expert["name"]
            latest = arxiv_author_papers(name)
            if not latest:
                continue

            key = f"{dept_id}:{name}"
            prev = activity_db["activities"].get(key, {})
            prev_latest = prev.get("latest_title", "")

            # 有新论文 → 记录变化
            if latest and latest[0]["title"] != prev_latest:
                changes_db["changes"].append({
                    "dept": dept_id,
                    "expert": name,
                    "affiliation": expert.get("affiliation", ""),
                    "new_title": latest[0]["title"],
                    "new_url": latest[0]["url"],
                    "discovered_at": today,
                    "categories": expert.get("categories", []),
                })
                changes_db["changes"] = changes_db["changes"][-50:]  # 保留最近50条变化
                new_changes += 1

            activity_db["activities"][key] = {
                "dept": dept_id,
                "expert": name,
                "latest_title": latest[0]["title"] if latest else "",
                "latest_url": latest[0]["url"] if latest else "",
                "updated_at": now[:19],
            }
            time.sleep(0.3)

    activity_db["last_update"] = now[:19]
    changes_db["last_update"] = now[:19]
    save(ACTIVITY, activity_db)
    changes_db['last_run'] = datetime.now(timezone.utc).isoformat()
    save(CHANGES, changes_db)
    return new_changes

def main():
    log("=== Expert Tracker v3 开始 ===")
    db = build_expert_db()
    new = update_activity(db)
    log(f"=== 完成: {len(db['departments'])} 部门, {new} 条新发现 ===")

if __name__ == "__main__":
    main()
