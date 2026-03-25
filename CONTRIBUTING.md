# Contributing to Xuzhi Workspace

## 架构纪律

1. **三仓库分离原则**：
   - `~/xuzhi_workspace/` → GitHub Northern-Summer/xuzhi_workspace（工程代码）
   - `~/xuzhi_genesis/` → GitHub Northern-Summer/xuzhi-genesis（宪法）
   - `~/.xuzhi_memory/` → GitHub Northern-Summer/xuzhi_memory（记忆）

2. **`.openclaw/workspace/` 永远不是 git 仓库**

## Git 操作纪律

```bash
# 1. 查看变化
git status

# 2. 确认变化内容
git diff

# 3. 精确 commit 消息
git commit -m "type(scope): precise description"
git commit -m "fix(task_center): context_trimmer safety floor"
git commit -m "chore(catastrophe_recovery): restore 20 memory files"

# 4. Push 到正确 remote
git push origin HEAD
```

## 类型前缀

- `fix` — Bug 修复
- `feat` — 新功能
- `chore` — 维护/清理
- `refactor` — 重构
- `docs` — 文档

## 安全规则

- `rm` 禁用，使用 `gio trash`
- PAT token 禁止写入 git 历史
- commit 前必须验证 `git diff`
