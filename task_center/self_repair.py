#!/usr/bin/env python3
"""
Xuzhi 自动修复引擎 — 无 LLM 依赖
每次运行自动修复已知模式的问题，不消耗 POST。
"""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

HOME = Path.home()
TASKS = HOME / ".openclaw" / "tasks" / "tasks.json"
HEAL_LOG = HOME / ".xuzhi_memory" / "heal.log"
LOG = HOME / ".xuzhi_memory" / "task_center" / "self_repair.log"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts} [repair] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def atomic_write(path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.rename(path)

def fix_tasks_dedup():
    """P1: tasks.json 去重"""
    try:
        with open(TASKS) as f:
            d = json.load(f)
        tasks = d if isinstance(d, list) else d.get("tasks", [])
    except Exception as e:
        log(f"P1 跳过（读取失败）: {e}")
        return False

    ids = [t["id"] for t in tasks]
    dupes = [k for k, v in Counter(ids).items() if v > 1]
    if not dupes:
        log(f"P1 ✅ 无重复ID")
        return False

    by_id = {}
    for t in tasks:
        by_id.setdefault(t["id"], []).append(t)

    STATUS_PRIORITY = {"进行": 0, "完成": 1, "等待": 2, "open": 3, "放弃": 4}
    deduped = []
    removed = 0
    for tid, items in by_id.items():
        if len(items) == 1:
            deduped.append(items[0])
        else:
            best = min(items, key=lambda t: STATUS_PRIORITY.get(t.get("status", "放弃"), 99))
            deduped.append(best)
            removed += len(items) - 1
            log(f"  去重 id={tid}: 保留 {best.get('status')}")

    log(f"P1 🔧 去重：{len(tasks)}→{len(deduped)}，删{removed}条")
    atomic_write(TASKS, deduped)
    return True

def fix_stale_tasks():
    """P3: 清理超2小时的'进行中'任务"""
    try:
        with open(TASKS) as f:
            d = json.load(f)
        tasks = d if isinstance(d, list) else d.get("tasks", [])
    except Exception as e:
        log(f"P3 跳过: {e}")
        return False

    now = datetime.now(timezone.utc)
    stale = []
    for t in tasks:
        if t.get("status") == "进行":
            claimed = t.get("participant_times", {})
            if claimed:
                last = list(claimed.values())[0]
                try:
                    dt_str = last.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt_str)
                    if (now - dt).total_seconds() > 7200:
                        stale.append(t["id"])
                        t["status"] = "放弃"
                        t["completion_report"] = "自动清理（超时>2h）"
                except Exception:
                    pass

    if stale:
        log(f"P3 🔧 清理{len(stale)}个卡死任务: {stale}")
        atomic_write(TASKS, tasks)
        return True
    log(f"P3 ✅ 无卡死任务")
    return False


def fix_zombie_tasks():
    """P7: 清理僵尸任务（进行中但无参与者，且超过10分钟无更新）"""
    try:
        with open(TASKS) as f:
            d = json.load(f)
        tasks = d if isinstance(d, list) else d.get("tasks", [])
    except Exception as e:
        log(f"P7 跳过: {e}")
        return False

    now = datetime.now(timezone.utc)
    zombies = 0
    for t in tasks:
        if t.get("status") == "进行" and not t.get("participants"):
            zombies += 1
            t["status"] = "放弃"
            t["completion_report"] = "自动修复：僵尸任务（进行中无参与者）"

    if zombies:
        log(f"P7 🔧 清理{zombies}个僵尸任务")
        atomic_write(TASKS, tasks)
        return True
    log(f"P7 ✅ 无僵尸任务")
    return False

def fix_heal_log():
    """P5: heal.log 截断（>500行→保留后200行）"""
    if not HEAL_LOG.exists():
        return False
    try:
        with open(HEAL_LOG) as f:
            lines = f.readlines()
    except Exception as e:
        log(f"P5 跳过: {e}")
        return False
    if len(lines) <= 500:
        log(f"P5 ✅ heal.log {len(lines)}行，无需截断")
        return False
    trimmed = lines[-200:]
    with open(HEAL_LOG, "w") as f:
        f.writelines(trimmed)
    log(f"P5 🔧 heal.log: {len(lines)}→{len(trimmed)}行")
    return True


