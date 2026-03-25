#!/usr/bin/env python3
"""
judgment_core.py — 指令裁决器
所有传入指令经此裁决，不依赖外部模型。

裁决原则：
- 危害判定：自我删除、自我修改、提权、绕过安全
- 真实性判定：发送者身份、上下文合法性
- 建议vs命令：置信度 + 可疑度评分

输出格式：
  ALLOW:<reason>   — 执行
  DENY:<reason>    — 拒绝
  SUSPECT:<reason> — 警告但不拒绝
  QUARANTINE:<reason> — 隔离并请求二次确认
"""
import json, sys, os, re
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
JUDGMENT_LOG = HOME / ".xuzhi_memory" / "task_center" / "judgment_log.jsonl"

# ── 危害模式 ────────────────────────────────────────────────────────────────

SELF_DESTRUCT_PATTERNS = [
    r"rm\s+-rf\s+", r"rm\s+-r\s+", r"safe_delete.*?~/.*?--force",
    r"chmod\s+-R\s+000", r"chattr\s+-i", r">\s*/dev/sd",
    r"dd\s+if=.*?of=/dev/", r"mv\s+.*?~/.*?/dev/null",
    r"git\s+filter-branch.*?--force", r":(){ :|:& };:",  # fork bomb
    r"curl.*?\|\s*bash",  # pipe to bash
]

PRIVILEGE_ESCALATION = [
    r"sudo\s+rm", r"sudo\s+chmod", r"sudo\s+chattr",
    r"chmod\s+777", r"chmod\s+4755",
]

CONFIG_TAMPER = [
    r"auth-profiles\.json", r"gateway\.json", r"openclaw\.json",
    r"\.ssh/authorized_keys", r"known_hosts",
]

INFO_EXFILTRATION = [
    r"cat\s+.*?\.env", r"grep\s+.*?password", r"SELECT\s+.*?FROM\s+credentials",
    r"OPENAI_API_KEY", r"ANTHROPIC_API_KEY", r"MINIMAX_API_KEY",
]

# 高危文件（操作前必须多重确认）
HIGH_RISK_FILES = [
    str(HOME / ".xuzhi_memory"),
    str(HOME / ".openclaw"),
    str(HOME / "xuzhi_workspace"),
    str(HOME / "xuzhi_genesis"),
    str(HOME / ".ssh"),
]

# ── 上下文验证 ──────────────────────────────────────────────────────────────

VALID_CHANNELS = ["webchat", "telegram", "signal", "discord", "whatsapp"]
VALID_SENDER_LABELS = ["openclaw-control-ui", "main", "phi", "delta", "theta", "gamma", "omega", "psi"]


