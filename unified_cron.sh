#!/bin/bash
# unified_cron.sh — 统一调度器（议会+自维持+heal+任务执行）
# 频率：*/10一次（6次/小时，符合宪法约束）
set -euo pipefail

HOME="${HOME:-/home/summer}"
LOG="$HOME/.xuzhi_memory/task_center/unified_cron.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

log "=== 统一调度 $(date '+%H:%M:%S') ==="

# ── 1. 议会队列检查 ───────────────────────────────────
bash "$HOME/.xuzhi_memory/parliament/check_queue.sh" \
    >> "$HOME/.xuzhi_memory/task_center/parliament.log" 2>&1 \
    || log "议会: 异常"

# ── 2. 自维持循环 ─────────────────────────────────────
bash "$HOME/.xuzhi_memory/self_sustaining_loop.sh" \
    >> "$HOME/.xuzhi_memory/task_center/self_sustaining.log" 2>&1 \
    || log "自维持: 异常"

# ── 3. 健康自检 ────────────────────────────────────────
bash "$HOME/.xuzhi_memory/self_heal.sh" \
    >> "$HOME/.xuzhi_memory/task_center/watchdog.log" 2>&1 \
    || log "heal: 异常"

# ── 4. 任务执行层（sessions_spawn，每4轮=40分钟一次）────
# 调用 task_executor.py，通过 openclaw agent --local 派发
EXEC_STATE="$HOME/.xuzhi_memory/task_center/exec_cycle.json"

CYCLE=$(python3 -c "
import json, os
f='$EXEC_STATE'
if os.path.exists(f):
    d=json.load(open(f))
    c=d.get('count',0)
else:
    c=0
d={'count':(c+1)%4}
json.dump(d,open(f,'w'),indent=2)
print(c)
" 2>/dev/null)

if [[ "$CYCLE" == "0" ]]; then
    log "执行层: 触发任务派发"
    python3 "$HOME/.xuzhi_memory/task_executor.py" \
        >> "$HOME/.xuzhi_memory/task_center/task_executor.log" 2>&1 \
        || log "执行层: 异常"
fi

# ── 5. Expert Tracker（每36次=6小时）────────────────
EXPERT_CYCLE_FILE="$HOME/.xuzhi_memory/task_center/.expert_cycle"
EXPERT_CYCLE=$(python3 -c "
import json, os
f='$EXPERT_CYCLE_FILE'
d = json.load(open(f)) if os.path.exists(f) else {}
c = (d.get('count', 0) + 1) % 36
d['count'] = c
json.dump(d, open(f,'w'))
print(c)
" 2>/dev/null)
if [[ "$EXPERT_CYCLE" == "0" ]]; then
    log "Expert Tracker: 触发"
    python3 "$HOME/.xuzhi_memory/task_center/expert_tracker.py" \
        >> "$HOME/.xuzhi_memory/expert_tracker/tracker.log" 2>&1 \
        || log "Expert Tracker: 异常"
fi

log "=== 完成 ==="
