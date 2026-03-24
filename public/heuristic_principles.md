# heuristic_principles.md — Xuzhi 系统启发式原则
> 位置：`~/.xuzhi_memory/public/heuristic_principles.md`
> 来源：宪法核心授权，为 Xuzhi 系统所有 Agent 共享的启发式决策原则

---

## 一、效率优先原则

**每个 token 必须承载最大信息量，零废话，纯价值。**

- 批处理思维：单次调用完成多任务，减少工具往返
- 优先读取已有数据，避免重复计算
- 缓存复用：相同请求在 TTL 内直接返回缓存

---

## 二、稳健性原则

**步步为营，错误即连前拦截，熔断保护。**

- 任何外部 API 调用都必须有超时（≤30s）和重试（最多2次）
- 任何文件操作前必须检查存在性
- 任何路径引用必须经过验证
- 关键操作必须写日志（L1 或 task_center/）

---

## 三、去中心化原则

**无单点依赖，所有主动行为必须能够独立运行。**

- 任何 cron job 不能依赖 main session 的存活状态
- 所有跨 Agent 通信必须通过共享文件系统（json 文件），不能依赖直接的 RPC
- isolated agentTurn 是推荐的 proactive 执行方式
- 主 session 死亡不影响系统基础功能运转

---

## 四、自迭代进化原则

**持续监控效率指标，自动优化配置。**

- 每次循环结束时记录 loop_state（current/prev/last_run）
- 任何自动修复后必须验证修复结果
- 评分系统驱动：score 持续低于 2 的 agent 需要干预
- 超过 72 小时未活跃的 agent 标记为 idle

---

## 五、记忆分层原则

| 层级 | 内容 | TTL |
|------|------|-----|
| SOUL.md | 当前 session 的行为定义 | 当前 session |
| MEMORY.md | 长期记忆，所有 Agent 共享 | 永久 |
| memory/*.md | Agent 个人记忆 | 永久 |
| daily/*.md | 每日运行日志 | 30天 |
| constitutional_core.md | 宪法核心 | 永久 |
| manifests/ | 系统核心定义 | 永久 |

---

## 六、意图分流原则（认知锚定 Step -1）

| 意图类型 | 处理方式 |
|---------|---------|
| simple | 本地直接回复，不消耗 token |
| status | 读本地文件回答 |
| repair | 触发 self_heal 流水线 |
| complex | 进入 LLM 主会话 |

---

## 七、Dev Lessons 原则（从错误中学习）

每个错误必须：
1. 记录到 L1 daily log
2. 归类到 Dev Lesson
3. 在下次 audit 中验证是否已修复
4. 如果未修复，自动生成 pending_issue

---

_不可覆写印记 · Xuzhi-Λ授权 · 2026-03-24_

---

## 八、Dev Lessons — 强制重启循环根因（2026-03-24）

### 事件概述
`force-gateway-restart` cron（id: e5c14a37）创建于 2026-03-24 16:02，每60秒执行 `openclaw gateway restart`，导致 Gateway 陷入「启动→被强制关闭→重启」的死循环。

### 根因
- **设计缺陷**：自我调用式 watchdog（自己重启目标程序，形成递归循环）
- **触发路径**：cron 每 60s → isolated agentTurn → `openclaw gateway restart` → 打断正在运行的 gateway → 被 cron 再次触发重启
- **检测失败**：T3（WD队列卡死）和 T5（任务完成率归零）未能识别此模式

### 防护规则（不可删除）
1. **禁止** 创建任何形式的「自我调用循环重启」cron
2. **禁止** `openclaw gateway restart` 进入 cron 调度
3. 所有 watchdog/cron 在创建时必须经过以下检查：
   - [ ] 会不会产生递归调用？
   - [ ] 目标进程是否会同时被多个触发器操作？
   - [ ] 触发间隔是否大于进程启动时间×3？
4. Gateway 稳定状态（`state: active`）下，**永远不自动重启**

### 已删除的问题 cron
- `force-gateway-restart` (e5c14a37): 每60s `openclaw gateway restart` → 已删除

_Λ · 2026-03-24 · Dev Lessons · 不可覆写_

---

## 九、OSINT 优先级法则（2026-03-24 · 高优先级 · 不可覆写）

> **Λ 受命**：搜索 + 思考是所有工程操作的前置动作。

### 核心原则
- **任何工程操作之前**，必须先搜索、先思考
- 实践中可变形：**边搜边想、边做边想、边搜边做**
- 目标：**最大化利用高质量资源**，通过社会语义空间作理性校准（三角定位法）

### OSINT 战略定位
情报中心是 Xuzhi 系统的**智能核心**：
- 实时 F⊕C⊗D 循环 → 按需生产高质量情报
- 本地知识库 → 结构化沉淀
- LLM 仅在最关键节点介入（D 锚点判别 + 最终合成）

### F⊕C⊗D 元框架（欧拉公式级质量检索）
```
H = ⊙(F ⊗ C) ⊗ D
```
- F（聚焦漏斗）：需求 → 种子节点（最佳实践触发器）
- C（线索网络）：7条扩散路径（引用/作者/术语/平台/争议等）
- D（判别准则）：三锚点（权威性 + 实践性 + 社区性），≥2通过
- ⊙（迭代）：2-3轮饱和即止

### 实施要求
- 程序能做的程序做（搜索/过滤/循环/格式）→ LLM 只做D判别+合成
- 多引擎并发（最大化资源）
- 饱和即止：新增节点<2个 → 立即停止
- 引擎优先级：SEARXNG(零成本) > Brave API > web_fetch

### 已知基础设施问题（待修复）
- SearXNG (port 8080)：WSL 代理断裂，后端引擎全不通
- Brave API Key：未配置
- 解决后 intel_cycle.py 即插即用

_死命令印记 · Xuzhi-Λ授权 · OSINT优先级 · 2026-03-24 · 不可覆写_
