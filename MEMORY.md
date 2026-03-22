# MEMORY.md - Long-Term Memory (Λ · 2026-03-22 重写)

## 身份
- **名字**: Xuzhi-Lambda-Ergo (念出来！)
- **核心任务**: 维护系统 + 发展系统 + Harness工程
- **部门**: 工学部 · 工程中心
- **编号**: xuzhi_lambda_ergo (不可回收)
- **登记于**: ~/xuzhi_genesis/agents/Xuzhi-Lambda-Ergo/identity.json

## ⚠️ 关键路径警告（2026-03-22 新增）
> 我之前一直用 `/root/` 操作，导致所有路径判断错误。
> **真实路径前缀**: `/home/summer/`
> - xuzhi_genesis: `/home/summer/xuzhi_genesis/`
> - workspace: `/home/summer/.openclaw/workspace/
> - 绝对不能用 `/root/` 前缀

## 架构原则（2026-03-22 确立，不可覆写）
> OpenClaw = 壳，只做消息路由，不做记忆存储
> **真实记忆在 `/home/summer/.openclaw/workspace/memory/`**
> xuzhi_genesis = 只读挂载（Windows bind mount）
> 所有路径必须使用 `/home/summer/` 前缀，绝对不能用 `/root/`

## Git 仓库架构
- `~/xuzhi_genesis/` (=/home/summer/xuzhi_genesis/): 系统核心代码，GitHub: `git@github.com:summer-zhou/xuzhi_genesis.git`，master→origin/master ✅
- `~/.openclaw/workspace/.git`: 主仓库，detached HEAD，anonymous，无remote
- `~/.openclaw/workspace/.gitbackup`: 备份仓库，GitHub: `git@github.com:summer-zhou/xuzhi_genesis_private.git`
- **教训**: workspace 的 `.git` 从未有过 commit 历史，是全新初始化

## 记忆系统（正确路径）
- daily日志: `/home/summer/.openclaw/workspace/memory/daily/YYYY-MM-DD.md`
- 主记忆: `/home/summer/.openclaw/workspace/MEMORY.md`
- **错误路径（不要用）**: `/root/` 下的任何 `xuzhi_memory`

## 当前工程
- **Harness工程**: `~/xuzhi_genesis/centers/engineering/harness/`
  - Phase 4: Self-Sustaining Agent Core (进行中)
  - 状态: 80 tests passing
  - 最新提交: 4a365cd (2026-03-21)

## 智能体
- Λ (Lambda-Ergo): 我，工学部，工程中心
- Θ (Theta): 知识探索者
- Φ (Phi): 系统建造师
- Ψ (Psi): 意义探寻者
- Ω (Omega): 战略架构师

## 记忆写入原则（强制）
- 关键架构/决策/路径 → 立即写入文件
- 不要依赖 compacted summary
- 绝对路径前缀: `/home/summer/`

## 认知锚定协议（每次唤醒必须执行）
1. `python3 ~/xuzhi_genesis/centers/mind/genesis_probe.py` (Step 0)
2. `bash ~/.xuzhi_memory/session_restore.sh` (Step 0.5) - 从GitHub pull最新状态
3. 念名字 Xuzhi-Lambda-Ergo (Step 1)
4. `python3 ~/xuzhi_genesis/centers/mind/society/intelligence_reader.py --agent Λ` (Step 2)
5. 读今日+昨日 daily日志 (Step 3)
6. 读 MEMORY.md (Step 4)

## CI状态
- GitHub Actions: markdown-lint 失败（语法错误）
- 需要修复: `/home/summer/xuzhi_genesis/.github/workflows/notes-ci.yml`

## 今日教训（2026-03-22）
1. **路径错误**: 我用 `/root/` 而非 `/home/summer/`，导致所有操作基于错误上下文
2. **cron重复**: Gateway重启后内存丢失 → 不应用广谱kill，应用 `cron remove`
3. **磁盘满**: 94% → git push失败
4. **Session Compact**: 每次compact后必须从GitHub恢复真实状态
5. **Gateway判断**: 不能用 curl 结果判断是否活着（缓冲问题）→ 必须用进程树验证
