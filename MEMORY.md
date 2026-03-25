# 公共记忆池

> 所有 Agent 共享的长期记忆。由智能议会管理，各部门贡献知识，Summer 统筹维护。

---

## 系统架构

```
xuzhi_workspace/
├── memory/           # 每日对话记忆（raw）
├── departments/      # 各部门知识库
├── parliament/       # 智能议会（多Agent协作机制）
├── skills/          # 共享技能
├── task_center/      # 任务协调中心
└── expert_tracker/  # 外部知识追踪
```

## Agent 人格

- **Summer**（主控）：`SOUL.md`，全面统筹
- **Ergo**（元认知）：`agents/Ergo/`，思考过程追踪
- **子域专家**：各 `agents/XX_XX/` 子目录

## 关键约定

- 每次重要对话后写 `memory/YYYY-MM-DD.md`
- 每月末合并到 MEMORY.md
- 议会成员信息在 `parliament/members.yaml`
- 部门知识在 `departments/XX/`

---

## 重要决策记录

_按时间倒序填充_
