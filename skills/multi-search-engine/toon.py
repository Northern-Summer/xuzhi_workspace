#!/usr/bin/env python3
"""
toon.py — TOON (Token-Oriented Object Notation) 转换工具
零依赖，纯Python实现，供 skill 系统使用。
"""
import sys
import json
import re
from pathlib import Path
from typing import Any


def json_to_toon(data: Any, indent: int = 0) -> str:
    """JSON → TOON 格式，专注表格数组节省token的特性"""
    pad = "  " * indent

    if isinstance(data, dict):
        if not data:
            return "{}"
        lines = []
        for k, v in data.items():
            v_str = json_to_toon(v, indent + 1)
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}: {v_str}")
            else:
                lines.append(f"{pad}{k}: {repr(v) if isinstance(v, str) else v}")
        return "{\n" + ",\n".join(lines) + "\n" + pad + "}"

    if isinstance(data, list):
        if not data:
            return "[]"
        # 检测是否为"表格数组"（所有元素为同类简单dict）
        if data and all(isinstance(item, dict) for item in data):
            keys = []
            for item in data:
                for k in item:
                    if k not in keys:
                        keys.append(k)

            # 如果所有dict共享相同字段结构 → 用TOON表格格式
            if all(set(item.keys()) == set(keys) for item in data if item):
                header = f"[{len(data)}]{{{','.join(keys)}}}"
                rows = []
                for item in data:
                    row = ",".join(str(item.get(k, "")) for k in keys)
                    rows.append(row)
                return f"{header}:\n" + "\n".join(f"  {r}" for r in rows)

        # 非均匀/嵌套数组 → 用标准JSON格式
        lines = [json_to_toon(item, indent + 1) for item in data]
        return "[\n" + ",\n".join("  " + l for l in lines) + "\n" + pad + "]"

    # 基础类型
    if isinstance(data, str):
        return repr(data)
    return str(data)


def toon_to_json(text: str) -> Any:
    """TOON → JSON 格式（支持表格数组语法）"""
    text = text.strip()

    # 匹配表格数组: name[N]{{key1,key2,key3}}: val1,val2 val3 ...
    table_match = re.match(r'(\w+)\[(\d+)\]\{([^}]+)\}:\s*\n((?:.+\n)*)', text)
    if table_match:
        name = table_match.group(1)
        count = int(table_match.group(2))
        keys = [k.strip() for k in table_match.group(3).split(",")]
        rows_text = table_match.group(4).strip()
        rows = []
        for line in rows_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            values = [v.strip() for v in line.split(",")]
            obj = dict(zip(keys, values))
            rows.append(obj)
        return {name: rows}

    # 尝试直接解析为JSON（TOON是JSON的超集，对于非表格部分）
    try:
        return json.loads(text)
    except Exception:
        return text


def compact_json(data: Any) -> str:
    """极简JSON（无缩进无空格），用于token压缩"""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  toon.py encode <json_file>     # JSON → TOON")
        print("  toon.py decode <toon_file>     # TOON → JSON")
        print("  toon.py compact <json_file>    # JSON → 极简JSON")
        print("  cat data.json | toon.py encode  # 从stdin读取")
        sys.exit(1)

    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    # 从stdin读取
    if arg == "-":
        content = sys.stdin.read()
    elif arg:
        content = Path(arg).read_text()
    else:
        content = sys.stdin.read()

    try:
        data = json.loads(content)
    except Exception as e:
        print(f"JSON解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if cmd == "encode":
        print(json_to_toon(data))
    elif cmd == "decode":
        print(json.dumps(toon_to_json(content), indent=2, ensure_ascii=False))
    elif cmd == "compact":
        print(compact_json(data))
    else:
        print(f"未知命令: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
