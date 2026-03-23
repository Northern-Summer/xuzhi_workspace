#!/bin/bash
# wd_consumer.sh — WD 队列消费者（bash纯文件操作）
# 被 isolated agentTurn cron 调用，或直接被 watchdog_task_engine.sh 调用
# 功能：逐条执行 watchdog_command_queue.json 中的命令

HOME="${HOME:-/home/summer}"
QUEUE="$HOME/.xuzhi_memory/watchdog_command_queue.json"
CHECKPOINT="$HOME/.xuzhi_memory/watchdog_checkpoint.json"
LOG="$HOME/.xuzhi_memory/wd_consumer.log"
L2="$HOME/.xuzhi_memory/shared_commitments.md"
L1_DIR="$HOME/.xuzhi_memory/daily"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [WD] $*" >> "$LOG"; }

# 读取并清空队列（原子操作）
read_and_clear_queue() {
    python3 -c "
import json, sys
try:
    with open('$QUEUE') as f:
        d = json.load(f)
    cmds = d.get('commands', [])
    # 清空队列
    with open('$QUEUE', 'w') as f:
        json.dump({'commands': []}, f)
    print(json.dumps(cmds))
except:
    print('[]')
" 2>/dev/null
}

# 更新 checkpoint
update_checkpoint() {
    python3 -c "
import json, datetime
d = {'last_run': '$(date -u +%Y-%m-%dT%H:%M:%SZ)', 'processed': $1, 'queue_cleared': True}
json.dump(d, open('$CHECKPOINT', 'w'))
" 2>/dev/null
}

# 写 L1 日志
write_l1() {
    local msg="$1"
    local l1_file="$L1_DIR/$(date +%Y-%m-%d).md"
    mkdir -p "$L1_DIR"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [WD] $msg" >> "$l1_file"
}

main() {
    log "=== WD 消费者启动 ==="
    
    local cmds_json
    cmds_json=$(read_and_clear_queue)
    
    local count
    count=$(echo "$cmds_json" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null)
    
    if (( count == 0 )); then
        log "队列空，无需处理"
        update_checkpoint 0
        return 0
    fi
    
    log "处理 $count 条命令"
    
    echo "$cmds_json" | python3 -c "
import json, sys, subprocess, time
cmds = json.load(sys.stdin)
for i, cmd in enumerate(cmds):
    c = cmd.get('cmd')
    sk = cmd.get('session_key','')
    msg = cmd.get('msg','')
    note = cmd.get('note','')
    
    print(f'[{i+1}/{len(cmds)}] cmd={c} key={sk}', flush=True)
    
    if c == 'sessions_send' and sk and msg:
        # 使用 openclaw send 命令发送
        import os
        escaped_msg = msg.replace('\"', '\\\"').replace('\n', ' ')
        result = subprocess.run(
            ['openclaw', 'sessions', 'send', '--session', sk, '--message', msg],
            capture_output=True, text=True, timeout=30, cwd=os.environ.get('HOME','/home/summer')
        )
        status = 'OK' if result.returncode == 0 else f'FAIL({result.returncode})'
        print(f'  → {status}', flush=True)
    else:
        print(f'  → SKIP: unknown cmd={c}', flush=True)
" 2>/dev/null
    
    log "命令处理完成"
    update_checkpoint $count
    write_l1 "WD队列处理完成: $count 条命令"
}

main "$@"
