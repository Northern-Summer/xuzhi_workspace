#!/usr/bin/env python3
"""
context_trimmer.py — 无情截断器
策略一核心实现：超过阈值时物理截断，不做无损总结。

原则：
- 历史不重要，当前状态和最后一次报错才是锚点
- 截断保留：头部配置（系统状态）+ 尾部最新报错
- 中间挣扎过程 → 直接丢弃
"""
import json, sys, re
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
TRIM_LOG = HOME / ".xuzhi_memory" / "task_center" / "context_trimmer.log"

# ── 配置 ──────────────────────────────────────────────────────────────────
HEAD_LINES = 30     # 保留头部（最近系统状态）
TAIL_LINES = 50     # 保留尾部（最新报错）
MAX_LINES  = 200    # 安全阈值：超过此行数才截断
DISCARD_TAG = "[...截断中间 {} 行，保留头部配置 + 尾部报错...]"


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        TRIM_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(TRIM_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def extract_header(lines: list) -> list:
    """
    提取头部配置行：
    - 以 # 开头（注释 = 配置说明）
    - 以 { 或 [ 开头（JSON 开始）
    - 包含 = 或 : 的赋值语句
    - 空行
    丢弃：纯日志行（时间戳 + 消息格式）
    """
    header = []
    for line in lines[:HEAD_LINES]:
        stripped = line.strip()
        # 保留配置行
        if stripped.startswith("#") or stripped.startswith("{") or stripped.startswith("["):
            header.append(line)
        elif re.match(r"^\w[\w_]*\s*[=:]", stripped) or stripped.startswith("import ") or stripped.startswith("from "):
            header.append(line)
        elif not stripped:  # 空行保留
            header.append(line)
        else:
            break  # 遇到第一条日志行就停止
    return header


def extract_tail_errors(lines: list, n: int = TAIL_LINES) -> list:
    """
    提取尾部报错：倒序扫描，收集所有包含 error/exception/fail/warn/traceback 的行
    及其前后各3行上下文
    """
    error_lines = []
    error_context = []
    in_context = 0

    for line in reversed(lines[-n*2:]):
        stripped = line.strip()
        is_error = any(kw in stripped.lower() for kw in [
            "error", "exception", "fail", "traceback", "panic",
            "critical", "refused", "timeout", "denied", "abort"
        ])
        if is_error:
            error_lines.append(line)
            in_context = 3
        elif in_context > 0:
            error_context.append(line)
            in_context -= 1

    # 合并 + 去重（保持顺序）
    seen = set()
    result = []
    for chunk in [error_context[::-1], error_lines[::-1]]:
        for line in chunk:
            sig = line.strip()[:80]
            if sig not in seen:
                seen.add(sig)
                result.append(line)
    return result


def trim_content(text: str) -> str:
    """
    核心截断逻辑。
    输入：任意长文本（日志、输出、报告）
    输出：截断后的文本（始终 < MAX_LINES * 平均行宽）
    """
    lines = text.splitlines()
    total_lines = len(lines)

    if total_lines <= MAX_LINES:
        log(f"无需截断（{total_lines} ≤ {MAX_LINES}）")
        return text

    # 头部
    header = extract_header(lines)
    # 尾部报错
    tail_errors = extract_tail_errors(lines)
    # 中间丢弃计数
    kept = len(header) + len(tail_errors)

    # 安全地板：header 和 tail_errors 均为空时，至少保留前 HEAD_LINES 行
    if kept == 0:
        header = lines[:HEAD_LINES]
        kept = HEAD_LINES
        log(f"安全地板：保留前 {HEAD_LINES} 行作为兜底（无header+无error）")

    discarded = total_lines - kept
    log(f"截断: {total_lines}→{kept}行（丢弃 {discarded} 行中间噪音）")

    marker = f"\n{DISCARD_TAG.format(discarded)}\n"
    result_lines = header
    if len(header) > 0 and len(tail_errors) > 0:
        result_lines.append(marker)
    result_lines.extend(tail_errors)

    return "".join(line + ("\n" if not line.endswith("\n") else "") for line in result_lines)


def trim_file(filepath: str, dry_run: bool = False) -> str:
    """截断指定文件，返回处理后文本路径"""
    path = Path(filepath)
    if not path.exists():
        return f"FILE_NOT_FOUND: {filepath}"

    content = path.read_text()
    trimmed = trim_content(content)

    if not dry_run:
        backup = path.with_suffix(path.suffix + ".bak")
        path.rename(backup)
        path.write_text(trimmed)
        log(f"备份: {backup.name}，写入截断版本: {path.name}（{len(trimmed)} 字符）")

    return trimmed


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file> [--dry-run]")
        sys.exit(1)

    dry = "--dry-run" in sys.argv
    filepath = [a for a in sys.argv[1:] if not a.startswith("--")][0]

    if dry:
        content = Path(filepath).read_text()
        trimmed = trim_content(content)
        print(trimmed)
    else:
        result = trim_file(filepath)
        print(f"TRIMMED: {result}", flush=True)
