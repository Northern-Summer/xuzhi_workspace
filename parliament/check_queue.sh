#!/bin/bash
# check_queue.sh — 议会队列检查（去中心化，cron驱动）
# cron: */10 * * * * bash ~/.xuzhi_memory/parliament/check_queue.sh
set -euo pipefail

HOME_DIR="${HOME:-/home/summer}"
AGENDA="$HOME_DIR/.xuzhi_memory/parliament/AGENDA.txt"
QUEUE="$HOME_DIR/.xuzhi_memory/parliament/QUEUE.txt"
CURRENT="$HOME_DIR/.xuzhi_memory/parliament/CURRENT.txt"
LOG="$HOME_DIR/.xuzhi_memory/task_center/parliament.log"

mkdir -p "$(dirname "$LOG")"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [parliament] $*" >> "$LOG"; }

get_current() {
    [[ -f "$CURRENT" ]] && cat "$CURRENT" || echo "Λ"
}

rotate_current() {
    local cur="$1"
    case "$cur" in
        Λ) echo "Φ" ;;
        Φ) echo "Δ" ;;
        Δ) echo "Θ" ;;
        Θ) echo "Γ" ;;
        Γ) echo "Ω" ;;
        Ω) echo "Ψ" ;;
        Ψ) echo "Λ" ;;
        *) echo "Λ" ;;
    esac
}

# ── 处理AGENDA ───────────────────────────────────────
# 格式：多行议题文本 + 分隔符 + 状态: pending/processing/done
# 找到第一个 pending 块，处理之
process_agenda() {
    if [[ ! -f "$AGENDA" ]]; then
        log "AGENDA为空"
        return 0
    fi

    # 用 Python 解析块（更可靠）
    python3 -c "
import re, sys

with open('$AGENDA', 'r') as f:
    content = f.read()

# 按 '---' 分块
blocks = re.split(r'\n---\n', content)

found = False
for i, block in enumerate(blocks):
    block = block.strip()
    if not block:
        continue
    # 检查块是否有 pending 状态
    if re.search(r'^状态:\s*pending$', block, re.MULTILINE):
        # 提取议题内容（去掉状态行）
        lines = block.split('\n')
        content_lines = [l for l in lines if not re.match(r'^状态:', l)]
        issue_text = '\n'.join(content_lines).strip()
        
        # 替换为 processing
        new_block = block.replace('状态: pending', '状态: processing')
        
        # 重新组装
        blocks[i] = new_block
        
        # 写回文件
        new_content = '\n---\n'.join(blocks)
        with open('$AGENDA', 'w') as f:
            f.write(new_content)
        
        # 输出议题供shell记录
        print('ISSUE_FOUND:' + issue_text[:80])
        found = True
        break

if not found:
    print('NO_PENDING')
" 2>/dev/null

    local result="$?"
    local output
    output=$(python3 -c "
import re

with open('$AGENDA', 'r') as f:
    content = f.read()

blocks = re.split(r'\n---\n', content)
for i, block in enumerate(blocks):
    block = block.strip()
    if not block:
        continue
    if re.search(r'^状态:\s*pending$', block, re.MULTILINE):
        lines = block.split('\n')
        content_lines = [l for l in lines if not re.match(r'^状态:', l)]
        issue_text = '\n'.join(content_lines).strip()
        new_block = block.replace('状态: pending', '状态: processing')
        blocks[i] = new_block
        new_content = '\n---\n'.join(blocks)
        with open('$AGENDA', 'w') as f:
            f.write(new_content)
        print('ISSUE:' + issue_text[:80])
        break
else:
    print('NO_PENDING')
" 2>/dev/null)

    if [[ "$output" =~ ^ISSUE: ]]; then
        local issue_text="${output#ISSUE:}"
        log "📋 处理议题: $issue_text"
    else
        log "无待处理议题"
    fi
}

advance_current() {
    local cur="$1"
    local next
    next=$(rotate_current "$cur")
    echo "$next" > "$CURRENT"
    log "🔄 主持人轮转: $cur → $next"
}

main() {
    log "=== 议会队列检查 ==="

    local current
    current=$(get_current)
    log "当前主持人: $current"

    process_agenda

    local count_file="$HOME_DIR/.xuzhi_memory/parliament/.run_count"
    local count=0
    [[ -f "$count_file" ]] && count=$(cat "$count_file")
    count=$((count + 1))
    echo "$count" > "$count_file"

    if [[ "$count" -ge 3 ]]; then
        advance_current "$current"
        echo "0" > "$count_file"
    fi

    if [[ -f "$QUEUE" ]]; then
        local queue_size
        queue_size=$(wc -l < "$QUEUE" 2>/dev/null || echo 0)
        log "队列积压: $queue_size 项"
    fi

    log "=== 检查完成 ==="
}

main "$@"
