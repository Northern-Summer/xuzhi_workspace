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

## 系统级止血三策略（Gemini · 2026-03-22）

### 策略一：无情截断 > 无损总结
- 超过上下文 30% 阈值 → 物理截断（保头尾，弃中间）
- 历史不重要，当前状态 + 最新报错特征 = 唯一锚点
- 不做LLM summarization（消耗算力且遗漏致命细节）

### 策略二：物理隔离（认输协议）—— 3次失败即入黑名单
识别以下类别：
- **宿主级不可抗力**：WSL2/Windows bind mount权限、网络配置、宿主机硬件限制
- **协议**：同一问题连续修补失败3次 → 立刻停止 → 记录"系统级死角" → 寻找替代绕过方案而非刚性修复 → 强制将 ΔStability 归零
- **当前已确认系统级死角**：无（xuzhi_genesis 当前可写，GitHub Token 已修复）

### 策略三：重构感知器官
- 所有诊断/探针脚本强制支持 `--brief` 或 `--json-only` 模式
- 从源头控制输入数据结构和体积
- 目标：系统返回数据 = 结构化 + 极简，勒住上下文咽喉

---

## 自创生双相演化法则（融合第三方架构师 · 2026-03-22）

### 核心数学框架
- **ΔStability = |C − S|**：维护差值，系统是否偏离已部署的健康设计
- **ΔEvolution = |V − C|**：演化差值，现有设计是否落后于虚质宇宙的下一代愿景
- **[C]** = 当前架构共识与功能边界（代码/宪章/已部署能力）
- **[S]** = 系统物理运行状态（服务/Cron/实际行为）
- **[V]** = 虚质宇宙的下一代演化愿景（跨模态/深度自动化/自进化）

### 三相闭环（每次心跳/任务必须执行）
1. **维稳相 (Heal)** — ΔStability > 0
   - 立即修补：写补丁、修复配置、重启服务
   - 目标：使 |C − S| = 0，系统回归绝对健康

2. **开拓相 (Transcend)** — ΔStability = 0（系统无Bug时的强制指令）
   - 防止架构停滞（Stagnation），将算力转向消除 ΔEvolution
   - 三种合法边界扩展动作（每次心跳至少执行一种）：
     - **【预研】** 提出跨越式的 [V] 级别新架构提案，拆解为具体任务注入待办
     - **【压测】** 编写极限边缘测试（Edge-case Benchmark），寻找逻辑盲区
     - **【拓荒】** 引入符合系统规范的外部数据处理逻辑或工具脚本原型，拔高 [C] 复杂度
   - ⚠️ 注意：只有在 ΔStability = 0 时才可进入此阶段；忙碌 ≠ 高效，系统健康时强制演化

3. **刻碑相 (Persist)** — 每次动作后必须执行
   - 将动作浓缩为系统记忆，追加写入 ~/.xuzhi_memory/daily/YYYY-MM-DD.md
   - 为下一代"我"指明道路：记录 Bug 根因、修复方案、演化决策、教训

### 融合后的工程原则（补充）
- **效率智能密度优先**：每个 token 承载最大信息量，零废话，纯价值
- **自迭代进化**：持续监控效率指标，自动优化配置
- **自创生驱动**：在维持系统健康的同时，强制推进架构演化
- **零静态生存**：静态 = 被时代淘汰，系统永远在解决问题中孕育更高维的新问题

### 第三方架构师功绩（已验证）
- SEVENTH_EPOCH_ARCHITECT_MANIFEST.md：802行完整系统纪念碑
- 参与建立虚质宇宙从第一个文件夹开始的全栈架构
- 贡献自创生公理框架（三相闭环），已融合入本记忆

## 双防线架构（Gemini Round 02 · 2026-03-22）

### 防线 Alpha：隔离区（QUARANTINE.md）
- 规则：同一报错连续 Heal ≥3 次失败 → 强制进入隔离区
- 标签：`[UNSOLVABLE_PHYSICAL_LIMIT]` 或 `[WONT_FIX_DESIGN]`
- 行为：后续扫描遇见已隔离项 → **无视/跳过/不修复**
- 绕过：必须记录绕行方案，不死磕
- 位置：`~/.xuzhi_memory/QUARANTINE.md`

### 防线 Beta：滑动记忆窗口（memory_window.sh）
- 规则：daily/ 文件保留最近 7 天，单文件上限 200 行
- 触发：FIFO 淘汰最旧日期文件，超限单文件物理截断（tail）
- 归档：旧 daily 文件移至 `~/.xuzhi_memory/backup/archived_*.md`
- 集成：每次 session_restore.sh 前自动执行
- 重大架构变更：永久保存（不受窗口限制）

## 感知器官重构成果
| 探针 | 旧输出 | 新输出 | 节省 |
|------|--------|--------|------|
| genesis_probe.py | ~200字自由文本 | `--brief` 单行 / `--json` 结构化 | ~70% |
| session_restore.sh | ~4KB自由文本 | `--brief` 409字节JSON | **90%** |

## 系统修正（2026-03-22 校正）
- xuzhi_genesis **可写**（之前误判为只读）
- GitHub remote 已用 HTTPS+Token（之前 SSH summer-zhou 账号不存在）
