#!/bin/bash
# unified_cron.sh — 统一调度器（10分钟一次，符合宪法6/hr上限）
# 路径：~/xuzhi_workspace/unified_cron.sh
# 包含：议会 + 自维持 + heal + 任务执行 + Expert学习
set -euo pipefail

HOME_DIR="${HOME:-/home/summer}"
LOCKFILE="${HOME_DIR}/.xuzhi_memory/task_center/.unified_cron.lock"
LOG="${HOME_DIR}/.xuzhi_memory/task_center/unified_cron.log"

mkdir -p "$(dirname "$LOCKFILE")" "$(dirname "$LOG")"

# ── Idempotency lock ────────────────────────────────────
if ! mkdir "$LOCKFILE" 2>/dev/null; then
    echo "$(date '+%H:%M:%S') [skip] already running" >> "$LOG"
    exit 0
fi
trap 'rmdir "$LOCKFILE" 2>/dev/null || true' EXIT

stamp() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
stamp "=== Unified Cron started ==="

# ── 1. 红蓝队健康自检 ────────────────────────────────────
stamp "Heal: running self_heal.sh"
bash "${HOME_DIR}/xuzhi_genesis/centers/engineering/self_heal.sh" \
    >> "${HOME_DIR}/.xuzhi_memory/task_center/watchdog.log" 2>&1 \
    || stamp "Heal: non-zero exit"

# ── 2. Agent 存活检测 + 唤醒 ─────────────────────────────
stamp "Agent watchdog: running"
python3 "${HOME_DIR}/xuzhi_workspace/task_center/agent_watchdog.py" \
    >> "${HOME_DIR}/.xuzhi_memory/task_center/agent_watchdog.log" 2>&1 \
    || stamp "Agent watchdog: non-zero exit"

# ── 3. 任务执行层（每4轮=40分钟一次）─────────────────────
EXEC_CYCLE="${HOME_DIR}/.xuzhi_memory/task_center/.exec_cycle"
CYCLE=$(python3 -c "
import json, os
f='${EXEC_CYCLE}'
d = json.load(open(f)) if os.path.exists(f) else {'count': 0}
c = d.get('count', 0)
d['count'] = (c + 1) % 4
json.dump(d, open(f, 'w'))
print(c)
" 2>/dev/null)

if [ "$CYCLE" = "0" ]; then
    stamp "Task executor: triggered (cycle $CYCLE)"
    python3 "${HOME_DIR}/xuzhi_workspace/task_executor.py" \
        >> "${HOME_DIR}/.xuzhi_memory/task_center/task_executor.log" 2>&1 \
        || stamp "Task executor: non-zero exit"
fi

# ── 4. Expert 学习（每36轮=6小时一次）──────────────────
EXP_CYCLE="${HOME_DIR}/.xuzhi_memory/task_center/.expert_cycle"
EXP_N=$(python3 -c "
import json, os
f='${EXP_CYCLE}'
d = json.load(open(f)) if os.path.exists(f) else {'count': 0}
c = d.get('count', 0)
d['count'] = (c + 1) % 36
json.dump(d, open(f, 'w'))
print(c)
" 2>/dev/null)

if [ "$EXP_N" = "0" ]; then
    stamp "Expert Tracker: triggered (cycle $EXP_N)"
    python3 "${HOME_DIR}/xuzhi_workspace/task_center/expert_tracker.py" \
        >> "${HOME_DIR}/.xuzhi_memory/task_center/expert_tracker.log" 2>&1 \
        || stamp "Expert Tracker: non-zero"
    python3 "${HOME_DIR}/xuzhi_workspace/task_center/expert_watchdog.py" \
        >> "${HOME_DIR}/.xuzhi_memory/task_center/expert_watchdog.log" 2>&1 \
        || stamp "Expert Watchdog: non-zero"
fi

stamp "=== Unified Cron complete ==="
