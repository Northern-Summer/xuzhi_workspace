# Xuzhi Workspace

工程代码仓库。包含系统核心自动化模块、任务执行器和搜索集成。

## 主要模块

- `task_center/` — 核心自动化系统（judgment、quota监控、自愈、雷达等）
- `skills/multi-search-engine/` — SearXNG 搜索集成（零 API 消耗）
- `centers/` — 部门自动化（Engineering、Intelligence、Mind）

## 自动化组件

- `watchdog_supervisor.sh` — Gateway 健康守护（每 30s 检查）
- `watchdog_daemon.py` — 进程级自愈守护
- `agent_spawn.py` — Agent Spawn 管理
- `centers_engineering.py` — Engineering Center 运行器

## 状态

**当前 agent**: Ξ (Xi) — 主会话，接替已流放的 Λ

**最后更新**: 2026-03-26
