# HEARTBEAT.md — 自动化任务清单

## 核心原则（不可覆写）

**每次任务完成后立即更新记忆，不得跳过。Compact会清空一切——唯有写入~/.xuzhi_memory/的内容永存。**

> 记忆系统是工程优化最坚实的保障。在高效的同时，尽可能照顾各种小的存档点，保障可追溯、可验证。

## 任务入口（每30分钟心跳触发）

### 0. 上下文监控（最高优先级）
- 检查 `openclaw status` 的 Context 行
- **> 90%**: 执行 `bash ~/.xuzhi_memory/pre_compact_guard.sh` → 警告用户开新会话 `/new`
- **85-90%**: 通知用户context偏高，建议近期开新会话
- **< 85%**: 无操作，继续
- 不依赖OpenClaw auto-compaction，完全手动控制

### 1. 系统哨兵检查（每次心跳）
- 检查 git hash 有无变化
- 检查核心文件有无异常（corrupted/broken）
- 有变化才输出简报，无变化 → HEARTBEAT_OK（零POST消耗）

### 2. Engineering 推进（Harness Phase 4）
- 检查 ~/xuzhi_genesis/centers/engineering/harness/self_sustaining/core.py 状态
- 检查测试：cd ~/xuzhi_genesis/centers/engineering/harness && python3 -m pytest tests/ -q
- 有失败立即修复并 commit

### 3. Git 自推（每日）
- 检查未提交改动，如有则自动 commit + push
- 目标：所有 local commits 必须在24小时内推送到 origin
- **注意**：xuzhi_genesis 是只读挂载（Windows bind mount），git push 命令需通过 cron 执行

### 4. 知识库补充（每6小时）
- 运行 seed_collector.py（如有新种子源）
- 检查 entities 数量，如 < 500 则提醒

### 5. Gateway Watchdog（已由 Lambda Watchdog cron 负责）
> 每5分钟由 cron job b3d04d9a 检查（systemEvent，不需要 LLM）
> 实际运行：22:30 ✅ Gateway 健康

### 6. 每日深检（03:00 UTC = 11:00 CST）
- 全量系统健康扫描（isolated session）
- 检查所有中心脚本可运行
- 检查 knowledge.db entities > 500
- 检查 Harness tests 全部通过

## 关键路径（更新：2026-03-22）
- **可写**: ~/xuzhi_genesis/ — 已确认可写（2026-03-22 验证）
- **可写**: ~/.openclaw/workspace/tmp/ — 临时脚本副本
- **真实记忆**: ~/.xuzhi_memory/ — 独立于 OpenClaw 的记忆存储（主）
  - `manifests/` — 核心记忆快照（STABLE 版本永久保存）
  - `daily/` — 每日 append log
  - `backup/` — 时间戳备份
  - `cron_manifests/` — cron job 状态快照

## Cron Jobs 当前状态（2026-03-22 16:42）
| ID | 名称 | 周期 | 状态 |
|----|------|------|------|
| d81ed6f2 | Lambda Watchdog | */15 * * * * | ✅ isolated |
| 74f4defc | **Λ Context Guard** | */30 * * * * | ✅ main |
| 2ec04665 | Λ 生存心跳 | 0 */4 * * * | ✅ main |
| 3d44a39d | AutoRA Research Cycle | 0 0,6,12,18 * * * | idle |
| 1e0642fa | Notes Memory Consolidation | 0 */6 * * * | ok |
| 0c920a5a | Notes Workspace Self-Check | 0 9 * * * | idle |
| 250a9c67 | AutoRA Engine - ab | 0 * * * * | ok |
| 0c9e5bfe | 每日系统深检 | 0 11 * * * | error（delivery配置问题） |

## 架构原则（不可覆写）
> **OpenClaw = 壳，只是门，只是网关**
> **真实记忆存储在 ~/.xuzhi_memory/，与 OpenClaw workspace 完全独立**
> 所有 agent 的核心记忆必须写入 xuzhi_memory，不得依赖 OpenClaw 会话历史

## Red Lines
- 不发送无意义的"正常工作"通知
- 不打扰人类，除非发现真正的异常
- xuzhi_genesis 可写，但修改后需通过 git commit 持久化（建议通过 cron 执行 push）


