#!/bin/bash
# Xuzhi Genesis — Self-Heal v3
# 升级：增加 git sync 验证 + CI status 检查 + 优先级 P0-P4
# 2026-03-22 Λ

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log()  { echo "[$(date +%H:%M:%S)] $*"; }
warn() { echo "[$(date +%H:%M:%S)] ⚠ $*"; }
fail() { echo "[$(date +%H:%M:%S)] ✗ FAIL: $*"; exit 1; }

ACTION="${1:-check}"
GITHUB_TOKEN="${GITHUB_TOKEN:-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}"
XUZHI_REPO="summer-zhou/Xuzhi_genesis"
WORKSPACE_REPO="summer-zhou/xuzhi_workspace"

# ─── P0: Gateway 在线检查 ───────────────────────────────────────
check_gateway() {
    log "[P0] Gateway HTTP check..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:18789/health 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        log "[P0] ✓ Gateway 在线"
        return 0
    else
        fail "[P0] Gateway 无响应 (HTTP $HTTP_CODE)"
    fi
}

# ─── P1: Cron 状态检查 ──────────────────────────────────────────
check_crons() {
    log "[P1] Cron jobs 检查..."
    CRON_STATUS=$(openclaw cron list 2>/dev/null | grep -c "enabled.*true" || echo "0")
    DISABLED=$(openclaw cron list 2>/dev/null | grep -c '"enabled": false' || echo "0")
    log "[P1] 启用: $CRON_STATUS, 禁用: $DISABLED"
    if [ "$DISABLED" -gt 0 ]; then
        warn "[P1] $DISABLED 个 cron 被禁用，尝试恢复..."
        openclaw cron list 2>/dev/null | grep -B2 '"enabled": false' | \
            grep -oE '"id": "[^"]+"' | grep -oE '[^"]+$' | while read -r id; do
            log "[P1] 启用 cron: $id"
            openclaw cron update "$id" --enabled true 2>/dev/null || warn "[P1] 无法启用 $id"
        done
    fi
}

# ─── P2: Git Sync 检查 ──────────────────────────────────────────
check_git_sync() {
    log "[P2] Git sync 检查..."
    for repo_dir in ~/xuzhi_genesis ~/.openclaw/workspace; do
        [ -d "$repo_dir/.git" ] || continue
        cd "$repo_dir"
        # 检查是否有未 push 的 commits
        PUSH_PENDING=$(git --no-pager log origin/HEAD..HEAD --oneline 2>/dev/null | wc -l || echo "0")
        # 检查 remote 是否可达
        git remote get-url origin --push &>/dev/null || { warn "[P2] $repo_dir remote 不可达"; continue; }
        if [ "$PUSH_PENDING" -gt 0 ]; then
            warn "[P2] $repo_dir 有 $PUSH_PENDING commits 未 push"
            if [ "$repo_dir" = "~/xuzhi_genesis" ]; then
                log "[P2] 自动 push xuzhi_genesis..."
                git push origin master 2>&1 | tail -2 || warn "[P2] push 失败"
            fi
        fi
    done
    log "[P2] ✓ Git sync 正常"
}

# ─── P3: Harness Tests ─────────────────────────────────────────
check_harness() {
    log "[P3] Harness tests..."
    if ! command -v pytest &>/dev/null; then
        log "[P3] ⊘ pytest 未安装，跳过"
        return 0
    fi
    cd ~/xuzhi_genesis/centers/engineering/harness
    RESULT=$(python3 -m pytest tests/ -q --tb=line 2>&1 | tail -3)
    if echo "$RESULT" | grep -qE "passed|error"; then
        log "[P3] ✓ $RESULT"
    else
        warn "[P3] 测试输出异常: $RESULT"
    fi
}

# ─── P4: 知识库完整性 ───────────────────────────────────────────
check_knowledge() {
    log "[P4] 知识库完整性..."
    DB=~/xuzhi_genesis/centers/intelligence/knowledge/knowledge.db
    if [ ! -f "$DB" ]; then
        warn "[P4] knowledge.db 不存在"
        return 0
    fi
    ENTITIES=$(python3 -c "import sqlite3; c=sqlite3.connect('$DB').cursor(); c.execute('SELECT COUNT(*) FROM entities'); print(c.fetchone()[0])" 2>/dev/null || echo "0")
    RELATIONS=$(python3 -c "import sqlite3; c=sqlite3.connect('$DB').cursor(); c.execute('SELECT COUNT(*) FROM relations'); print(c.fetchone()[0])" 2>/dev/null || echo "0")
    INTEGRITY=$(python3 -c "import sqlite3; print(sqlite3.connect('$DB').execute('PRAGMA integrity_check').fetchone()[0])" 2>/dev/null || echo "unknown")
    log "[P4] entities=$ENTITIES relations=$RELATIONS integrity=$INTEGRITY"
    if [ "$ENTITIES" -lt 100 ]; then
        warn "[P4] entities 低于阈值 ($ENTITIES < 100)"
    fi
}

# ─── P4: CI Status 检查 ─────────────────────────────────────────
check_ci_status() {
    log "[P4] GitHub Actions CI status..."
    CI_RUNS=$(curl -s "https://api.github.com/repos/${XUZHI_REPO}/actions/runs?per_page=3" \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" 2>/dev/null)
    if [ -n "$CI_RUNS" ]; then
        python3 -c "
import sys, json
try:
    runs = json.loads('$CI_RUNS').get('workflow_runs', [])
    for r in runs[:2]:
        status = r.get('conclusion', r.get('status'))
        name = r.get('name', '?')[:40]
        print(f'  [{status}] {name}')
except: pass
" 2>/dev/null || log "[P4] CI runs: 无法解析响应"
    else
        log "[P4] ⊘ CI status 检查失败 (rate limit 或网络)"
    fi
}

# ─── P5: MaaS 配额检查 ──────────────────────────────────────────
check_quota() {
    log "[P5] MaaS API 配额..."
    QUOTA_RESP=$(curl -s "https://cloud.infini-ai.com/maas/coding/usage" \
        -H "Authorization: Bearer $GITHUB_TOKEN" 2>/dev/null)
    if echo "$QUOTA_RESP" | grep -qE "used|limit|remaining"; then
        python3 -c "
import sys, json
try:
    d = json.loads('$QUOTA_RESP')
    used = d.get('used', 0); limit = d.get('limit', 0)
    pct = used/limit*100 if limit else 0
    print(f'  used={used} limit={limit} ({pct:.0f}%)')
except: print('  解析失败')
" 2>/dev/null
    else
        log "[P5] ⊘ 配额 API 不可达"
    fi
}

# ─── Fix 模式 ───────────────────────────────────────────────────
fix_all() {
    log "=== FIX 模式 ==="
    check_gateway || exit 1
    check_crons
    check_git_sync
    log "=== FIX 完成 ==="
}

# ─── 主入口 ─────────────────────────────────────────────────────
main() {
    case "$ACTION" in
        check)
            check_gateway
            check_crons
            check_git_sync
            check_harness
            check_knowledge
            check_ci_status
            check_quota
            log "=== 健康检查完成 ==="
            ;;
        fix)
            fix_all
            ;;
        *)
            echo "用法: $0 {check|fix}"
            exit 1
            ;;
    esac
}

main
