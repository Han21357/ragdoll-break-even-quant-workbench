# Architecture

```text
数据源
-> 统一数据层
-> 因子层
-> 策略DSL
-> AKQuant适配边界/回测执行
-> 因子和绩效分析
-> 策略体检
-> 组合与持仓
-> AI解释与复盘
```

## Runtime

- `wyckoff-server.py`：兼容入口，负责启动Flask、旧接口和安全静态文件。
- `app/api/quant_workbench.py`：新版量化工作台API。
- `app/templates/index.html`：新版工作台模板。
- `app/static/css|js`：拆分后的前端资源。

默认端口为 `8766`。CORS限制在 `.env` 的 `RAGDOLL_ALLOWED_ORIGINS`。根目录不再作为静态目录暴露。

## Data Layer

```text
app/services/data/
  base.py
  models.py
  registry.py
  cache.py
  provenance.py
  providers/
    akshare_provider.py
    baostock_provider.py
```

AKShare是主数据源，Baostock是降级数据源。所有Provider返回 `DataResult`，包含 `ok/data/error/provenance`。空数据和接口失败分开处理。

## Factor Layer

`app/services/factors/registry.py` 注册P0因子，状态包括 `available/partial/unavailable/experimental`。不可用因子不能进入正式策略。

`calculator.py` 根据规范化日线计算MA、收益、波动率、RSI、MACD、OBV、ATR等确定性因子。

## Strategy DSL

`app/schemas/strategy.py` 定义 `StrategyDSL`、`ConditionGroup`、`Condition`。条件只允许白名单操作符，不允许任意Python。

`app/services/strategies/compiler.py` 把自然语言投资想法转换成三层确认结果。`validator.py` 校验因子和数据可用性。`screener.py` 输出筛选漏斗和逐股解释。

## Backtest

```text
app/services/backtest/
  engine.py
  akquant_adapter.py
  result_normalizer.py
  diagnostics.py
```

AKQuant被隔离在适配器后，前端永远只接收项目自己的稳定JSON结构。当前执行器计算A股成本、整手、T+1、滑点、权益曲线、回撤曲线、成交记录和体检。分红送转、涨跌停无法成交、退市和ST历史变化会作为限制显示。

## Storage

SQLite默认路径：`.ragdoll_data/ragdoll.sqlite3`。

保存对象：

- 策略
- 策略版本
- 回测任务和结果
- 模拟组合
- 持仓策略血缘
- AI研究记录
- 决策复盘
- 迁移日志

旧JSON文件不删除。启动时自动备份并迁移，备份保存在 `.ragdoll_data/`。

## AI Modules

主流程只保留结构化Agent角色：策略编译、数据审计、回测诊断、稳健性、组合风险和个股研究。旧 `agent_chain.py` 和 `ta_adapter.py` 是兼容/实验模块，不再作为量化策略生成和回测核心。

