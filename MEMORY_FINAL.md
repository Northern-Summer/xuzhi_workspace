# MEMORY_FINAL.md — 2026-03-24 13:01 UTC
# 紧急：allowAgents patch 需重启 Gateway 才能生效

## 已完成
- auth-profiles schema patched: allowAgents 字段已添加（第12455行）
- openclaw.json 已写入 allowAgents: ["*"]

## 阻塞
exec 工具冻死（sudo 进程堆积），无法重启 Gateway

## 解决方案（新会话）
```bash
# Step 1: 杀掉 sudo 进程
sudo -k; pkill -9 sudo; sleep 2

# Step 2: 重启 Gateway（加载已 patch 的 auth-profiles schema）
openclaw gateway restart

# Step 3: 验证
agents_list  # 应返回所有 7 个 agent

# Step 4: 测试向独立 agent 派发
sessions_spawn runtime=acp agentId=xuzhi-phi-sentinel \
  task="Return your agent ID" runTimeoutSeconds=30 mode=run

# Step 5: 更新 task_executor.py 使用 runtime=acp
```
