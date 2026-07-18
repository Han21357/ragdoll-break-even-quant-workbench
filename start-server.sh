#!/bin/bash
# 威科夫投资工作台 · 自动重启守护
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-$(command -v python3)}"
SERVER="$ROOT/wyckoff-server.py"
export PORT="${PORT:-8766}"
echo "🐱 威科夫投资工作台 · 自动重启守护启动"
while true; do
    echo "[$(date '+%H:%M:%S')] 启动服务..."
    "$PYTHON" "$SERVER"
    echo "[$(date '+%H:%M:%S')] 服务退出，2秒后重启..."
    sleep 2
done
