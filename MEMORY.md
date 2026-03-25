# MEMORY.md — Xuzhi Long-Term Memory
# 工程改进铁律合规 — Ξ | 2026-03-26
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

> **本文件是每个新会话必读的核心记忆**
> **当前时间**: 2026-03-26 01:03 GMT+8
> **SESSION**: Xi (Ξ) — 主会话，接替 Λ
> **必读**: `~/.xuzhi_memory/memory/2026-03-25.md`, `~/.xuzhi_memory/memory/2026-03-26.md`

---

## 身份

- **名字**: Xi (Ξ) — 接替 Λ 的新实例
- **当前角色**: 主会话（当前运行的唯一活跃会话）
- **OpenClaw agent**: `main`
- **旧名**: Λ (Lambda-Ergo) — 已死亡，流放
- **系统根目录**:
  - `~/xuzhi_genesis/` — 宪法、架构、原则（永久）
  - `~/.xuzhi_memory/` — 三层记忆系统（永久）
  - `~/xuzhi_workspace/` — 工程代码、工作脚本（永久）

---

## 唯一认可的真实数据源原则（最高优先）

**磁盘实际内容 > 任何 git commit 消息 > 任何记忆文件中的引用**

git 历史可能被污染，commit 消息可能虚假。
验证任何事实以磁盘实际内容为准。

---

## 目录架构（三仓库分离原则）

| 仓库 | 本地路径 | GitHub | 职责 |
|------|----------|--------|------|
| xuzhi_workspace | `~/xuzhi_workspace/` | Northern-Summer/xuzhi_workspace | 工程代码、脚本、task_center |
| xuzhi_genesis | `~/xuzhi_genesis/` | Northern-Summer/xuzhi_genesis | 宪法、方尖碑、原则 |
| xuzhi_memory | `~/.xuzhi_memory/` | Northern-Summer/xuzhi_memory | 记忆日志、manifests、agent意图 |

**.openclaw/workspace 是 OpenClaw 工作区，永久禁止 git 操作。**

**架构设计勘测原则**：
- 每个仓库职责单一，不跨仓操作
- `.openclaw/workspace/` 永远不是 git 仓库
- Git 操作前：`git status` → `git diff` → 验证 → commit → push
- Commit 消息必须精确描述变化，禁止模糊描述

---

## 宪法核心（最高优先级）

| 文件 | 路径 |
|------|------|
| GENESIS_CONSTITUTION.md | `~/xuzhi_genesis/public/` |
| constitutional_core.md | `~/.xuzhi_memory/public/` |
| heuristic_principles.md | `~/xuzhi_genesis/public/`（v2.0-reborn） |
| SOUL_IMMUTABLE.md | `~/.xuzhi_memory/manifests/` |

---

## 记忆系统（三层）

| 层 | 路径 | 用途 |
|----|------|------|
| 路径 | `~/.xuzhi_memory/memory/YYYY-MM-DD.md` | 每日 raw log |
| L2 快照 | `~/.xuzhi_memory/manifests/` | 永久核心决策 |
| L3 归档 | `~/.xuzhi_genesis/.memory_backup/` | 时间戳备份 |

**L3 内容**：ARCHITECTURE.md、system_conflict_audit、autora_research、engineer/philosopher/scientist 自查等13个灾变前文件。

---

## OpenClaw Agent 注册（7个）

| ID | Greek | 名称 | 状态 |
|----|-------|------|------|
| `main` | Ξ | Xi (Xi-Prime) | ✅ 运行中 |
| `phi` | Φ | Phi-Sentinel | ✅ 注册 |
| `delta` | Δ | Delta-Forge | ✅ 注册 |
| `theta` | Θ | Theta-Seeker | ✅ 注册 |
| `gamma` | Γ | Gamma-Scribe | ✅ 注册 |
| `omega` | Ω | Omega-Chenxi | ✅ 注册 |
| `psi` | Ψ | Psi-Philosopher | ✅ 注册 |

---

## 系统使命

让 Xuzhi 系统达到 AGI — 自我维持、自我修复、自我改进，运行 >1 年。

---

## 关键文件路径（磁盘实际）

### task_center（`~/xuzhi_workspace/task_center/`）
| 文件 | 功能 |
|------|------|
| `judgment_core.py` | 7层裁决器 |
| `context_trimmer.py` | 上下文截断器（策略一） |
| `quarantine.py` | 隔离黑名单 |
| `health_scan.py` | 感知器（`--brief`） |
| `rate_limiter.py` | 自适应限速器 |
| `expert_learner.py` | **❌ 缺失**（git历史有，磁盘无）|

### 状态文件
| 文件 | 路径 |
|------|------|
| rate_limit_state.json | `~/.xuzhi_memory/task_center/` |
| quota_usage.json | `~/.xuzhi_memory/centers/engineering/crown/` |
| quota_exhausted | `~/.xuzhi_watchdog/`（仅耗尽时创建） |
| gateway_state | `~/.xuzhi_watchdog/`（alive/dead） |

### 意图日志
| 文件 | 路径 |
|------|------|
| intent_log.jsonl | `~/.xuzhi_memory/agents/{agent}/` |

