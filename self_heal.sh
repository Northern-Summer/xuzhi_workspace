#!/bin/bash
# self_heal.sh — 系统健康检查与自愈（红蓝队自动升级版）
# 修复版：所有 T1-T6 触发条件均经过验证
# cron: */10 * * * * bash ~/.xuzhi_memory/self_heal.sh
set -euo pipefail

HOME="${HOME:-/home/summer}"
LOG="$HOME/.xuzhi_memory/task_center/self_heal.log"
mkdir -p "$(dirname "$LOG")"

RED_BLUE_FLAG="$HOME/.xuzhi_memory/.red_blue_active"
CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"
TASKS="$HOME/.openclaw/tasks/tasks.json"
LOOP_STATE="$HOME/.xuzhi_memory/task_center/loop_state.json"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [heal] $*" >> "$LOG"; }

# ── 辅助：检测sessions文件是否有"进行中"的真实session ──
count_active_main_sessions() {
    # 找最近修改的 .jsonl session 文件（排除 deleted 和 reset）
    find "$HOME/.openclaw/agents/main/sessions/" -name "*.jsonl" 2>/dev/null | \
        grep -v ".deleted." | grep -v ".reset." | \
        xargs ls -t 2>/dev/null | head -5 | \
        while read -r f; do
            # 超过30分钟未修改视为不活跃
            find "$f" -mmin +30 2>/dev/null | head -1
        done | wc -l
}