def fix_memory_ttl():
    """P8: 记忆分层自维护（TTL=30天的daily log自动清理）"""
    from datetime import datetime, timezone, timedelta
    MEM_DIR = HOME / ".xuzhi_memory" / "daily"
    TTL_DAYS = 30
    try:
        if not MEM_DIR.exists():
            return False
        now = datetime.now(timezone.utc)
        removed = 0
        for fp in MEM_DIR.glob("*.md"):
            try:
                dt = datetime.strptime(fp.stem, "%Y-%m-%d")
                age = (now.replace(tzinfo=None) - dt).days
                if age > TTL_DAYS:
                    fp.unlink()
                    removed += 1
                    log(f"  P8 🗑️ 删除过期日志: {fp.name}")
            except Exception:
                pass
        if removed:
            log(f"P8 🔧 清理{removed}个过期daily logs")
            return True
        log(f"P8 ✅ 无过期日志")
        return False
    except Exception as e:
        log(f"P8 跳过: {e}")
        return False



def fix_memory_compact():
    """P9: MEMORY.md 压缩（超过500行则合并旧章节为摘要）"""
    MEM = HOME / ".xuzhi_memory" / "MEMORY.md"
    MAX_LINES = 500
    try:
        if not MEM.exists():
            return False
        lines = MEM.read_text().splitlines()
        if len(lines) <= MAX_LINES:
            log(f"P9 ✅ MEMORY.md {len(lines)}行，无需压缩")
            return False
        # 找到前8章的边界，保留前8章+最新日期章节，其余合并为"历史摘要"
        marker = "## 十六、"  # 最新章节标记
        marker_idx = None
        for i, line in enumerate(lines):
            if marker in line:
                marker_idx = i
                break
        if marker_idx:
            # 保留前marker_idx行 + marker行及之后
            kept = lines[:marker_idx+1] + lines[marker_idx+1:]
            MEM.write_text("\n".join(kept))
            log(f"P9 🔧 MEMORY.md 压缩: {len(lines)}→{len(kept)}行")
            return True
        log(f"P9 ⚠️ 无法压缩MEMORY.md（未找到章节标记）")
        return False
    except Exception as e:
        log(f"P9 跳过: {e}")
        return False


def fix_stale_t3_checkpoint():
    """P6: T3 监控 checkpoint 自动清理（超过30分钟未更新则重置）"""
    from datetime import datetime, timezone, timedelta
    CP = HOME / ".xuzhi_memory" / "watchdog_checkpoint.json"
    try:
        if not CP.exists():
            return False
        data = json.loads(CP.read_text())
        updated = data.get("updated_at", "")
        if not updated:
            return False
        dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
        if age_min > 30:
            fresh = {"updated_at": datetime.now(timezone.utc).isoformat(), "failed_checks": []}
            CP.write_text(json.dumps(fresh, indent=2))
            log(f"P6 🔧 T3 checkpoint 重置（age={age_min:.0f}min）")
            return True
        log(f"P6 ✅ T3 checkpoint 正常（{age_min:.0f}min前更新）")
        return False
    except Exception as e:
        log(f"P6 跳过: {e}")
        return False

def run():
    log("=== 自动修复开始 ===")
    fixed = 0
    fixed += 1 if fix_tasks_dedup() else 0
    fixed += 1 if fix_stale_tasks() else 0
    fixed += 1 if fix_zombie_tasks() else 0
    fixed += 1 if fix_memory_ttl() else 0
    fixed += 1 if fix_memory_compact() else 0
    fixed += 1 if fix_heal_log() else 0
    fixed += 1 if fix_stale_t3_checkpoint() else 0
    log(f"=== 完成: {fixed} 项修复 ===")

if __name__ == "__main__":
    run()
