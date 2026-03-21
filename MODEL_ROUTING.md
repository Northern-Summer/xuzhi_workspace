# MODEL_ROUTING.md — 本地模型最大化架构

## 核心原则（来自 Karpathy AutoResearch）
**小模型不是大模型的阉割版，而是不同任务的正确工具。**

## 模型能力矩阵

| 模型 | 规格 | 速度 | 最佳用途 |
|------|------|------|----------|
| `lfm2.5-thinking:1.2b` | 731MB | ⚡极速 | 路由、意图分类、快速Yes/No |
| `lfm2.5-thinking-optimized:latest` | 731MB | ⚡极速 | 轻量推理、代码执行 |
| `gemini-3-flash-preview:latest` | ? | ⚡快速 | 研究搜索、实时信息 |
| `gemma3:4b` | 3.3GB | 🔥快 | 快速分析、翻译、格式化 |
| `qwen3.5:4b` | 3.4GB | 🔥快 | 平衡推理、工具调用 |
| `qwen3-vl:8b` | 6.1GB | 🐢中 | 视觉任务、图表分析 |
| `qwen3.5:9b` | 6.6GB | 🐢中 | 深度推理、复杂代码 |
| `infini minimax-m2.7` | 云端 | 🧠极强 | 高层规划、创作、复杂推理 |

## 任务路由表

```
任务类型 → 模型选择

1. 路由决策       → lfm2.5-thinking:1.2b    (简单分类、Yes/No)
2. 知识查询       → knowledge-query skill   (内建路由)
3. 网络搜索       → gemini-3-flash-preview  (实时信息)
4. 轻量格式化     → gemma3:4b               (翻译、简单格式化)
5. 平衡推理       → qwen3.5:4b              (一般推理)
6. 深度推理       → qwen3.5:9b              (复杂分析)
7. 视觉任务       → qwen3-vl:8b             (图像理解)
8. 高层规划       → infini minimax-m2.7     (战略、创作)
```

## Clawiser 融合

```
Search     → gemini-3-flash-preview（搜索生成）
Read       → qwen3-vl:8b（图像）+ lfm2.5:1.2b（相关性）
Think      → qwen3.5:9b（深度）+ minimax（高层）
Write      → qwen3.5:4b（格式化）+ gemma3:4b（翻译）
```

## OpenClaw 配置

在 `openclaw.json` 的 `agents.defaults.models` 中已添加：
- `ollama/lfm2.5-thinking:1.2b` (router)
- `ollama/gemma3:4b` (light)
- `ollama/qwen3.5:4b` (medium)
- `ollama/qwen3.5:9b` (heavy)
- `ollama/qwen3-vl:8b` (vision)

## 前置条件

Ollama 必须通过 TCP API 运行（而非 Unix socket）才能被 OpenClaw 调用：

```bash
# 启动ollama（TCP模式）
OLLAMA_HOST=http://127.0.0.1:11434 ollama serve
# 验证
curl http://localhost:11434/api/tags
```

## 实施状态

- [x] MODEL_ROUTING.md 设计完成
- [x] openclaw.json ollama provider 配置
- [ ] ollama TCP API 启动并验证
- [ ] model_router.py 路由脚本创建
- [ ] 基准测试：云端 vs 本地质量对比
