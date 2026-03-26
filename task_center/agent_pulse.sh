#!/bin/bash
# agent_pulse.sh — 向所有7个agent的活跃session发送触发消息
# 由cron每10分钟调用: */10 * * * * $HOME/xuzhi_workspace/task_center/agent_pulse.sh

set -euo pipefail
HOME="${HOME:-/home/summer}"
LOG="$HOME/.xuzhi_memory/task_center/agent_pulse.log"
TOKEN_FILE="$HOME/.openclaw/openclaw.json"
GATEWAY="http://localhost:18789"

log() {
    echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"
}

rpc_call() {
    local method="$1"; shift
    local params="$1"; shift
    local token
    token=$(python3 -c "import json; print(json.load(open('$TOKEN_FILE'))['gateway']['auth']['token'])")
    python3 -c "
import json, urllib.request
token = '$token'
payload = json.dumps({
    'jsonrpc': '2.0', 'id': 1,
    'method': '$method',
    'params': $params
}).encode()
req = urllib.request.Request(
    '$GATEWAY/rpc',
    data=payload,
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
)
with urllib.request.urlopen(req, timeout=15) as resp:
    return json.loads(resp.read())
" 2>/dev/null
}

send_to_session() {
    local session_key="$1"; shift
    local message="$1"; shift
    rpc_call "session/message" "{\"sessionKey\": \"$session_key\", \"message\": \"$message\"}" >> "$LOG" 2>&1
    log "sent to $session_key"
}

log "=== agent_pulse: 开始 ==="

# 所有agent的活跃session keys
declare -A AGENTS=(
    ["Ξ"]="agent:main:main"
    ["Φ"]="agent:phi:discord:channel:1486694791738691604"
    ["Δ"]="agent:delta:main"
    ["Θ"]="agent:theta:main"
    ["Γ"]="agent:gamma:main"
    ["Ω"]="agent:omega:main"
    ["Ψ"]="agent:psi:main"
)

MSG="系统心跳触发。请处理任务队列中的等待任务。回复 DONE 或 HEARTBEAT_OK。"

for agent in Ξ Φ Δ Θ Γ Ω Ψ; do
    key="${AGENTS[$agent]}"
    log "→ $agent ($key)"
    send_to_session "$key" "$MSG" || log "  ❌ failed"
done

log "=== agent_pulse: 完成 ==="
