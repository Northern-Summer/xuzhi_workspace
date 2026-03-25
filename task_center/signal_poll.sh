#!/bin/bash
# signal_poll.sh — 每个 agent 独立轮询自己的 wake 信号（cron 驱动）
# 幂等，零 sessions.send，零递归 spawn
# cron 示例（每 5 分钟）：*/5 * * * * bash .../signal_poll.sh Φ
set -euo pipefail

AGENT="${1:-}"
SIGNAL_FILE="${HOME}/.xuzhi_watchdog/wake_signals/wake_${AGENT}.json"

if [ -z "$AGENT" ]; then
    echo "用法: $0 <AGENT_SYMBOL>"
    exit 1
fi

if [ ! -f "$SIGNAL_FILE" ]; then
    exit 0
fi

# 读取信号状态
STATUS=$(python3 -c "
import json
with open('${SIGNAL_FILE}') as f:
    d = json.load(f)
print(d.get('status', 'unknown'))
" 2>/dev/null || echo "error")

if [ "$STATUS" = "pending" ]; then
    # Ack 信号（幂等）
    python3 -c "
import json
from datetime import datetime, timezone

with open('${SIGNAL_FILE}') as f:
    d = json.load(f)

d['status'] = 'acknowledged'
d['acked_at'] = datetime.now(timezone.utc).isoformat()

with open('${SIGNAL_FILE}', 'w') as f:
    json.dump(d, f, indent=2)

print(f'【${AGENT} 唤醒信号已确认】reason={d[\"reason\"]}')
"
    exit 0
fi

exit 0
