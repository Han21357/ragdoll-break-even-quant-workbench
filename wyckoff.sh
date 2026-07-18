#!/bin/bash
# WyckoffTradingAgent 快速启动脚本
# 用法:
#   ./wyckoff.sh              # 启动 CLI 对话
#   ./wyckoff.sh dashboard    # 启动本地可视化面板
#   ./wyckoff.sh model list   # 查看模型配置
#   ./wyckoff.sh screen       # 全市场漏斗筛选

WYCKOFF_BIN="/Users/solojyhan/.workbuddy/binaries/python/envs/wyckoff/bin/wyckoff"

if [ $# -eq 0 ]; then
    exec "$WYCKOFF_BIN"
else
    exec "$WYCKOFF_BIN" "$@"
fi
