# Changelog

## 2026-07-19

- Added resilient AKShare Sina-first market snapshots and single-stock daily quotes, Eastmoney/Baostock fallback paths, single-flight concurrency control and persistent market panorama caching.
- Restored local TokenHub/Hunyuan-compatible AI configuration, legacy Wyckoff CLI discovery and GitHub Actions secret wiring; verified a real TokenHub response.
- Added a clearly labeled three-stock demo portfolio using real historical closes; the first user holding replaces the demo set.
- Rebuilt the home page as a real market panorama dashboard with four top cards, four-index normalized chart, market breadth structure, portfolio preview, signal/action center and multi-section right rail.
- Added `/api/market/panorama` and a market panorama service for index normalization, breadth buckets, deterministic regime derivation, provenance and partial-state handling.
- Restored the original ragdoll cat avatar, warm time-based greeting and assistant entry so the professional workbench keeps the legacy product warmth.
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
