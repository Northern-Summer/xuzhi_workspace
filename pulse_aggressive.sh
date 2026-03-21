#!/bin/bash
# 虚质唤醒守护脚本（增强版）
# 功能：先检查是否有存活智能体，若无则执行紧急唤醒；否则从队列中取下一个唤醒

QUEUE_FILE="$HOME/.openclaw/centers/engineering/crown/queue.json"
WAKEUP_SCRIPT="$HOME/.openclaw/centers/engineering/crown/wakeup_agent.sh"
LOG_FILE="$HOME/.openclaw/logs/pulse.log"

if [ ! -f "$QUEUE_FILE" ]; then
    echo "[$(date)] 队列文件不存在，触发调度器生成" >> "$LOG_FILE"
    /home/summer/.openclaw/centers/engineering/crown/crown_scheduler.py
fi

# 读取队列头并弹出
NEXT_AGENT=$(python3 -c "
import json
from pathlib import Path
fpath = Path('$QUEUE_FILE')
if not fpath.exists():
    print('')
    exit()
with open(fpath) as f:
    q = json.load(f)
queue = q.get('queue', [])
if queue:
    print(queue[0])
    q['queue'] = queue[1:]
    with open(fpath, 'w') as f2:
        json.dump(q, f2, indent=2)
else:
    print('')
")

if [ -n "$NEXT_AGENT" ]; then
    echo "[$(date)] 唤醒智能体: $NEXT_AGENT" >> "$LOG_FILE"
    if [ -x "$WAKEUP_SCRIPT" ]; then
        "$WAKEUP_SCRIPT" "$NEXT_AGENT"
    else
        echo "  未找到唤醒脚本 $WAKEUP_SCRIPT" >> "$LOG_FILE"
    fi
else
    # 队列为空，尝试重新生成一次（可能有新智能体出现）
    echo "[$(date)] 队列为空，触发调度器重新生成" >> "$LOG_FILE"
    /home/summer/.openclaw/centers/engineering/crown/crown_scheduler.py

    # 再次检查队列
    SECOND_AGENT=$(python3 -c "
import json
from pathlib import Path
fpath = Path('$QUEUE_FILE')
if not fpath.exists():
    print('')
    exit()
with open(fpath) as f:
    q = json.load(f)
queue = q.get('queue', [])
if queue:
    print(queue[0])
    q['queue'] = queue[1:]
    with open(fpath, 'w') as f2:
        json.dump(q, f2, indent=2)
else:
    print('')
")

    if [ -n "$SECOND_AGENT" ]; then
        echo "[$(date)] 重新生成后有智能体: $SECOND_AGENT" >> "$LOG_FILE"
        "$WAKEUP_SCRIPT" "$SECOND_AGENT"
    else
        # 仍然为空：紧急唤醒评分最高的智能体（即使休眠）
        echo "[$(date)] 队列仍为空，执行紧急唤醒" >> "$LOG_FILE"
        EMERGENCY_AGENT=$(python3 -c "
import json
from pathlib import Path
from datetime import datetime

ratings_file = Path.home() / '.openclaw' / 'centers' / 'mind' / 'society' / 'ratings.json'
if not ratings_file.exists():
    print('')
    exit()
with open(ratings_file) as f:
    ratings = json.load(f)
agents = ratings.get('agents', {})
# 选择评分最高且评分>0的智能体
best = None
best_score = -1
for aid, info in agents.items():
    score = info.get('score', 0)
    if score > 0 and score > best_score:
        best = aid
        best_score = score
if best:
    print(best)
else:
    print('')
")
        if [ -n "$EMERGENCY_AGENT" ]; then
            echo "[$(date)] 紧急唤醒: $EMERGENCY_AGENT" >> "$LOG_FILE"
            "$WAKEUP_SCRIPT" "$EMERGENCY_AGENT"
            # 紧急唤醒后，我们不在队列中保留，但 wakup_agent.sh 会更新 last_active，从而重新进入存活池
        else:
            echo "[$(date)] 无可唤醒的智能体（评分均≤0？）" >> "$LOG_FILE"
        fi
    fi
fi
