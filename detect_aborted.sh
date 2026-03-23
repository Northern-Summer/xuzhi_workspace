#!/bin/bash
# detect_aborted.sh — 检测 aborted sessions 并写结果到文件
# 由 self_heal.sh 调用，或直接由 cron 调用
# 输出：aborted_sessions.txt（每行一个 session_key）

OUTPUT="${HOME}/.xuzhi_memory/aborted_sessions.txt"
QUEUE="${HOME}/.xuzhi_memory/watchdog_command_queue.json"

# 生成 micro-agent 任务检测 aborted sessions
python3 << 'PYEOF'
import json
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SESSIONS_FILE = HOME / '.openclaw' / 'agents' / 'sessions_detect.json'

# 生成检测脚本
detect_script = '''
import json
from pathlib import Path

results = []
for agent_dir in Path.home().glob(".openclaw/agents/*"):
    if not agent_dir.is_dir():
        continue
    sessions_dir = agent_dir / "sessions"
    if not sessions_dir.exists():
        continue
    for sf in sessions_dir.glob("*.jsonl"):
        try:
            with open(sf) as f:
                lines = f.readlines()
            if not lines:
                continue
            last = json.loads(lines[-1])
            if last.get("role") != "assistant":
                continue
            # aborted 标记在 session list API 里，不在 transcript 里
            # 但 stopReason == "abort" 意味着 aborted
            if last.get("stopReason") == "abort" or last.get("errorMessage"):
                results.append(str(sf))
        except:
            pass
print(json.dumps(results))
'''

import tempfile, os
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(detect_script)
    script_path = f.name

result = subprocess.run(['python3', script_path], capture_output=True, text=True, timeout=15)
os.unlink(script_path)

try:
    files = json.loads(result.stdout)
    print(json.dumps(files))
except:
    print(json.dumps([]))
PYEOF

# 输出到文件
echo "" > "$OUTPUT"
