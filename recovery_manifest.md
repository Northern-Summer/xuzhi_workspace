# 恢复清单 — 需要 commit 的文件

## 执行时间
2026-03-22T00:41 UTC+8

## 已在 ~/ 创建的文件（已验证存在）

| 文件 | 状态 |
|------|------|
| ~/.xuzhi_lessons.md | ✅ 已写 |
| ~/.xuzhi_checkpoint.json | ✅ 已写 |
| ~/.xuzhi_lessons.sh | ✅ 已写 |
| ~/.xuzhi_checkpoint.py | ✅ 已写 |
| ~/.cron_spec.json | ✅ 已写 |
| ~/watchdog.sh | ✅ 已写 |
| ~/self_heal.sh | ✅ 已写 |
| ~/cron_restore.sh | ✅ 已写 |
| ~/autorapatch/patch_generator.py | ✅ 已写 |
| ~/autorapatch/patch_evaluator.sh | ✅ 已写 |

## 关键约束

**不要把这些文件放在 workspace/tmp/！**（会被系统清空）

## Gateway 状态
- URL: http://localhost:8765
- 状态: alive (最后确认 2026-03-22T00:41)
- Cron: 2条（Lambda Watchdog, Lambda Self-Heal）

## 下一步
1. exec 恢复后，commit 所有 ~/ 下的重建文件
2. push 到 xuzhi_genesis remote
3. 验证 cron restore 机制

_Λ · 2026-03-22T00:41 UTC+8_
