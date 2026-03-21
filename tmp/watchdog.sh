#!/bin/bash
# watchdog.sh — Lambda Watchdog（systemEvent版）
# cron 触发器，纯 shell，无 LLM
# 作用：检测 Gateway 是否存活，异常时通知 main session

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8765/health}"
TIMEOUT=5

http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$GATEWAY_URL" 2>/dev/null)

if [ "$http_code" = "200" ]; then
    echo "Gateway: OK ($http_code)"
    exit 0
else
    echo "Gateway: FAIL ($http_code)"
    # 写入状态文件，main session 下次心跳时会读到
    echo "{\"ts\":$(date +%s),\"gateway_status\":\"$http_code\",\"host\":\"$(hostname)\"}" \
        > /home/summer/.openclaw/workspace/memory/gateway_alert.json
    exit 1
fi
