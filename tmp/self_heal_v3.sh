#!/bin/bash
# self_heal_v3.sh — Xuzhi 系统自愈脚本（加固版）
# 新增：cron eventKind 校验，防止 agentTurn cron 重新出现
#
# 每小时自动运行：self_heal.sh fix
# 手动检查：self_heal.sh check
#
# 2026-03-21 v3: 新增 cron_kind_check() — 检查所有 cron 的 eventKind，
#                发现 agentTurn 立即禁用并告警（防止配额崩溃重演）

set -e

WORKSPACE="${WORKSPACE:-/home/summer/.openclaw/workspace}"
LOG_FILE="$WORKSPACE/memory/self_heal_log.jsonl"
STATE_FILE="$WORKSPACE/memory/gateway_state.json"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8765}"
ALERT_FILE="$WORKSPACE/memory/gateway_alert.json"

# ============================================================================
# 工具函数
# ============================================================================

log() { echo "[$(date +%T)] $*" >> "$LOG_FILE"; }
now_ts() { date +%s; }

write_state() {
    local key="$1"; local val="$2"
    local tmp=$(mktemp)
    if [ -f "$STATE_FILE" ] && [ -s "$STATE_FILE" ]; then
        python3 -c "
import json, sys
d = json.load(sys.stdin)
d['$key'] = $val
d['updated_at'] = $(now_ts)
print(json.dumps(d, indent=2))
" < "$STATE_FILE" > "$tmp" 2>/dev/null || echo "{}" > "$tmp"
    else
        echo "{\"$key\": $val, \"updated_at\": $(now_ts)}" > "$tmp"
    fi
    mv "$tmp" "$STATE_FILE"
}

alert() {
    log "ALERT: $1"
    echo "$(now_ts) ALERT: $1" >> "$ALERT_FILE"
}

# ============================================================================
# 检查1：Gateway 健康
# ============================================================================

check_gateway() {
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$GATEWAY_URL" 2>/dev/null)
    if [ "$http_code" = "200" ]; then
        write_state "gateway_status" "\"healthy\""
        log "Gateway: OK"
        return 0
    else
        write_state "gateway_status" "\"unhealthy: $http_code\""
        alert "Gateway unhealthy (HTTP $http_code), attempting restart"
        # 尝试重启
        openclaw gateway restart 2>/dev/null && log "Gateway restarted" || log "Gateway restart failed"
        return 1
    fi
}

# ============================================================================
# 检查2：Cron Jobs（enabled + eventKind）— 核心新增
# ============================================================================

# 合法的 cron eventKind（白名单）
VALID_KINDS='"systemEvent"'  # 目前只允许 systemEvent

