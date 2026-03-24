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
