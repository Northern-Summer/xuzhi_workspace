#!/usr/bin/env python3
"""
constitution_verifier.py — 宪法运行时一致性验证器
启动时检查 sticky-bit 宪法文件 hash 是否与上次记录一致。
不一致 → quarantine 该次启动，不允许覆盖宪法。
"""
import json, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
PUBLIC_DIR = HOME / "xuzhi_genesis" / "public"
MEMORY_PUBLIC = HOME / ".xuzhi_memory" / "public"
HASH_DB = HOME / ".xuzhi_memory" / "task_center" / "constitution_hashes.json"
QUARANTINE = HOME / ".xuzhi_watchdog" / "constitution_alert"
LOG = HOME / ".xuzhi_memory" / "task_center" / "constitution_verifier.log"

# 必须存在的宪法文件
CONSTITUTION_FILES = [
    "GENESIS_CONSTITUTION.md",
    "SEVENTH_EPOCH.md",
    "VALIDATION_SYSTEM.md",
    "ELEGANCE_SYSTEM.md",
]

ALERT = """宪法文件哈希不一致！

上次记录的哈希与当前磁盘内容不匹配。
可能原因：
1. 外部修改（合法，需要人工授权更新哈希）
2. 未授权篡改（非法）

当前操作已 quarantined。
如需解锁，请运行：
  python3 constitution_verifier.py --authorize "<reason>"

如需查看差异：
  python3 constitution_verifier.py --diff
"""


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def get_file_hashes() -> dict:
    """计算所有宪法文件的当前 hash"""
    hashes = {}
    for fname in CONSTITUTION_FILES:
        for base in [PUBLIC_DIR, MEMORY_PUBLIC]:
            p = base / fname
            if p.exists():
                hashes[fname] = sha256_of(p)
                break
    return hashes


def load_hashes() -> dict:
    if HASH_DB.exists():
        try:
            return json.loads(HASH_DB.read_text())
        except Exception:
            pass
    return {}


def save_hashes(hashes: dict):
    HASH_DB.parent.mkdir(parents=True, exist_ok=True)
    HASH_DB.write_text(json.dumps({
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "hashes": hashes
    }, indent=2))


def verify() -> tuple:
    """
    验证宪法一致性。
    返回 (ok: bool, message: str, details: dict)
    """
    current = get_file_hashes()
    saved = load_hashes().get("hashes", {})

    if not saved:
        # 首次运行：保存当前哈希，不报错
        save_hashes(current)
        log("📋 首次运行，保存当前宪法哈希")
        return True, "first_run_hashes_saved", current

    # 比较
    mismatches = {}
    for fname, current_hash in current.items():
        saved_hash = saved.get(fname)
        if not saved_hash:
            mismatches[fname] = "missing_in_saved"
        elif saved_hash != current_hash:
            mismatches[fname] = {
                "saved": saved_hash,
                "current": current_hash,
            }

    for fname in saved:
        if fname not in current:
            mismatches[fname] = "file_missing"

    if mismatches:
        QUARANTINE.parent.mkdir(parents=True, exist_ok=True)
        QUARANTINE.write_text(json.dumps({
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "mismatches": mismatches,
            "alert": ALERT.strip(),
        }))
        log(f"🚨 宪法不一致: {list(mismatches.keys())}")
        return False, "hash_mismatch", mismatches

    log("✅ 宪法哈希一致")
    return True, "verified", {}


def authorize(reason: str):
    """人工授权后，更新哈希记录"""
    current = get_file_hashes()
    save_hashes(current)
    log(f"✅ 宪法已授权更新: {reason}")
    if QUARANTINE.exists():
        QUARANTINE.unlink()


def show_diff():
    """显示当前与记录的差异"""
    saved = load_hashes().get("hashes", {})
    current = get_file_hashes()
    for fname in set(list(saved.keys()) + list(current.keys())):
        s = saved.get(fname, "N/A")[:16]
        c = current.get(fname, "N/A")[:16]
        status = "✅" if s == c else "❌"
        print(f"{status} {fname}: saved={s}... current={c}...")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "--authorize":
        reason = sys.argv[2] if len(sys.argv) > 2 else "human_authorized"
        authorize(reason)
        print("AUTHORIZED")

    elif cmd == "--diff":
        show_diff()

    elif cmd == "--check":
        ok, msg, details = verify()
        print(json.dumps({"ok": ok, "reason": msg, "details": details}, indent=2), flush=True)
        sys.exit(0 if ok else 1)

    else:
        # 默认：验证
        ok, msg, details = verify()
        if ok:
            print("VERIFIED", flush=True)
        else:
            print(f"QUARANTINED: {msg}", flush=True)
            sys.exit(1)
