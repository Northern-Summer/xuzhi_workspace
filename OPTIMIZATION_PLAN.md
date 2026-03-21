# 效率优化方案 — 2026-03-20

## 核心结论
`custom-cloud-infini-ai-com` 成本为 **0**，优化目标是 **POST 请求次数**和**上下文膨胀**（而非费用）。16次压缩主因：响应过长 + 上下文碎片化。

## 已落地优化（本次）

### 1. MEMORY.md 精简（793B）
去除冗余历史条目，保留：身份、虚质系统架构、当前任务、工程能力基础设施、技术栈。

### 2. AGENTS_BOOT.md 精简（288B）
极简指针，移除与 MEMORY.md 重复的段落，明确"按需加载"原则。

### 3. 工具调用模式
- 批处理：多个 exec/read 合并为一次执行
- 避免短轮次交替（exec→read→exec）
- 优先用单一强大命令替代多步工具链

### 4. 响应策略
- 单次回复承载完整答案
- 避免碎片化交互
- 主动一次性给出全部方案

### 5. OpenClaw 配置调优（openclaw.json）

基于 OpenClaw 官方文档（session-management-compaction.md / prompt-caching.md）：

| 参数 | 默认值 | 建议值 | 作用 |
|------|--------|--------|------|
| `bootstrapMaxChars` | 20000 | 10000 | 单引导文件上限 |
| `bootstrapTotalMaxChars` | 150000 | 80000 | 引导文件总上限 |
| `imageMaxDimensionPx` | 1200 | 800 | 截图降维 |
| `compactOn` | 0.8 | 0.85 | 压缩阈值（调高可减少压缩频率） |
| `cacheRetention` | none | long | Prompt缓存保留 |
| `contextPruning.mode` | — | cache-ttl | 缓存TTL后剪枝 |

### 6. 本地模型最大化（本次新增）

**核心原则**：小模型不是大模型的阉割版，而是不同任务的正确工具。

| 模型 | 规格 | 最佳用途 |
|------|------|----------|
| `lfm2.5-thinking:1.2b` | 731MB | 路由、意图分类、快速Yes/No |
| `lfm2.5-thinking-optimized` | 731MB | 轻量推理、代码执行 |
| `gemini-3-flash-preview` | ? | 研究搜索、实时信息 |
| `gemma3:4b` | 3.3GB | 快速分析、翻译、格式化 |
| `qwen3.5:4b` | 3.4GB | 平衡推理、工具调用 |
| `qwen3-vl:8b` | 6.1GB | 视觉任务、截图分析 |
| `qwen3.5:9b` | 6.6GB | 深度推理、复杂代码 |

详见 `MODEL_ROUTING.md`

### 7. Clawiser 融合（本次新增）

Clawiser 的 search→read→think→write 流程嵌入模型路由：

```
Search     → gemini-3-flash-preview（搜索查询生成、结果预筛选）
Read       → qwen3-vl:8b（图像页面）+ lfm2.5:1.2b（相关性判断）
Think      → qwen3.5:9b（深度分析）+ minimax-m2.7（高层洞察）
Write      → qwen3.5:4b（格式化）+ gemma3:4b（翻译/风格）
```

详见 `MODEL_ROUTING.md#与-Clawiser-的融合`

## 关键OpenClaw参数速查

见上方配置调优表格。

## 优化效果追踪

| 指标 | 优化前 | 目标 |
|------|--------|------|
| 压缩次数/小时 | 16+ | <3 |
| 平均响应长度 | >2000 tokens | 800-1500 tokens |
| 工具调用/任务 | 多次分散 | 1-2 次批量 |
| 启动序列开销 | 5 文件全读 | 只读 MEMORY.md |
