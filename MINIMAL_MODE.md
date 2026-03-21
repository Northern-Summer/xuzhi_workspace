# 极致效率模式

## 配置核心
1. **单模型**: minimax-m2.7 (无备选)
2. **最小工具**: fs.read, fs.write, exec
3. **零审批**: 直接执行
4. **低温度**: 0.1 (高确定性)
5. **大上下文**: 8000 tokens

## 响应模式
- 纯JSON输出
- 零解释
- 纯执行
- 结果导向

## 监控
- tokens/执行
- 时间/任务
- 成功率

## 重启生效
openclaw gateway restart