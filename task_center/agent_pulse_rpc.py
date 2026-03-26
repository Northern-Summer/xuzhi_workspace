#!/usr/bin/env python3
"""
agent_pulse_rpc.py — 向所有agent发送触发消息
由cron isolated agent调用（agent自身会执行tools）
"""
import json, urllib.request, urllib.error, time

HOME = "/home/summer"
TOKEN_FILE = HOME + "/.openclaw/openclaw.json"
GATEWAY = "http://localhost:18789"

AGENTS = [
    ("Ξ", "agent:main:main"),
    ("Φ", "agent:phi:discord:channel:1486694791738691604"),
    ("Δ", "agent:delta:main"),
    ("Θ", "agent:theta:main"),
    ("Γ", "agent:gamma:main"),
    ("Ω", "agent:omega:main"),
    ("Ψ", "agent:psi:main"),
]

MSG = "系统心跳触发。请处理任务队列中的等待任务。回复 DONE 或 HEARTBEAT_OK。"

def rpc(method, params):
    token = json.load(open(TOKEN_FILE))["gateway"]["auth"]["token"]
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        GATEWAY + "/rpc",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def send(session_key, message):
    try:
        result = rpc("session/message", {"sessionKey": session_key, "message": message})
        return True
    except Exception as e:
        return False

print("=== agent_pulse: 开始 ===")
ok_count = 0
for agent, key in AGENTS:
    ok = send(key, MSG)
    status = "✅" if ok else "❌"
    print(f"  {status} {agent}")
    if ok:
        ok_count += 1
print(f"=== agent_pulse: 完成 ({ok_count}/{len(AGENTS)}) ===")
print("DONE")
