# Third Party Notices

License check performed on 2026-07-18.

| Project | Use | Version / Pin | License | Notes |
|---|---|---:|---|---|
| AKShare | Primary A-share data provider | `akshare==1.18.64` | MIT | Wrapped by `app/services/data/providers/akshare_provider.py`. |
| AKQuant | Backtest adapter boundary | `akquant==0.1.3` | MIT | Kept behind `app/services/backtest/akquant_adapter.py`; local compatibility runner is used when public APIs are unavailable. |
| Baostock | Fallback A-share daily data | `baostock==0.8.9` | BSD-style free software license | Normalized to the same fields as AKShare. |
| Lightweight Charts | Local browser chart rendering | `5.0.8` vendored JS | Apache-2.0 | Local files under `app/static/vendor/lightweight-charts/`; page includes TradingView attribution. |
| Flask | Web service | `3.1.1` | BSD-3-Clause | Backend API server. |
| Flask-CORS | Local CORS policy | `6.0.1` | MIT | Restricted to configured localhost origins. |
| pandas | Factor and backtest calculations | `2.3.1` | BSD-3-Clause | Dataframe calculations. |
| Pydantic | Strategy DSL validation | `2.11.7` | MIT | Rejects unsafe operators and unregistered executable-like factors. |
| SQLAlchemy | Optional future repository layer | `2.0.41` | MIT | Pinned but current repository uses stdlib sqlite3. |
| LangGraph / LangChain Core | Legacy AI chain support | `1.2.0` / `1.4.0` | MIT | Kept for compatibility, not the main quant workflow. |
| Alphalens Reloaded | Optional P1 factor analysis | `0.4.4` | Apache-2.0 | Optional dependency only. |
| QuantStats | Optional P1 performance analytics | `0.0.64` | Apache-2.0 | Optional dependency only; daily positive-return rate is not called trade win rate. |
| PyPortfolioOpt | Optional P1 portfolio optimization | `1.5.6` | MIT | Optional dependency only. |
| Qlib | Optional P2 ML research | `0.9.7` | MIT | Not a startup dependency. |
| RD-Agent | P2 workflow reference | not installed | MIT | Research loop pattern only, not embedded. |
| TradingAgents | Optional individual-stock research | `0.7.0` | Apache-2.0 | Experimental module only; outputs do not become strategy signals automatically. |

VectorBT is intentionally not included because of its Commons Clause licensing constraints.

