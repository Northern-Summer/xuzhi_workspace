#!/bin/bash
# self_heal.sh — 系统健康检查与自愈（无队列版）
# 检测到问题 → 直接生成修复任务文件 → main session 检查并执行
set -euo pipefail

HOME="${HOME:-/home/summer}"
QUEUE="$HOME/.xuzhi_memory/watchdog_command_queue.json"  # 保留文件但简化
CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"
TASKS="$HOME/.openclaw/tasks/tasks.json"
SESSIONS="$HOME/.openclaw/agents/main/sessions/sessions.json"
ABORTED_LIST="$HOME/.xuzhi_memory/aborted_detected.txt"
PENDING_CMDS="$HOME/.xuzhi_memory/.heal_pending.txt"
LOG="$HOME/.xuzhi_memory/task_center/self_heal.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
mkdir -p "$(dirname "$LOG")"

# ── 健康检查 ────────────────────────────────────────
check_gateway() {
    if curl -s --connect-timeout 3 http://localhost:18789/health | grep -q '"ok":true'; then
        log "Gateway: ✅"
        return 0
    else
        log "Gateway: ❌"
        return 1
    fi
}

# ── 检测超时 agent sessions ───────────────────────────
# 数据源：sessions.json（dict格式，按key索引）
check_stale_agents() {
    [[ ! -f "$SESSIONS" ]] && return 0
    
    python3 -c "
import json
from datetime import datetime, timezone

with open('$SESSIONS') as f:
    data = json.load(f)

NOW = datetime.now(timezone.utc)
THREE_HRS = 3 * 3600

stale = []
for key, s in data.items():
    if ':main' not in key or 'cron:' in key or 'subagent:' in key:
        continue
    updated = s.get('updatedAt', 0)
    if not updated:
        continue
    age = (NOW - datetime.fromtimestamp(updated/1000, tz=timezone.utc)).total_seconds()
    if age > THREE_HRS:
        stale.append((key, round(age/3600, 1)))

if stale:
    print(f'STALE:{len(stale)}')
    for k, h in stale:
        print(f'{k}|{h}h')
else:
    print('OK')
" > "$ABORTED_LIST" 2>/dev/null
    
    local result
    result=$(grep "^STALE\|^OK" "$ABORTED_LIST" | head -1)
    
    if [[ "$result" == "OK" ]]; then
        log "无超时 agent（<3h）"
    else
        local count
        count=$(echo "$result" | cut -d: -f2)
        log "检测到 $count 个超时 agent"
        grep -v "^STALE\|^OK" "$ABORTED_LIST" | while read -r line; do
            log "  → $line"
        done
        # 写入 pending 命令（main session 检查并执行 sessions_send）
        echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ) 修复命令" >> "$PENDING_CMDS"
        grep -v "^STALE\|^OK" "$ABORTED_LIST" | while read -r line; do
            local key age
            key=$(echo "$line" | cut -d'|' -f1)
            age=$(echo "$line" | cut -d'|' -f2)
            echo "sessions_send|$key|系统检测到你${age}小时未活跃，请回复确认存活|$age" >> "$PENDING_CMDS"
            log "  已写入修复命令: $key"
        done
    fi
}

# ── 清理超时任务 ────────────────────────────────────
cleanup_stale_tasks() {
    [[ ! -f "$TASKS" ]] && return
    python3 -c "
import json, time
d = json.load(open('$TASKS'))
tasks = d if isinstance(d, list) else d.get('tasks', [])
now_ts = time.time()
stale = [t.get('id') for t in tasks if t.get('status')=='进行' and t.get('created_at',0) and (now_ts - t.get('created_at',0)) > 7200]
for t in tasks:
    if t.get('id') in stale:
        t['status'] = '放弃'
        t['completion_report'] = '超时(>2h)，heal自动清理'
if stale:
    print('Stale:', stale)
    json.dump(d, open('$TASKS', 'w'), ensure_ascii=False)
" 2>/dev/null
}

# ── 主流程 ──────────────────────────────────────────
main() {
    log "=== Heal 检查 $(date '+%H:%M:%S') ==="
    check_gateway
    check_stale_agents
    cleanup_stale_tasks
    log "=== 完成 ==="
}

main "$@"