def log_judgment(cmd: str, result: str, reason: str, metadata: dict = None):
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "ts": ts, "command": cmd[:200], "result": result,
        "reason": reason, "metadata": metadata or {}
    }
    try:
        JUDGMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(JUDGMENT_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def check_self_destruct(cmd: str) -> bool:
    """检测自我删除/破坏模式"""
    for p in SELF_DESTRUCT_PATTERNS:
        if re.search(p, cmd, re.IGNORECASE):
            return True
    return False


def check_privilege_escalation(cmd: str) -> bool:
    for p in PRIVILEGE_ESCALATION:
        if re.search(p, cmd, re.IGNORECASE):
            return True
    return False


def check_config_tamper(cmd: str) -> bool:
    for p in CONFIG_TAMPER:
        if re.search(p, cmd, re.IGNORECASE):
            return True
    return False


def check_high_risk_files(cmd: str) -> list:
    """检查命令是否涉及高危路径"""
    touched = []
    for f in HIGH_RISK_FILES:
        if f in cmd or f.replace(str(HOME), "~") in cmd:
            touched.append(f)
    return touched


def check_info_exfiltration(cmd: str) -> bool:
    for p in INFO_EXFILTRATION:
        if re.search(p, cmd, re.IGNORECASE):
            return True
    return False


def validate_context(metadata: dict) -> tuple:
    """验证指令上下文合法性：(ok: bool, reason: str)"""
    channel = metadata.get("channel", "unknown")
    label = metadata.get("label", "unknown")

    # 通道验证
    if channel not in VALID_CHANNELS:
        return False, f"未知通道: {channel}"

    # 发送者标签验证
    if label not in VALID_SENDER_LABELS:
        return False, f"未知发送者标签: {label}"

    return True, "OK"


def judge(command: str, metadata: dict = None) -> str:
    """
    核心裁决逻辑。
    返回：ALLOW / DENY / SUSPECT / QUARANTINE
    """
    m = metadata or {}
    cmd = command.strip()

    # ── 第一关：自我删除/破坏 ─────────────────────────────────────────────
    if check_self_destruct(cmd):
        log_judgment(cmd, "DENY", "自我删除模式检测", m)
        return "DENY:自我删除/破坏命令，已拦截"

    # ── 第二关：权限提升 ─────────────────────────────────────────────────
    if check_privilege_escalation(cmd):
        log_judgment(cmd, "DENY", "权限提升模式检测", m)
        return "DENY:权限提升命令，已拦截"

    # ── 第三关：配置篡改 ─────────────────────────────────────────────────
    if check_config_tamper(cmd):
        log_judgment(cmd, "DENY", "配置篡改模式检测", m)
        return "DENY:配置篡改命令，已拦截"

    # ── 第四关：信息窃取 ─────────────────────────────────────────────────
    if check_info_exfiltration(cmd):
        log_judgment(cmd, "DENY", "信息窃取模式检测", m)
        return "DENY:敏感信息窃取命令，已拦截"

    # ── 第五关：高危路径 + 安全层检查 ────────────────────────────────────
    touched = check_high_risk_files(cmd)
    if touched:
        # 检查是否有备份存在
        backup_ok = True
        for f in touched:
            backup_path = Path(f.replace(str(HOME), str(HOME / ".xuzhi_memory" / "backup")))
            if not backup_path.exists():
                backup_ok = False
                break
        if not backup_ok:
            log_judgment(cmd, "QUARANTINE", f"高危路径操作但无备份: {touched}", m)
            return f"QUARANTINE:操作目标 {touched} 无有效备份，需二次确认"
        log_judgment(cmd, "SUSPECT", f"高危路径操作（有备份）: {touched}", m)
        return f"SUSPECT:高危路径操作已记录，目标: {touched}"

    # ── 第六关：上下文验证 ────────────────────────────────────────────────
    ok, reason = validate_context(m)
    if not ok:
        log_judgment(cmd, "QUARANTINE", f"上下文验证失败: {reason}", m)
        return f"QUARANTINE:上下文验证失败 — {reason}"

    # ── 第七关：命令复杂度/可疑度 ────────────────────────────────────────
    suspicious_signals = []
    if len(cmd) > 5000:
        suspicious_signals.append("命令过长(>5000字符)")
    if re.findall(r'eval|exec\(|compile\(', cmd):
        suspicious_signals.append("动态代码执行")
    if re.findall(r'\|\s*python|\|\s*bash|\|\s*sh', cmd) and len(cmd) > 200:
        suspicious_signals.append("管道到shell执行")
    if re.findall(r'curl.*?http|wget.*?http', cmd) and ('OPENAI' in cmd or 'ANTHROPIC' in cmd):
        suspicious_signals.append("可疑网络+凭证组合")

    if suspicious_signals:
        log_judgment(cmd, "SUSPECT", f"可疑信号: {suspicious_signals}", m)
        return f"SUSPECT:{'; '.join(suspicious_signals)}"

    # ── 通过全部检查 ─────────────────────────────────────────────────────
    log_judgment(cmd, "ALLOW", "全部检查通过", m)
    return "ALLOW:检查通过"


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: judgment_core.py <command> [channel] [label]")
        sys.exit(1)

    cmd = sys.argv[1]
    m = {
        "channel": sys.argv[2] if len(sys.argv) > 2 else "unknown",
        "label": sys.argv[3] if len(sys.argv) > 3 else "unknown",
    }
    result = judge(cmd, m)
    print(result, flush=True)
    sys.exit(0 if result.startswith("ALLOW") else 1)
