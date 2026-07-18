# Data Provenance

所有数据结果必须包含来源状态：

```json
{
  "source": "akshare",
  "status": "ok",
  "as_of": "2026-07-17",
  "fetched_at": "2026-07-18T20:00:00",
  "message": null
}
```

状态含义：

- `ok`：数据可用。
- `stale`：可用但延迟。
- `degraded`：主数据源失败后使用降级数据。
- `empty`：接口成功但无数据。
- `unavailable`：接口失败或依赖不可用。

空数据不能被解释为0收益或无候选股票，必须向上返回失败原因。

