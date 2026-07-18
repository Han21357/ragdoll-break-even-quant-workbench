# Changelog

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

