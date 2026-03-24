#!/bin/bash
# pre_compact_guard.sh — 离开前保护脚本（每次离开前执行）
# 在 context compaction 之前运行，确保重要状态已快照
# 调用方式: bash ~/.xuzhi_memory/pre_compact_guard.sh
set -euo pipefail

HOME_DIR="${HOME:-/home/summer}"
LOG="$HOME_DIR/.xuzhi_memory/daily/$(date +%Y-%m-%d).md"

log_msg() {
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "[$ts] [pre_compact_guard] $1" >> "$LOG" 2>/dev/null || true
    echo "[pre_compact_guard] $1"
}

snapshot_loop_state() {
    local state_file="$HOME_DIR/.xuzhi_memory/task_center/loop_state.json"
    local snapshot="$HOME_DIR/.xuzhi_memory/session_snapshot.json"
    if [[ -f "$state_file" ]]; then
        cp "$state_file" "$snapshot" 2>/dev/null || true
        log_msg "loop_state 快照已保存"
    fi
}

update_ratings_last_active() {
    local ratings="$HOME_DIR/xuzhi_genesis/centers/mind/society/ratings.json"
    python3 -c "
import json
from datetime import datetime, timezone
NOW = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
try:
    d = json.load(open('$ratings'))
    agents = d.get('agents', d)
    for k, v in agents.items():
        if isinstance(v, dict) and v.get('status') == 'active':
            v['last_active'] = NOW
    json.dump(d, open('$ratings', 'w'), ensure_ascii=False, indent=2)
    print('ok')
except:
    pass
" 2>/dev/null || true
    log_msg "ratings last_active 已更新"
}

flush_heal_log() {
    local heal_log="$HOME_DIR/.xuzhi_memory/task_center/self_heal.log"
    if [[ -f "$heal_log" ]]; then
        # 截断到最近100行（防止无限增长）
        tail -100 "$heal_log" > "${heal_log}.tmp" 2>/dev/null && mv "${heal_log}.tmp" "$heal_log" || true
        log_msg "heal log 已截断"
    fi
}

write_departure_marker() {
    local marker="$HOME_DIR/.xuzhi_memory/.last_departure"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$marker"
    log_msg "离开标记已写入"
}

main() {
    log_msg "=== Pre-Compact Guard $(date '+%H:%M:%S') ==="
    snapshot_loop_state
    update_ratings_last_active
    flush_heal_log
    write_departure_marker
    log_msg "=== 离开前保护完成 ==="
}

main "$@"
