# 技术架构文档

## 1. 系统总览

```
┌─────────────────────────────────────────────────┐
│              浏览器（前端单文件）                  │
│         wyckoff-portfolio.html (201KB)           │
│  14 个面板 · 原生 JS · 无框架 · 红涨绿跌          │
└──────────────────────┬──────────────────────────┘
                       │ HTTP /fetch
┌──────────────────────┴──────────────────────────┐
│              Flask 后端（71KB）                    │
│            wyckoff-server.py                      │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ 持仓 API  │ │ 行情 API  │ │  Agent 链路 API   │ │
│  │ /portfolio│ │ /market  │ │  /agent/analyze   │ │
│  └──────────┘ └──────────┘ └────────┬─────────┘ │
│  ┌──────────┐ ┌──────────┐          │           │
│  │ 量化选股  │ │ 回测引擎  │          │           │
│  │ /quant/* │ │/backtest │          │           │
│  └──────────┘ └──────────┘          │           │
│  ┌──────────┐                       │           │
│  │ 效果度量  │                       │           │
│  │ /effect/*│                       │           │
│  └──────────┘                       │           │
└─────────────────────────────────────┼───────────┘
                                      │
                    ┌─────────────────┴──────────┐
                    │     Agent 编排层            │
                    │                             │
                    │  ┌─────────────────────┐   │
                    │  │ agent_chain.py       │   │
                    │  │ 自研 5 层 10 节点     │   │
                    │  │ LangGraph StateGraph │   │
                    │  └─────────────────────┘   │
                    │                             │
                    │  ┌─────────────────────┐   │
                    │  │ ta_adapter.py        │   │
                    │  │ TradingAgents 适配器  │   │
                    │  │ FakeTicker→baostock  │   │
                    │  └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────┴───────────────┐
                    │      数据 / LLM 层           │
                    │                             │
                    │  baostock (A 股行情)         │
                    │  wyckoff CLI (市场扫描)      │
                    │  TokenHub → DeepSeek-v4-pro │
                    │  effect_tracker.py (追踪)   │
                    └─────────────────────────────┘
```

## 2. Agent 链路架构

### 2.1 自研 5 层链路

```python
# agent_chain.py
StateGraph:
  START → market_scanner
       → [wyckoff_analyst, technical_analyst, fundamental_analyst]  # 并行
       → bull_researcher → bear_researcher → debate_summarizer
       → trader → risk_manager → portfolio_manager
       → END
```

State 共享：`AgentState(TypedDict)` 携带 16 个字段，每层追加结果。
Trace 日志：每步记录 layer/agent/content/duration_ms。

### 2.2 TradingAgents 集成

```python
# ta_adapter.py
# 关键：在 import tradingagents 之前注入假 yfinance
sys.modules["yfinance"] = fake_module  # FakeTicker 用 baostock
# 然后 TradingAgents 所有 import yfinance 都拿到 FakeTicker
```

7 角色：基本面/情绪/新闻/技术分析师 → 多空辩论 → 交易员 → 风控 → PM

## 3. 效果度量闭环

```
record_prediction() ──→ .ai_effect_tracker.json
                           │
           7天后 check_matured_predictions()
                           │
              baostock 回查实际收盘价
                           │
              is_correct 判定
              ┌──────────┼──────────┐
           买入看涨    卖出看跌    持有看平
              │          │          │
              └──────────┼──────────┘
                         │
              _calc_stats()
              ┌──────────┼──────────┐
           准确率    平均收益    夏普比率
```

## 4. 数据流

### 4.1 市场数据
```
baostock subprocess → fetch_baostock_indices() → 后台线程更新缓存
wyckoff screen CLI → build_market_data() → hot_sectors + regime
→ /api/market → 前端 updateIndexCards() → 指数卡 + 板块 + 温度
```

### 4.2 Agent 链路
```
POST /api/agent/analyze → task_id → 后台线程
  → run_agent_chain(graph, code, name)
    → 10 个节点顺序执行（8 次 LLM）
    → 全程 trace 记录
  → GET /api/agent/analyze/:task_id 轮询
  → 前端 renderAgentResult() 展示
  → 自动 record_prediction() 到效果追踪
```

### 4.3 回测引擎
```
POST /api/backtest/run → task_id → 后台线程
  → subprocess 调 baostock 获取历史 K 线
  → 逐月模拟：选股 → 买入 → 持有 → 卖出
  → 计算 6 项统计 + 权益曲线 + 月度收益
  → baostock 失败时用模拟数据兜底
```

## 5. 前端架构

### 5.1 Z-Index 层级规范
```
1:     base
20:    sidebar / rightbar
30:    fab / assistant button
100:   sticky elements
200:   dropdown menus
1000:  modal content
999:   modal overlay
1100:  assistant panel
9999:  loading overlay
```

### 5.2 非阻塞 Loading
```javascript
// 不再用全屏灰屏 overlay
function showLoading(text) {
  _loadingProgress = showAIProgressCard(text); // 右下角 320px 进度卡
}
```

### 5.3 面板切换
```javascript
switchNav(el, page) {
  // 特殊操作页：screen/backtest/report/pattern/config/settings/signals/quant/agent/realbacktest/effect
  // 普通面板：隐藏所有 → 显示目标 → 加载数据
}
```

## 6. 关键技术决策

| 决策 | 原因 | 替代方案 |
|------|------|---------|
| 原生 HTML 不用 React/Vue | 单文件部署、无构建步骤 | React（但增加复杂度） |
| Flask 不用 FastAPI | 已有代码基础、足够用 | FastAPI（异步更好但过度设计） |
| LangGraph 不用 CrewAI | 状态管理+checkpoint+白盒 | CrewAI（更简单但不显深度） |
| baostock 不用 Tushare | 免费无限制、A 股完整 | Tushare（需积分） |
| TokenHub 不用直接 OpenAI | 免费、DeepSeek 中文好 | OpenAI（更贵） |
| sys.modules 注入不改源码 | 升级安全、零侵入 | Fork TradingAgents（维护成本高） |
