#!/usr/bin/env python3
"""测试 TradingAgents 集成"""
import os
import sys
import pytest

if os.getenv("RUN_LIVE_TESTS") != "1":
    pytest.skip("live TradingAgents import; set RUN_LIVE_TESTS=1 to run", allow_module_level=True)

# 清除代理
for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
    os.environ.pop(k, None)
# 用 TokenHub 作为 OpenAI 兼容端点
api_key = os.getenv("TOKENHUB_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    print("SKIP: 请先设置 TOKENHUB_API_KEY 或 OPENAI_API_KEY")
    sys.exit(0)
os.environ['OPENAI_API_KEY'] = api_key
os.environ['OPENAI_BASE_URL'] = os.getenv("TOKENHUB_BASE_URL", "https://tokenhub.tencentmaas.com/v1")

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
print('Config OK:', config.llm_provider, config.deep_think_llm)

ta = TradingAgentsGraph(debug=False, config=config)
print('Graph OK, ready to propagate')
