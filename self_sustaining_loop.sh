#!/bin/bash
# self_sustaining_loop.sh — 跨 agent 自维持闭环（系统 cron，零 POST）
# cron: */15 * * * * bash ~/.xuzhi_memory/self_sustaining_loop.sh
# 2026-03-24: 添加 LC_ALL=C 修复 grep -oP 在 UTF-8 下失效问题
export LC_ALL=C
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

# ── 生成任务（去重：检查 tasks.json 是否有有效的未完成任务）───
# 逻辑：
#   - 有 'open' 状态任务（未认领）→ 可以生成更多（任务池充裕）
#   - 有 '进行中' 任务（已认领，<2h）→ 跳过
#   - 有 '进行中' 任务（已认领，>2h）→ 认为是卡死任务 → 允许生成
should_generate() {
    local dept="$1"
    local tasks_file="$HOME/.openclaw/tasks/tasks.json"
    [[ ! -f "$tasks_file" ]] && echo "yes" && return
    
    python3 -c "
import json, sys, time
try:
    d = json.load(open('$tasks_file'))
    tasks = d if isinstance(d, list) else d.get('tasks', [])
    
    # 按部门筛选
    dept_tasks = [t for t in tasks if t.get('department') == '$dept' or t.get('department') == 'all']
    
    # 有已认领且活跃的任务吗（<2h）？
    now = time.time()
    in_progress_active = [
        t for t in dept_tasks 
        if t.get('status') in ('进行', 'open', 'claimed') 
        and t.get('claimed_at', 0) > 0
        and (now - t.get('claimed_at', now)) < 7200
    ]
    
    # 有卡死任务吗（>2h仍在进行）？
    stuck = [
        t for t in dept_tasks 
        if t.get('status') in ('进行', 'claimed')
        and t.get('claimed_at', 0) > 0
        and (now - t.get('claimed_at', now)) >= 7200
    ]
    
    if stuck:
        print('stuck_tasks_clear')
    elif in_progress_active:
        print('no')
    else:
        print('yes')
except Exception as e:
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
    
    # 处理卡死任务（可选优化：标记放弃）
    if [[ "$gen" == "stuck_tasks_clear" ]]; then
        python3 -c "
import json, time
try:
    d = json.load(open('$HOME/.openclaw/tasks/tasks.json'))
    tasks = d if isinstance(d, list) else d.get('tasks', [])
    now = time.time()
    for t in tasks:
        if t.get('department') == '$dept' or t.get('department') == 'all':
            if t.get('status') in ('进行','claimed') and t.get('claimed_at',0) > 0 and (now - t.get('claimed_at',now)) >= 7200:
                t['status'] = '放弃'
                t['completion_report'] = 'heal: 超时(>2h)自动放弃，任务槽释放'
    json.dump(d, open('$HOME/.openclaw/tasks/tasks.json','w'), ensure_ascii=False, indent=2)
    print('cleared_stuck')
except Exception as e:
    print('clear_failed')
" 2>/dev/null
        log "🧹 清理卡死任务"
    fi

    if [[ "$gen" == "yes" || "$gen" == "stuck_tasks_clear" ]]; then
        # 生成新任务（必须用 python3，不是 bash）
        # generate_task.py 需要 agent_id（如 Λ, Δ），不是 dept
        # 使用临时文件避免 pipe+set -e 导致 || 失效的问题
        local tmp_out="/tmp/gen_task_$$.txt"
        python3 "$HOME/xuzhi_genesis/centers/task/generate_task.py" "$current" > "$tmp_out" 2>&1 || true
        local task_id
        # generate_task.py 用全角数字（⁰¹²³⁴⁵⁶⁷⁸⁹）编码 task ID
        # 提取 ID: <数字> 格式（去掉转义括号，兼容全角括号），是真正的 ASCII 数字
        task_id=$(python3 -c "
import re
try:
    with open('$tmp_out', 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'ID:\s*(\d+)', content)
    print('task_' + m.group(1) if m else '')
except: print('')
" 2>/dev/null || true)
        rm -f "$tmp_out"
        if [[ -n "$task_id" ]]; then
            log "✅ 生成任务 ($current/$dept) ID=$task_id"
        else
            # 备选方案：直接import python模块
            local tmp_out2="/tmp/gen_task_fallback_$$.txt"
            python3 -c "
import sys
sys.path.insert(0, '$HOME/xuzhi_genesis/centers/task')
from generate_task import main as gen_main
sys.argv = ['generate_task.py', '$current']
try: gen_main()
except Exception as e: print('ERROR:' + str(e), file=sys.stderr)
" > "$tmp_out2" 2>&1 || true
            task_id=$(python3 -c "
import re
try:
    with open('$tmp_out2', 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'ID:\s*(\d+)', content)
    print('task_' + m.group(1) if m else '')
except: print('')
" 2>/dev/null || true)
            rm -f "$tmp_out2"
            if [[ -n "$task_id" ]]; then
                log "✅ 生成任务 ($current/$dept) ID=$task_id (fallback)"
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
from datetime import datetime, timezone
d = {
    'current': '$next',
    'prev': '$current',
    'dept': '$(dept_of $next)',
    'last_run': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
}
with open('$LOOP_STATE', 'w') as f:
    json.dump(d, f, ensure_ascii=False)
"
    
    log "→ 下轮 $next"
    log "=== 自维持完成 ==="
}

main "$@"
