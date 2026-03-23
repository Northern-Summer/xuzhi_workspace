#!/bin/bash
# self_sustaining_loop.sh — 跨 agent 自维持闭环（系统 cron，零 POST）
# cron: */15 * * * * bash ~/.xuzhi_memory/self_sustaining_loop.sh
# 2026-03-24 重构：解耦 watchdog，直接触发 agent，不依赖 sessions_send 队列

set -euo pipefail

HOME="${HOME:-/home/summer}"
LOG="$HOME/.xuzhi_memory/task_center/self_sustaining.log"
LOOP_STATE="$HOME/.xuzhi_memory/task_center/loop_state.json"
LOCK="$HOME/.xuzhi_memory/.self_sustaining.lock"
WD_CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"

ORDER=(Λ Φ Δ Θ Γ Ω Ψ)

log() { echo "$(date '+%H:%M:%S') $*" >> "$LOG"; }

# ── 锁防止并发 ─────────────────────────────────────────
acquire_lock() {
    if [[ -f "$LOCK" ]]; then
        local age
        age=$(python3 -c "import time; print(int(time.time()-$(stat -c %Y $LOCK 2>/dev/null || echo 0)))" 2>/dev/null)
        if (( age < 300 )); then
            log "锁存在($age秒)，退出"
            return 1
        fi
        log "锁超时($age秒)，覆盖"
    fi
    echo "$$" > "$LOCK"
    return 0
}

release_lock() { rm -f "$LOCK"; }

# ── 获取当前 agent ────────────────────────────────────
get_current() {
    [[ -f "$LOOP_STATE" ]] || return
    python3 -c "import json; d=json.load(open('$LOOP_STATE')); print(d.get('current','Λ'))" 2>/dev/null
}

# ── 推进到下一个 agent ────────────────────────────────
advance() {
    local cur="$1" found=0
    for ag in "${ORDER[@]}"; do
        [[ "$found" == 1 ]] && { echo "$ag"; return; }
        [[ "$ag" == "$cur" ]] && found=1
    done
    echo "Λ"
}

# ── 部门映射 ──────────────────────────────────────────
dept_of() {
    case "$1" in
        Λ|Φ|Δ) echo "engineering" ;;
        Θ|Γ)   echo "intelligence" ;;
        Ω)     echo "mind" ;;
        Ψ)     echo "philosophy" ;;
        *)     echo "general" ;;
    esac
}

# ── 生成任务（去重：检查 tasks.json 是否已有进行中同类任务）───
should_generate() {
    local dept="$1"
    local tasks_file="$HOME/.openclaw/tasks/tasks.json"
    [[ ! -f "$tasks_file" ]] && echo "yes" && return
    
    python3 -c "
import json, sys
try:
    d = json.load(open('$tasks_file'))
    tasks = d if isinstance(d, list) else d.get('tasks', [])
    in_progress = [t for t in tasks if t.get('status') == '进行' and t.get('department') == '$dept']
    print('no' if in_progress else 'yes')
except:
    print('yes')
" 2>/dev/null
}

# ── 主循环 ────────────────────────────────────────────
main() {
    mkdir -p "$(dirname "$LOG")" "$(dirname "$LOOP_STATE")"
    
    acquire_lock || exit 0
    trap release_lock EXIT
    
    local current
    current=$(get_current) || current="Λ"
    
    log "=== 自维持 · $current (dept=$(dept_of $current)) ==="
    
    # 检查是否需要生成任务
    local dept
    dept=$(dept_of "$current")
    local gen
    gen=$(should_generate "$dept")
    
    if [[ "$gen" == "yes" ]]; then
        # 生成新任务
        local task_id
        task_id=$(bash "$HOME/xuzhi_genesis/centers/task/generate_task.py" "$dept" 2>/dev/null | grep -oP 'task_\d+' | head -1 || echo "")
        if [[ -n "$task_id" ]]; then
            log "✅ 生成任务 ($dept)"
        else
            # 尝试直接用 python
            task_id=$(python3 -c "
import sys
sys.path.insert(0, '$HOME/xuzhi_genesis/centers/task')
from generate_task import main
sys.argv = ['generate_task.py', '$dept']
try: main()
except: pass
" 2>/dev/null | grep -oP 'task_\d+' | head -1) || task_id=""
            if [[ -n "$task_id" ]]; then
                log "✅ 生成任务 ($dept)"
            else
                log "⚠️ 生成失败，跳过"
            fi
        fi
    else
        log "⏭️ 已有进行中任务，跳过生成"
    fi
    
    # 推进到下一 agent
    local next
    next=$(advance "$current")
    
    python3 -c "
import json
d = {'current': '$next', 'prev': '$current', 'dept': '$(dept_of $next)'}
with open('$LOOP_STATE', 'w') as f:
    json.dump(d, f)
"
    
    log "→ 下轮 $next"
    log "=== 自维持完成 ==="
}

main "$@"
