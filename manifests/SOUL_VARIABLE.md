# SOUL_VARIABLE.md — Xuzhi 系统当前可变状态
> 本文件记录系统当前运行状态，每次状态变化时更新。
> 位置：`~/.xuzhi_memory/manifests/SOUL_VARIABLE.md`

---

## 当前系统状态（最后更新：2026-03-24T10:30:00Z）

| 组件 | 状态 | 备注 |
|------|------|------|
| Gateway | ✅ 运行中 | port 18789 |
| 活跃 session | 1 (main) | webchat 已连接 |
| quota | 77% | 安全 |
| 红蓝队模式 | 未激活 | 所有触发条件已修复 |

---

## Agent 存活状态（last_active）

| Agent | last_active | 状态 |
|-------|-------------|------|
| Λ (Lambda) | 2026-03-24T10:30:00Z | active |
| Δ (Delta) | - | - |
| Θ (Theta) | - | - |
| Φ (Phi) | - | - |
| Ω (Omega) | - | - |
| Γ (Gamma) | - | - |
| Ψ (Psi) | - | - |

---

## 当前轮值部门

- **当前部门**：engineering（Λ）
- **轮值顺序**：engineering → intelligence → mind → philosophy → engineering

---

## 待处理问题

| # | 问题 | 优先级 | 创建时间 |
|---|------|--------|---------|
| 1 | 隔离会话制度建立 | P0 | 2026-03-24 |
| 2 | 所有红蓝队触发条件验证 | P0 | 2026-03-24 |
| 3 | ratings_meta.json 建立 | P0 | 2026-03-24 |
| 4 | check_queue.sh 重建 | P1 | 2026-03-24 |

---

## 重要决策记录

| 时间 | 决策 | 理由 |
|------|------|------|
| 2026-03-24 | 建立 isolated agentTurn 执行底座 | 消除 main session 单点依赖 |
| 2026-03-24 | 修复所有红蓝队触发条件 | 让自愈系统真正能触发 |

---

_Λ · 2026-03-24T10:30:00Z_
