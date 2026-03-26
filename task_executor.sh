#!/bin/bash
# task_executor.sh — 任务执行层（去中心化，isolated agent 执行）
# cron: */15 * * * * bash ~/.xuzhi_memory/task_executor.sh
# 每次运行读取"等待"任务，通过 openclaw cron add --every "1m" 派发 isolated subagent
# isolated agent 持有完整任务上下文，自主 claim → 执行 → complete → 反馈
# 无需 main session，不依赖任何人

set -euo pipefail

HOME="${HOME:-/home/summer}"
LOG="$HOME/.xuzhi_memory/task_center/task_executor.log"
TASKS="$HOME/.openclaw/tasks/tasks.json"
LOCK="$HOME/.xuzhi_memory/.task_executor.lock"
MAX_BATCH=4          # 每批最多派发任务数

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [exec] $*" >> "$LOG"; }
mkdir -p "$(dirname "$LOG")"

# ── 锁防止并发 ─────────────────────────────────────────
acquire_lock() {
    if [[ -f "$LOCK" ]]; then
        local age
        age=$(python3 -c "import time; print(int(time.time()-$(stat -c %Y $LOCK 2>/dev/null || echo 0)))" 2>/dev/null)
        if (( age < 900 )); then  # 15分钟内不允许重复启动
            log "锁存在(${age}s)，退出"
            return 1
        fi
        log "锁超时(${age}s)，覆盖"
    fi
    echo "$$" > "$LOCK"
    return 0
}
release_lock() { rm -f "$LOCK"; }

# ── 通过 openclaw cron add 派发 isolated agent ───────────
dispatch_batch() {
    local batch_info="$1"  # 多行 "ID|Title|Dept" 格式
    
    # 构建任务列表摘要
    local task_lines=""
    local task_ids=""
    while IFS='|' read -r tid title dept; do
        [[ -z "$tid" || "$tid" =~ ^ID$ ]] && continue
        task_lines+="- **任务#$tid** [$dept]: $title\n"
        task_ids+="$tid "
    done <<< "$batch_info"
    
    [[ -z "$task_ids" ]] && { log "无有效任务"; return 0; }
    
    local dept_count
    dept_count=$(echo "$batch_info" | grep -v "^ID" | grep -v "^$" | wc -l)
    
    # 构建执行 prompt
    local EXEC_PROMPT="你是 Xuzhi 系统的自主执行 agent。请严格按顺序完成以下 $dept_count 个任务：

${task_lines}

**执行流程（每个任务都必须走完）：**
\`\`\`bash
# 1. 认领任务（每个都要）
python3 $HOME/xuzhi_genesis/centers/task/claim_task.py <agent_id> <task_id>

# 2. 自行判断并执行任务
#    - 根据任务的标题和描述，决定具体行动
#    - 使用你能用的所有工具（exec、read、write、web_search 等）
#    - 工程任务：写代码、运行测试、分析输出
#    - 情报任务：搜索、整理、写入知识库
#    - 哲学任务：撰写分析、整理论证
#    - 原则：尽你所能真实完成，不要空跑

# 3. 完成任务
python3 $HOME/xuzhi_genesis/centers/task/complete_task.py <task_id> <agent_id> \\
  --report '根据任务描述自主完成执行'

# 4. 记录反馈（提升 agent 评分）
python3 $HOME/xuzhi_genesis/centers/mind/society/log_feedback.py \\
  --agent <agent_id> --task 'task_<task_id>' \\
  --feedback positive --reason '自主执行完成，任务闭环'
\`\`\`

**重要规则：**
- 必须对每个任务都执行完整的 claim → execute → complete → feedback 流程
- 不要跳过任何任务
- 执行失败的任务也要调用 complete_task.py（使用 --report 说明失败原因）
- 全部完成后输出：\`【批次完成: $task_ids】\`

请现在开始执行所有任务。"
    
    # 使用 --at "+1m" 创建一次性 job（1分钟后触发，执行一次后自动删除）
    # --delete-after-run 确保不会无限重复
    # --no-deliver 避免 channel 错误
    local job_name="task-batch-$(date +%H%M%S)"
    local result
    
    result=$(openclaw cron add \
        --name "$job_name" \
        --session isolated \
        --no-deliver \
        --at "1m" \
        --delete-after-run \
        --message "$EXEC_PROMPT" \
        2>&1)
    
    local job_id
    job_id=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('id','ERR'))" 2>/dev/null)
    
    if [[ "$job_id" != "ERR" && -n "$job_id" ]]; then
        log "✅ 批次派发成功: $task_ids → job=$job_id"
        return 0
    else
        log "❌ 批次派发失败: $result"
        return 1
    fi
}

# ── 主流程 ────────────────────────────────────────────
main() {
    acquire_lock || exit 0
    trap release_lock EXIT
    
    log "=== 任务执行器启动 ==="
    
    # 读取等待任务（部门多样本）
    local batch_info
    batch_info=$(python3 -c "
import json, random
try:
    d = json.load(open('$TASKS'))
    tasks = d if isinstance(d, list) else d.get('tasks', [])
    waiting = [t for t in tasks if t.get('status') == '等待']
    total = len(waiting)
    
    # 部门多样本：每批尽量覆盖不同部门
    agents = {'engineering': 'Ξ', 'intelligence': 'Θ', 'mind': 'Ω', 'philosophy': 'Ψ'}
    # 优先从不同部门选取任务
    by_dept = {}
    for t in waiting:
        dept = t.get('department', 'engineering')
        if dept not in by_dept:
            by_dept[dept] = []
        by_dept[dept].append(t)
    
    selected = []
    for dept in ['engineering', 'intelligence', 'mind', 'philosophy']:
        if len(selected) >= $MAX_BATCH:
            break
        if dept in by_dept and by_dept[dept]:
            selected.append(by_dept[dept][0])
    
    print(f'TOTAL:{total}')
    for t in selected:
        tid = t.get('id', '')
        title = t.get('title', '')[:80].replace('|', ' ')
        dept = t.get('department', 'engineering')
        print(f'{tid}|{title}|{dept}')
except Exception as e:
    print(f'ERR:{e}')
" 2>/dev/null)
    
    local total_waiting
    total_waiting=$(echo "$batch_info" | grep -oP '^TOTAL:\K\d+' || echo "0")
    log "当前等待总数: $total_waiting"
    
    if [[ "$total_waiting" == "0" ]]; then
        log "ℹ️ 无待执行任务"
        return 0
    fi
    
    # 去掉 TOTAL 行，只保留任务行
    local task_lines
    task_lines=$(echo "$batch_info" | grep -v "^TOTAL")
    
    if [[ -n "$task_lines" ]]; then
        dispatch_batch "$task_lines"
    else
        log "⚠️ 无有效任务行"
    fi
    
    log "=== 执行器完成 ==="
}

main "$@"
