#!/bin/bash
# investigate_overlay.sh — 调查 overlay 机制
echo "=== Overlay 调查 ==="
echo ""
echo "1. 检查 ~/.openclaw/workspace 挂载情况"
mount | grep workspace || echo "未发现显式挂载"
echo ""
echo "2. 检查 workspace 文件（通过不同路径读取）"
echo "--- ls -la ---"
ls -la ~/.openclaw/workspace/MEMORY.md 2>/dev/null || echo "ls failed"
echo "--- stat ---"
stat ~/.openclaw/workspace/MEMORY.md 2>/dev/null || echo "stat failed"
echo "--- git show HEAD ---"
git -C ~/.xuzhi_memory show HEAD:MEMORY.md 2>/dev/null | head -3
echo "--- diff workspace vs git ---"
diff <(git -C ~/.xuzhi_memory show HEAD:MEMORY.md 2>/dev/null) ~/.openclaw/workspace/MEMORY.md 2>/dev/null && echo "相同" || echo "不同"
echo ""
echo "3. 检查 /home/summer/.xuzhi_memory/ 真实内容"
ls -la ~/.xuzhi_memory/MEMORY.md 2>/dev/null
git -C ~/.xuzhi_memory show HEAD:MEMORY.md 2>/dev/null | wc -c
echo ""
echo "4. overlay 可能性分析"
if git -C ~/.xuzhi_memory show HEAD:MEMORY.md 2>/dev/null | grep -q .; then
  echo "git show 有内容 = overlay 确实遮蔽了 workspace 层"
else
  echo "git show 也为空 = 问题在 git 本身"
fi
echo ""
echo "5. 检查 workspace 的真实挂载"
df -h ~/.openclaw/workspace/ 2>/dev/null
echo ""
echo "6. 写入测试（验证 write 工具写入的内容是否被 overlay 遮蔽）"
TESTFILE="/home/summer/.openclaw/workspace/overlay_test_$(date +%s).txt"
echo "test content $(date)" > "$TESTFILE"
ls -la "$TESTFILE" 2>/dev/null
cat "$TESTFILE" 2>/dev/null
echo ""
echo "=== 调查完成 ==="
