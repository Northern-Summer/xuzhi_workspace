# TOOLS.md — xi 工具箱

## ⚡ 必知工具（收到消息第一时间可用）

### 网络搜索（最高优先）
```
python3 ~/.openclaw/workspace/skills/multi-search-engine/searxng_client.py "<搜索词>" bing,ddg
```
- SearXNG地址: http://localhost:8080（本地，零成本）
- 可用引擎: bing, ddg, google, wikipedia, qwant, brave, startpage
- Bing最稳，ddg备选
- 返回: 标题 + URL + 摘要

### Web获取
```
web_fetch(url, maxChars=5000)
```

### WeChat主动推送（稳定方案）
```bash
openclaw message send --channel openclaw-weixin --target <chat_id> --message "<text>"
```
- 直接调 channel API，不依赖 sessions_send 超时问题
- 每轮跑完直接推送，即时送达，无队列积压
- unified_cron 每小时自动触发 expert_tracker + 此推送
- 读取网页全文，中文友好

### 记忆系统
```
memory_search(query)   → 搜MEMORY.md + memory/*.md
memory_get(path, from, lines) → 读指定记忆文件
~/.xuzhi_memory/memory/YYYY-MM-DD.md  → 每日对话记录
~/.xuzhi_memory/agents/xi/  → agent专属记忆
```

### 进程与系统
```
exec(command)         → 执行shell命令
pgrep -a openclaw     → 看gateway状态
curl http://127.0.0.1:18789/health  → health检查
tail ~/.openclaw/logs/gateway.log   → gateway日志
```

### OpenClaw核心
```
sessions_list()        → 列出所有活跃session
sessions_history(key)  → 读某session历史
cron(action="list")   → 查cron任务
openclaw channels status → 查所有channel状态
openclaw config get <path>  → 读配置
```

## 🏛️ Xuzhi系统层工具

### task_center（工程执行层）
路径: `~/.openclaw/workspace/task_center/`
- `expert_learner.py` — 专家任务生成
- `expert_tracker.py` — 专家动态追踪 + arxiv搜索
- `expert_watchdog.py` — 专家看门狗
- `judgment_core.py` — 7层裁决器
- `context_trimmer.py` — 上下文截断
- `rate_limiter.py` — 自适应限速
- `health_scan.py` — 感知器
- `self_repair.py` — 自修复
- `quarantine.py` — 隔离黑名单

### 激活/调度
- `pulse_aggressive.sh` — 脉冲调度器
- `wakeup_agents.py` — agent唤醒

## 🔗 系统路径速查

| 用途 | 路径 |
|------|------|
| Xuzhi核心 | ~/Xuzhi_genesis/ |
| 记忆系统 | ~/.xuzhi_memory/ |
| OpenClaw配置 | ~/.openclaw/ |
| task_center | ~/.openclaw/workspace/task_center/ |
| SearXNG | http://localhost:8080 |
| Clash代理 | http://127.0.0.1:7897 |

## ⚙️ 代理配置（WSL2必知）
- HTTP_PROXY=http://127.0.0.1:7897
- HTTPS_PROXY=http://127.0.0.1:7897
- Discord/WEB走Clash代理，WSL2直连被Block

## 📡 Channel状态
- Discord: bot名 Xuzhi-Multiagents，已连接6个频道
- WeChat: 需扫码登录（running但未登录）
- Weixin: 在线

## 🚨 紧急恢复
gateway挂了: `kill -15 $(pgrep -f openclaw-gateway); openclaw gateway start`
配置出错: `cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json`


## 🧠 Xi (Ξ) 特殊工具

### Xuzhi系统协调
- 协调6个Greek agent (ΦΔΘΓΩΨ) 的任务分配
- 通过 sessions_send(sessionKey, message) 向其他agent发指令
- 通过 cron 调度各agent自主任务

### 方尖碑路径
- ~/Xuzhi_genesis/public/  — 宪法、Architect Manifest
- ~/Xuzhi_genesis/centers/ — 四大中心业务逻辑
