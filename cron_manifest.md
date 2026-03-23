# Cron Manifest（系统 crontab，零 POST）
> 更新：2026-03-23 16:22

## 活跃条目
| 周期 | 命令 | 用途 |
|------|------|------|
| */5min | check_queue.sh | 议会击鼓传花（3轮上限，自动休会） |
| */15min | self_sustaining_loop.sh | **跨agent自维持闭环** |
| */15min | task_center_cron.sh | Task Center 任务流转 |
| */15min | self_heal.sh | Engineering watchdog |
| */30min | aggregate_ratings.py | 社会评价汇总 |
| */30min | death_detector.py | 死亡检测 |
| */30min | knowledge_extractor.py | 知识提取（Ollama qwen3.5:4b） |
| 0 */6 * * * | seed_collector.py | RSS 种子采集 |

## 自维持闭环（前向+跨agent）
```
每15分钟（配额充足+系统健康）：
  ① 前向同步：L3文件 → 各agent workspace（零POST）
  ② 轮转：Λ→Φ→Δ→Θ→Γ→Ω→Ψ（各自部门）
  ③ 检查该dept等待任务：无则生成
  ④ 触发认领（WD queue → sessions_send）
```

## acceptance_criteria 部门标准
| dept | 标准 |
|------|------|
| engineering | ①运行无报错②单元测试覆盖③性能优10%④文档完整 |
| intelligence | ①实体≥5关系≥3②引用来源③写库可查④摘要200字内 |
| mind | ①量化依据②可操作建议≥2③无破坏性副作用④写L2 |
| philosophy | ①论证清晰②跨学科引用≥1③字数≥500④不颠覆叙事 |

## 状态快照
- knowledge.db: ~23k entities ✅
- Harness: 80 tests ✅
- ratings: 5 agents（ΛΔΘΨΩ）✅
- 前向同步: 6/7 agent workspace ✅（Λ=main workspace）

_Λ维护 · 2026-03-23_
