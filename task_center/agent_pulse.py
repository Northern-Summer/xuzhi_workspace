#!/usr/bin/env python3
"""
agent_pulse.py — 向所有7个agent的活跃session发送触发消息
由cron每10分钟调用一次
"""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
LOG = HOME / ".xuzhi_memory" / "task_center" / "agent_pulse.log"

AGENTS = {
    "Ξ": "agent:main:main",
    "Φ": "agent:phi:discord:channel:1486694791738691604",
    "Δ": "agent:delta:main",
    "Θ": "agent:theta:main",
    "Γ": "agent:gamma:main",
    "Ω": "agent:omega:main",
    "Ψ": "agent:psi:main",
}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def sessions_send_msg(session_key: str, message: str) -> bool:
    """向指定session发送消息"""
    try:
        result = subprocess.run(
            [
                "python3", "-c",
                f"""
import json, urllib.request, urllib.error
token = json.loads(open('{HOME}/.openclaw/openclaw.json').read())['gateway']['auth']['token']
payload = json.dumps({{
    "jsonrpc": "2.0", "id": 1,
    "method": "session/message",
    "params": {{"sessionKey": "{session_key}", "message": {json.dumps(message)}}}
}}).encode()
req = urllib.request.Request(
    "http://localhost:18789/rpc",
    data=payload,
    headers={{"Content-Type": "application/json", "Authorization": f"Bearer {{token}}"}}
)
with urllib.request.urlopen(req, timeout=15) as resp:
    return json.loads(resp.read())
"""
            ],
            capture_output=True, text=True, timeout=20
        )
        return result.returncode == 0
    except Exception as e:
        log(f"  ❌ {session_key}: {e}")
        return False

def main():
    log("=== agent_pulse: 开始 ===")
    message = "系统心跳触发。请处理任务队列中的等待任务。回复 DONE 或 HEARTBEAT_OK。"
    
    sent = 0
    for agent, session_key in AGENTS.items():
        ok = sessions_send_msg(session_key, message)
        status = "✅" if ok else "❌"
        log(f"  {status} {agent} → {session_key}")
        if ok:
            sent += 1
    
    log(f"=== agent_pulse: 发送 {sent}/{len(AGENTS)} ===")

if __name__ == "__main__":
    main()