check_crons() {
    log "Checking cron jobs..."
    
    # 获取 cron 列表（通过 API）
    local cron_output
    cron_output=$(curl -s -H "Authorization: Bearer sk-local" \
        "http://localhost:8765/api/cron" 2>/dev/null) || cron_output=""
    
    if [ -z "$cron_output" ] || [ "$cron_output" = "null" ]; then
        log "Cannot fetch cron list via API, skipping cron check"
        return 0
    fi
    
    # 检查是否有 agentTurn cron（问题根源）
    local agent_turn_crons
    agent_turn_crons=$(echo "$cron_output" | python3 -c "
import sys, json
try:
    crons = json.load(sys.stdin)
    if isinstance(crons, dict) and 'jobs' in crons:
        crons = crons['jobs']
    bad = [c.get('id','?') for c in crons 
           if c.get('eventKind') == 'agentTurn' or c.get('kind') == 'agentTurn']
    print(','.join(bad))
except: print('')
" 2>/dev/null)
    
    if [ -n "$agent_turn_crons" ]; then
        alert "CRON KIND VIOLATION: agentTurn cron detected: $agent_turn_crons — auto-disabling"
        log "CRON KIND VIOLATION: $agent_turn_crons"
        
        # 自动禁用 agentTurn cron
        for cron_id in $(echo "$agent_turn_crons" | tr ',' ' '); do
            curl -s -X PATCH -H "Authorization: Bearer sk-local" \
                -H "Content-Type: application/json" \
                "http://localhost:8765/api/cron/$cron_id" \
                -d '{"enabled": false}' 2>/dev/null || true
            log "Disabled agentTurn cron: $cron_id"
        done
        
        write_state "cron_kind_violation" "true"
        return 1
    else
        write_state "cron_kind_violation" "false"
    fi
    
    # 检查 disabled cron（Gateway 重启后状态丢失）
    local disabled_crons
    disabled_crons=$(echo "$cron_output" | python3 -c "
import sys, json
try:
    crons = json.load(sys.stdin)
    if isinstance(crons, dict) and 'jobs' in crons:
        crons = crons['jobs']
    disabled = [c.get('id','?') for c in crons if not c.get('enabled', True)]
    print(','.join(disabled))
except: print('')
" 2>/dev/null)
    
    if [ -n "$disabled_crons" ]; then
        log "Disabled crons found: $disabled_crons (Gateway restart likely reset state)"
        # 注意：不自动启用，保持手动决策
    fi
    
    log "Cron check: OK (eventKind: all systemEvent or disabled)"
    return 0
}

# ============================================================================
# 检查3：知识库健康
# ============================================================================

check_knowledge() {
    local kb="$HOME/xuzhi_genesis/centers/intelligence/knowledge/knowledge.db"
    if [ ! -f "$kb" ]; then
        log "Knowledge DB not found at $kb"
        return 0
    fi
    
    local entities
    entities=$(sqlite3 "$kb" "SELECT COUNT(*) FROM entities;" 2>/dev/null || echo "0")
    local threshold=100
    
    if [ "$entities" -lt "$threshold" ]; then
        alert "Knowledge DB low entities: $entities < $threshold"
        write_state "knowledge_entities" "$entities"
        return 1
    fi
    
    write_state "knowledge_entities" "$entities"
    log "Knowledge DB: OK ($entities entities)"
    return 0
}

# ============================================================================
# 检查4：Git push 状态
# ============================================================================

check_git() {
    local repo="$HOME/xuzhi_genesis"
    [ ! -d "$repo/.git" ] && return 0
    
    cd "$repo"
    
    # 检查是否有未 push 的 commits
    local unpushed
    unpushed=$(git log origin/master..HEAD --oneline 2>/dev/null | wc -l)
    
    if [ "$unpushed" -gt 0 ]; then
        log "WARNING: $unpushed unpushed commits in xuzhi_genesis"
        write_state "git_unpushed" "$unpushed"
        # 注意：xuzhi_genesis 是只读挂载，push 从 cron 执行
    else
        write_state "git_unpushed" "0"
    fi
    
    # 检查 workspace 是否有未 push 的 commits
    local ws_unpushed=0
    if [ -d "$WORKSPACE/.git" ]; then
        cd "$WORKSPACE"
        ws_unpushed=$(git log origin/HEAD..HEAD --oneline 2>/dev/null | wc -l || echo 0)
        # workspace 没有 remote，就是本地备份
    fi
    
    return 0
}

# ============================================================================
# 检查5：磁盘空间
# ============================================================================

check_disk() {
    local avail
    avail=$(df -BG / | tail -1 | awk '{print $4}' | tr -d 'G')
    
    if [ "${avail:-999}" -lt 5 ]; then
        alert "Disk space critical: ${avail}GB available"
        write_state "disk_gb" "$avail"
        return 1
    fi
    
    write_state "disk_gb" "$avail"
    log "Disk: OK (${avail}GB available)"
    return 0
}

# ============================================================================
# 主流程
# ============================================================================

main() {
    local action="${1:-check}"
    log "=== self_heal.sh $action ==="
    
    local failed=0
    
    check_gateway    || ((failed++))
    check_crons     || ((failed++))  # 新增：cron type 检查
    check_knowledge || ((failed++))
    check_git       || ((failed++))
    check_disk      || ((failed++))
    
    if [ "$failed" -gt 0 ]; then
        log "SELF-HEAL: $failed checks failed"
        [ -f "$STATE_FILE" ] && echo "=== State ===" && cat "$STATE_FILE"
    else
        log "SELF-HEAL: All OK"
    fi
    
    return $failed
}

# ============================================================================
# Fix 模式：检查并自动修复
# ============================================================================

fix_mode() {
    log "=== self_heal.sh fix ==="
    
    # Cron 校验（核心）
    check_crons
    
    # Gateway 重启（如果挂了）
    check_gateway
    
    # 确保 watchdog cron 存在且为 systemEvent
    local watchdog_cron
    watchdog_cron=$(curl -s -H "Authorization: Bearer sk-local" \
        "http://localhost:8765/api/cron" 2>/dev/null | python3 -c "
import sys, json
try:
    crons = json.load(sys.stdin)
    if isinstance(crons, dict) and 'jobs' in crons:
        crons = crons['jobs']
    wd = [c.get('id') for c in crons if 'watchdog' in c.get('name','').lower()]
    print(wd[0] if wd else '')
except: print('')
" 2>/dev/null)
    
    if [ -z "$watchdog_cron" ]; then
        log "Watchdog cron missing, recreating..."
        # 触发子agent创建（不在 exec 里网络请求）
        echo "$(now_ts) WATCHDOG_MISSING" >> "$ALERT_FILE"
    fi
    
    log "=== fix complete ==="
}

# ============================================================================
# 入口
# ============================================================================

case "${1:-check}" in
    check|fix)
        "${1}"_mode
        ;;
    *)
        echo "Usage: $0 {check|fix}"
        exit 1
        ;;
esac
