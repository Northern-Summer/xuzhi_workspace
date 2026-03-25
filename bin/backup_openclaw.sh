#!/usr/bin/env bash
# backup_openclaw.sh — 优雅备份 .openclaw（不含凭证）
# 工程改进铁律合规 — Ξ | 2026-03-25
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES
set -euo pipefail

BACKUP_DIR="/tmp/openclaw_backup_$$"
GIT_DIR="$HOME/.openclaw"
TOKEN_SOURCE="$HOME/xuzhi_workspace"

mkdir -p "$BACKUP_DIR"
trap "rm -rf $BACKUP_DIR" EXIT 2>/dev/null || true

log() { echo "[$(date '+%H:%M:%S')] $1"; }

# Token: 从 xuzhi_workspace git remote 动态提取（零硬编码）
get_token() {
    git -C "$TOKEN_SOURCE" config --get remote.origin.url 2>/dev/null | \
        grep -o 'ghp_[A-Za-z0-9]\+' | head -1 || echo ""
}

TOKEN=$(get_token)
if [ -z "$TOKEN" ]; then
    log "ERROR: Could not obtain GitHub token"
    exit 1
fi

REPO="xuzhi_openclaw"

# 1. 复制 workspace .md 文件（无敏感信息）
log "备份 workspace .md..."
for f in IDENTITY SOUL AGENTS HEARTBEAT TOOLS USER MEMORY SOUL_VARIABLE SOUL_IMMUTABLE; do
    cp "$GIT_DIR/workspace/${f}.md" "$BACKUP_DIR/" 2>/dev/null || true
done

# 2. 复制 cron jobs 和 tasks
log "备份调度..."
cp "$GIT_DIR/cron/jobs.json" "$BACKUP_DIR/" 2>/dev/null || true
cp "$GIT_DIR/tasks/tasks.json" "$BACKUP_DIR/" 2>/dev/null || true

# 3. 脱敏复制 openclaw.json 和 agents/*.json
log "脱敏配置..."
if [ -f "$GIT_DIR/openclaw.json" ]; then
    python3 -c "
import json
d = json.load(open('$GIT_DIR/openclaw.json'))
for a in d.get('agents', {}).get('list', []):
    ident = a.get('identity', {})
    if 'name' in ident: ident['name'] = 'REDACTED'
    if 'emoji' in ident: ident['emoji'] = '?'
redact_keys = ('token', 'apiKey', 'secret')
def r(obj):
    for k in redact_keys:
        if k in obj and isinstance(obj[k], str) and len(obj[k]) > 8:
            obj[k] = 'REDACTED'
r(d.get('auth', {}))
r(d.get('gateway', {}).get('auth', {}))
print(json.dumps(d, indent=2, ensure_ascii=False))
" > "$BACKUP_DIR/openclaw.json"
fi

for agent in main phi delta theta gamma omega psi; do
    [ -f "$GIT_DIR/agents/${agent}.json" ] && \
        cp "$GIT_DIR/agents/${agent}.json" "$BACKUP_DIR/" 2>/dev/null || true
done

# 4. Git 操作
cd "$BACKUP_DIR"
git init --quiet
git remote add origin "https://${TOKEN}@github.com/Northern-Summer/${REPO}.git" 2>/dev/null || \
    git remote set-url origin "https://${TOKEN}@github.com/Northern-Summer/${REPO}.git"
git config user.email "xi@xuzhi.system" 2>/dev/null || true
git config user.name "Xuzhi Xi" 2>/dev/null || true

if git rev-parse --verify origin/master >/dev/null 2>&1; then
    git pull origin master --ff --quiet 2>/dev/null || true
fi

git add -A
git commit --quiet -m "backup: $(date '+%Y-%m-%d %H:%M')"
git push origin master 2>&1 | tail -3

log "备份完成"
