#!/bin/bash
# self_heal.sh — 系统健康检查与自愈（bash版，无LLM调用）
# 被 self_sustaining_loop.sh 的 check_health() 调用
# 2026-03-24 修复：检测 aborted sessions 并写入修复队列

set -euo pipefail

HOME="${HOME:-/home/summer}"
TOKEN_FILE="$HOME/.openclaw/secrets.json"
QUEUE="$HOME/.xuzhi_memory/watchdog_command_queue.json"
CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"
LOG="$HOME/.xuzhi_memory/task_center/self_heal.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [heal] $*" >> "$LOG"; }

get_token() {
    python3 -c "
import json
d=json.load(open('$TOKEN_FILE'))
print(d.get('operator_token','') or d.get('token',''))
" 2>/dev/null
}

gateway_health() {
    local h
    h=$(curl -s --connect-timeout 3 http://localhost:18789/health 2>/dev/null)
    if echo "$h" | grep -q '"ok":true'; then
        echo "ok"
        return 0
    else
        echo "fail:$h"
        return 1
    fi
}

# ── 检测 aborted sessions ───────────────────────────────
check_aborted_sessions() {
    local token="$1"
    local output
    output=$(curl -s --connect-timeout 5 \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        "http://localhost:18789/api/sessions" 2>/dev/null)
    
    # 检查是否返回HTML（认证失败）
    if echo "$output" | grep -q "<html"; then
        log "认证失败，token可能无效"
        return 0
    fi
    
    # 检查 aborted sessions
    local aborted
    aborted=$(echo "$output" | python3 -c "
import json, sys
try:
    sessions = json.load(sys.stdin)
    if isinstance(sessions, dict):
        sessions = sessions.get('sessions', [])
    count = sum(1 for s in sessions if s.get('abortedLastRun', False))
    names = [s.get('displayName', s.get('key', '?')) for s in sessions if s.get('abortedLastRun', False)]
    print(count)
    for n in names: print(n)
except:
    print('0')
" 2>/dev/null) || aborted="0"
    
    local count
    count=$(echo "$aborted" | head -1)
    
    if (( count > 0 )); then
        log "检测到 $count 个 aborted sessions:"
        echo "$aborted" | tail -n +2 | while read -r name; do
            log "  - $name"
        done
        
        # 写入修复命令到队列
        echo "$aborted" | tail -n +2 | while read -r name; do
            # 提取 agent key
            local key
            key=$(echo "$name" | grep -oP 'agent:[^:]+:[^:]+' | head -1)
            if [[ -n "$key" ]]; then
                log "生成修复命令 for $key"
                # 追加到队列
                python3 -c "
import json
queue = []
if [[ -f '$QUEUE' ]]; then
    try: queue = json.load(open('$QUEUE'))
    except: pass
queue.append({'cmd': 'sessions_send', 'session_key': '$key', 'msg': '【WD修复】检测到你上轮任务异常中止。请回复任意内容确认存活。如果有未完成任务，请重新认领或标记为放弃。', 'note': 'aborted_recovery'})
json.dump({'commands': queue}, open('$QUEUE', 'w'))
"
            fi
        done
        return 1
    else
        log "无 aborted sessions"
        return 0
    fi
}

# ── 修复断点卡死 ─────────────────────────────────────
check_stuck_checkpoint() {
    if [[ -f "$CHECKPOINT" ]]; then
        local last ts age
        last=$(python3 -c "import json; d=json.load(open('$CHECKPOINT')); print(d.get('last_run',''))" 2>/dev/null)
        ts=$(python3 -c "import json; d=json.load(open('$CHECKPOINT')); print(d.get('ts',''))" 2>/dev/null)
        if [[ -n "$ts" ]]; then
            age=$(python3 -c "
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
t = datetime.fromisoformat('$ts'.replace('Z','+00:00'))
print(int((now - t).total_seconds()))
" 2>/dev/null) || age=0
            if (( age > 3600 )); then
                log "断点卡死（${age}s），重置为 idle"
                python3 -c "import json; json.dump({'phase':'idle','idx':0,'pending_done':''}, open('$CHECKPOINT', 'w'))"
            fi
        fi
    fi
}

# ── 主流程 ───────────────────────────────────────────
main() {
    log "=== 健康检查开始 ==="
    
    # 1. Gateway 健康
    local gh
    gh=$(gateway_health)
    if [[ "$gh" == "ok" ]]; then
        log "Gateway: ✅"
    else
        log "Gateway: ❌ $gh"
    fi
    
    # 2. 检测 aborted sessions
    local tok
    tok=$(get_token)
    if [[ -n "$tok" && ${#tok} -gt 20 ]]; then
        check_aborted_sessions "$tok"
    else
        log "Token 无效或缺失（长度: ${#tok}），跳过 aborted 检测"
    fi
    
    # 3. 修复断点
    check_stuck_checkpoint
    
    log "=== 健康检查结束 ==="
}

main "$@"
