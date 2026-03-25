#!/usr/bin/env bash
# cron_runner.sh — Xuzhi periodic task runner (isolated from Gateway)
# Triggered by xuzhi-cron.timer every 5 minutes.
# Handles all periodic Xuzhi tasks including Gateway restart decisions.
set -euo pipefail

HOME_DIR="$HOME"
STATE_DIR="${HOME_DIR}/.xuzhi_watchdog"
LOG="${HOME_DIR}/.xuzhi_cron.log"
RECOVERY_TRIGGER="${STATE_DIR}/recovery_trigger"
MARKER="${STATE_DIR}/gateway_state"
RESTART_COUNTER="${STATE_DIR}/restart_count"
BACKOFF_FILE="${STATE_DIR}/restart_backoff"

mkdir -p "$STATE_DIR"

stamp() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ─── Restart loop protection (exponential backoff) ────────────────────────────
# Principle: idempotent restart decision with bounded retry
# If Gateway died and recovered N times in quick succession, stop auto-restarting
# and force human intervention (write alert file for main session to report)

check_restart_backoff() {
    local reason="$1"
    local now_sec=$(date +%s)
    local last_restart=0
    local backoff_sec=0

    if [ -f "$BACKOFF_FILE" ]; then
        read -r last_restart backoff_sec < "$BACKOFF_FILE"
    fi

    if [ "$backoff_sec" -gt 3600 ]; then
        # Been >1 hour since last restart — reset
        backoff_sec=0
        stamp "BACKOFF: reset (was ${backoff_sec}s)"
    fi

    if [ "$now_sec" -lt "$((last_restart + backoff_sec))" ]; then
        local wait=$((last_restart + backoff_sec - now_sec))
        stamp "BACKOFF: skipping restart, need ${wait}s more (backoff=${backoff_sec}s)"
        # Write escalation alert
        echo "$(date '+%Y-%m-%d %H:%M:%S') ESCALATE: restart loop detected, backoff=${backoff_sec}s" \
            > "${STATE_DIR}/escalation_alert"
        return 1
    fi

    # Increment backoff: 5min, 10min, 20min, 40min, 80min (doubling)
    if [ "$last_restart" -gt 0 ]; then
        backoff_sec=$((backoff_sec == 0 ? 300 : backoff_sec * 2))
        [ "$backoff_sec" -gt 7200 ] && backoff_sec=7200  # cap at 2h
    fi
    echo "$now_sec $backoff_sec" > "$BACKOFF_FILE"
    stamp "BACKOFF: next earliest restart in ${backoff_sec}s (doubled)"
    return 0
}

# ─── Gateway recovery handling ─────────────────────────────────────────────────
if [ -f "$RECOVERY_TRIGGER" ]; then
    RECOVERY_INFO=$(cat "$RECOVERY_TRIGGER")
    rm -f "$RECOVERY_TRIGGER"
    stamp "GATEWAY_RECOVERY: $RECOVERY_INFO"

    # Verify Gateway is actually alive
    if curl -sf --connect-timeout 3 http://localhost:18789/health > /dev/null 2>&1; then
        # Check backoff — don't restart if in loop protection
        if ! check_restart_backoff "recovery"; then
            stamp "SKIP: restart blocked by backoff (possible loop)"
        fi
        # If not in backoff, restart cleanly
    else
        stamp "Gateway still dead, not restarting"
    fi
fi

# ─── Periodic Gateway health check (every cycle) ──────────────────────────────
if [ -f "$MARKER" ]; then
    STATE=$(cat "$MARKER")
    if [ "$STATE" = "dead" ]; then
        stamp "Gateway MARKER=dead — checking if systemd can restart..."
        if curl -sf --connect-timeout 3 http://localhost:18789/health > /dev/null 2>&1; then
            stamp "Gateway is actually alive (systemd recovered it)"
            echo "alive" > "$MARKER"
        else
            if ! check_restart_backoff "marker_dead"; then
                stamp "Auto-restart blocked — escalation alert written"
            else
                stamp "Issuing openclaw gateway restart..."
                openclaw gateway restart >> "$LOG" 2>&1 || stamp "RESTART_FAILED"
            fi
        fi
    fi
fi


# ─── Parliament bell: 击鼓传花流动笔记 ─────────────────────────────────────
PARLIAMENT_RING="${HOME_DIR}/xuzhi_genesis/centers/mind/parliament/parliament_ring.py"
FLOW_FILE="${HOME_DIR}/xuzhi_genesis/centers/mind/parliament/flow.json"
if [ -f "$FLOW_FILE" ] && [ -f "$PARLIAMENT_RING" ]; then
    RESULT=$(python3 "$PARLIAMENT_RING" --bell 2>/dev/null || true)
    [ -n "$RESULT" ] && stamp "BELL: $RESULT"
fi

# ─── Regular task dispatch ────────────────────────────────────────────────────
MINUTE=$(date '+%M')

# SSH agent for GitHub (cron non-interactive shell needs explicit startup)
if ! ssh-add -l >/dev/null 2>&1; then
    eval "$(ssh-agent -s)"
    SSH_AUTH_SOCK=$(git config --get socket 2>/dev/null || echo "/tmp/ssh-agent.sock")
    ssh-add ~/.ssh/xuzhi_github >/dev/null 2>&1 || true
fi


# Memory Forge: DISABLED — Broken Concept (sessions.json.bak never existed)
# Future: if sessions archive is needed, implement with correct path



# Expert Tracker + Memory Window + GitHub push (hourly at :00)
if [ "$MINUTE" = "00" ]; then
    stamp "Memory window: running daily trim"
    bash "${HOME_DIR}/xuzhi_genesis/memory_window.sh" >> "$LOG" 2>&1 || stamp "Memory window: FAILED"

    stamp "Expert Tracker: hourly run"
    cd "${HOME_DIR}/xuzhi_workspace"

    # GitHub push: xuzhi_workspace (SSH) + xuzhi_memory (HTTPS)
    stamp "GitHub push: xuzhi_workspace"
    git push origin master >> "$LOG" 2>&1 || stamp "GitHub push xuzhi_workspace: FAILED"

    stamp "GitHub push: xuzhi_memory"
    git -C "${HOME_DIR}/.xuzhi_memory" push origin master >> "$LOG" 2>&1 || stamp "GitHub push xuzhi_memory: FAILED"

    # .openclaw backup via Contents API (HTTPS, bypasses git protocol)
    stamp "GitHub push: .openclaw backup"
    python3 "${HOME_DIR}/xuzhi_workspace/bin/push_openclaw.py" >> "$LOG" 2>&1 || stamp "GitHub push .openclaw: FAILED"
fi

if [ "$((10#$MINUTE % 15))" = "0" ]; then
    stamp "Agent watchdog: 15min check"
    cd "${HOME_DIR}/xuzhi_workspace/task_center"
    python3 agent_watchdog.py >> "$LOG" 2>&1 || stamp "Agent watchdog: FAILED"
fi

if [ "$((10#$MINUTE % 30))" = "0" ]; then
    stamp "Expert watchdog: 30min check"
    cd "${HOME_DIR}/xuzhi_workspace/task_center"
    python3 expert_watchdog.py >> "$LOG" 2>&1 || stamp "Expert watchdog: FAILED"
fi

stamp "Cron runner: complete"
