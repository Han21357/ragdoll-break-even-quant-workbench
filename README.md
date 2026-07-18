# 老布偶猫回本之路

AI量化研究与投资决策工作台。

> 把你的投资想法，变成一套能验证、能跟踪、能复盘的量化策略。

## 定位

本项目面向个人投资者。产品通过自然语言和可视化交互，把投资想法转换为透明、可计算、可回测、可跟踪的策略，并持续监控策略在真实持仓中的有效性、风险和执行偏差。

核心链路：

```text
发现市场机会 -> 表达投资想法 -> AI拆解量化定义 -> 用户检查规则
-> 数据可用性检查 -> 股票筛选 -> 历史回测 -> 策略体检
-> 保存策略版本 -> 观察池/模拟组合 -> 持仓策略血缘 -> 复盘偏差
```

产品不连接券商、不自动下单、不承诺收益。AI只做结构化解释和审计，事实必须来自数据接口或明确标记缺口。

## 功能架构

- 工作台：市场状态、策略信号、持仓偏离、回测任务。
- 市场雷达：市场宽度、成交额、涨跌家数、确定性市场环境派生。
- 策略实验室：自然语言策略生成、语义拆解、Pydantic DSL、数据校验、筛选漏斗。
- 因子研究：基础因子注册表，P1预留Alphalens Reloaded分析。
- 回测中心：A股成本、整手、T+1、滑点、权益曲线、交易记录、策略体检。
- 组合中心：观察池、模拟组合、真实持仓血缘接口。
- AI研究员：策略编译、数据审计、回测诊断、组合风险解释。
- 复盘：模型信号与用户操作对照，保留旧决策复盘兼容接口。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash start-server.sh
open http://localhost:8766
```

P1/P2能力可选安装：

```bash
pip install -r requirements-optional.txt
```

## 数据来源

正式数据层位于 `app/services/data/`：

1. AKShare作为主数据源。
2. Baostock作为降级数据源。
3. 两者通过同一接口返回规范字段：`symbol/trade_date/open/high/low/close/volume/amount/turnover_rate/pct_change/adjustment/source/as_of/status`。
4. 接口失败会返回来源状态和失败原因，不会被解释为空结果。

行情和大规模因子数据使用本地缓存目录；策略、版本、回测、组合、血缘和复盘记录使用SQLite，默认在 `.ragdoll_data/ragdoll.sqlite3`。

## 回测限制

当前回测入口已经计算手续费、最低佣金、卖出印花税、过户费、滑点、整手约束和T+1。当前限制会在API和页面展示：

- 未处理分红送转。
- 未完整处理停牌期间订单排队。
- 未处理涨跌停无法成交。
- 未处理退市和ST全历史变更。
- 当前股票池若来自当日股票列表，可能存在幸存者偏差。
- AKQuant包已固定依赖并隔离在适配器后；当前仍使用项目稳定结构输出。

## 产品边界

- 不自动交易，不连接真实券商账户。
- 不生成随机收益、随机股票或未标注模拟数据。
- 数据不可用时失败并显示原因。
- AI不得编造行情、指标、财务、新闻或机构观点。
- VectorBT未加入正式依赖。

## 主要API

```text
GET  /api/data/status
GET  /api/market/overview
GET  /api/market/regime
GET  /api/factors
POST /api/strategies/compile
POST /api/strategies/validate
GET  /api/strategies
POST /api/strategies
POST /api/strategies/<id>/screen
POST /api/backtests
GET  /api/backtests/<task_id>/result
GET  /api/backtests/<task_id>/diagnostics
GET  /api/portfolios
POST /api/reviews
```

旧接口仍保留兼容层，其中 `/api/backtest/run` 会返回 `deprecated: true`，内部使用新版回测引擎。

