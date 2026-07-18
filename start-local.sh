#!/bin/bash
# ============================================
#  老布偶猫回本之路 · 本地启动脚本
#  在终端执行: bash start-local.sh
#  不依赖沙盒，不依赖对话窗口
# ============================================

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-$(command -v python3)}"
SERVER="$ROOT/wyckoff-server.py"
LOG="$ROOT/logs/server.log"
export PORT="${PORT:-8766}"

mkdir -p "$(dirname "$LOG")"

echo "🐱 老布偶猫回本之路 · 智能投资工作站"
echo "   地址: http://localhost:${PORT}"
echo "   日志: $LOG"
echo "   按 Ctrl+C 停止服务"
echo "----------------------------------------"

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动服务..."
    "$PYTHON" "$SERVER" >> "$LOG" 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 服务退出(退出码: $?)，2秒后重启..."
    sleep 2
done