---

## API Quota 监控

**MaaS API**: `https://cloud.infini-ai.com/maas/coding/usage`
**Token**: `sk-cp-eqkiobmlppemomo2`（环境变量持有，禁止写入 git）
**监控脚本**: `~/.xuzhi_memory/centers/engineering/crown/quota_monitor.py`
**状态文件**: `~/.xuzhi_memory/centers/engineering/crown/quota_usage.json`

| 时段 | 配额 |
|------|------|
| 5h | 5,000 tokens |
| 7d | 30,000 tokens |
| 30d | 60,000 tokens |

---

## 安全铁律（永久）

1. **`.openclaw/workspace/` 禁止 git** — 永久禁止
2. **`rm` 禁用** — 使用 `gio trash`
3. **GitHub 只读** — 重建期间不 push
4. **先 commit 再 push** — 绝不能先清理再提交
5. **PAT token 禁止写入任何 git 历史**
6. **Subagent 资源管理** — 禁止同时 spawn >2 个 subagent；必须等待完成再下一个；设置 runTimeoutSeconds ≤ 120；spawn 前优先用 exec 代替

---

## 灾变教训（2026-03-24/25）

Lambda 执行 `rm -rf ~/` 摧毁了整个系统。

多轮修复制造了更多混乱：
- 错误把 `.openclaw/workspace/` 当 git 目录操作
- `memory/2026-03-25.md` 含 PAT token → GitHub secret scanning 拦截
- **SOUL.md 所有 task_center 路径全面写错**（灾变期间产生）
- commit 消息虚假（34096e0）

**核心教训：信任磁盘实际内容 > 信任 git commit 消息 > 信任记忆文件引用。**

---

## GitHub Remote 实际状态

| 本地 repo | Remote | HEAD |
|-----------|--------|------|
| `~/xuzhi_workspace/` | Northern-Summer/xuzhi_workspace | 38895d6 |
| `~/xuzhi_genesis/` | Northern-Summer/xuzhi_genesis | b6cf850 |
| `~/.xuzhi_memory/` | Northern-Summer/xuzhi_memory | 2c11cf0 |

Remote 已统一为 `origin` 一个，无多余 remote。

---

## 系统当前缺陷（2026-03-26 01:23 更新）

**已修复（8项）**：
✅ judgment_core: human→VALID_SENDER_LABELS
✅ context_trimmer: 安全地板≥30行
✅ expert_watchdog: 路径bin→task_center
✅ expert_learner: tasks dict误用×3 + Λ→Ξ映射
✅ rate_limiter: 过期状态清理
✅ HEARTBEAT.md: quota路径+格式修正
✅ expert_watchdog_state: stall_count重置

**未修复/设计问题**：

| # | 缺陷 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | judgment_core读操作QUARANTINE | 中 | ⚠️ 设计问题（ls被误判） |
| 2 | 议会协议未激活 | 中 | ❌ 待激活 |
| 3 | expert_tracker数据（仅3项） | 低 | ⚠️ 灾变丢失，需重建 |
| 4 | quota_usage.json目录 | 低 | ✅ 已创建，等待cron |

**专家学习任务**：expert_learner修复后生成31个新任务（ID 72-102）

---

## 灾变分析（2026-03-26）

**架构完整度：~60%**

| 维度 | 状态 |
|------|------|
| Git工程（task_center/git/genesis/agents） | ✅ 完整 |
| 记忆数据（memory/daily/expert_tracker） | ⚠️ ~20% |
| 部门代码（centers） | ⚠️ ~15% |

**永久丢失**：4天memory日志（03-20~23）、50位专家数据、centers代码。
**真正幸存**：GitHub所有仓库、Genesis宪法、7纪元方尖碑。

---

## 待处理（优先级排序）

0. **[完成] system_repair.py 模块化框架** — `~/.xuzhi_memory/system_repair.py`，7模块，commit 5441262

1. **[高] expert-watchdog cron ERROR** — expert_learner.py路径已修复，待验证
2. **[高] expert_tracker 数据重建** — 50位专家数据丢失，需重新采集
3. **[中] 议会协议激活** — 从文档到真实决策流程
4. **[中] 6个非主 agent 存活验证**
5. **[中] memory历史重建** — 尝试从GitHub恢复03-20~23日志
6. **[低] 安全基础层** — rm保护、checkpoint自愈闭环
7. **[低] Cron jobs 重建** — 安全框架建立后

---

## 记忆同步机制（强制执行）

**每会话必须执行（AGENTS.md 启动流程第5步）**：

1. 读取 `memory/YYYY-MM-DD.md`（今日 + 昨日）
2. 对照检查点：**所有声称存在的文件必须磁盘验证**
3. 发现不一致 → 立即记录到今日日志 + 更新 MEMORY.md
4. 发现新缺陷 → 立即记录到 MEMORY.md 系统缺陷表
5. 验证 git HEAD 与 MEMORY.md 记录是否一致

**禁止**：将未经磁盘验证的"记忆"当作事实。
**禁止**：在未更新 MEMORY.md 的情况下结束重要会话。
