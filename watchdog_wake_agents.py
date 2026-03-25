#!/usr/bin/env python3
"""
watchdog_wake_agents.py — Gateway 恢复后唤醒 agents
幂等，只通知 main session 一个，其他 agents 等下次心跳自醒。
不依赖 agents 主动轮询文件。

设计原则：
- watchdog_daemon 只负责 Gateway 健康检查和重启（单一职责）
- recovery 唤醒只通知 main session（main session 心跳正常，能处理消息）
- 其他 agents 在下次心跳时自然恢复就绪（无需显式唤醒）
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
TOKEN_FILE = HOME / ".openclaw" / "openclaw.json"
LOG_FILE   = HOME / ".xuzhi_watchdog" / "wake.log"

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def rpc_call(method: str, params: dict = None) -> dict:
    """幂等 RPC 调用"""
    with open(TOKEN_FILE) as f:
        token = json.load(f)["gateway"]["auth"]["token"]
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": method,
        "params": params or {}
    }).encode()
    req = urllib.request.Request(
        "http://localhost:18789/rpc",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def wait_gateway(timeout=30) -> bool:
    """等待 Gateway 就绪（幂等）"""
    for _ in range(timeout):
        try:
            rpc_call("sessions.list", {"limit": 1})
            return True
        except Exception:
            pass
    return False

def wake_main():
    """只唤醒 main session（Ξ）"""
    if not wait_gateway(timeout=20):
        log("Gateway 20s 内未就绪，跳过")
        return

    log("Gateway 已就绪，发送恢复通知到 main session")
    try:
        rpc_call("sessions.send", {
            "sessionKey": "agent:main:main",
            "message": (
                "【系统恢复】Gateway 已自动重启。"
                "请确认所有 agents 状态，如有异常请处理。"
            ),
            "timeoutSeconds": 30
        })
        log("✅ main session 恢复通知已发送")
    except Exception as e:
        log(f"❌ main session 通知失败: {e}")

if __name__ == "__main__":
    wake_main()
