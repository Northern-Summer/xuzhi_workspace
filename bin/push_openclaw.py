#!/usr/bin/env python3
"""
push_openclaw.py — 用 GitHub Contents API 推送 .openclaw 备份
绕过 git push (git protocol 路由问题)
Token: 从 ~/.xuzhi_memory/.github_token 读取（600权限，零硬编码在脚本中）
工程改进铁律合规 — Ξ | 2026-03-25
"""
import base64, json, os, subprocess, sys, urllib.request as ur, shutil
from pathlib import Path

TOKEN_FILE = Path.home() / ".xuzhi_memory" / ".github_token"
REPO = "Northern-Summer/xuzhi_workspace"
API = f"https://api.github.com/repos/{REPO}"
OPENCLAW = Path.home() / ".openclaw"
BACKUP_DIR = Path("/tmp/openclaw_backup_push")

def get_token():
    try:
        return TOKEN_FILE.read_text().strip()
    except:
        return ""

TOKEN = get_token()
if not TOKEN:
    print("ERROR: No GitHub token")
    sys.exit(1)

def api(method, path, data=None):
    url = f"{API}/{path}"
    req = ur.Request(url, data=json.dumps(data).encode() if data else None,
                     headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    req.get_method = lambda: method
    try:
        with ur.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except ur.HTTPError as e:
        return {"error": e.read().decode()}

def get_sha(path):
    r = api("GET", f"contents/{path}")
    return r.get("sha", "")

def upload_file(fname, fpath):
    if not fpath.exists():
        return True
    content = base64.b64encode(fpath.read_bytes()).decode()
    sha = get_sha(fname)
    data = {"message": f"backup: {fname}", "content": content}
    if sha:
        data["sha"] = sha
    r = api("PUT", f"contents/{fname}", data)
    if "error" in r:
        print(f"  FAIL {fname}: {str(r['error'])[:80]}")
        return False
    print(f"  OK   {fname}")
    return True

# 收集文件
BACKUP_DIR.mkdir(exist_ok=True)
for f in OPENCLAW.glob("workspace/*.md"):
    shutil.copy2(f, BACKUP_DIR / f.name)

for subdir in ("cron", "tasks"):
    p = OPENCLAW / subdir
    if p.is_dir():
        for f in p.glob("*.json"):
            shutil.copy2(f, BACKUP_DIR / f.name)

for agent in ["main", "phi", "delta", "theta", "gamma", "omega", "psi"]:
    p = OPENCLAW / "agents" / f"{agent}.json"
    if p.exists():
        shutil.copy2(p, BACKUP_DIR / f"{agent}.json")

# 脱敏 openclaw.json
op = OPENCLAW / "openclaw.json"
if op.exists():
    d = json.loads(op.read_text())
    for a in d.get("agents", {}).get("list", []):
        i = a.get("identity", {})
        if "name" in i: i["name"] = "REDACTED"
        if "emoji" in i: i["emoji"] = "?"
    for k in ("token", "apiKey", "secret"):
        for p in (d.get("auth", {}), d.get("gateway", {}).get("auth", {})):
            if k in p and len(p[k]) > 8:
                p[k] = "REDACTED"
    (BACKUP_DIR / "openclaw.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))

files = sorted([f.name for f in BACKUP_DIR.iterdir() if not f.name.startswith(".")])
print(f"Pushing {len(files)} files to {REPO}...")
ok = sum(upload_file(f, BACKUP_DIR / f) for f in files)
print(f"\nDone: {ok}/{len(files)} files pushed")

# 清理
shutil.rmtree(BACKUP_DIR, ignore_errors=True)
