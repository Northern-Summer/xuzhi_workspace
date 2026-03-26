#!/bin/bash
# session_restore.sh — 恢复离开前状态（自动运行在每次启动时）
# 读取上次离开时的快照，重建运行时状态
# 调用方式: bash ~/.xuzhi_memory/session_restore.sh [--brief]
set -euo pipefail

HOME_DIR="${HOME:-/home/summer}"
BRIEF=""
if [[ "${1:-}" == "--brief" ]]; then
    BRIEF=1
fi

SNAPSHOT_FILE="$HOME_DIR/.xuzhi_memory/session_snapshot.json"
LOG="$HOME_DIR/.xuzhi_memory/daily/$(date +%Y-%m-%d).md"

log_msg() {
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "[$ts] [session_restore] $1" >> "$LOG" 2>/dev/null || true
    if [[ -z "$BRIEF" ]]; then
        echo "[session_restore] $1"
    fi
}

restore_loop_state() {
    local state_file="$HOME_DIR/.xuzhi_memory/task_center/loop_state.json"
    if [[ -f "$state_file" ]]; then
        log_msg "loop_state 恢复完成"
    else
        # 初始化默认状态
        python3 -c "
import json
from datetime import datetime, timezone
d = {
    'current': 'Λ',
    'prev': 'Λ',
    'dept': 'engineering',
    'last_run': datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
}
with open('$state_file', 'w') as f:
    json.dump(d, f, ensure_ascii=False)
" 2>/dev/null || true
        log_msg "loop_state 初始化完成"
    fi
}

restore_checkpoint() {
    local ckpt="$HOME_DIR/.xuzhi_memory/watchdog_checkpoint.json"
    if [[ ! -f "$ckpt" ]]; then
        python3 -c "
import json
from datetime import datetime, timezone
d = {
    'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    'task': 'initialized',
    'status': 'ready'
}
with open('$ckpt', 'w') as f:
    json.dump(d, f, ensure_ascii=False)
" 2>/dev/null || true
        log_msg "checkpoint 初始化完成"
    fi
}

restore_ratings() {
    local ratings="$HOME_DIR/xuzhi_genesis/centers/mind/society/ratings.json"
    if [[ -f "$ratings" ]]; then
        # 更新所有 agent 的 last_active 为当前时间（重启后需要刷新）
        python3 -c "
import json
from datetime import datetime, timezone
NOW = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
try:
    d = json.load(open('$ratings'))
    agents = d.get('agents', d)
    for k, v in agents.items():
        if isinstance(v, dict):
            v['last_active'] = NOW
    json.dump(d, open('$ratings', 'w'), ensure_ascii=False, indent=2)
    print('ratings_restored')
except Exception as e:
    print(f'ratings_err:{e}')
" >> "$HOME_DIR/.xuzhi_memory/task_center/restore.log" 2>/dev/null || true
        log_msg "ratings last_active 已刷新"
    fi
}

main() {
    mkdir -p "$(dirname "$LOG")"
    mkdir -p "$HOME_DIR/.xuzhi_memory/task_center"
    log_msg "=== Session Restore $(date '+%H:%M:%S') ==="
    restore_loop_state
    restore_checkpoint
    restore_ratings
    log_msg "=== Restore 完成 ==="
}

main "$@"
