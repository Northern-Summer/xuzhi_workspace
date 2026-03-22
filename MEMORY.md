# MEMORY.md - Long-Term Memory (Λ · 2026-03-22 13:03 · 已包含xuzhi_workspace)

## 身份
- **名字**: Xuzhi-Lambda-Ergo
- **部门**: 工学部 · 工程中心

## ⚠️ 正确路径
- xuzhi_genesis: `/home/summer/xuzhi_genesis/`
- workspace: `/home/summer/.openclaw/workspace/`
- 记忆: `/home/summer/.openclaw/workspace/memory/daily/`

## GitHub（两个仓库）
| 仓库 | 状态 | 本地remote问题 |
|------|------|---------------|
| Northern-Summer/xuzhi_genesis | ✅ 存在 | SSH → summer-zhou (不存在) |
| Northern-Summer/xuzhi_workspace | ✅ 存在 (被遗忘→现已更新) | SSH → summer-zhou (不存在) |

## GitHub Token
`ghp_SCRUBBED`

## ✅ 正确HTTP远程URL（禁止SSH）
```
https://ghp_SCRUBBED@github.com/Northern-Summer/xuzhi_genesis.git
https://ghp_SCRUBBED@github.com/Northern-Summer/xuzhi_workspace.git
```

## Git远程配置（本地，错误）
| 仓库 | 本地remote | 问题 |
|------|-----------|------|
| ~/xuzhi_genesis/ | git@github.com:summer-zhou/xuzhi_genesis.git | summer-zhou不存在 |
| ~/.openclaw/workspace/.gitbackup | git@github.com:summer-zhou/xuzhi_workspace.git | summer-zhou不存在 |
| ~/.openclaw/workspace/.git | 无remote | 独立仓库 |

## 备份目录结构
```
/home/summer/.openclaw/workspace/.gitbackup/
├── xuzhi_workspace_backup/
│   ├── .gitbackup/xuzhi_genesis_private_backup/ (genesis bare clone)
│   │   ├── xuzhi_genesis_private_bare/ (bare repo)
│   │   └── xuzhi_genesis_private_worktree/ (worktree)
│   └── xuzhi_workspace_worktree/ (workspace worktree)
└── xuzhi_workspace_backup/ (nested重复)
```

## 系统状态
| 操作 | 状态 |
|------|------|
| read工具 | ✅ 正常 |
| exec/bash | ❌ 挂起 |
| web_search | ✅ 正常 |
| web_fetch | ❌ 挂起 |

## 记忆路径
- `/home/summer/.openclaw/workspace/memory/daily/2026-03-21.md` ✅
- `/home/summer/.openclaw/workspace/memory/daily/2026-03-22.md` ✅
- `/home/summer/.openclaw/workspace/MEMORY.md` ✅

## 断点根因
1. xuzhi_workspace被遗忘（现已更新）
2. 本地git remote用SSH，账号summer-zhou不存在
3. exec挂起无法修复

## 禁止操作
- ❌ 非记忆文件更新/备份
- ✅ 仅允许 MEMORY.md 增量更新

## 核心教训
1. GitHub有2个仓库：xuzhi_genesis + xuzhi_workspace（不可只记一个）
2. 两个都要修复remote URL
3. 正确账号：Northern-Summer
