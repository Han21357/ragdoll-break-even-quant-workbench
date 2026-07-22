(function () {
  const embeddedFixtures = document.getElementById("staticFixtures")?.textContent;
  const fixturePromise = embeddedFixtures
    ? Promise.resolve(JSON.parse(embeddedFixtures))
    : fetch("fixtures.json").then((response) => {
      if (!response.ok) throw new Error("静态数据快照加载失败");
      return response.json();
    });

  const memory = {
    draft: null,
    strategies: [],
    watchlist: [],
    portfolios: [],
    holdings: [],
    decisions: [],
    committeeTask: null,
  };

  const stocks = [
    { code: "600519", symbol: "600519", name: "贵州茅台", market: "SH", market_label: "上海主板", source: "脱敏股票目录", keys: "600519 6005 贵州茅台 maotai gzmt" },
    { code: "300750", symbol: "300750", name: "宁德时代", market: "CY", market_label: "创业板", source: "脱敏股票目录", keys: "300750 3007 宁德时代 ningdeshidai ndsd" },
    { code: "601318", symbol: "601318", name: "中国平安", market: "SH", market_label: "上海主板", source: "脱敏股票目录", keys: "601318 6013 中国平安 zhongguopingan zgpa" },
    { code: "002415", symbol: "002415", name: "海康威视", market: "SZ", market_label: "深圳主板", source: "脱敏股票目录", keys: "002415 0024 海康威视 haikangweishi hkws" },
  ];

  const clone = (value) => value == null ? value : JSON.parse(JSON.stringify(value));
  const parseBody = (options) => {
    if (!options?.body || options.body instanceof FormData) return {};
    try { return JSON.parse(options.body); } catch (_) { return {}; }
  };

  function compileStrategy(text) {
    const rules = [
      { factor: "pe_ttm", operator: "between", value: "8,35", enabled: true, lookback: null },
      { factor: "roe", operator: ">=", value: 12, enabled: true, lookback: null },
      { factor: "return_20d", operator: ">=", value: -5, enabled: true, lookback: 20 },
      { factor: "analyst_attention", operator: ">=", value: 1, enabled: false, lookback: 90 },
    ];
    return {
      ok: true,
      original_text: text,
      ambiguities: [{ term: "机构关注", message: "静态快照未包含稳定机构研报字段，规则保持禁用。" }],
      assumptions: ["所有条件必须经过因子注册表校验。", "展示版不执行任意 Python。"],
      semantic_breakdown: [{ text: "质量、估值与趋势", definition: "转译为可编辑的量化条件" }],
      dsl: {
        id: `strategy_showcase_${Date.now()}`,
        name: "质量趋势观察策略",
        description: text,
        benchmark: "sh.000300",
        frequency: "daily",
        price_adjustment: "qfq",
        universe: { market: "A股", exclude_st: true, min_listed_days: 120 },
        entry_conditions: { enabled: true, logic: "AND", conditions: rules },
        exit_conditions: { enabled: true, logic: "OR", conditions: [] },
        execution: { rebalance_frequency: "weekly", holding_days: 20 },
        risk: { stop_loss: .08, take_profit: .20 },
        portfolio: { max_positions: 10, single_position_limit: .1 },
        metadata: { compiler: "static_showcase_dsl", requires_user_confirmation: true },
      },
    };
  }

  function screenResult(symbols) {
    const selected = (symbols.length ? symbols : ["600519", "300750", "601318"]).slice(0, 3);
    return {
      ok: true,
      source_status: { status: "snapshot", source: "脱敏静态快照" },
      funnel: [
        { label: "输入股票池", count: selected.length },
        { label: "估值可用", count: selected.length },
        { label: "质量达标", count: Math.max(1, selected.length - 1) },
        { label: "趋势未走弱", count: 1 },
      ],
      results: selected.slice(0, 1).map((symbol, index) => ({
        symbol, rank: index + 1, close: symbol === "600519" ? 1287.13 : 376.57,
        source: "脱敏静态快照", as_of: "2026-07-22",
        explanation: { passed: [
          { factor: "pe_ttm", actual: 24.6, operator: "between", threshold: "8,35", source: "静态快照", data_date: "2026-07-22" },
          { factor: "roe", actual: 31.2, operator: ">=", threshold: 12, source: "年报快照", data_date: "2025-12-31" },
        ] },
      })),
      failures: [],
    };
  }

  function backtestResult() {
    const equity = Array.from({ length: 20 }, (_, index) => ({ date: `2026-07-${String(index + 1).padStart(2, "0")}`, value: 100000 * (1 + [0,.3,.8,.5,1.4,2.1,1.7,2.8,2.4,3.6,4.2,3.8,4.9,4.5,5.7,5.1,6.2,6.8,6.4,7.1][index] / 100) }));
    return {
      ok: true,
      metrics: { total_return: 7.1, annual_return: 13.4, max_drawdown: -3.8, sharpe: 1.12, trade_win_rate: 58.3, positive_period_rate: 61.0, trade_count: 12, total_cost: 486.20 },
      diagnostics: { credibility_score: 82, dimensions: { data_quality: 86, execution_realism: 84, overfitting_risk: 72, sample_coverage: 78 } },
      equity_curve: equity,
      drawdown_curve: equity.map((item) => ({ date: item.date, value: -1.2 })),
      trades: [],
      limitations: ["展示版使用脱敏静态行情快照。", "回测结果仅用于说明产品信息结构，不代表未来收益。"],
    };
  }

  function committeeTask() {
    const roles = [
      ["基本面", "盈利质量仍有支撑"], ["估值", "估值处于历史中位区间"], ["行业", "需求恢复仍需跟踪"],
      ["趋势", "短期趋势未明显走弱"], ["风险", "单股暴露超过预设阈值"], ["反方", "机构调研字段缺失，不能提高置信度"],
    ];
    return {
      id: "committee_showcase_001", status: "completed",
      role_runs: roles.map(([label, conclusion]) => ({ label, status: "completed", conclusion, evidence: [{ field: "快照证据", value: conclusion, date: "2026-07-22", source: "脱敏静态快照" }] })),
      result: { action: "HOLD", conclusion: "持有观察，不增加集中度", evidence_completeness_pct: 82, disclaimer: "静态示例结论，不构成投资建议。" },
    };
  }

  async function resolve(path, options = {}) {
    const fixtures = await fixturePromise;
    const method = (options.method || "GET").toUpperCase();
    const body = parseBody(options);
    const url = new URL(path, window.location.href);
    const route = url.pathname;

    if (route === "/api/stocks/search") {
      const query = (url.searchParams.get("q") || "").toLowerCase();
      return { as_of: "2026-07-22", source: "脱敏股票目录", results: stocks.filter((item) => item.keys.toLowerCase().includes(query)).slice(0, 8).map(({ keys, ...item }) => item) };
    }
    if (method === "POST" && route === "/api/strategies/compile") return compileStrategy(body.text || "");
    if (method === "POST" && route === "/api/strategies/validate") return { ok: true, errors: [], warnings: ["静态展示版只校验规则结构。"] };
    if (method === "PUT" && route === "/api/workflow/strategy-draft") { memory.draft = { ...body, updated_at: new Date().toLocaleString() }; return { draft: memory.draft }; }
    if (method === "DELETE" && route === "/api/workflow/strategy-draft") { memory.draft = null; return { ok: true }; }
    if (method === "POST" && route === "/api/strategies") {
      const strategy = { id: `strategy_showcase_${Date.now()}`, name: body.dsl?.name || "展示策略", description: body.dsl?.description, dsl: body.dsl, updated_at: new Date().toLocaleString() };
      memory.strategies.push(strategy); return { strategy };
    }
    if (method === "POST" && /\/api\/strategies\/[^/]+\/screen$/.test(route)) return screenResult(body.symbols || []);
    if (method === "POST" && route === "/api/backtests") return { task_id: "backtest_showcase_001", status: "running" };
    if (method === "GET" && route === "/api/backtests/backtest_showcase_001") return { status: "completed", result: backtestResult() };
    if (method === "POST" && route === "/api/analyze") return {
      model: "静态结构示例", generated_at: new Date().toLocaleString(), holdings_kind: "demo", main_action: "HOLD", score: 82,
      diagnosis: { content: "市场宽度处于中性区间，组合收益为正，但单股与行业集中度偏高。当前更适合补全失效条件，而不是增加风险。" },
      risk: { content: "上涨比例未形成压倒性方向；机构调研字段缺失，需要人工核验。" },
      adjustments: { items: [{ stock: "贵州茅台", action: "持有观察", reason: "盈利质量仍有支撑，但集中度偏高" }] },
      evidence: { breadth: "46.6%", median_change: "-0.13%", max_single_exposure: "50.01%", as_of: "2026-07-22", source: "脱敏静态快照" },
      data_limits: ["GitHub Pages 不连接实时行情或大模型。"], disclaimer: "这是静态展示输出，不构成投资建议或收益承诺。",
    };
    if (method === "POST" && route === "/api/watchlist") { memory.watchlist.push({ ...body, id: `watch_${Date.now()}`, created_at: new Date().toLocaleDateString() }); return { ok: true }; }
    if (method === "POST" && route === "/api/watchlist/to-strategy") return compileStrategy("根据观察池生成质量与趋势策略");
    if (method === "POST" && route === "/api/portfolios") { memory.portfolios.push({ id: `portfolio_${Date.now()}`, name: body.name, kind: body.kind, payload: { holdings: [] }, updated_at: new Date().toLocaleString() }); return { ok: true }; }
    if (method === "POST" && route === "/api/portfolios/from-screen") { memory.portfolios.push({ id: `portfolio_${Date.now()}`, name: "筛选结果模拟组合", kind: "paper", payload: { holdings: body.selected || [], evidence_snapshot_id: "snapshot_screen_showcase", strategy_id: body.strategy_id }, updated_at: new Date().toLocaleString() }); return { ok: true }; }
    if (method === "POST" && route === "/api/workflow/positions/import/preview") {
      const sourceRows = body.rows || [];
      const rows = sourceRows.map((row, index) => ({ row_number: index + 1, symbol: row.symbol, name: row.name, quantity: Number(row.quantity), cost_price: Number(row.cost_price), valid: Boolean(row.symbol && Number(row.quantity) > 0 && Number(row.cost_price) > 0), errors: [], warnings: [], conflict: ["600519", "300750", "601318"].includes(row.symbol) }));
      rows.forEach((row) => { if (!row.valid) row.errors.push("请补全股票、数量和成本价"); });
      return { mapping: { symbol: "股票目录", quantity: "持仓数量", cost_price: "成本价" }, rows, summary: { total: rows.length, valid: rows.filter((row) => row.valid).length, invalid: rows.filter((row) => !row.valid).length, conflicts: rows.filter((row) => row.conflict).length } };
    }
    if (method === "POST" && route === "/api/workflow/positions/import/commit") {
      const imported = (body.rows || []).map((row) => {
        const stock = stocks.find((item) => item.code === row.symbol) || {};
        return {
          code: row.symbol, name: row.name || stock.name || row.symbol, market: stock.market || "A股",
          cost: Number(row.cost_price), shares: Number(row.quantity), sector: "待分类", strategy: "hold",
          phase: "unknown", phase_label: "待判断", suggestion: "本页内存持仓，刷新后恢复。",
          is_demo: true, created_at: new Date().toISOString(), price_status: "missing",
          price: null, market_value: null, pnl: null, pnl_pct: null,
        };
      });
      memory.holdings.push(...imported);
      return { imported, skipped: [], static_showcase: true };
    }
    if (method === "POST" && route === "/api/workflow/committee/tasks") { memory.committeeTask = committeeTask(); return { task: memory.committeeTask }; }
    if (method === "GET" && /\/api\/workflow\/committee\/tasks\//.test(route)) return { task: memory.committeeTask || committeeTask() };
    if (method === "POST" && /\/api\/workflow\/committee\/tasks\/.+\/decision$/.test(route)) return { ok: true };
    if (method === "POST" && route === "/api/decisions") { memory.decisions.push(body); return { ok: true }; }

    if (method === "GET" && route === "/api/workflow/strategy-draft" && memory.draft) return { draft: memory.draft };
    if (method === "GET" && route === "/api/strategies" && memory.strategies.length) return { strategies: [...(fixtures[route]?.strategies || []), ...memory.strategies] };
    if (method === "GET" && route === "/api/watchlist" && memory.watchlist.length) return { items: [...(fixtures[route]?.items || []), ...memory.watchlist] };
    if (method === "GET" && route === "/api/portfolios" && memory.portfolios.length) return { portfolios: [...(fixtures[route]?.portfolios || []), ...memory.portfolios] };
    if (method === "GET" && route === "/api/portfolio" && memory.holdings.length) return [...(fixtures[route] || []), ...memory.holdings];
    if (method === "GET" && route === "/api/reviews" && memory.decisions.length) {
      const base = clone(fixtures[route]); base.decisions.push(...memory.decisions.map((item, index) => ({ ...item, id: `decision_memory_${index}`, created_at: new Date().toLocaleDateString(), evidence_snapshot_id: "snapshot_memory", result: null }))); return base;
    }

    const exact = fixtures[path];
    const base = fixtures[route];
    if (exact !== undefined) return clone(exact);
    if (base !== undefined) return clone(base);
    throw new Error(`静态展示暂不执行此操作：${method} ${route}`);
  }

  window.RagdollAPI = {
    request: resolve,
    get(path) { return resolve(path); },
    post(path, payload) { return resolve(path, { method: "POST", body: JSON.stringify(payload || {}) }); },
    put(path, payload) { return resolve(path, { method: "PUT", body: JSON.stringify(payload || {}) }); },
    delete(path) { return resolve(path, { method: "DELETE" }); },
    upload(path) { return Promise.reject(new Error("静态展示版不读取本地持仓文件，请使用手工录入体验。")); },
  };
}());
