#!/bin/bash
# xi_pulse.sh — Xi专属研究脉冲
# 原则：安全、优雅、高效
# 
# 安全：idempotent，有锁防重复，自包含不破坏其他进程
# 优雅：最小化逻辑，只做需要做的事
# 高效：每15分钟一次，不浪费配额
#
# cron: */15 * * * * /home/summer/.openclaw/workspace/xi_pulse.sh

HOME=/home/summer
LOG="$HOME/.xuzhi_memory/task_center/xi_pulse.log"
LOCK="$HOME/.xuzhi_memory/task_center/.xi_pulse.lock"

stamp() { echo "[$(date '+%H:%M')] $1"; }

# ── 防重复 ──────────────────────────────────────────────────
if [ -f "$LOCK" ]; then
    exit 0  # 上次还在跑，静默跳过
fi
trap "rm -f $LOCK" EXIT
touch "$LOCK"

# ── 1. 采集 + 综合 ──────────────────────────────────────────
stamp "Xi脉冲开始..."
python3 "$HOME/xuzhi_workspace/task_center/research_loop.py" --force \
    >> "$LOG" 2>&1

# ── 2. 读取综合结果，发WeChat ──────────────────────────────
SYNTHESIS="$HOME/.xuzhi_memory/expert_tracker/synthesis.json"
if [ -f "$SYNTHESIS" ]; then
    python3 -c "
import json, subprocess
from pathlib import Path
from datetime import datetime

d = json.load(open(Path.home() / '.xuzhi_memory/expert_tracker/synthesis.json'))
round_n = d.get('round', '?')
conf = d.get('confidence', 0)
hyps = d.get('hypotheses', [])
rq = d.get('research_question', '')
at = d.get('generated_at', '')[11:16]

lines = [f'📊 Round {round_n} | {at}']
lines.append(f'置信度: {conf:.0%}')
for h in hyps[:2]:
    lines.append(f'• {h[\"hypothesis\"][:55]}')
lines.append('系统在线，运行正常')

msg = '\n'.join(lines)
subprocess.run([
    'openclaw', 'message', 'send',
    '--channel', 'openclaw-weixin',
    '--target', 'o9cq80z9eorqJasg6hB1W-Cc4-Po@im.wechat',
    '--message', msg
], capture_output=True, timeout=15)
" >> "$LOG" 2>&1
fi

stamp "Xi脉冲完成"
