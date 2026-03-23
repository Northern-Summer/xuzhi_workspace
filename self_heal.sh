#!/bin/bash
# self_heal.sh — 系统健康检查与自愈
# 2026-03-24 重写：使用 sessions.json（dict格式）做 aborted 检测
set -euo pipefail

HOME="${HOME:-/home/summer}"
AUTH_FILE="$HOME/.openclaw/identity/device-auth.json"
QUEUE="$HOME/.xuzhi_memory/watchdog_command_queue.json"
CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"
TASKS="$HOME/.openclaw/tasks/tasks.json"
SESSIONS="$HOME/.openclaw/agents/main/sessions/sessions.json"
ABORTED_LIST="$HOME/.xuzhi_memory/aborted_detected.txt"
LOG="$HOME/.xuzhi_memory/task_center/self_heal.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [heal] $*" >> "$LOG"; }
mkdir -p "$(dirname "$LOG")"

# ── Gateway 健康 ─────────────────────────────────────
check_gateway() {
    local h
    h=$(curl -s --connect-timeout 3 http://localhost:18789/health 2>/dev/null)
    if echo "$h" | grep -q '"ok":true'; then
        log "Gateway: ✅"
        return 0
    else
        log "Gateway: ❌ $h"
        return 1
    fi
}

# ── 检测 aborted sessions ─────────────────────────────
# 数据源：sessions.json（main agent的sessions）
# 注意：跨agent的aborted需要 isolated cron job 调用 sessions_list 检测
check_aborted_from_file() {
    if [[ ! -f "$SESSIONS" ]]; then
        log "sessions.json 不存在"
        return 0
    fi
    
    # 写入当前检测时间
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ABORTED_LIST"
    
    # 检测超时未活跃的 agent main sessions（>3小时无更新）
    python3 -c "
import json
from datetime import datetime, timezone
from pathlib import Path

sessions_file = Path('$SESSIONS')
if not sessions_file.exists():
    print('no_sessions_file')
    exit()

with open(sessions_file) as f:
    data = json.load(f)

NOW = datetime.now(timezone.utc)
THREE_HOURS = 3 * 3600

# 只检查 agent main sessions（非 cron/subagent）
aborted = []
for key, s in data.items():
    if ':main' not in key or 'cron:' in key or 'subagent:' in key:
        continue
    
    updated = s.get('updatedAt', 0)
    if not updated:
        continue
    
    age_seconds = (NOW - datetime.fromtimestamp(updated/1000, tz=timezone.utc)).total_seconds()
    
    if age_seconds > THREE_HOURS:
        aborted.append((key, round(age_seconds/3600, 1)))

print(f'ABORTED:{len(aborted)}')
for k, h in aborted:
    print(f'{k}|{h}h')
" >> "$ABORTED_LIST"
    
    local count
    count=$(grep "^ABORTED:" "$ABORTED_LIST" | cut -d: -f2)
    
    if [[ -n "$count" && "$count" != "0" ]]; then
        log "检测到 $count 个超时未活跃 agent sessions"
        grep -v "^ABORTED:" "$ABORTED_LIST" | while read -r line; do
            log "  $line"
            
            # 写入修复命令
            local key
            key=$(echo "$line" | cut -d'|' -f1)
            if [[ -n "$key" ]]; then
                python3 -c "
import json
queue = []
if [[ -f '$QUEUE' ]]; then
    try: queue = json.load(open('$QUEUE')).get('commands', [])
    except: pass
fi
if not any(c.get('session_key') == '$key' for c in queue):
    queue.append({'cmd': 'sessions_send', 'session_key': '$key', 'msg': '【WD修复】检测到你超过3小时未活跃。请回复任意内容确认存活。', 'note': 'stale_recovery'})
    json.dump({'commands': queue}, open('$QUEUE', 'w'))
"
            fi
        done
    else
        log "无超时 agent sessions（<3小时未活跃）"
    fi
}

# ── 清理 stale 任务 ─────────────────────────────────
cleanup_stale_tasks() {
    if [[ ! -f "$TASKS" ]]; then return; fi
    python3 -c "
import json, time
d = json.load(open('$TASKS'))
tasks = d if isinstance(d, list) else d.get('tasks', [])
now_ts = time.time()
stale = []
for t in tasks:
    if t.get('status') == '进行':
        created = t.get('created_at', 0)
        if created and (now_ts - created) > 7200:
            stale.append(t.get('id'))
            t['status'] = '放弃'
            t['completion_report'] = '超时(>2h)，Λ自动清理'
if stale:
    print('Stale:', stale)
    json.dump(d, open('$TASKS', 'w'), ensure_ascii=False)
" 2>/dev/null
}

# ── 修复断点卡死 ────────────────────────────────────
fix_checkpoint() {
    if [[ ! -f "$CHECKPOINT" ]]; then return; fi
    
    python3 -c "
import json
from datetime import datetime, timezone
d = json.load(open('$CHECKPOINT'))
ts = d.get('ts','')
if not ts:
    print('no_ts')
    exit()
t = datetime.fromisoformat(ts.replace('Z','+00:00'))
age = (datetime.now(timezone.utc) - t).total_seconds()
print(f'checkpoint_age:{int(age)}')
if age > 3600:
    print('STALE')
" > /tmp/checkpoint_age.txt 2>/dev/null
    
    local result
    result=$(cat /tmp/checkpoint_age.txt)
    
    if echo "$result" | grep -q "STALE"; then
        log "断点卡死，重置idle"
        python3 -c "import json; json.dump({'phase':'idle','idx':0,'pending_done':'','ts':''}, open('$CHECKPOINT', 'w'))"
    fi
}

# ── 主流程 ──────────────────────────────────────────
main() {
    log "=== 健康检查 ==="
    check_gateway
    check_aborted_from_file
    fix_checkpoint
    cleanup_stale_tasks
    log "=== 完成 ==="
}

main "$@"
