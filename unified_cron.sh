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
d['count'] = (c + 1) % 6   # 6×10分钟=1小时（从36改为6）
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

    # ── 自动推送Expert结果到WeChat ───────────────────────
    # 用 openclaw message send，稳定方案
    python3 << 'PUSH_EOF' >> "${HOME_DIR}/.xuzhi_memory/task_center/expert_push.log" 2>&1
import subprocess, json
from pathlib import Path

changes = Path('${HOME_DIR}/.xuzhi_memory/expert_tracker/changes.json')
if changes.exists():
    d = json.load(open(changes))
    changes_list = d.get('changes', [])
    recent = changes_list[-10:] if len(changes_list) >= 10 else changes_list
    lines = [f'[{c["dept"]}] {c["expert"]}: {c["new_title"][:40]}' for c in recent]
    body = '\n'.join(lines) if lines else '无新发现'
    msg = f'📚 Expert学习（自动推送）\n累计{len(changes_list)}条\n\n{body}'
else:
    msg = '📚 Expert学习：无新数据'

# openclaw message send 是稳定方案，不依赖sessions_send
result = subprocess.run([
    'openclaw', 'message', 'send',
    '--channel', 'openclaw-weixin',
    '--target', 'o9cq80z9eorqjasg6hb1w-cc4-po@im.wechat',
    '--message', msg
], capture_output=True, text=True, timeout=15)
print(result.stdout[-200:] if result.stdout else '', result.stderr[-200:] if result.stderr else '', file=open('${HOME_DIR}/.xuzhi_memory/task_center/expert_push.log', 'a'))
PUSH_EOF

stamp "=== Unified Cron complete ==="
