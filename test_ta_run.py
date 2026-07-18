#!/usr/bin/env python3
"""测试 TradingAgents 实际运行 A 股分析"""
import os, sys
import pytest

if os.getenv("RUN_LIVE_TESTS") != "1":
    pytest.skip("live TradingAgents run; set RUN_LIVE_TESTS=1 to run", allow_module_level=True)

for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
    os.environ.pop(k, None)
api_key = os.getenv("TOKENHUB_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    print("SKIP: 请先设置 TOKENHUB_API_KEY 或 OPENAI_API_KEY")
    sys.exit(0)
os.environ['OPENAI_API_KEY'] = api_key
os.environ['OPENAI_BASE_URL'] = os.getenv("TOKENHUB_BASE_URL", "https://tokenhub.tencentmaas.com/v1")

print("1. 测试 yfinance A股数据...")
try:
    import yfinance as yf
    ticker = yf.Ticker("600519.SS")
    hist = ticker.history(period="5d")
    if len(hist) > 0:
        print(f"   OK: 贵州茅台 5日数据, 最新收盘: {hist['Close'].iloc[-1]:.2f}")
    else:
        print("   WARN: 无数据，yfinance 可能无法访问 A股")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n2. 启动 TradingAgents 分析...")
from tradingagents import TradingAgentsConfig, TradingAgentsGraph
config = TradingAgentsConfig(
    llm_provider='openai',
    deep_think_llm='deepseek-v4-pro',
    quick_think_llm='deepseek-v4-pro',
    max_debate_rounds=1,
    max_risk_discuss_rounds=1,
    max_recur_limit=50,
    response_language='zh-CN',
)
ta = TradingAgentsGraph(debug=True, config=config)
try:
    state, decision = ta.propagate("600519.SS", "2026-07-11")
    print("\n=== 决策结果 ===")
    print(f"decision: {decision}")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
