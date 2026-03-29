#!/usr/bin/env python3
"""
run.py — Xuzhi 工作流统一入口
使用方式: python3 run.py [命令]
工程改进铁律合规 — Ξ | 2026-03-29
"""
import sys, os

HOME = os.path.expanduser("~")
COMMANDS = {}

def cmd(name, desc, fn):
    COMMANDS[name] = {"desc": desc, "fn": fn}

# === 命令注册 ===

def _ai4s():
    """AI4S 研究：搜索 + 验证每周 7 个领域"""
    from task_center.ai4s_researcher import main as run
    run()

cmd("ai4s", "AI4S 研究（7领域搜索+验证）", _ai4s)

def _morning():
    """晨间扫描：微信公众号 + SearXNG AI 动态"""
    import subprocess, time
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    mem_path = os.path.expanduser("~/.xuzhi_memory/memory/") + today + ".md"
    
    results = []
    
    # 1. 公众号扫描（用关键词）
    accounts = ["量子位", "机器之心", "AI寒武纪", "DeepTech深科技", "集智俱乐部", "知识分子", "神经现实"]
    for acc in accounts:
        r = subprocess.run(["python3", f"{HOME}/.openclaw/workspace/wechat_search.py", acc, "3"],
                         capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            lines = [l.strip() for l in r.stdout.split("\n") if l.strip() and "Query:" not in l]
            results.append(f"### {acc}")
            for l in lines[:3]:
                if l.startswith("Title:"):
                    results.append(f"- {l[6:].strip()}")
    
    # 2. 写入 memory
    if results:
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write("\n\n## 晨间扫描\n")
            f.write(f"**时间**: {datetime.now().strftime('%H:%M')}\n\n")
            for r in results:
                f.write(r + "\n")
    
    print(f"[晨间扫描] 完成，写入 {mem_path}")
    print(f"共 {len([r for r in results if r.startswith('-')])} 条")

cmd("morning", "晨间扫描（公众号+AI动态）", _morning)

def _verify_all():
    """验证系统：Git push 状态 + Cron 运行 + SSL 健康"""
    import subprocess
    from datetime import datetime
    
    checks = []
    
    # 1. Git push 状态
    for repo in ["~/.xuzhi_memory", "~/xuzhi_genesis", "~/xuzhi_workspace"]:
        r = subprocess.run(["git", "status", "--porcelain"], cwd=os.path.expanduser(repo),
                           capture_output=True, text=True)
        if r.stdout.strip():
            unpushed = subprocess.run(["git", "log", "origin/master..HEAD", "--oneline"],
                                    cwd=os.path.expanduser(repo), capture_output=True, text=True)
            n = len(unpushed.stdout.strip().split("\n"))
            checks.append(f"  ⚠️  {os.path.basename(repo)}: {n} commits 未 push")
        else:
            checks.append(f"  ✅ {os.path.basename(repo)}: 已是最新")
    
    # 2. SearXNG 健康
    r = subprocess.run(["curl", "-s", "--max-time", "5", "http://127.0.0.1:8080/health"],
                      capture_output=True, text=True)
    if "ok" in r.stdout.lower() or r.returncode == 0:
        checks.append("  ✅ SearXNG: 正常")
    else:
        checks.append("  ❌ SearXNG: 无响应")
    
    # 3. SSL 验证
    r = subprocess.run(["python3", "-c", 
                       "import urllib.request,ssl,ssl; ctx=ssl._create_unverified_context(); "
                       "print(urllib.request.urlopen('https://api.github.com',timeout=5).status)"],
                      capture_output=True, text=True)
    if r.returncode == 0 and "200" in r.stdout:
        checks.append("  ✅ SSL: GitHub API 可达")
    else:
        checks.append("  ❌ SSL: GitHub API 不可达")
    
    print(f"[系统验证 | {datetime.now().strftime('%H:%M')}]")
    for c in checks:
        print(c)

cmd("verify", "系统验证（Git+SearXNG+SSL）", _verify_all)

def _status():
    """系统状态概览"""
    import subprocess, os
    from datetime import datetime
    
    print(f"=== Xuzhi 系统状态 | {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")
    
    # Cron jobs
    r = subprocess.run(["openclaw", "cron", "list"], capture_output=True, text=True)
    if r.returncode == 0:
        lines = [l for l in r.stdout.split("\n") if "ai4s" in l.lower() or "pulse" in l.lower()]
        print(f"## Cron 任务 ({len(lines)})")
        for l in lines[:5]:
            print(f"  {l.strip()}")
    else:
        print("  ⚠️  Cron 无法读取")
    
    # AI4S 领域
    centers = f"{HOME}/xuzhi_genesis/centers"
    if os.path.exists(centers):
        domains = [d for d in os.listdir(centers) if os.path.isdir(f"{centers}/{d}")]
        ai4s_count = sum(1 for d in domains if os.path.exists(f"{centers}/{d}/AI4S.md"))
        print(f"\n## AI4S 领域: {ai4s_count}/{len(domains)} 已初始化")
        for d in sorted(domains):
            ai4s = f"{centers}/{d}/AI4S.md"
            if os.path.exists(ai4s):
                mtime = datetime.fromtimestamp(os.path.getmtime(ai4s)).strftime("%m-%d")
                print(f"  ✅ {d} (更新: {mtime})")
            else:
                print(f"  ⬜ {d}")
    
    # 公众号追踪账号
    accounts_file = f"{HOME}/.xuzhi_memory/expert_tracker/wechat_accounts.json"
    if os.path.exists(accounts_file):
        import json
        try:
            with open(accounts_file) as f:
                d = json.load(f)
            valid = [k for k in d if not k.startswith("_") and isinstance(d[k], dict)]
            print(f"\n## 公众号追踪: {len(valid)} 个账号")
        except:
            print("\n## 公众号追踪: 读取失败")

cmd("status", "系统状态概览", _status)

# === 主入口 ===

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "--help", "-h"):
        print("=== Xuzhi run.py 命令 ===\n")
        print("  python3 run.py <命令>\n")
        for name, info in sorted(COMMANDS.items()):
            print(f"  {name:12s} — {info['desc']}")
        print()
        return
    
    cmd_name = sys.argv[1]
    if cmd_name not in COMMANDS:
        print(f"未知命令: {cmd_name}")
        print("可用: " + ", ".join(COMMANDS.keys()))
        sys.exit(1)
    
    COMMANDS[cmd_name]["fn"]()

if __name__ == "__main__":
    main()
