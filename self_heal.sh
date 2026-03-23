#!/bin/bash
# self_heal.sh — 系统健康检查与自愈（bash版，无LLM调用）
# 被 self_sustaining_loop.sh 的 check_health() 调用
# 2026-03-24 红蓝队修复：修正operator token路径，增强aborted检测+自愈

set -euo pipefail

HOME="${HOME:-/home/summer}"
AUTH_FILE="$HOME/.openclaw/identity/device-auth.json"
QUEUE="$HOME/.xuzhi_memory/watchdog_command_queue.json"
CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"
TASKS="$HOME/.openclaw/tasks/tasks.json"
LOG="$HOME/.xuzhi_memory/task_center/self_heal.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [heal] $*" >> "$LOG"; }

get_token() {
    python3 -c "
import json
d=json.load(open('$AUTH_FILE'))
print(d.get('tokens',{}).get('operator',{}).get('token','') or '')
" 2>/dev/null
}

gateway_health() {
    local h
    h=$(curl -s --connect-timeout 3 http://localhost:18789/health 2>/dev/null)
    if echo "$h" | grep -q '"ok":true'; then
        echo "ok"
        return 0
    else
        echo "fail"
        return 1
    fi
}

# ── 检测 aborted sessions ───────────────────────────────
check_aborted() {
    local token="$1"
    local out
    out=$(curl -s --connect-timeout 5 \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        "http://localhost:18789/sessions" 2>/dev/null)
    
    if echo "$out" | grep -q "<html"; then
        log "AUTH FAIL: HTML response, token invalid"
        return 0
    fi
    
    local result
    result=$(echo "$out" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    sessions = d if isinstance(d, list) else d.get('sessions', d.get('data', []))
    aborted = [(s['key'], s.get('displayName','')) for s in sessions if s.get('abortedLastRun')]
    print(len(aborted))
    for k, dn in aborted: print(k)
except Exception as e:
    print('ERR:', e)
" 2>/dev/null) || result="0"
    
    local count
    count=$(echo "$result" | head -1)
    
    if [[ "$count" =~ ^[0-9]+$ ]] && (( count > 0 )); then
        log "检测到 $count 个 aborted sessions"
        echo "$result" | tail -n +2 | while read -r key; do
            [[ -z "$key" ]] && continue
            log "生成修复命令: $key"
            python3 -c "
import json
queue = []
if [[ -f '$QUEUE' ]]; then
    try: queue = json.load(open('$QUEUE')).get('commands', [])
    except: pass
fi
# 检查是否已在队列
if not any(c.get('session_key') == '$key' for c in queue):
    queue.append({'cmd': 'sessions_send', 'session_key': '$key', 'msg': '【WD修复】检测到你上轮异常中止。请回复任意内容确认存活。', 'note': 'aborted_recovery'})
json.dump({'commands': queue}, open('$QUEUE', 'w'))
"
        done
    else
        log "无 aborted sessions"
    fi
}

# ── 修复断点卡死（>1小时未动） ──────────────────────
fix_stuck_checkpoint() {
    if [[ -f "$CHECKPOINT" ]]; then
        local ts age
        ts=$(python3 -c "import json; d=json.load(open('$CHECKPOINT')); print(d.get('ts',''))" 2>/dev/null)
        if [[ -n "$ts" ]]; then
            age=$(python3 -c "
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
t = datetime.fromisoformat('$ts'.replace('Z','+00:00'))
print(int((now - t).total_seconds()))
" 2>/dev/null) || age=0
            if (( age > 3600 )); then
                log "断点卡死(${age}s)，重置idle"
                python3 -c "import json; json.dump({'phase':'idle','idx':0,'pending_done':'','ts':''}, open('$CHECKPOINT', 'w'))"
            fi
        fi
    fi
}

# ── 清理 tasks.json 中超时任务（>2小时仍在进行） ──────
cleanup_stale_tasks() {
    if [[ ! -f "$TASKS" ]]; then return; fi
    python3 -c "
import json, time
from datetime import datetime, timezone
d = json.load(open('$TASKS'))
tasks = d if isinstance(d, list) else d.get('tasks', [])
now_ts = time.time()
stale = []
for t in tasks:
    if t.get('status') == '进行':
        created = t.get('created_at', 0)
        if created and (now_ts - created) > 7200:  # 2h
            stale.append(t.get('id'))
            t['status'] = '放弃'
            t['completion_report'] = '超时未完成（>2h），Λ系统自动清理'
if stale:
    print('Stale tasks cleaned:', stale)
    json.dump(d, open('$TASKS', 'w'), ensure_ascii=False)
" 2>/dev/null
}

# ── 主流程 ───────────────────────────────────────────
main() {
    log "=== 健康检查开始 ==="
    
    local gh
    gh=$(gateway_health)
    [[ "$gh" == "ok" ]] && log "Gateway: ✅" || log "Gateway: ❌"
    
    local tok
    tok=$(get_token)
    if [[ -n "$tok" && ${#tok} -gt 20 ]]; then
        check_aborted "$tok"
    else
        log "Token无效(length=${#tok})，跳过aborted检测"
    fi
    
    fix_stuck_checkpoint
    cleanup_stale_tasks
    
    log "=== 检查结束 ==="
}

main "$@"
