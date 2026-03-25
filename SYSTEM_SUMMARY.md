# 系统架构摘要

> 2026-03-25 重建。原文版本管理混乱，本版重新梳理。

## 核心原则

- **清晰优于完备**。宁可少做，不要做乱。
- **文件即记忆**。不靠脑子记，靠文件。
- **每个 Agent 有明确职责**，不重复、不重叠。
- **议会决策，Summer 拍板**。

## 系统组件

### 1. Summer（主控）
- 文件：`SOUL.md`、`USER.md`、`BOOT.md`
- 职责：全局统筹、最终决策、对外沟通

### 2. Ergo（元认知）
- 文件：`agents/Ergo/SOUL.md`、`agents/Ergo/logs/`
- 职责：追踪思考过程、识别逻辑漏洞、记录决策理由

### 3. 智能议会（Parliament）
- 目录：`parliament/`
- 成员：`parliament/members/members.yaml`
- 规则：`parliament/PARLIAMENT.md`
- 主席：Summer | 记录官：Ergo

### 4. 部门（Departments）
- 目录：`departments/{research,engineering,strategy}/`
- 各自有 `SOUL.md`，向议会报告

### 5. 公共记忆池
- 主文件：`MEMORY.md`（精华，长期）
- 每日：`memory/YYYY-MM-DD/`
- 每周：`memory/YYYY-WXX/`

### 6. 技能库
- 目录：`skills/`
- 共享工具和知识，对所有 Agent 开放

## 待重建项目

- [ ] 各 Agent 独立工作区（`agents/XX/` 子目录结构化）
- [ ] 情报收集机制（SearXNG + 外部搜索）
- [ ] 任务中心（`task_center/` 运作流程）
- [ ] 专家追踪系统（`expert_tracker/`）

## 命名规范

- 目录：全小写、下划线分隔
- 文件：大写开头、驼峰式（SOUL.md、MEMORY.md）
- Agent 目录：`agent_name/`（小写、下划线）
