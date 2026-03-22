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

## ⚠️ Token 存储原则
- Token 不应明文写入文件（GitHub Secret Scanning 会阻止 push）
- 使用 `git remote -v` 查看当前配置的 remote URL
- Token 如需使用：通过 GitHub CLI (`gh auth token`) 或环境变量

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

## P0优化：上下文爆炸修复（2026-03-22 15:21）

### 问题根因
- contextPruning mode=cache-ttl，ttl=1h，每小时自动prune+compaction
- SOUL.md 396行全量注入，每次占用大量上下文
- session恢复形成git pull死循环（workspace overlay机制）
- Project Context合计超1200行/次注入

### 解决方案
| 改动 | 效果 |
|------|------|
| P0-A: SOUL.md精简 | 396行→98行（节省76%） |
| P0-A: SOUL_IMMUTABLE.md | 56行不可覆写核心独立保存 |
| P0-A: SOUL_VARIABLE.md | 35行当前状态独立保存 |
| P0-B: session_restore.sh | 去除无效git pull，仅读xuzhi_memory层 |
| P0-C: contextPruning=off | 完全禁用自动pruning |
| P0-C: hardClearRatio=0.95 | 95%上下文才强制清理 |

### 验收状态
- ✅ 所有6项安全检查通过
- ✅ contextPruning=off后预算足够（~350轮对话）
- ✅ Gateway已热重载生效
- ✅ pre_compact_guard验证通过（创建commit 9666c15）

### 风险评估
- 🟡 contextPruning=off：session无限膨胀风险 → 由200k ctx硬上限保护
- 🟡 SOUL精简：不可覆写段落保留 → 由SOUL_IMMUTABLE.md独立保护
