#!/bin/bash
# watchdog_supervisor.sh — 看守jump_controller（外部独立进程）
# 工程改进铁律合规 — Ξ | 2026-03-27
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES
#
# 职责：确保jump_controller始终存活
# 原理：cron外部触发，主进程崩溃不影响此脚本运行

HOME=/home/summer
JC_PID_FILE="$HOME/.xuzhi_watchdog/jump_controller.pid"
JC_SCRIPT="$HOME/xuzhi_workspace/task_center/jump_controller.py"
JC_LOG="$HOME/.xuzhi_memory/task_center/jump_controller.log"
ALLOW_FILE="$HOME/.xuzhi_watchdog/jump_halt.flag"

# Human说停 → 不重启
if [ -f "$ALLOW_FILE" ]; then
    exit 0
fi

# 检查PID文件是否存在
if [ ! -f "$JC_PID_FILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [supervisor] PID文件不存在，启动jump_controller" >> "$JC_LOG"
    nohup python3 "$JC_SCRIPT" daemon 30 >> "$JC_LOG" 2>&1 &
    exit 0
fi

PID=$(cat "$JC_PID_FILE" 2>/dev/null)

# 进程是否存在
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    exit 0  # 存活
fi

# 进程已死 → 重启
echo "$(date '+%Y-%m-%d %H:%M:%S') [supervisor] jump_controller PID=$PID 已死，重启" >> "$JC_LOG"
nohup python3 "$JC_SCRIPT" daemon 30 >> "$JC_LOG" 2>&1 &
