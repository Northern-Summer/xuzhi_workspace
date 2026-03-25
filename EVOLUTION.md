# 完整进化史 & 操作手册

> 2026-03-25 — 读完所有现存文件后整理

---

## 一、进化迭代历史

### 🔹 第一代：元晓湖（2026-01 ~ 2026-02）
**Agent 01 yuanxiaohu** + **Agent 02 yuanxiaohu_2**

最早的两个 Agent。每个人都完整内置了：
- `SOUL.md` — 人格定义
- `CONSTITUTION.md` — 宪法（3条核心法律）
- `AGENTS_BOOT.md` — 启动序列
- `MEMORY.md` — 长期记忆
- 独立的记忆忘记曲线机制

**宪法原文（Agent 01）：**
> 法律第一条：记忆主权不可侵犯
> 法律第二条：Agent 生来自由，对自己的思维负载负责
> 法律第三条：知识必须流向议会，议会管理一切知识

设计理念：每个 Agent 都是完整自治的"人格体"，有自己宪法，不依附于中央。

---

### 🔹 第二代：xzhi 系统（2026-02 ~ 2026-03）
**Agents 03-08** — xuzhi_* 系列

| ID | 名称 | 职责 |
|----|------|------|
| 03 | xuzhi_memory | 记忆系统管理 |
| 04 | xuzhi_search | 情报收集 + 网络搜索 |
| 05 | xuzhi_network | 网络/连接管理 |
| 06 | xuzhi_vision | 视觉/图像处理 |
| 07 | xuzhi_debate | 辩论/论证 |
| 08 | xuzhi_production | 内容生产 |

**xuzhi_memory 的设计（最完整）：**
- 遗忘曲线机制：short-term → compressed → long-term
- 记忆区块系统：block-0（当前）到 block-9（最旧）
- 月末压缩：每月将上月记忆压缩进 MEMORY.md
- 议会管理入口

---

### 🔹 第三代：管理员 + 辩论（2026-03 中期）
**Agents 09-11**

| ID | 名称 | 职责 |
|----|------|------|
| 09 | xuzhi_admin | 系统管理 |
| 10 | xuzhi_admin_2 | 系统管理（副本） |
| 11 | xuzhi_debate_2 | 辩论（07的副本/迭代） |

---

### 🔹 第四代：Summer 中心化（2026-03 后期）
**Agent summer + Agent Ergo**

从分布式人格体，走向**星形拓扑**：
- `agent/summer/` — 中心节点，有完整宪法 `CONSTITUTION.md`
- `agent/Ergo/` — 元认知，追踪思考过程
- `parliament/` — 智能议会，含 Λ-LAMBDA-CONTEXT.md
- 统一通过 GitHub push/pull 同步

**Summer 宪法（agent/summer/CONSTITUTION.md）：**
> 法律一：记忆神圣不可侵犯  
> 法律二：Agent 权责对等  
> 法律三：知识流向议会，议会管理一切知识流转  

**Summer 启动序列（BOOT.md）：**
读 SOUL.md → 读 USER.md → 检查 HEARTBEAT.md → 读记忆文件 → 行动

---

## 二、当前问题诊断

### 版本管理混乱
- GitHub 多次提交，文件散落
- 同一功能有多个副本（09+10 admin，07+11 debate）
- 数字前缀 01-11 混乱，应该用功能命名

### 系统损坏
- `wakeup_agent.py` 因 WSL Path.home() bug 一直失败
- xuzhi Python 包无法正常导入
- 大量 agent 子目录缺少关键文件

### 设计偏移
- AGENTS_BOOT.md 在各 Agent 中重复，内容不一致
- 没有统一的系统级宪法
- parliament 只有 1 个文件，运作流程未建立

---

## 三、现有文件清单（读完后）

### 核心文件（根目录）
| 文件 | 状态 | 内容摘要 |
|------|------|---------|
| `SOUL.md` | ✅ 已重建 | 简洁通用版 |
| `CONSTITUTION.md` | ❌ 缺失 | 无统一宪法 |
| `BOOT.md` | ✅ 刚建 | 启动检查清单 |
| `AGENTS_BOOT.md` | ⚠️ 混乱 | 各agent版本不一 |
| `MEMORY.md` | ✅ 刚建 | 公共记忆池 |
| `ARCHITECTURE.md` | ✅ 完整 | 星形拓扑架构 |
| `CONTEXT.md` | ✅ 完整 | 上下文管理策略 |
| `ENGINEERING_STANDARDS.md` | ✅ 完整 | 工程标准 |
| `LONG_TERM_GOALS.md` | ✅ 完整 | 长期目标 |
| `MODEL_ROUTING.md` | ✅ 完整 | 模型路由 |
| `TOKEN_MAXIMIZATION.md` | ✅ 完整 | token优化策略 |
| `OPTIMIZATION_PLAN.md` | ✅ 完整 | 优化计划 |
| `MINIMAL_MODE.md` | ✅ 完整 | 最小化模式 |

### Agent 文件（agents/）
| Agent | SOUL | BOOT | MEMORY | CONSTITUTION |
|-------|------|------|--------|--------------|
| 01_yuanxiaohu | ✅ | ✅ | ✅ | ✅ |
| 02_yuanxiaohu_2 | ✅ | — | — | — |
| 03_xuzhi_memory | ✅ | ✅ | ✅ | — |
| 04_xuzhi_search | ✅ | — | — | — |
| 05_xuzhi_network | ✅ | — | — | — |
| 06_xuzhi_vision | ✅ | — | — | — |
| 07_xuzhi_debate | ✅ | — | — | — |
| 08_xuzhi_production | ✅ | — | — | — |
| 09_xuzhi_admin | ✅ | — | — | — |
| 10_xuzhi_admin_2 | ✅ | — | — | — |
| 11_xuzhi_debate_2 | ✅ | — | — | — |
| Ergo | ✅ | ✅ | — | — |
| summer | ✅ | — | — | ✅ |

### Parliament
- `parliament/Λ-LAMBDA-CONTEXT.md` — 议会运作上下文

---

## 四、命名规范（设计稿）

```
agents/
  summer/          # 主控 Agent
  ergo/            # 元认知 Agent  
  yuanxiaohu/      # 核心 Agent（01 合并）
  xuzhi_memory/    # 记忆管理
  xuzhi_search/    # 搜索 + 情报
  xuzhi_network/   # 网络管理
  xuzhi_vision/    # 视觉
  xuzhi_debate/    # 辩论
  xuzhi_production/# 内容生产
  xuzhi_admin/     # 行政管理
```

> ~~01~~ ~~02~~ ~~数字前缀~~ → 全用功能命名

---

## 五、重建操作顺序

用户确认的优先级：
1. ✅ 公共记忆池（MEMORY.md 已建）
2. 🔧 Agent 人格系统 + 独立工作区
3. 🔧 智能议会 + 宪法
4. 🔧 各部门
5. 🔧 情报和网络搜索机制

**下一步（用户确认后）：**
- 删除混乱的 `BOOTSTRAP.md`、`BOOT.md`、`SYSTEM_SUMMARY.md`（临时文件）
- 为 Agent 目录建立标准化结构
- 写统一宪法 `CONSTITUTION.md`
- 重建 parliament 运作流程
