#!/bin/bash
# self_heal.sh — 系统健康检查与自愈（红蓝队自动升级版）
# 检测到触发条件 → 自动进入红蓝队升级模式
set -euo pipefail

HOME="${HOME:-/home/summer}"
CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"
TASKS="$HOME/.openclaw/tasks/tasks.json"
SESSIONS="$HOME/.openclaw/agents/main/sessions/sessions.json"
PENDING="$HOME/.xuzhi_memory/.heal_pending.txt"
RED_BLUE_FLAG="$HOME/.xuzhi_memory/.red_blue_active"
LOG="$HOME/.xuzhi_memory/task_center/self_heal.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [heal] $*" >> "$LOG"; }
mkdir -p "$(dirname "$LOG")"

# ── 红蓝队升级触发检查 ─────────────────────────────
check_red_blue_triggers() {
    local triggers=()
    
    # T1: Gateway 不可达（连续2次）
    if ! curl -s --connect-timeout 3 http://localhost:18789/health 2>/dev/null | grep -q '"ok":true'; then
        triggers+=("T1:Gateway不可达")
    fi
    
    # T2: >80% agents aborted
    if [[ -f "$SESSIONS" ]]; then
        local total aborted
        total=$(python3 -c "
import json
with open('$SESSIONS') as f: data = json.load(f)
total = sum(1 for k,v in data.items() if ':main' in k and 'cron:' not in k and 'subagent:' not in k)
aborted = sum(1 for k,v in data.items() if ':main' in k and 'cron:' not in k and 'subagent:' not in k and v.get('abortedLastRun')
print(f'{total},{aborted}')
" 2>/dev/null)
        if [[ -n "$total" && "$total" != "0,0" ]]; then
            local t a pct
            t=$(echo "$total" | cut -d, -f1)
            a=$(echo "$total" | cut -d, -f2)
            pct=$(( a * 100 / t ))
            if (( pct >= 80 )); then
                triggers+=("T2:Agent淘汰率${pct}%")
            fi
        fi
    fi
    
    # T3: checkpoint 卡死 >30分钟
    if [[ -f "$CHECKPOINT" ]]; then
        local age
        age=$(python3 -c "
import json
from datetime import datetime, timezone
try:
    d = json.load(open('$CHECKPOINT'))
    ts = d.get('ts','')
    if ts:
        t = datetime.fromisoformat(ts.replace('Z','+00:00'))
        print(int((datetime.now(timezone.utc) - t).total_seconds()))
except: print(0)
" 2>/dev/null) || age=0
        if (( age > 1800 )); then
            triggers+=("T3:Checkpoint卡死${age}s")
        fi
    fi
    
    # T4: 自维持循环失效 >1小时（检查 loop_state）
    local loop_age=0
    if [[ -f "$HOME/.xuzhi_memory/task_center/loop_state.json" ]]; then
        loop_age=$(python3 -c "
import json
from datetime import datetime, timezone
try:
    d = json.load(open('$HOME/.xuzhi_memory/task_center/loop_state.json'))
    ts = d.get('last_run','')
    if ts:
        t = datetime.fromisoformat(ts.replace('Z','+00:00'))
        print(int((datetime.now(timezone.utc) - t).total_seconds()))
    else: print(0)
except: print(0)
" 2>/dev/null) || loop_age=0
        if (( loop_age > 3600 )); then
            triggers+=("T4:自维持循环失效${loop_age}s")
        fi
    fi
    
    # T5: 任务完成率归零
    if [[ -f "$TASKS" ]]; then
        python3 -c "
import json
try:
    d = json.load(open('$TASKS'))
    tasks = d if isinstance(d, list) else d.get('tasks', [])
    total = len([t for t in tasks if t.get('status') not in ('放弃','等待')])
    done = len([t for t in tasks if t.get('status') == '完成'])
    print(f'{total},{done}')
except: print('0,0')
" > /tmp/tasks_stats.txt 2>/dev/null
        local ts
        ts=$(cat /tmp/tasks_stats.txt)
        if [[ -n "$ts" && "$ts" != "0,0" ]]; then
            local t d
            t=$(echo "$ts" | cut -d, -f1)
            d=$(echo "$ts" | cut -d, -f2)
            if (( t > 5 && d == 0 )); then
                triggers+=("T5:任务完成率归零")
            fi
        fi
    fi
    
    # 如有触发条件 → 进入红蓝队模式
    if (( ${#triggers[@]} > 0 )); then
        log "🚨 红蓝队升级触发！条件: ${triggers[*]}"
        echo "RED_BLUE_ACTIVE" > "$RED_BLUE_FLAG"
        echo "trigger_ts:$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RED_BLUE_FLAG"
        echo "triggers:${triggers[*]}" >> "$RED_BLUE_FLAG"
        log "红蓝队标志已写入: $RED_BLUE_FLAG"
        return 1  # 有问题
    else
        log "✅ 红蓝队检查通过（无触发条件）"
        # 清除标志（如果之前有）
        [[ -f "$RED_BLUE_FLAG" ]] && rm -f "$RED_BLUE_FLAG"
        return 0  # 正常
    fi
}

# ── Gateway 健康 ─────────────────────────────────────
check_gateway() {
    if curl -s --connect-timeout 3 http://localhost:18789/health 2>/dev/null | grep -q '"ok":true'; then
        log "Gateway: ✅"
        return 0
    else
        log "Gateway: ❌"
        return 1
    fi
}

# ── 检测超时 agent sessions ───────────────────────────
check_stale_agents() {
    [[ ! -f "$SESSIONS" ]] && return 0
    
    python3 -c "
import json
from datetime import datetime, timezone

with open('$SESSIONS') as f:
    data = json.load(f)

NOW = datetime.now(timezone.utc)
stale = []
for key, s in data.items():
    if ':main' not in key or 'cron:' in key or 'subagent:' in key:
        continue
    updated = s.get('updatedAt', 0)
    if not updated:
        continue
    age = (NOW - datetime.fromtimestamp(updated/1000, tz=timezone.utc)).total_seconds()
    if age > 10800:  # 3小时
        stale.append((key, round(age/3600, 1)))

if stale:
    print(f'STALE:{len(stale)}')
    for k, h in stale:
        print(f'{k}|{h}h')
else:
    print('OK')
" > "$HOME/.xuzhi_memory/aborted_detected.txt" 2>/dev/null
    
    local result
    result=$(grep "^STALE\|^OK" "$HOME/.xuzhi_memory/aborted_detected.txt" 2>/dev/null | head -1)
    
    if [[ "$result" == "OK" ]]; then
        log "无超时 agent（<3h）"
    else
        local count
        count=$(echo "$result" | cut -d: -f2)
        log "检测到 $count 个超时 agent"
        grep -v "^STALE\|^OK" "$HOME/.xuzhi_memory/aborted_detected.txt" 2>/dev/null | while read -r line; do
            log "  → $line"
            local key
            key=$(echo "$line" | cut -d'|' -f1)
            [[ -n "$key" ]] && echo "sessions_send|$key|系统检测到你超过3小时未活跃，请回复确认存活|" >> "$PENDING"
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
    check_red_blue_triggers || true  # 无论是否触发都继续其他检查
    check_gateway || true
    check_stale_agents
    cleanup_stale_tasks
    log "=== 完成 ==="
}

main "$@"
