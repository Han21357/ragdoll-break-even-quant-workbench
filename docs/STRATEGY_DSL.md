# Strategy DSL

`StrategyDSL` 是策略的稳定保存格式。核心字段：

- `universe`
- `frequency`
- `price_adjustment`
- `entry_conditions`
- `exit_conditions`
- `ranking`
- `portfolio`
- `execution`
- `risk`
- `benchmark`
- `parameters`
- `metadata`

条件使用 `Condition`：

```json
{
  "factor": "close",
  "operator": "<",
  "value": 100,
  "lookback": null,
  "params": {},
  "enabled": true
}
```

允许操作符：`>`、`>=`、`<`、`<=`、`==`、`between`、`cross_above`、`cross_below`、`top_percentile`、`bottom_percentile`。

组合逻辑支持 `AND`、`OR`、`NOT` 和嵌套组。

