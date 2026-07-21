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

## Provider 与降级顺序

`DataProvider` 是页面和业务服务的唯一数据入口：

1. AKShare，以及配置 `AKTOOLS_URL` 后的 AKTools HTTP 网关。
2. efinance（实时/历史/资金流）、腾讯行情、Mootdx 和 BaoStock（历史/指数/交易日）。
3. 东财与巨潮公开接口（板块、个股资料、研报、新闻、公告）。
4. 配置 `TUSHARE_TOKEN` 后的可选增强。

每个 provider 最多尝试2次，单次10秒超时。指数历史优先使用能区分交易所代码的 BaoStock 备源，避免 `000001` 被错解为个股。上游全部失败时，可返回最近一次可核验快照，但 `cache_status` 必须为 `stale`，且同时保留本次上游错误。

## 缓存结构

- `.ragdoll_data/cache/provider/<method>-<request-hash>.json`：统一请求缓存，原子写入，按方法设置 TTL。
- `.ragdoll_data/cache/market_panorama.json`：市场全景派生指标快照。
- `.ragdoll_data/cache/sector_history.json`：板块日快照，用于轮动持续性的增量计算。

历史行情、指数和资金流按 `symbol + date` 合并增量记录；响应统一携带 `data_date`、`updated_at`、`completeness`、`missing_fields`、`cache_status` 和 `sources`。
