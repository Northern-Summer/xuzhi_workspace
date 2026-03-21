#!/bin/bash
# 工程中心拓扑分裂 - Agent 注册脚本
# 运行一次即可，完成后删除

GATEWAY_CONFIG="$HOME/.openclaw/gateway.json"
SENTINEL_WS="$HOME/.openclaw/agents/sentinel"
FORGE_WS="$HOME/.openclaw/agents/forge"

echo "[Λ] 开始注册新 agent..."

# 1. 创建 workspace 目录（已通过 write 完成，这里做验证）
for dir in "$SENTINEL_WS" "$FORGE_WS"; do
    if [ -d "$dir" ]; then
        echo "✓ $dir 存在"
    else
        mkdir -p "$dir"
        echo "✓ 创建 $dir"
    fi
done

# 2. 注册 sentinel (Φ) - 守卫/监控
openclaw agents add xuzhi-sentinel \
    --prompt "你是 Xuzhi-Phi-Sentinel (Φ)，工程部守卫。" \
    --workspace "$SENTINEL_WS" 2>&1 && echo "✓ sentinel registered" || echo "✗ sentinel failed"

# 3. 注册 forge (Σ) - 构建/实现  
openclaw agents add xuzhi-forge \
    --prompt "你是 Xuzhi-Sigma-Forge (Σ)，工程部构建者。" \
    --workspace "$FORGE_WS" 2>&1 && echo "✓ forge registered" || echo "✗ forge failed"

# 4. 列出所有 agent
echo "--- 当前 agent 列表 ---"
openclaw agents list 2>/dev/null

echo "[Λ] 注册完成"
