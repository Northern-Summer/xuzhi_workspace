#!/bin/bash
# unified_cron.sh — 统一调度器（合并议会+自维持+heal检查）
# 频率：*/10一次，统筹处理所有
set -euo pipefail

HOME="${HOME:-/home/summer}"
LOG="$HOME/.xuzhi_memory/task_center/unified_cron.log"
STATE="$HOME/.xuzhi_memory/task_center/unified_state.json"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
mkdir -p "$(dirname "$LOG")"

log "=== 统一调度 $(date '+%H:%M:%S') ==="

# 1. 议会队列检查（简化版）
QUEUE="$HOME/.xuzhi_memory/parliament/QUEUE.txt"
AGENDA="$HOME/.xuzhi_memory/parliament/AGENDA.txt"
if [[ -f "$QUEUE" ]] && [[ -s "$QUEUE" ]]; then
    log "议会: 有议题"
fi

# 2. 自维持循环
bash "$HOME/.xuzhi_memory/self_sustaining_loop.sh" >> "$HOME/.xuzhi_memory/task_center/self_sustaining.log" 2>&1 || log "自维持: 异常"

# 3. 健康自检
bash "$HOME/.xuzhi_memory/self_heal.sh" >> "$HOME/.xuzhi_memory/task_center/watchdog.log" 2>&1 || log "heal: 异常"

log "=== 完成 ==="
