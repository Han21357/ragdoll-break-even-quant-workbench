# Backtest Assumptions

默认A股配置：

- timezone: Asia/Shanghai
- lot_size: 100
- sellable_after_days: 1
- commission_rate: 0.0003
- min_commission: 5元
- stamp_tax_rate: 0.001，仅卖出
- transfer_fee_rate: 0.00001
- slippage: 0.0005
- price_adjustment: qfq
- allow_short: false

当前已处理：手续费、最低佣金、卖出印花税、过户费、滑点、整手约束、T+1。

当前限制：未处理分红送转、涨跌停无法成交、退市和ST历史变化；停牌只做日线可交易近似；当前股票池可能存在幸存者偏差。

年化收益基于完整区间CAGR，最大回撤基于完整权益曲线峰值回撤。

