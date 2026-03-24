#!/bin/bash
# check_queue.sh — 议会队列检查（无队列版）
# cron: */5 * * * * bash ~/.xuzhi_memory/parliament/check_queue.sh
# 逻辑：
#   1. 检查 QUEUE.txt 是否为空
#   2. 如果有议题 → 注入 AGENDA.txt
#   3. 议会正常轮转（但实际由 systemEvent 驱动，Λ自然响应）
#   4. 检查 .heal_pending.txt → 有待执行命令则注入 systemEvent 提醒Λ

HOME="${HOME:-/home/summer}"
QUEUE="$HOME/.xuzhi_memory/parliament/QUEUE.txt"
AGENDA="$HOME/.xuzhi_memory/parliament/AGENDA.txt"
CURRENT="$HOME/.xuzhi_memory/parliament/CURRENT.txt"
PENDING="$HOME/.xuzhi_memory/.heal_pending.txt"
LOG="$HOME/.xuzhi_memory/parliament/check.log"

log() {
    mkdir -p "$(dirname "$LOG")"
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"
}

log "=== 队列检查 $(date '+%H:%M:%S') ==="

# 检查是否有待处理 heal 命令
if [[ -f "$PENDING" ]] && [[ -s "$PENDING" ]]; then
    pending_count=$(grep -v "^#" "$PENDING" 2>/dev/null | grep -c "sessions_send" || echo 0)
    if (( pending_count > 0 )); then
        log "检测到 $pending_count 个待执行 heal 命令，将在Λ响应时执行"
    fi
fi

# 检查 QUEUE 是否为空
if [[ ! -f "$QUEUE" ]] || [[ ! -s "$QUEUE" ]]; then
    log "QUEUE为空，无议会议题"
    # 如果有AGENDA但无QUEUE，议会结束
    if [[ -f "$AGENDA" ]] && [[ -s "$AGENDA" ]]; then
        log "议会结束"
        echo "" > "$AGENDA"
    fi
    exit 0
fi

# 显示当前议题（如果存在）
if [[ -f "$AGENDA" ]] && [[ -s "$AGENDA" ]]; then
    topic=$(head -1 "$AGENDA")
    log "议题: $topic"
fi

# 推进队列
log "队列检查完成"

# 注意：实际的systemEvent注入由cron job处理
# check_queue.sh 只负责文件状态管理
