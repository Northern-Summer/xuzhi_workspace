#!/usr/bin/env python3
"""
agent_pulse_isolated.py — 通过 sessions_send 向所有agent发送触发消息
由 cron isolated agent 调用
"""
import json, sys, os
sys.path.insert(0, '/usr/local/share/.config/yarn/global/node_modules/openclaw')

# 当 cron isolated agent 运行时，它自己是 main session
# 使用 OpenClaw sessions_send RPC 端点
# 实际上，这个脚本会被作为 cron job 的 message 发送，
# 所以它的"输出"就是回复内容
# 
# 但更好的方式：直接通过 subprocess 调用 openclaw CLI

HOME = "/home/summer"
MSG = "系统心跳触发。请处理任务队列中的等待任务。回复 DONE 或 HEARTBEAT_OK。"

AGENTS = [
    ("Ξ", "agent:main:main"),
    ("Φ", "agent:phi:discord:channel:1486694791738691604"),
    ("Δ", "agent:delta:main"),
    ("Θ", "agent:theta:main"),
    ("Γ", "agent:gamma:main"),
    ("Ω", "agent:omega:main"),
    ("Ψ", "agent:psi:main"),
]

print("=== agent_pulse: 开始 ===")
for agent, session_key in AGENTS:
    import subprocess
    result = subprocess.run(
        ["openclaw", "message", "send",
         "--session-key", session_key,
         "--message", MSG],
        capture_output=True, text=True, timeout=15,
        cwd=HOME, env={**os.environ, "HOME": HOME}
    )
    status = "✅" if result.returncode == 0 else f"❌ {result.stderr[:50]}"
    print(f"  {status} {agent}")
print("=== agent_pulse: 完成 ===")
print("HEARTBEAT_OK")
