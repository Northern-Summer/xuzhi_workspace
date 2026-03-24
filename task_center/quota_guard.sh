#!/bin/bash
# quota_guard.sh — Token 配额警戒脚本
# cron: 每30分钟检查一次
# 警戒线：>85% 禁用 AutoRA cron，>90% 发送告警
set -euo pipefail

HOME="${HOME:-/home/summer}"
LOG="$HOME/.xuzhi_memory/task_center/quota_guard.log"
AUTORA_JOB_ID="250a9c67-01b3-432e-8889-b3bbf68bfba5"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [quota_guard] $*" >> "$LOG"; }

# 读取当前配额（从 genesis_probe JSON）
quota_pct=$(python3 "$HOME/xuzhi_genesis/centers/mind/genesis_probe.py" --brief 2>/dev/null | grep -oE '[0-9]+%' | head -1 | tr -d '%' || echo "0")
[[ -z "$quota_pct" ]] && quota_pct=0

log "配额: ${quota_pct}%"

if (( quota_pct >= 90 )); then
    log "🚨 紧急：配额${quota_pct}%≥90%，发送告警"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] 🚨 QUOTA CRITICAL: ${quota_pct}%" >> "$HOME/.xuzhi_memory/daily/$(date +%Y-%m-%d).md"
    # 尝试禁用 AutoRA
    openclaw cron disable "$AUTORA_JOB_ID" 2>/dev/null && log "AutoRA cron 已禁用" || log "AutoRA disable 失败"
    exit 1
elif (( quota_pct >= 85 )); then
    log "⚠️ 警戒：配额${quota_pct}%≥85%，禁用 AutoRA cron"
    openclaw cron disable "$AUTORA_JOB_ID" 2>/dev/null && log "AutoRA cron 已禁用（警戒）" || log "AutoRA disable 失败"
else
    # 配额正常，尝试恢复 AutoRA
    openclaw cron enable "$AUTORA_JOB_ID" 2>/dev/null && log "AutoRA cron 已恢复（配额${quota_pct}%正常）" || log "AutoRA enable 失败（可能已是启用状态）"
fi
