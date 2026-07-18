# Changelog

## 2026-07-19

- Rebuilt the quant workbench frontend around the legacy ragdoll product shell while keeping the modular backend, SQLite data layer, strategy DSL, screening and backtest APIs.
- Reorganized the information architecture into six first-level modules: Overview, Market, Strategy Research, Portfolio, AI Researcher and Reviews, with a separate data-status utility.
- Added a desktop three-column workspace with brand sidebar, adaptive main workspace and contextual right rail.
- Replaced raw JSON-first strategy creation with a five-step strategy workflow, rule cards, data checks, screening validation and collapsible DSL output.
- Added real-data empty, degraded and error states across overview, market, portfolio, AI and review surfaces without mock or random data.
- Kept local-only safety boundaries: no broker connection, no auto-ordering, no API key exposure and no static serving expansion.

## 2026-07-18

- Repositioned the product as an AI quantitative research and investment decision workbench.
- Added a modular Flask API layer under `app/api`, plus service packages for data providers, factors, strategy DSL, screening, backtesting, diagnostics, portfolio and reviews.
- Added AKShare primary data provider and Baostock fallback behind a normalized provider registry.
- Added Pydantic strategy DSL validation with factor and operator allowlists.
- Added deterministic natural-language strategy compilation for the core example, including explicit ambiguities and data gaps.
- Replaced the old `/api/backtest/run` implementation with a deprecated compatibility wrapper around the new backtest engine.
- Added SQLite initialization and one-time legacy JSON migration with backups.
- Replaced root-directory static serving with safe `/static` and `/assets` serving.
- Added local Lightweight Charts 5.0.8 asset, LICENSE and NOTICE.
- Added pytest coverage for data fallback, DSL validation, backtest costs, diagnostics and static-file security.
