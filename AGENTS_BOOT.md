# AGENTS_BOOT.md — 动态上下文指针

## 启动链路
```
genesis_probe.py → SOUL.md → MEMORY.md → 主任务
```
MEMORY.md 已包含所有必要上下文。SOUL.md 每次读取。
memory/YYYY-MM-DD.md 仅在需要时读取（按需，而非启动链路）。

## 核心原则
- 效率密度优先：每个token必须承载最大信息量
- 批处理思维：单次调用完成多任务
- Red Lines：不泄露私有数据 · `trash > rm` · 破坏性操作须确认
- "好钢用在刀刃上"：最小消耗，最大智能密度