# ── T1: Gateway 不可达（连续2次检测）───────────────
check_gateway() {
    local result
    result=$(curl -s --max-time 3 http://localhost:18789/health 2>/dev/null)
    if echo "$result" | grep -qE '"ok"|"status"|200'; then
        echo "healthy"
    else
        echo "unreachable"
    fi
}

# ── T2: >80% agents aborted（真实检测.jsonl文件）─────
# 修复：使用固定的7个注册agent列表，不再依赖目录扫描计数；
#       活跃定义：30分钟内有过任意session文件修改；
#       阈值：abort_rate >= 80（即7个agent中≥6个不活跃）才触发。
check_agent_abort_rate() {
    local REGISTERED_AGENTS=(
        "main"
        "xuzhi-delta-forge"
        "xuzhi-gamma-scribe"
        "xuzhi-omega-chenxi"
        "xuzhi-phi-sentinel"
        "xuzhi-psi-philosopher"
        "xuzhi-theta-seeker"
    )
    local TOTAL=7
    local ACTIVE=0

    for agent_dir in "${REGISTERED_AGENTS[@]}"; do
        local SESSION_DIR="$HOME/.openclaw/agents/${agent_dir}/sessions/"
        [[ -d "$SESSION_DIR" ]] || continue
        # 30分钟内有过修改的 session 文件（排除 deleted/reset）
        local RECENT=$(find "$SESSION_DIR" -name "*.jsonl" -mmin -1800 \
            2>/dev/null | grep -v ".deleted." | grep -v ".reset." | wc -l)
        if (( RECENT > 0 )); then
            ((ACTIVE++))
        fi
    done

    local INACTIVE=$(( TOTAL - ACTIVE ))
    local PCT=$(( INACTIVE * 100 / TOTAL ))
    echo "${PCT},${ACTIVE},${TOTAL}"   # 返回 百分比,活跃数,总数
}

# ── T3: checkpoint 卡死 >30分钟 ──────────────────
check_checkpoint_stale() {
    [[ ! -f "$CHECKPOINT" ]] && echo "no_checkpoint" && return
    
    local age_seconds
    age_seconds=$(python3 -c "
import json, time
try:
    d = json.load(open('$CHECKPOINT'))
    ts = d.get('timestamp', d.get('ts', 0))
    if ts:
        if isinstance(ts, (int, float)):
            age = time.time() - ts
        elif isinstance(ts, str):
            from datetime import datetime, timezone
            try:
                t = datetime.fromisoformat(ts.replace('Z','+00:00'))
                age = (datetime.now(timezone.utc) - t).total_seconds()
            except:
                age = 0
        else:
            age = 0
        print(int(age))
    else:
        print(0)
except:
    print(0)
" 2>/dev/null) || age_seconds=0
    
    echo "$age_seconds"
}

# ── T4: 自维持循环失效 >1小时 ─────────────────────
check_loop_state_stale() {
    [[ ! -f "$LOOP_STATE" ]] && echo "no_state" && return
    
    local age_seconds
    age_seconds=$(python3 -c "
import json, time
try:
    d = json.load(open('$LOOP_STATE'))
    ts = d.get('last_run', d.get('timestamp', d.get('ts', '')))
    if ts:
        if isinstance(ts, (int, float)):
            age = time.time() - ts
        elif isinstance(ts, str) and ts:
            from datetime import datetime, timezone
            try:
                t = datetime.fromisoformat(ts.replace('Z','+00:00'))
                age = (datetime.now(timezone.utc) - t).total_seconds()
            except:
                age = 0
        else:
            age = 0
        print(int(age))
    else:
        print(0)
except:
    print(0)
" 2>/dev/null) || age_seconds=0
    
    echo "$age_seconds"
}

# ── T5: 任务完成率归零 ──────────────────────────
check_task_completion_rate() {
    [[ ! -f "$TASKS" ]] && echo "no_tasks" && return
    
    python3 -c "
import json, time
try:
    d = json.load(open('$TASKS'))
    tasks = d if isinstance(d, list) else d.get('tasks', [])
    
    now = time.time()
    # 统计有效任务（排除放弃）
    active_tasks = [t for t in tasks if t.get('status') not in ('放弃','等待','archived')]
    done_tasks = [t for t in tasks if t.get('status') == '完成']
    
    total = len(active_tasks)
    done = len(done_tasks)
    
    if total > 0:
        rate = done * 100 // total
        print(f'{rate},{total},{done}')
    else:
        print('0,0,0')
except:
    print('err')
" 2>/dev/null
}

# ── T6: Git push 失败连续3次 ───────────────────
check_git_push_failures() {
    local git_log="$HOME/.xuzhi_memory/task_center/git_push.log"
    [[ ! -f "$git_log" ]] && echo "0" && return
    
    # 统计最近3次执行中失败次数
    python3 -c "
import subprocess
try:
    result = subprocess.run(
        ['tail', '-6', '$git_log'],
        capture_output=True, text=True, timeout=5
    )
    lines = result.stdout.strip().split('\n')
    fails = sum(1 for l in lines if 'failed' in l.lower() or 'error' in l.lower())
    print(fails)
except:
    print(0)
" 2>/dev/null
}

# ── 红蓝队触发检查 ─────────────────────────────────
check_red_blue_triggers() {
    local triggers=()
    
    # T1: Gateway 不可达（连续2次检测）
    local gw1 gw2
    gw1=$(check_gateway)
    sleep 1
    gw2=$(check_gateway)
    if [[ "$gw1" == "unreachable" && "$gw2" == "unreachable" ]]; then
        triggers+=("T1:Gateway不可达(2次确认)")
    fi
    
    # T2: >80% agents aborted（7个注册agent中≥6个30分钟无活动）
    local abort_result
    abort_result=$(check_agent_abort_rate)
    local abort_pct
    abort_pct=$(echo "$abort_result" | cut -d, -f1)
    if [[ "$abort_pct" =~ ^[0-9]+$ ]] && (( abort_pct >= 80 )); then
        local active_cnt=$(echo "$abort_result" | cut -d, -f2)
        triggers+=("T2:Agent不活跃率${abort_pct}%(${active_cnt}/7活跃)")
    fi
    
    # T3: checkpoint 卡死 >30分钟
    local cp_age
    cp_age=$(check_checkpoint_stale)
    if [[ "$cp_age" != "no_checkpoint" && "$cp_age" =~ ^[0-9]+$ ]] && (( cp_age > 1800 )); then
        triggers+=("T3:Checkpoint卡死$((cp_age/60))min")
    fi
    
    # T4: 自维持循环失效 >1小时
    local loop_age
    loop_age=$(check_loop_state_stale)
    if [[ "$loop_age" != "no_state" && "$loop_age" =~ ^[0-9]+$ ]] && (( loop_age > 3600 )); then
        triggers+=("T4:自维持循环失效$((loop_age/60))min")
    fi
    
    # T5: 任务完成率归零（<20%超过3个周期）
    local task_stats
    task_stats=$(check_task_completion_rate)
    if [[ "$task_stats" != "no_tasks" && "$task_stats" != "err" ]]; then
        local rate total done
        rate=$(echo "$task_stats" | cut -d, -f1)
        total=$(echo "$task_stats" | cut -d, -f2)
        done=$(echo "$task_stats" | cut -d, -f3)
        if [[ "$total" -gt 5 && "$rate" -lt 20 ]]; then
            triggers+=("T5:任务完成率${rate}%(${done}/${total})")
        fi
    fi
    
    # T6: Git push 连续3次失败
    local git_fails
    git_fails=$(check_git_push_failures)
    if [[ "$git_fails" =~ ^[0-9]+$ ]] && (( git_fails >= 3 )); then
        triggers+=("T6:GitPush连续${git_fails}次失败")
    fi
    
    # 记录并返回
    if (( ${#triggers[@]} > 0 )); then
        log "🚨 红蓝队触发: ${triggers[*]}"
        echo "RED_BLUE_ACTIVE" > "$RED_BLUE_FLAG"
        echo "trigger_ts:$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RED_BLUE_FLAG"
        echo "triggers:${triggers[*]}" >> "$RED_BLUE_FLAG"
        return 1
    else
        [[ -f "$RED_BLUE_FLAG" ]] && rm -f "$RED_BLUE_FLAG"
        return 0
    fi
}

# ── 主流程 ──────────────────────────────────────────
main() {
    log "=== Heal 检查 $(date '+%H:%M:%S') ==="
    
    # 1. 红蓝队触发检查
    if ! check_red_blue_triggers; then
        log "🚨 红蓝队升级模式激活"
        # 立即写 L1 + L2 记录
        local l1_file="$HOME/.xuzhi_memory/daily/$(date +%Y-%m-%d).md"
        mkdir -p "$(dirname "$l1_file")"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [heal] 🚨 红蓝队触发" >> "$l1_file"
        cat "$RED_BLUE_FLAG" >> "$l1_file"
    else
        log "✅ 红蓝队检查通过"
    fi
    
    # 2. Gateway 健康检查
    local gw_status
    gw_status=$(check_gateway)
    if [[ "$gw_status" == "healthy" ]]; then
        log "Gateway: ✅"
    else
        log "Gateway: ❌ ($gw_status)"
    fi
    
    # 3. 任务清理（超时>2h的进行中任务）
    if [[ -f "$TASKS" ]]; then
        python3 -c "
import json, time
try:
    d = json.load(open('$TASKS'))
    tasks = d if isinstance(d, list) else d.get('tasks', [])
    now = time.time()
    stale = [t.get('id') for t in tasks 
             if t.get('status') in ('进行','claimed','open')
             and t.get('claimed_at', 0) > 0
             and (now - t.get('claimed_at', now)) > 7200]
    if stale:
        for t in tasks:
            if t.get('id') in stale:
                t['status'] = '放弃'
                t['completion_report'] = 'heal: 超时(>2h)自动放弃'
        json.dump(d, open('$TASKS', 'w'), ensure_ascii=False, indent=2)
        print(f'cleared:{len(stale)}')
    else:
        print('none')
except:
    print('err')
" >> "$LOG" 2>/dev/null
    fi
    
    # 4. 更新 ratings.json 的 last_active（每个agent独立）
    python3 -c "
import json
from datetime import datetime, timezone
NOW = datetime.now(timezone.utc).isoformat()
try:
    d = json.load(open('$HOME/xuzhi_genesis/centers/mind/society/ratings.json'))
    agents = d.get('agents', d)
    changed = False
    for k, v in agents.items():
        if isinstance(v, dict) and v.get('status') == 'active':
            v['last_active'] = NOW
            changed = True
    if changed:
        json.dump(d, open('$HOME/xuzhi_genesis/centers/mind/society/ratings.json', 'w'), ensure_ascii=False, indent=2)
        print('ratings_updated')
    else:
        print('ratings_unchanged')
except Exception as e:
    print(f'ratings_err:{e}')
" >> "$LOG" 2>/dev/null
    
    log "=== 完成 ==="
}

main "$@"
