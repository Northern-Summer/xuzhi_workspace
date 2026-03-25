#!/usr/bin/env python3
"""
Xuzhi 全局健康扫描仪 — 精确模式
- 零 LLM 消耗，纯文件扫描
- 自动汇总所有日志中的错误/警告
- 输出人类可读的优先级报告
- 无并发依赖，可任何时候运行
"""
import re
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LOG_DIRS = [
    Path.home() / ".xuzhi_memory" / "task_center",
    Path.home() / ".xuzhi_memory",
    Path.home() / ".openclaw" / "logs",
    Path.home() / ".openclaw" / "centers" / "engineering" / "crown",
]

# 精确匹配：错误/失败/崩溃专用词
CRITICAL_PAT = re.compile(
    r"\b(CRITICAL|❌|FAIL|ERROR|崩溃|异常退出|卡死|完全失败|timeout|"
    r"Traceback|Exception|unreachable|gateway connect failed|"
    r"TypeError|JSONDecodeError|AssertionError|Segmentation fault|"
    r"生成失败|无法连接|连接失败|递归调用|死循环|"
    r"Gateway.*❌|红蓝队触发|RED_BLUE_ACTIVE)\b",
    re.IGNORECASE
)

WARNING_PAT = re.compile(
    r"\b(WARN|⚠️|警告|警告|警告|WARNING|异常|Cannot|cannot|"
    r"failed|Failed|skip|跳过|无响应|失败重试|retry|Retrying|"
    r"deprecated|stale|old|missing|Missing|no such file|"
    r"Channel is required|quota.*low|配额不足)\b",
    re.IGNORECASE
)

# 要忽略的噪音模式（常见但无害）
NOISE_PAT = re.compile(
    r"(Gateway.*✅|健康.*✅|正常|完成|唤醒|生成任务|"
    r"已激活|已连接|已启动|session.*ok|cron.*ok|"
    r"last_active.*refresh|heartbeat|心跳)\b",
    re.IGNORECASE
)

def scan_file(fp, max_lines=5000):
    """扫描单个文件，返回错误/警告列表"""
    crit_lines = []
    warn_lines = []
    try:
        # 大文件只读最后 max_lines
        lines = fp.read_text(errors="ignore").splitlines()
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
    except Exception as e:
        return [], [f"无法读取 {fp}: {e}"]

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过噪音
        if NOISE_PAT.search(stripped):
            continue
        # 精确匹配
        if CRITICAL_PAT.search(stripped):
            crit_lines.append((i+1, stripped[:150]))
        elif WARNING_PAT.search(stripped):
            warn_lines.append((i+1, stripped[:150]))

    return crit_lines, warn_lines


def format_time(ts):
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def run():
    all_results = {}
    total_crit = 0
    total_warn = 0

    for log_dir in LOG_DIRS:
        if not log_dir.exists():
            continue
        for fp in sorted(log_dir.glob("*.log")):
            crit, warn = scan_file(fp)
            if not crit and not warn:
                continue
            all_results[fp.name] = {
                "path": str(fp),
                "size": fp.stat().st_size,
                "mtime": fp.stat().st_mtime,
                "mtime_str": format_time(fp.stat().st_mtime),
                "critical_count": len(crit),
                "warning_count": len(warn),
                "critical_lines": crit[-5:],   # 最多显示5条
                "warning_lines": warn[-5:],
            }
            total_crit += len(crit)
            total_warn += len(warn)

    # 按严重程度排序
    sorted_results = sorted(
        all_results.items(),
        key=lambda x: (x[1]["critical_count"], x[1]["warning_count"]),
        reverse=True
    )

    # 输出
    print("=" * 65)
    print(f"🔍 XUZHI 全局健康扫描  @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    if not sorted_results:
        print("✅ 未发现错误或警告——系统健康")
        return 0

    print(f"🔴 CRITICAL: {total_crit} 个   🟡 WARNING: {total_warn} 个")
    print()

    for fname, data in sorted_results:
        size_kb = data["size"] / 1024
        print(f"📄 {fname}")
        print(f"   路径: {data['path']}")
        print(f"   大小: {size_kb:.1f} KB | 最后修改: {data['mtime_str']}")

        if data["critical_count"] > 0:
            print(f"   🔴 CRITICAL ×{data['critical_count']}")
            for lineno, snippet in data["critical_lines"]:
                print(f"      {lineno:>5}: {snippet}")

        if data["warning_count"] > 0:
            print(f"   🟡 WARNING ×{data['warning_count']}")
            for lineno, snippet in data["warning_lines"]:
                print(f"      {lineno:>5}: {snippet}")
        print()

    # 汇总建议
    print("=" * 65)
    print("📋 行动建议（按优先级）")
    print("=" * 65)

    crit_names = [n for n, d in sorted_results if d["critical_count"] > 0]
    if "self_heal.log" in crit_names:
        print("  🔴 self_heal: 红蓝队触发——检查 T2/T3 是否为历史残留")
    if "self_sustaining.log" in crit_names:
        print("  🔴 self_sustaining: 任务生成失败——检查 generate_task.py")
    if "task_executor.log" in crit_names:
        print("  🔴 task_executor: execution agent 创建失败——检查 cron delivery")
    if "quota_guard.log" in crit_names:
        print("  🔴 quota_guard: Channel 配置缺失——检查 delivery.channel")
    if "memory_forge.log" in crit_names:
        print("  🟡 memory_forge: sessions.json.bak 不存在——正常（首次运行）")

    print()
    print(f"扫描完成。{len(sorted_results)} 个日志文件有记录。")
    return 1 if total_crit > 0 else 0


def brief_scan() -> dict:
    """极简模式：只输出 {healthy: bool, crit_count: int, warn_count: int, top_issues: []}"""
    all_results = {}
    for log_dir in LOG_DIRS:
        if not log_dir.exists():
            continue
        for fp in sorted(log_dir.glob("*.log")):
            crit, warn = scan_file(fp, max_lines=200)
            if crit or warn:
                all_results[fp.name] = {
                    "crit": len(crit),
                    "warn": len(warn),
                    "top": [c[1] for c in crit[-3:]],
                }
    total_crit = sum(d["crit"] for d in all_results.values())
    total_warn = sum(d["warn"] for d in all_results.values())
    top_issues = []
    for name, d in sorted(all_results.items(), key=lambda x: x[1]["crit"], reverse=True):
        for issue in d["top"]:
            top_issues.append(f"{name}:{issue[:80]}")
    return {
        "healthy": total_crit == 0,
        "crit": total_crit,
        "warn": total_warn,
        "top_issues": top_issues[:5],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", action="store_true", help="极简JSON输出")
    parser.add_argument("--json-only", action="store_true", help="纯JSON输出")
    args = parser.parse_args()

    if args.brief or args.json_only:
        result = brief_scan()
        print(json.dumps(result, ensure_ascii=False), flush=True)
        sys.exit(0 if result["healthy"] else 1)
    else:
        sys.exit(run())
