const api = window.RagdollAPI;
const $ = (id) => document.getElementById(id);
const html = (value) => String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

const state = {
  view: "overview",
  activeTabs: { market: "radar", strategy: "create", portfolio: "paper" },
  dataStatus: null,
  systemStatus: null,
  marketPanorama: null,
  legacyMarket: null,
  marketSignals: [],
  marketActions: [],
  marketOverview: null,
  marketRegime: null,
  portfolioSummary: null,
  holdings: [],
  strategies: [],
  factors: [],
  health: [],
  portfolios: [],
  reviews: [],
  reviewStats: null,
  compiled: null,
  savedStrategyId: null,
  strategyStep: 0,
  screenResult: null,
  backtest: null,
  chart: null,
  panoramaChart: null,
  panoramaSeries: {},
  panoramaRange: 40,
  enabledIndices: { sh: true, sz: true, cy: true, hs300: true },
};

const icons = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-7h6v7"/></svg>',
  market: '<svg viewBox="0 0 24 24"><path d="M4 19V5"/><path d="M4 19h16"/><path d="m7 15 3-4 3 2 4-7"/></svg>',
  strategy: '<svg viewBox="0 0 24 24"><path d="M4 6h16"/><path d="M4 12h10"/><path d="M4 18h7"/><path d="M17 13v6"/><path d="M14 16h6"/></svg>',
  portfolio: '<svg viewBox="0 0 24 24"><path d="M4 8h16v11H4z"/><path d="M8 8V5h8v3"/><path d="M8 13h8"/></svg>',
  ai: '<svg viewBox="0 0 24 24"><path d="M12 3v3"/><path d="M12 18v3"/><path d="M4.9 4.9 7 7"/><path d="m17 17 2.1 2.1"/><path d="M3 12h3"/><path d="M18 12h3"/><circle cx="12" cy="12" r="5"/><path d="M10 12h4"/></svg>',
  review: '<svg viewBox="0 0 24 24"><path d="M6 3h12v18H6z"/><path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h3"/></svg>',
  data: '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></svg>',
  alert: '<svg viewBox="0 0 24 24"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 4.5 2.8 18a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.5a2 2 0 0 0-3.4 0z"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="m20 6-11 11-5-5"/></svg>',
  arrow: '<svg viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>',
};

const strategySteps = [
  { title: "表达想法", hint: "输入自然语言" },
  { title: "确认规则", hint: "编辑量化定义" },
  { title: "数据检查", hint: "因子可用性" },
  { title: "筛选验证", hint: "运行漏斗" },
  { title: "保存策略", hint: "版本和后续动作" },
];

function init() {
  renderIcons();
  updateGreeting();
  bindNavigation();
  bindActions();
  $("btEnd").value = new Date().toISOString().slice(0, 10);
  renderStrategyStep();
  renderAiTasks();
  refreshAll();
  setInterval(updateGreeting, 60000);
}

function renderIcons() {
  document.querySelectorAll(".nav-icon").forEach((node) => {
    node.innerHTML = icons[node.dataset.icon] || icons.home;
  });
}

function bindNavigation() {
  document.querySelectorAll("[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      setView(view, btn.dataset.title, btn.dataset.subtitle);
    });
  });
  document.querySelectorAll("[data-tab-target]").forEach((btn) => {
    btn.addEventListener("click", () => setTab(btn.dataset.tabTarget, btn.dataset.tab));
  });
}

function bindActions() {
  $("refreshAllBtn").addEventListener("click", refreshAll);
  $("reloadSystemBtn").addEventListener("click", loadSystem);
  $("reloadStrategiesBtn").addEventListener("click", loadStrategies);
  $("screenBtn").addEventListener("click", screenStrategy);
  $("runBacktestBtn").addEventListener("click", runBacktest);
  $("createPaperPortfolio").addEventListener("click", createPaperPortfolio);
  $("checkReviewsBtn").addEventListener("click", checkReviews);
  $("toggleAdvancedBt").addEventListener("click", () => $("advancedBt").classList.toggle("collapsed"));
  document.querySelectorAll("[data-tab-target='strategy']").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.tab === "factors") renderFactors();
      if (btn.dataset.tab === "library") renderStrategyLibrary();
    });
  });
  document.querySelectorAll("[data-range]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.panoramaRange = Number(btn.dataset.range) || 40;
      document.querySelectorAll("[data-range]").forEach((node) => node.classList.toggle("active", node === btn));
      drawPanoramaChart();
    });
  });
}

function updateGreeting() {
  const now = new Date();
  const hour = now.getHours();
  let timeGreet = "你好";
  if (hour < 9) timeGreet = "早上好";
  else if (hour < 12) timeGreet = "上午好";
  else if (hour < 14) timeGreet = "中午好";
  else if (hour < 18) timeGreet = "下午好";
  else if (hour < 22) timeGreet = "晚上好";
  else timeGreet = "夜深了，注意休息";
  const positions = state.portfolioSummary?.positions;
  const suffix = positions ? `，先看 ${positions} 只持仓和今天的市场结构` : "，先看依据，再做决定";
  $("headerGreeting").textContent = `${timeGreet}${suffix}`;
}

function setView(view, title, subtitle) {
  state.view = view;
  document.querySelectorAll(".nav-item, .utility-btn").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((node) => node.classList.toggle("active", node.id === view));
  $("pageTitle").textContent = title || view;
  $("breadcrumbNow").textContent = title || view;
  $("pageSubtitle").textContent = subtitle || "";
  renderContext();
}

function setTab(target, tab) {
  state.activeTabs[target] = tab;
  document.querySelectorAll(`.tab[data-tab-target="${target}"]`).forEach((node) => node.classList.toggle("active", node.dataset.tab === tab));
  document.querySelectorAll(`[data-panel^="${target}:"]`).forEach((node) => node.classList.toggle("active", node.dataset.panel === `${target}:${tab}`));
  renderContext();
}

async function refreshAll() {
  $("lastUpdated").textContent = "刷新中";
  await Promise.allSettled([
    loadDataStatus(),
    loadSystem(),
    loadMarket(),
    loadPortfolio(),
    loadStrategies(),
    loadHealth(),
    loadPortfolios(),
    loadReviews(),
  ]);
  renderOverview();
  renderMarket();
  renderStrategyLibrary();
  renderFactors();
  renderPortfolio();
  renderReviews();
  renderContext();
  $("lastUpdated").textContent = `更新于 ${new Date().toLocaleTimeString()}`;
}

async function safeLoad(label, fn) {
  try {
    return await fn();
  } catch (error) {
    return { __error: `${label}失败：${error.message}` };
  }
}

async function loadDataStatus() {
  state.dataStatus = await safeLoad("数据状态", () => api.get("/api/data/status"));
  updateSideStatus();
}

async function loadSystem() {
  state.systemStatus = await safeLoad("系统状态", () => api.get("/api/status"));
  renderSystem();
  updateSideStatus();
}

async function loadMarket() {
  const [panorama, legacy, signals, actions, overview, regime] = await Promise.all([
    safeLoad("行情全景", () => api.get("/api/market/panorama")),
    safeLoad("兼容市场", () => api.get("/api/market")),
    safeLoad("市场信号", () => api.get("/api/signals")),
    safeLoad("行动建议", () => api.get("/api/actions")),
    safeLoad("市场概览", () => api.get("/api/market/overview")),
    safeLoad("市场环境", () => api.get("/api/market/regime")),
  ]);
  state.marketPanorama = panorama;
  state.legacyMarket = legacy;
  state.marketSignals = Array.isArray(signals) ? signals : [];
  state.marketActions = Array.isArray(actions) ? actions : [];
  state.marketOverview = overview;
  state.marketRegime = regime;
}

async function loadPortfolio() {
  const [summary, holdings] = await Promise.all([
    safeLoad("持仓汇总", () => api.get("/api/portfolio/summary")),
    safeLoad("持仓列表", () => api.get("/api/portfolio")),
  ]);
  state.portfolioSummary = summary;
  state.holdings = Array.isArray(holdings) ? holdings : [];
}

async function loadStrategies() {
  const data = await safeLoad("策略库", () => api.get("/api/strategies"));
  state.strategies = data.strategies || [];
}

async function loadFactors() {
  const data = await safeLoad("因子库", () => api.get("/api/factors"));
  state.factors = data.factors || [];
}

async function loadHealth() {
  const data = await safeLoad("策略健康", () => api.get("/api/strategy-health"));
  state.health = data.items || [];
}

async function loadPortfolios() {
  const data = await safeLoad("组合列表", () => api.get("/api/portfolios"));
  state.portfolios = data.portfolios || [];
}

async function loadReviews() {
  const [reviews, effectList, effectStats] = await Promise.all([
    safeLoad("复盘列表", () => api.get("/api/reviews")),
    safeLoad("决策记录", () => api.get("/api/effect/list")),
    safeLoad("复盘统计", () => api.get("/api/effect/stats")),
  ]);
  state.reviews = Array.isArray(effectList) ? effectList : [];
  state.reviewStats = effectStats.__error ? null : effectStats;
  state.reviewMessage = reviews.message || null;
}

function updateSideStatus() {
  const dataOk = state.dataStatus && !state.dataStatus.__error && state.dataStatus.status === "ok";
  $("sideDataStatus").textContent = dataOk ? "数据正常" : "数据降级/待查";
  const llm = state.systemStatus && !state.systemStatus.__error && state.systemStatus.llm_configured;
  $("sideLlmStatus").textContent = llm ? "LLM 已配置" : "LLM 未配置";
  $("sidePositions").textContent = state.portfolioSummary?.positions ?? "--";
  $("sideStrategies").textContent = state.strategies?.length ?? "--";
  $("sideReviews").textContent = state.reviewStats?.pending ?? "--";
  $("badgeStrategy").textContent = String(state.strategies?.length ?? "--");
  $("badgePortfolio").textContent = String(state.portfolioSummary?.positions ?? "--");
  $("badgeReview").textContent = String(state.reviewStats?.pending ?? "--");
  $("badgeMarket").textContent = dataOk ? "OK" : "检查";
}

function renderOverview() {
  updateSideStatus();
  updateGreeting();
  const p = state.portfolioSummary || {};
  const panorama = state.marketPanorama || {};
  const b = panorama.breadth || {};
  const r = panorama.regime || {};
  const cards = [
    summaryCard("市场环境", r.label || "待确认", `${r.trend || "趋势待确认"} · ${r.method || "确定性派生"}`, "market", "info"),
    summaryCard("市场宽度", b.up_ratio != null ? `${(b.up_ratio * 100).toFixed(1)}%` : "不可用", `${safeNum(b.up_count)} 上涨 / ${safeNum(b.down_count)} 下跌 · 中位 ${pct(b.median_change)}`, "market", b.up_ratio == null ? "warning" : b.up_ratio >= .55 ? "up" : b.up_ratio <= .45 ? "down" : "brand"),
    summaryCard("全市场成交额", b.amount ? `${(b.amount / 1e8).toFixed(1)}亿` : "不可用", `${panorama.as_of || b.as_of || "日期待确认"} · ${primarySource(panorama)}`, "market", "brand"),
    p.positions ? summaryCard("我的组合盈亏", pct(p.total_pnl_pct), `${money(p.total_pnl)} · 行情覆盖 ${p.priced_positions ?? 0}/${p.positions ?? 0}`, "portfolio", (p.total_pnl || 0) >= 0 ? "up" : "down")
      : summaryCard("我的组合盈亏", "尚未添加真实持仓", "进入组合页添加持仓后显示盈亏和覆盖率", "portfolio", "warning"),
  ];
  $("overviewMetrics").innerHTML = cards.join("");
  renderMarketPanorama();
  renderPortfolioPreview();
  $("actionList").innerHTML = buildActionTasks().join("");
  $("strategyHealthList").innerHTML = renderHealthRows();
}

function renderMarketPanorama() {
  const data = state.marketPanorama || {};
  const indices = Array.isArray(data.indices) ? data.indices : [];
  $("panoramaMeta").textContent = `${data.as_of || "日期待确认"} · ${primarySource(data)} · ${data.status || "loading"}`;
  $("indexStrip").innerHTML = indices.length ? indices.map(indexCard).join("") : errorCard("指数行情不可用", data.__error || data.error || "接口没有返回指数数据。");
  $("indexLegend").innerHTML = indices.filter((idx) => idx.status === "ok").map((idx, i) => {
    const color = indexColor(idx.id, i);
    const off = state.enabledIndices[idx.id] === false ? "off" : "";
    return `<button class="legend-toggle ${off}" data-index-toggle="${html(idx.id)}"><i style="background:${color}"></i>${html(idx.name)}</button>`;
  }).join("");
  document.querySelectorAll("[data-index-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.indexToggle;
      state.enabledIndices[id] = state.enabledIndices[id] === false;
      renderMarketPanorama();
    });
  });
  $("breadthPanel").innerHTML = renderBreadth(data.breadth || {});
  $("sectorHeatmap").innerHTML = renderSectorHeatmap();
  drawPanoramaChart();
}

function indexCard(idx) {
  if (idx.status !== "ok") {
    return `<article class="index-card unavailable"><div class="idx-name">${html(idx.name)}</div><div class="idx-val">不可用</div><div class="idx-chg flat">${html(idx.error || idx.status || "无数据")}</div></article>`;
  }
  const cls = idx.change_pct > 0 ? "up" : idx.change_pct < 0 ? "down" : "flat";
  return `<article class="index-card" title="${html(idx.source || "")} ${html(idx.as_of || "")}">
    <div class="idx-name">${html(idx.name)}</div>
    <div class="idx-val">${formatNumber(idx.value, 2)}</div>
    <div class="idx-chg ${cls}">${signedPct(idx.change_pct)}</div>
    ${sparkline(idx.series, cls)}
    <div class="meta">${html(idx.as_of || "日期待确认")} · ${html(idx.source || "source")}</div>
  </article>`;
}

function sparkline(series, cls) {
  const points = (series || []).slice(-20).filter((p) => p.normalized != null);
  if (points.length < 2) return `<svg class="sparkline" viewBox="0 0 120 30"></svg>`;
  const values = points.map((p) => p.normalized);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const d = points.map((p, i) => {
    const x = i / (points.length - 1) * 120;
    const y = 26 - ((p.normalized - min) / span * 22);
    return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const color = cls === "up" ? "var(--up)" : cls === "down" ? "var(--down)" : "var(--text-muted)";
  return `<svg class="sparkline" viewBox="0 0 120 30"><path d="${d}" stroke="${color}"/></svg>`;
}

function renderBreadth(b) {
  if (!b || b.status === "unavailable") return errorCard("涨跌结构不可用", "全市场快照没有返回 pct_change，未用估算数据填充。");
  const total = b.total || 0;
  const max = Math.max(...(b.buckets || []).map((x) => x.count || 0), 1);
  const rows = (b.buckets || []).map((bucket) => {
    const tone = bucket.label.includes("+") ? "up" : bucket.label.includes("-") ? "down" : "flat";
    const ratio = total && bucket.count != null ? `${(bucket.count / total * 100).toFixed(1)}%` : "--";
    const width = bucket.count == null ? 0 : Math.max(3, bucket.count / max * 100);
    return `<div class="breadth-row" title="${html(bucket.label)} · ${html(bucket.count ?? "不可用")} 只 · ${ratio}">
      <span>${html(bucket.label)}</span><div class="breadth-track"><i class="breadth-fill ${tone}" style="width:${width}%"></i></div><b>${html(bucket.count ?? "--")}</b>
    </div>`;
  }).join("");
  return `<div class="card-head"><h2>全市场涨跌结构</h2><span class="status-pill ${b.status === "ok" ? "ok" : "warning"}">${html(b.status || "partial")}</span></div>
    <div class="breadth-summary">
      ${miniKpi("上涨", safeNum(b.up_count), b.up_ratio != null ? `${(b.up_ratio * 100).toFixed(1)}%` : "比例不可用")}
      ${miniKpi("下跌", safeNum(b.down_count), `平盘 ${safeNum(b.flat_count)}`)}
      ${miniKpi("中位涨跌", pct(b.median_change), "基于 pct_change")}
      ${miniKpi("样本", safeNum(b.total), b.as_of || "日期待确认")}
    </div>
    <div class="breadth-bars">${rows}</div>`;
}

function miniKpi(label, value, meta) {
  return `<div class="breadth-kpi"><strong>${html(value)}</strong><span>${html(label)} · ${html(meta)}</span></div>`;
}

function renderSectorHeatmap() {
  const sectors = (state.legacyMarket?.hot_sectors || state.marketPanorama?.sectors || []).slice(0, 8);
  if (!sectors.length) {
    const refreshing = state.legacyMarket?.refreshing || state.legacyMarket?.provenance?.hot_sectors?.status === "loading";
    return `<div class="notice">${refreshing ? "板块扫描正在后台刷新；指数和市场宽度已先展示。" : "暂无真实板块主线数据；不会显示固定假板块。"}</div>`;
  }
  const maxHeat = Math.max(...sectors.map((s) => Number(s.heat) || 0), 1);
  return sectors.map((s) => {
    const pctValue = Number(s.change_pct);
    const bg = pctValue >= 0 ? `rgba(217, 93, 79, ${Math.min(.28, .08 + (Number(s.heat) || 0) / maxHeat * .2)})` : "rgba(62, 154, 112, .18)";
    return `<button class="sector-tile" data-jump-view="market" title="${html(s.source || "source")} · 热度 ${html(s.heat ?? "--")} · 涨停 ${html(s.limit_up ?? "--")}" style="background:${bg}">
      <strong>${html(s.name || "未命名板块")}</strong><span class="${pctValue >= 0 ? "market-up" : "market-down"}">${signedPct(pctValue)}</span>
      <small>热度 ${html(s.heat ?? "--")} · 涨停 ${html(s.limit_up ?? "--")} · ${html(s.source || "source")}</small>
    </button>`;
  }).join("");
}

function renderPortfolioPreview() {
  if (!state.holdings.length) {
    $("portfolioPreview").innerHTML = emptyBlock("尚未添加真实持仓", "添加持仓后，这里会显示最多5条持仓的价格、盈亏、权重、策略和信号。");
    return;
  }
  const pricedValue = state.holdings.reduce((sum, h) => sum + (Number(h.market_value) || 0), 0) || 1;
  const sorted = state.holdings.slice().sort((a, b) => holdingRiskScore(b) - holdingRiskScore(a)).slice(0, 5);
  $("portfolioPreview").innerHTML = sorted.map((h) => {
    const pnlPct = Number(h.pnl_pct);
    const signal = h.current_signal || h.signal || h.strategy || h.phase || "观察";
    return `<div class="holding-preview-row">
      <div><strong>${html(h.name || h.code || h.symbol)}</strong><small>${html(h.code || h.symbol || "")} · ${html(h.price_date || h.as_of || "日期待确认")}</small></div>
      <div>最新价<small>${formatNumber(h.price ?? h.latest_price, 2)}</small></div>
      <div>当日<small class="${toneFromNumber(h.change_pct)}">${signedPct(h.change_pct)}</small></div>
      <div>盈亏<small class="${toneFromNumber(pnlPct)}">${pct(pnlPct)}</small></div>
      <div>权重<small>${h.market_value ? `${(Number(h.market_value) / pricedValue * 100).toFixed(1)}%` : "不可用"}</small></div>
      <div>信号<small>${html(signal)}</small></div>
    </div>`;
  }).join("");
}

function holdingRiskScore(h) {
  let score = 0;
  if (["breakdown", "exit"].includes(String(h.phase || h.strategy || "").toLowerCase())) score += 50;
  if (Number(h.pnl_pct) < -8) score += 30;
  if (h.price_status && h.price_status !== "ok") score += 20;
  return score;
}

function summaryCard(label, value, meta, target, tone) {
  return `<article class="summary-card ${tone || ""}" data-card-target="${target}">
    <div class="label">${html(label)}</div>
    <div class="value">${html(value)}</div>
    <div class="meta">${html(meta)}</div>
  </article>`;
}

function infoBlock(title, value, meta) {
  return `<div class="check-card"><strong>${html(title)}</strong><p><b>${html(value)}</b><br>${html(meta)}</p></div>`;
}

function buildActionTasks() {
  const tasks = [];
  (state.marketActions || []).slice(0, 5).forEach((item) => {
    tasks.push(taskItem(priorityFromAction(item.type), item.title || item.type || "持仓操作", item.desc || "来自 /api/actions", "portfolio", null, item.time || item.as_of || item.source, item.source || "actions"));
  });
  (state.marketSignals || []).slice(0, 5).forEach((item) => {
    const view = item.source === "wyckoff_cli:event_feed" ? "market" : "portfolio";
    tasks.push(taskItem(priorityFromSignal(item.type), item.title || "市场信号", item.desc || "来自 /api/signals", view, null, item.time || item.as_of, item.source || "signals"));
  });
  if (state.dataStatus?.status !== "ok") {
    tasks.push(taskItem("high", "数据源需要检查", "数据状态不是 ok，请查看来源状态和错误原因。", "system", null, state.dataStatus?.generated_at, "data/status"));
  }
  if (!state.portfolioSummary?.positions) {
    tasks.push(taskItem("medium", "暂无真实持仓", "添加真实持仓后才能计算市值、盈亏和策略血缘。", "portfolio", null, "获取时间", "portfolio"));
  }
  if (!state.strategies.length) {
    tasks.push(taskItem("medium", "还没有保存策略", "从策略研究创建第一版 DSL 策略。", "strategy", "create", "获取时间", "strategies"));
  }
  if ((state.reviewStats?.pending || 0) > 0) {
    tasks.push(taskItem("high", "有决策待复盘", `${state.reviewStats.pending} 条记录待回查。`, "reviews", null, state.reviewStats?.as_of || "获取时间", "effect/stats"));
  }
  (state.health || []).filter((x) => x.status && x.status !== "正常").slice(0, 3).forEach((item) => {
    tasks.push(taskItem("medium", `${item.name || item.strategy_id} · 策略体检`, item.reason || "策略健康接口提示需要观察。", "strategy", "library", item.updated_at || "获取时间", "strategy-health"));
  });
  if (!tasks.length) {
    tasks.push(taskItem("low", "暂无必须处理事项", "当前真实接口没有返回高优先级任务。", "overview", null, "获取时间", "workbench"));
  }
  return tasks.slice(0, 8);
}

function taskItem(priority, title, meta, view, tab, time, source) {
  return `<div class="task priority-${priority}">
    <div class="task-icon">${icons.alert}</div>
    <div><div class="task-title">${html(title)}</div><div class="task-meta">${html(meta)} · ${html(time || "获取时间")} · ${html(source || "source")}</div></div>
    <button class="secondary" data-jump-view="${view}" ${tab ? `data-jump-tab="${tab}"` : ""}>处理</button>
  </div>`;
}

function priorityFromAction(type) {
  return { exit: "high", trim: "high", attack: "medium", probe: "medium", hold: "low" }[String(type || "").toLowerCase()] || "medium";
}

function priorityFromSignal(type) {
  return { alert: "high", entry: "medium", confirmed: "medium", watching: "low" }[String(type || "").toLowerCase()] || "medium";
}

function renderHealthRows() {
  if (!state.health.length) {
    if (!state.strategies.length) return emptyBlock("暂无已保存策略", "从策略研究创建第一版策略后，首页会展示健康状态和最近回测。");
    return state.strategies.slice(0, 5).map((strategy) => `<div class="strategy-row">
      <div class="row-title"><strong>${html(strategy.name)}</strong><span>${html(strategy.id)}</span></div>
      <div class="row-cell">策略已保存<small>尚未运行回测</small></div>
      <div class="row-cell">数据状态<small>等待体检</small></div>
      <button class="secondary" data-jump-view="strategy" data-jump-tab="backtest">运行回测</button>
    </div>`).join("");
  }
  return state.health.slice(0, 5).map((item) => `<div class="strategy-row">
    <div class="row-title"><strong>${html(item.name)}</strong><span>${html(item.strategy_id)}</span></div>
    <div class="row-cell"><span class="chip partial">${html(item.status)}</span><small>${html(item.reason || "等待真实样本积累。")}</small></div>
    <div class="row-cell">最近回测<small>${html(item.latest_backtest?.as_of || "尚未运行")}</small></div>
    <div class="row-cell">可信度<small>${html(item.credibility_score ?? "暂无评分")}</small></div>
    <div class="row-cell">数据状态<small>${html(item.dimensions?.data_health || item.data_status || "待检查")}</small></div>
    <button class="secondary" data-jump-view="strategy" data-jump-tab="library">详情</button>
  </div>`).join("");
}

function renderMarket() {
  const m = state.marketOverview?.overview;
  const r = state.marketRegime?.regime;
  if (!m || state.marketOverview.__error) {
    $("marketRadarGrid").innerHTML = errorCard("市场概览不可用", state.marketOverview?.__error || state.marketOverview?.error || "数据源没有返回市场概览。");
    $("marketRegimeCard").innerHTML = "";
    $("marketBreadthPanel").innerHTML = "";
    return;
  }
  $("marketRadarGrid").innerHTML = [
    summaryCard("A股样本", safeNum(m.total), `${m.source || "source"} · ${m.as_of || "无日期"}`, "market", "brand"),
    summaryCard("上涨家数", safeNum(m.up_count), "来自市场快照；不可用则显示缺失", "market", "up"),
    summaryCard("下跌家数", safeNum(m.down_count), "A股红涨绿跌，绿色代表下跌", "market", "down"),
    summaryCard("成交额", m.amount ? `${(m.amount / 1e8).toFixed(1)}亿` : "不可用", sourceLine(state.marketOverview), "market", "info"),
    summaryCard("市场宽度", r?.breadth || "待确认", r?.method || "等待市场环境接口", "market", "warning"),
    summaryCard("风险偏好", r?.risk_appetite || "待确认", `风格：${r?.style || "待确认"}`, "market", "info"),
  ].join("");
  $("marketRegimeCard").innerHTML = `<div class="card-head"><h2>市场环境</h2><span class="status-pill info">确定性派生</span></div>
    <div class="data-check-grid">
      ${infoBlock("趋势", r?.trend || "待确认", r?.method || "暂无方法说明")}
      ${infoBlock("波动", r?.volatility || "待确认", "当前为基础状态，等待波动率序列接入。")}
      ${infoBlock("风格", r?.style || "待确认", "大小盘相对强弱接口待扩展。")}
    </div>`;
  $("marketBreadthPanel").innerHTML = `<div class="card-head"><h2>指数与市场宽度</h2><span class="${statusClass(state.marketOverview?.source_status?.status)}">${html(state.marketOverview?.source_status?.status || "unknown")}</span></div>
    <div class="notice">上涨家数、下跌家数和成交额来自数据接口；缺失字段不会用估算填充。样本范围：${html(m.total || "待确认")} 只。</div>`;
}

function renderStrategyStep() {
  $("strategyStepper").innerHTML = strategySteps.map((step, index) => {
    const cls = index < state.strategyStep ? "done" : index === state.strategyStep ? "active" : "";
    return `<button class="step ${cls}" data-step="${index}"><strong>${index + 1}. ${html(step.title)}</strong><span>${html(step.hint)}</span></button>`;
  }).join("");
  document.querySelectorAll("[data-step]").forEach((btn) => btn.addEventListener("click", () => {
    const next = Number(btn.dataset.step);
    if (next <= state.strategyStep || canEnterStep(next)) {
      state.strategyStep = next;
      renderStrategyStep();
    } else {
      toast("请先完成前置步骤");
    }
  }));
  const renderers = [renderIdeaStep, renderRuleStep, renderDataCheckStep, renderScreenStep, renderSaveStep];
  $("strategyStepContent").innerHTML = renderers[state.strategyStep]();
  bindStepActions();
  renderContext();
}

function canEnterStep(index) {
  if (index === 0) return true;
  if (index <= 2) return Boolean(state.compiled);
  if (index === 3) return Boolean(state.compiled);
  if (index === 4) return Boolean(state.compiled);
  return false;
}

function renderIdeaStep() {
  const examples = [
    "低价、未进入下行通道、近期未大涨",
    "趋势向上且波动率较低",
    "回撤后重新站上均线",
    "排除 ST 和流动性不足标的",
  ];
  return `<h2>表达投资想法</h2>
    <p class="notice">示例只会填充输入框，不会自动生成股票或收益。</p>
    <div class="example-list">${examples.map((x) => `<button class="example-chip" data-example="${html(x)}">${html(x)}</button>`).join("")}</div>
    <textarea id="ideaInput">找价格低于100元、最近没有进入下行通道、近5日没有大涨、行业景气较强、机构关注增加的股票。</textarea>
    <div class="card-head"><button id="compileBtn">生成策略翻译确认页</button><span class="status-pill warning">不会直接返回股票名单</span></div>`;
}

function renderRuleStep() {
  if (!state.compiled) return emptyBlock("还没有策略草案", "请先在第一步输入投资想法并生成 DSL。");
  const conditions = state.compiled.dsl.entry_conditions.conditions || [];
  const cards = conditions.map((c, idx) => ruleCard(c, idx)).join("");
  return `<div class="card-head"><h2>确认规则</h2><button id="validateBtn" class="secondary">校验规则</button></div>
    <div class="rule-grid">${cards}</div>
    <details><summary>查看技术定义 DSL</summary><pre>${html(JSON.stringify(state.compiled.dsl, null, 2))}</pre></details>`;
}

function ruleCard(c, idx) {
  const ambiguity = (state.compiled.ambiguities || []).find((a) => c.factor.includes("analyst") || a.term?.includes("行业"));
  return `<article class="rule-card ${c.enabled ? "" : "disabled"}">
    <strong>${html(c.factor)}</strong>
    <div class="rule-code">${html(c.factor)} ${html(c.operator)} ${html(c.value)}</div>
    <div class="rule-meta">操作符：${html(c.operator)} · 阈值：${html(c.value)} · lookback：${html(c.lookback || "无")}<br>
    状态：${c.enabled ? "启用" : "禁用"}${ambiguity ? ` · 歧义：${html(ambiguity.message || ambiguity.selected || "")}` : ""}</div>
    <div class="rule-actions">
      <input data-rule-value="${idx}" value="${html(c.value)}" aria-label="规则阈值">
      <button class="secondary" data-apply-rule="${idx}">更新阈值</button>
      <button class="secondary" data-toggle-rule="${idx}">${c.enabled ? "禁用" : "启用"}</button>
    </div>
  </article>`;
}

function renderDataCheckStep() {
  if (!state.compiled) return emptyBlock("等待规则", "生成策略草案后才能检查因子可用性。");
  const conditions = state.compiled.dsl.entry_conditions.conditions || [];
  const byStatus = { available: [], partial: [], unavailable: [], disabled: [] };
  conditions.forEach((c) => {
    const factor = state.factors.find((f) => f.id === c.factor);
    const status = !c.enabled ? "disabled" : factor?.status || "unavailable";
    (byStatus[status] || byStatus.unavailable).push({ c, factor });
  });
  return `<div class="card-head"><h2>数据检查</h2><span class="status-pill info">复权：${html(state.compiled.dsl.price_adjustment)}</span></div>
    <div class="data-check-grid">
      ${checkGroup("可用因子", byStatus.available, "ok")}
      ${checkGroup("部分可用", byStatus.partial, "partial")}
      ${checkGroup("不可用/禁用", [...byStatus.unavailable, ...byStatus.disabled], "error")}
    </div>
    <div class="notice">股票池范围：用户输入或数据源股票列表。若使用当前股票列表作为历史股票池，可能存在幸存者偏差。</div>
    <button id="gotoScreenStep">进入筛选验证</button>`;
}

function checkGroup(title, items, tone) {
  return `<div class="check-card"><strong>${html(title)} <span class="chip ${tone}">${items.length}</span></strong><p>${items.map((x) => `${html(x.c.factor)} · ${html(x.factor?.data_source || "无来源")}`).join("<br>") || "无"}</p></div>`;
}

function renderScreenStep() {
  return `<div class="card-head"><h2>筛选验证</h2><span class="status-pill info">逐步漏斗</span></div>
    <div class="inline-form"><label>股票池代码<input id="symbolsInputStep" value="${html($("symbolsInput")?.value || "")}" placeholder="600519,300750,002415"></label><button id="screenBtnStep">运行筛选</button></div>
    <div id="screenResultStep" class="screen-result">${state.screenResult ? renderScreenResult(state.screenResult) : emptyBlock("尚未运行筛选", "输入明确股票池后运行。没有数据时会展示失败来源。")}</div>`;
}

function renderSaveStep() {
  if (!state.compiled) return emptyBlock("等待策略草案", "完成规则确认后才能保存。");
  const enabledRules = (state.compiled.dsl.entry_conditions.conditions || []).filter((x) => x.enabled).length;
  return `<div class="card-head"><h2>保存策略版本</h2><span class="status-pill warning">保存前确认限制</span></div>
    <div class="data-check-grid">
      ${infoBlock("策略名称", state.compiled.dsl.name, "可在后续版本中重命名。")}
      ${infoBlock("版本", "v1.0", `${enabledRules} 条启用规则。`)}
      ${infoBlock("已知限制", "数据缺口需保留", "机构关注、涨跌停等不可用因子不会进入正式策略。")}
    </div>
    <div class="inline-form"><label>版本说明<input id="strategyVersionNote" value="初版自然语言策略"></label><button id="saveStrategyBtn">保存策略 v1.0</button></div>
    <div id="saveResult">${state.savedStrategyId ? `<div class="success">已保存：${html(state.savedStrategyId)}</div>` : ""}</div>`;
}

function bindStepActions() {
  document.querySelectorAll("[data-example]").forEach((btn) => btn.addEventListener("click", () => {
    $("ideaInput").value = btn.dataset.example;
  }));
  $("compileBtn")?.addEventListener("click", compileIdea);
  $("validateBtn")?.addEventListener("click", validateDsl);
  $("gotoScreenStep")?.addEventListener("click", () => { state.strategyStep = 3; renderStrategyStep(); });
  $("saveStrategyBtn")?.addEventListener("click", saveStrategy);
  $("screenBtnStep")?.addEventListener("click", () => {
    $("symbolsInput").value = $("symbolsInputStep").value;
    screenStrategy(true);
  });
  document.querySelectorAll("[data-toggle-rule]").forEach((btn) => btn.addEventListener("click", () => {
    const i = Number(btn.dataset.toggleRule);
    state.compiled.dsl.entry_conditions.conditions[i].enabled = !state.compiled.dsl.entry_conditions.conditions[i].enabled;
    renderStrategyStep();
  }));
  document.querySelectorAll("[data-apply-rule]").forEach((btn) => btn.addEventListener("click", () => {
    const i = Number(btn.dataset.applyRule);
    const cond = state.compiled.dsl.entry_conditions.conditions[i];
    const input = document.querySelector(`[data-rule-value="${i}"]`);
    const value = input?.value;
    if (value !== undefined && value !== "") {
      cond.value = Number.isNaN(Number(value)) ? value : Number(value);
      renderStrategyStep();
    }
  }));
}

async function compileIdea() {
  const input = $("ideaInput");
  $("strategyStepContent").insertAdjacentHTML("beforeend", `<div class="notice" id="compileLoading">正在生成策略翻译确认页...</div>`);
  try {
    const data = await api.post("/api/strategies/compile", { text: input.value });
    state.compiled = data;
    state.strategyStep = 1;
    toast("策略草案已生成");
    renderStrategyStep();
  } catch (error) {
    $("compileLoading")?.remove();
    $("strategyStepContent").insertAdjacentHTML("beforeend", errorCard("策略编译失败", error.message));
  }
}

async function validateDsl() {
  if (!state.compiled) return;
  try {
    const data = await api.post("/api/strategies/validate", { dsl: state.compiled.dsl });
    const kind = data.ok ? "success" : "error";
    $("strategyStepContent").insertAdjacentHTML("afterbegin", `<div class="${kind}">${data.ok ? "策略校验通过，启用因子可进入筛选。" : html(data.errors.join("；"))}</div>`);
  } catch (error) {
    $("strategyStepContent").insertAdjacentHTML("afterbegin", errorCard("校验失败", error.message));
  }
}

async function saveStrategy() {
  if (!state.compiled) return;
  try {
    const data = await api.post("/api/strategies", { dsl: state.compiled.dsl, version: "v1.0", note: $("strategyVersionNote")?.value || "" });
    state.savedStrategyId = data.strategy.id;
    await loadStrategies();
    renderStrategyStep();
    renderStrategyLibrary();
    toast("策略 v1.0 已保存");
  } catch (error) {
    $("saveResult").innerHTML = errorCard("保存失败", error.message);
  }
}

async function screenStrategy(fromStep = false) {
  if (!state.compiled) {
    setTab("strategy", "create");
    toast("请先创建或确认策略 DSL");
    return;
  }
  if (!state.savedStrategyId) await saveStrategy();
  const symbols = ($("symbolsInput")?.value || $("symbolsInputStep")?.value || "").split(",").map((x) => x.trim()).filter(Boolean);
  const target = fromStep ? $("screenResultStep") : $("screenResult");
  target.innerHTML = `<div class="notice">正在读取真实日线并执行筛选漏斗...</div>`;
  try {
    const data = await api.post(`/api/strategies/${state.savedStrategyId}/screen`, { dsl: state.compiled.dsl, symbols });
    state.screenResult = data;
    target.innerHTML = renderScreenResult(data);
    toast("筛选完成");
  } catch (error) {
    target.innerHTML = errorCard("筛选失败", error.message);
  }
}

function renderScreenResult(data) {
  if (!data?.ok) return errorCard("筛选不可用", data?.error || "没有返回筛选结果。");
  const max = Math.max(...data.funnel.map((x) => x.count), 1);
  const funnel = `<div class="funnel">${data.funnel.map((x) => `<div class="funnel-step"><div><strong>${html(x.label)}</strong><div class="funnel-bar"><i style="width:${Math.max(4, x.count / max * 100)}%"></i></div></div><b>${html(x.count)}</b></div>`).join("")}</div>`;
  const stocks = data.results.length ? `<div class="stock-list">${data.results.map((x) => `<article class="stock-card">
    <strong>${html(x.symbol)} · 第${html(x.rank)}名</strong>
    <p class="row-cell">收盘 ${html(x.close)} · ${html(x.source)} · ${html(x.as_of)}</p>
    <details><summary>查看入选原因</summary>${(x.explanation?.passed || []).map((p) => `<div class="rule-meta">${html(p.factor)}=${html(p.actual)} / ${html(p.operator)} ${html(p.threshold)} · ${html(p.source)} ${html(p.data_date)}</div>`).join("")}</details>
  </article>`).join("")}</div>` : emptyBlock("无入选股票", "筛选条件下没有股票通过，系统没有补造候选。");
  const failures = data.failures?.length ? `<div class="partial">部分股票数据失败：${data.failures.map((f) => `${html(f.symbol)} ${html(f.reason)}`).join("；")}</div>` : "";
  return `${funnel}${stocks}${failures}`;
}

function renderStrategyLibrary() {
  if (!state.strategies.length) {
    $("strategyLibrary").innerHTML = emptyBlock("暂无策略", "在创建策略流程中保存 v1.0 后会出现在这里。");
    return;
  }
  $("strategyLibrary").innerHTML = state.strategies.map((s) => `<div class="strategy-row">
    <div class="row-title"><strong>${html(s.name)}</strong><span>${html(s.description || s.id)}</span></div>
    <div class="row-cell">版本<small>v1.0 / ${html(s.updated_at || "无时间")}</small></div>
    <div class="row-cell">规则<small>${(s.dsl?.entry_conditions?.conditions || []).length} 条</small></div>
    <div class="row-cell">复权<small>${html(s.dsl?.price_adjustment || "qfq")}</small></div>
    <div class="row-cell">基准<small>${html(s.dsl?.benchmark || "sh.000300")}</small></div>
    <button class="secondary" data-use-strategy="${html(s.id)}">载入</button>
  </div>`).join("");
  document.querySelectorAll("[data-use-strategy]").forEach((btn) => btn.addEventListener("click", () => {
    const strategy = state.strategies.find((x) => x.id === btn.dataset.useStrategy);
    if (strategy) {
      state.compiled = { dsl: strategy.dsl, ambiguities: [], semantic_breakdown: [], original_text: strategy.description || "" };
      state.savedStrategyId = strategy.id;
      state.strategyStep = 1;
      setTab("strategy", "create");
      renderStrategyStep();
    }
  }));
}

function renderFactors() {
  const factors = state.factors || [];
  $("factorCountTag").textContent = `${factors.length} 个因子`;
  const categories = [...new Set(factors.map((f) => f.category))];
  $("factorCategories").innerHTML = categories.map((c) => `<button class="example-chip" data-factor-cat="${html(c)}">${html(c)} · ${factors.filter((f) => f.category === c).length}</button>`).join("");
  $("factorTable").innerHTML = `<table><thead><tr><th>ID</th><th>名称</th><th>分类</th><th>公式</th><th>来源</th><th>覆盖</th><th>状态</th></tr></thead><tbody>${factors.map((f) => `<tr data-factor-id="${html(f.id)}"><td>${html(f.id)}</td><td>${html(f.name)}</td><td>${html(f.category)}</td><td>${html(f.formula)}</td><td>${html(f.data_source)}</td><td>${html(f.coverage)}</td><td><span class="chip ${f.status === "available" ? "ok" : f.status === "unavailable" ? "error" : "partial"}">${html(f.status)}</span></td></tr>`).join("")}</tbody></table>`;
  $("factorDetail").innerHTML = factorDetail(factors[0]);
  document.querySelectorAll("[data-factor-id]").forEach((row) => row.addEventListener("click", () => {
    $("factorDetail").innerHTML = factorDetail(factors.find((f) => f.id === row.dataset.factorId));
  }));
}

function factorDetail(f) {
  if (!f) return emptyBlock("暂无因子", "因子接口没有返回数据。");
  return `<div class="card-head"><h2>${html(f.name)}</h2><span class="chip ${f.status === "available" ? "ok" : f.status === "unavailable" ? "error" : "partial"}">${html(f.status)}</span></div>
    <div class="context-body">
      ${contextItem("定义", f.description)}
      ${contextItem("计算公式", f.formula)}
      ${contextItem("数据来源", f.data_source)}
      ${contextItem("样本范围", f.coverage)}
      ${contextItem("缺失情况", "当前尚未完成缺失率截面统计，不绘制伪图表。")}
      ${contextItem("Alphalens接口", "分层收益、IC、Rank IC 接口已预留，尚未完成计算。")}
    </div>`;
}

async function runBacktest() {
  const payload = {
    stocks: $("btStocks").value.split(",").map((x) => x.trim()).filter(Boolean),
    start_date: $("btStart").value,
    end_date: $("btEnd").value,
    initial_capital: Number($("btCapital").value),
    hold_days: Number($("btHoldDays").value),
    max_positions: Number($("btMaxPositions").value),
    commission_rate: Number($("btCommission").value),
    min_commission: Number($("btMinCommission").value),
    stamp_tax_rate: Number($("btStampTax").value),
    transfer_fee_rate: Number($("btTransferFee").value),
    slippage: Number($("btSlippage").value),
    lot_size: Number($("btLotSize").value),
    sellable_after_days: Number($("btT1").value),
  };
  $("backtestProgress").innerHTML = renderBtProgress(0);
  $("backtestResult").innerHTML = "";
  try {
    const task = await api.post("/api/backtests", payload);
    pollBacktest(task.task_id, 1);
  } catch (error) {
    $("backtestProgress").innerHTML = errorCard("回测提交失败", error.message);
  }
}

function renderBtProgress(active) {
  const steps = ["读取行情", "数据校验", "生成信号", "撮合成交", "计算权益曲线", "生成策略体检"];
  return steps.map((s, i) => `<div class="bt-step ${i < active ? "done" : i === active ? "active" : ""}"><span class="bt-dot"></span>${html(s)}</div>`).join("");
}

async function pollBacktest(taskId, tick = 1) {
  $("backtestProgress").innerHTML = renderBtProgress(Math.min(5, tick));
  const data = await api.get(`/api/backtests/${taskId}`);
  if (data.status === "running") {
    setTimeout(() => pollBacktest(taskId, tick + 1), 1100);
    return;
  }
  if (data.status === "error") {
    $("backtestProgress").innerHTML = errorCard("回测失败", data.error || "任务失败。");
    return;
  }
  state.backtest = data.result;
  $("backtestProgress").innerHTML = renderBtProgress(6);
  renderBacktest(data.result);
  renderOverview();
  renderContext();
}

function renderBacktest(result) {
  if (!result?.ok) {
    $("backtestResult").innerHTML = errorCard("回测不可用", result?.error || "没有结果。");
    return;
  }
  const m = result.metrics;
  $("backtestResult").innerHTML = `<div class="result-metrics">
    ${resultMetric("累计收益", pct(m.total_return), "当前仅显示策略曲线", toneFromNumber(m.total_return))}
    ${resultMetric("年化收益", pct(m.annual_return), "CAGR口径", toneFromNumber(m.annual_return))}
    ${resultMetric("最大回撤", pct(m.max_drawdown), "完整权益曲线峰值回撤", "down")}
    ${resultMetric("Sharpe", m.sharpe, "收益周期统计", "info")}
    ${resultMetric("交易级胜率", pct(m.trade_win_rate), `${m.trade_count} 笔交易`, "brand")}
    ${resultMetric("正收益周期", pct(m.positive_period_rate), "不是交易胜率", "info")}
    ${resultMetric("交易成本", money(m.total_cost), "含佣金/印花税/过户费/滑点", "warning")}
    ${resultMetric("可信度", `${result.diagnostics.credibility_score}/100`, "确定性体检评分", "warning")}
  </div>
  <section class="work-card"><div class="card-head"><h2>策略体检</h2><span class="status-pill warning">LLM不能改写评分</span></div><div class="diagnostic-grid">${Object.entries(result.diagnostics.dimensions || {}).map(([k, v]) => `<div class="diag-card"><strong>${html(dimensionLabel(k))} · ${html(v)}</strong><p>${diagnosticText(k)}</p></div>`).join("")}</div></section>
  <section class="work-card"><div class="card-head"><h2>成交记录</h2><span class="status-pill muted">${result.trades.length} 笔</span></div>${renderTrades(result.trades)}</section>
  <section class="work-card"><div class="card-head"><h2>已知限制</h2><span class="status-pill warning">展示给用户</span></div><div class="partial">${result.limitations.map(html).join("<br>")}</div></section>`;
  drawEquity(result.equity_curve, result.drawdown_curve);
}

function resultMetric(label, value, meta, tone) {
  return `<div class="result-metric ${tone || ""}"><span>${html(label)}</span><strong>${html(value)}</strong><small>${html(meta)}</small></div>`;
}

function renderTrades(trades) {
  if (!trades.length) return emptyBlock("暂无成交", "如果股票池、资金或整手约束导致无法成交，会显示为空。");
  return `<div class="table-wrap"><table><thead><tr><th>股票</th><th>入场</th><th>退出</th><th>股数</th><th>收益</th><th>成本</th><th>持有</th></tr></thead><tbody>${trades.slice(-20).map((t) => `<tr><td>${html(t.symbol)}</td><td>${html(t.entry_date)} @ ${html(t.entry_price)}</td><td>${html(t.exit_date)} @ ${html(t.exit_price)}</td><td>${html(t.shares)}</td><td>${html(t.pnl)} / ${html(t.return_pct)}%</td><td>${html(t.cost)}</td><td>${html(t.hold_days)}天</td></tr>`).join("")}</tbody></table></div>`;
}

function drawEquity(points) {
  const node = $("equityChart");
  node.innerHTML = "";
  if (!window.LightweightCharts || !points?.length) return;
  if (state.chart) state.chart.remove();
  state.chart = LightweightCharts.createChart(node, {
    layout: { background: { color: "#fcfdfc" }, textColor: "#352c26" },
    grid: { vertLines: { color: "#e7ebe8" }, horzLines: { color: "#e7ebe8" } },
    rightPriceScale: { borderColor: "#d9dfdb" },
    timeScale: { borderColor: "#d9dfdb" },
  });
  const equity = addLineSeriesCompat(state.chart, { color: "#b58e65", lineWidth: 2 });
  equity.setData(points.map((p) => ({ time: p.date, value: p.equity })));
  state.chart.timeScale().fitContent();
}

function drawPanoramaChart() {
  const node = $("panoramaChart");
  if (!node) return;
  node.innerHTML = "";
  if (state.panoramaChart) {
    state.panoramaChart.remove();
    state.panoramaChart = null;
    state.panoramaSeries = {};
  }
  const indices = (state.marketPanorama?.indices || []).filter((idx) => idx.status === "ok" && state.enabledIndices[idx.id] !== false);
  if (!window.LightweightCharts || !indices.length) {
    node.innerHTML = `<div class="notice">指数走势图暂无可用数据。</div>`;
    return;
  }
  state.panoramaChart = LightweightCharts.createChart(node, {
    layout: { background: { color: "#fffefa" }, textColor: "#352c26" },
    grid: { vertLines: { color: "#eee7dc" }, horzLines: { color: "#eee7dc" } },
    rightPriceScale: { borderColor: "#d9dfdb" },
    timeScale: { borderColor: "#d9dfdb" },
    crosshair: { mode: 1 },
  });
  indices.forEach((idx, i) => {
    const series = addLineSeriesCompat(state.panoramaChart, { color: indexColor(idx.id, i), lineWidth: 2 });
    const points = (idx.series || []).slice(-state.panoramaRange).map((p) => ({ time: p.date, value: p.normalized }));
    series.setData(points);
    state.panoramaSeries[idx.id] = series;
  });
  state.panoramaChart.timeScale().fitContent();
  state.panoramaChart.subscribeCrosshairMove((param) => {
    const tooltip = $("chartTooltip");
    if (!param.point || !param.time || !param.seriesData?.size) {
      tooltip.style.display = "none";
      return;
    }
    const lines = [`日期：${param.time}`];
    indices.forEach((idx) => {
      const datum = param.seriesData.get(state.panoramaSeries[idx.id]);
      if (datum) lines.push(`${idx.name}：${formatNumber(datum.value, 2)}`);
    });
    tooltip.innerHTML = lines.map(html).join("<br>");
    tooltip.style.display = "block";
    tooltip.style.left = `${Math.min(param.point.x + 16, node.clientWidth - 150)}px`;
    tooltip.style.top = `${Math.max(param.point.y + 10, 12)}px`;
  });
}

function addLineSeriesCompat(chart, options) {
  if (typeof chart.addLineSeries === "function") return chart.addLineSeries(options);
  if (window.LightweightCharts?.LineSeries && typeof chart.addSeries === "function") {
    return chart.addSeries(window.LightweightCharts.LineSeries, options);
  }
  throw new Error("Lightweight Charts line series API unavailable");
}

function renderPortfolio() {
  $("portfolioPanel").innerHTML = state.portfolios.length ? state.portfolios.map((p) => `<div class="portfolio-row">
    <div class="row-title"><strong>${html(p.name)}</strong><span>${html(p.kind)} · ${html(p.updated_at || "无更新时间")}</span></div>
    <div class="row-cell">当前市值<small>待持仓接入</small></div>
    <div class="row-cell">收益<small>待计算</small></div>
    <div class="row-cell">持仓数量<small>${html((p.payload?.holdings || []).length)}</small></div>
    <div class="row-cell">数据状态<small>partial</small></div>
    <button class="secondary" data-jump-view="portfolio" data-jump-tab="lineage">血缘</button>
  </div>`).join("") : emptyBlock("暂无模拟组合", "创建模拟组合后，策略候选和持仓血缘会在这里汇总。");
  $("holdingsPanel").innerHTML = renderHoldings();
  $("lineagePanel").innerHTML = renderLineage();
}

function renderHoldings() {
  if (!state.holdings.length) return emptyBlock("暂无真实持仓", "通过旧兼容持仓接口添加真实持仓后，这里会显示价格、成本、收益和信号。");
  return `<div class="card-head"><h2>真实持仓</h2><span class="status-pill muted">${state.holdings.length} 只</span></div>${state.holdings.map((h) => `<div class="holding-row">
    <div class="row-title"><strong>${html(h.name || h.code)}</strong><span>${html(h.code)} · ${html(h.price_source || "无来源")} ${html(h.price_date || "")}</span></div>
    <div class="row-cell">现价<small>${html(h.price ?? "不可用")}</small></div>
    <div class="row-cell">成本<small>${html(h.cost ?? "--")}</small></div>
    <div class="row-cell">收益<small>${html(pct(h.pnl_pct))}</small></div>
    <div class="row-cell">策略<small>${html(h.strategy || "未关联")}</small></div>
    <button class="secondary" data-jump-view="ai">挑战观点</button>
  </div>`).join("")}`;
}

function renderLineage() {
  return `<div class="card-head"><h2>策略血缘</h2><span class="status-pill warning">接口预留</span></div>
    <div class="timeline-row"><div class="row-title"><strong>策略版本 → 入选 → 观察池 → 用户操作 → 当前偏离</strong><span>等待持仓关联来源策略后生成真实时间线。</span></div><div class="row-cell">不生成示例链路</div><div></div><div></div><div></div><button class="secondary" data-jump-view="strategy">去建策略</button></div>`;
}

async function createPaperPortfolio() {
  await api.post("/api/portfolios", { name: "策略观察池", kind: "paper", holdings: [] });
  await loadPortfolios();
  renderPortfolio();
  toast("模拟组合已创建");
}

function renderAiTasks() {
  const tasks = [
    ["市场", "解释当前市场状态", "使用市场概览、市场环境和数据来源。"],
    ["策略", "分析一个策略", "使用已保存 DSL、因子可用性和规则风险。"],
    ["筛选", "解释筛选结果", "使用筛选漏斗、入选原因和失败数据。"],
    ["回测", "诊断回测异常", "使用确定性体检和交易成本。"],
    ["组合", "解释组合风险", "使用持仓、权重和血缘接口。"],
    ["决策", "生成复盘建议", "使用真实决策记录和样本量。"],
  ];
  $("aiTaskGrid").innerHTML = tasks.map(([obj, title, desc], i) => `<article class="ai-task ${i === 0 ? "active" : ""}" data-ai-task="${obj}"><strong>${html(title)}</strong><p>${html(desc)}</p></article>`).join("");
  document.querySelectorAll("[data-ai-task]").forEach((node) => node.addEventListener("click", () => {
    document.querySelectorAll(".ai-task").forEach((x) => x.classList.remove("active"));
    node.classList.add("active");
    renderAiOutput(node.dataset.aiTask);
  }));
  renderAiOutput("市场");
}

function renderAiOutput(kind) {
  const basis = {
    市场: ["数据来源：/api/market/panorama、/api/market、/api/signals、/api/actions", `数据时间：${state.marketPanorama?.as_of || "待确认"}`, "使用字段：四大指数、归一化序列、涨跌幅分布、成交额、热点主线"],
    策略: ["数据来源：/api/strategies、/api/factors", `策略数量：${state.strategies.length}`, "使用字段：DSL、因子状态、复权方式"],
    筛选: ["数据来源：/api/strategies/<id>/screen", `最近筛选：${state.screenResult ? "已运行" : "未运行"}`, "使用字段：漏斗步骤、逐股因子值、失败原因"],
    回测: ["数据来源：/api/backtests/<id>/result", `最近回测：${state.backtest ? "已完成" : "未运行"}`, "使用字段：权益曲线、成交记录、策略体检"],
    组合: ["数据来源：/api/portfolio、/api/portfolios", `持仓数量：${state.holdings.length}`, "使用字段：价格、成本、策略字段、组合payload"],
    决策: ["数据来源：/api/effect/list、/api/effect/stats", `决策记录：${state.reviews.length}`, "使用字段：AI观点、用户反馈、观察期结果"],
  }[kind];
  $("aiOutput").innerHTML = `<div class="data-check-grid">
    ${sectionBlock("数据依据", basis)}
    ${sectionBlock("确定性结果", deterministicPoints(kind))}
    ${sectionBlock("AI解释", ["当前页面只组织待核验解释结构。", "若调用LLM，必须引用左侧数据依据。", "不会自动记录为决策。"])}
    ${sectionBlock("数据缺口", missingPoints(kind))}
    ${sectionBlock("用户操作", ["采纳", "修改", "拒绝", "记录为决策时需真实基准价"])}
  </div>`;
}

function sectionBlock(title, lines) {
  return `<div class="check-card"><strong>${html(title)}</strong><p>${lines.map(html).join("<br>")}</p></div>`;
}

function deterministicPoints(kind) {
  if (kind === "回测" && state.backtest) return [`可信度：${state.backtest.diagnostics.credibility_score}/100`, `交易：${state.backtest.metrics.trade_count} 笔`, `最大回撤：${state.backtest.metrics.max_drawdown}%`];
  if (kind === "策略") return [`策略数：${state.strategies.length}`, `因子数：${state.factors.length}`, "规则由Pydantic校验"];
  return ["当前使用已接入接口返回值。", "缺失值不会被替换成模拟数据。"];
}

function missingPoints(kind) {
  return ["新闻数据未接入", "机构观点不可用时禁用", kind === "组合" ? "行业/风格暴露等待持仓行业数据" : "高级分析接口按P1/P2预留"];
}

function renderReviews() {
  const s = state.reviewStats || {};
  $("reviewMetrics").innerHTML = [
    summaryCard("完整记录率", "暂无真实记录", "需记录假设、反证和失效条件", "reviews", "warning"),
    summaryCard("到期复盘完成率", "暂无到期记录", "基于真实到期记录", "reviews", "info"),
    summaryCard("AI观点采纳率", "暂无确认记录", "需用户确认/修改/拒绝字段", "reviews", "brand"),
    summaryCard("用户修改率", "暂无反馈记录", "等待结构化反馈", "reviews", "warning"),
    summaryCard("方向样本", String(s.directional_checked ?? 0), `至少 ${s.min_directional_sample ?? 30} 条`, "reviews", "info"),
    summaryCard("持有样本", String(s.hold_checked ?? 0), s.sample_sufficient === false ? "样本不足" : "真实记录", "reviews", "info"),
  ].join("");
  $("reviewTimeline").innerHTML = state.reviews.length ? state.reviews.map((p) => `<div class="timeline-row">
    <div class="row-title"><strong>${html(p.stock_name || p.stock_code)}</strong><span>${html(p.decision_date)} · ${html(p.stock_code)}</span></div>
    <div class="row-cell">当时价格<small>${html(p.price_at_decision)}</small></div>
    <div class="row-cell">AI观点<small>${html(p.action)} · 置信度 ${html(p.confidence)}</small></div>
    <div class="row-cell">观察期<small>${html(p.check_date)}</small></div>
    <div class="row-cell">结果<small>${html(p.status)} / ${html(p.actual_return ?? "待回查")}</small></div>
    <button class="secondary">复盘</button>
  </div>`).join("") : emptyBlock("暂无决策记录", state.reviewMessage || "只有用户确认后记录的观点才会进入复盘。");
  $("reviewInsight").innerHTML = [
    insight("样本量提示", s.sample_sufficient === false ? `方向样本 ${s.directional_checked || 0}/${s.min_directional_sample || 30}，不能输出策略有效结论。` : "样本量状态待确认。"),
    insight("偏差分类", "信息错误、规则错误、参数错误、市场环境变化、执行错误、未遵循信号。"),
    insight("月度总结", "当前仅基于真实记录生成；没有记录时不生成模板化总结。"),
  ].join("");
}

function insight(title, text) {
  return `<div class="insight-card"><strong>${html(title)}</strong><p>${html(text)}</p></div>`;
}

async function checkReviews() {
  try {
    const data = await api.post("/api/effect/check", {});
    await loadReviews();
    renderReviews();
    toast(`已检查到期记录：${data.updated || 0} 条更新`);
  } catch (error) {
    $("reviewTimeline").insertAdjacentHTML("afterbegin", errorCard("到期检查失败", error.message));
  }
}

function renderSystem() {
  $("systemPanel").innerHTML = [
    sectionBlock("数据源", Object.entries(state.dataStatus?.checks || {}).map(([k, v]) => `${k}: ${v.ok ? "installed" : v.error}`)),
    sectionBlock("LLM", [state.systemStatus?.llm_configured ? `${state.systemStatus.llm_provider} · ${state.systemStatus.llm_model}` : "未配置，不会泄露Key到前端"]),
    sectionBlock("安全", ["根目录静态文件不暴露", "CORS按本地可信来源限制", "不连接券商，不自动下单"]),
  ].join("");
}

function renderContext() {
  const panorama = state.marketPanorama || {};
  const b = panorama.breadth || {};
  const r = panorama.regime || {};
  const tasks = buildActionTasks().slice(0, 3).map((item) => `<div class="context-item">${item.replace(/<button[\s\S]*?button>/, "")}</div>`).join("");
  const signals = (state.marketSignals || []).slice(0, 3).map((s) => contextItem(s.title || "信号", `${s.desc || ""} · ${s.time || "获取时间"} · ${s.source || "signals"}`)).join("") || contextItem("最新信号", "当前真实接口没有返回新信号。");
  $("contextBody").innerHTML = [
    contextSection("市场状态", [
      contextItem("环境", `${r.label || "待确认"} · ${r.trend || "趋势待确认"}`),
      contextItem("上涨比例", b.up_ratio != null ? `${(b.up_ratio * 100).toFixed(1)}% · ${safeNum(b.up_count)} 上涨 / ${safeNum(b.down_count)} 下跌` : "不可用"),
      contextItem("板块轮动", state.legacyMarket?.regime?.regime_label || "等待真实扫描"),
      contextItem("数据日期", panorama.as_of || b.as_of || "待确认"),
    ]),
    contextSection("今日必看", [tasks || contextItem("暂无任务", "当前真实接口没有返回高优先级任务。")]),
    contextSection("最新信号", [signals]),
    contextSection("数据状态", [
      contextItem("AKShare", providerStatus("akshare")),
      contextItem("Baostock", providerStatus("baostock")),
      contextItem("Wyckoff CLI", state.systemStatus?.wyckoff_cli_available ? "可用" : "不可用或未检查"),
      contextItem("LLM", state.systemStatus?.llm_configured ? `${state.systemStatus.llm_provider || "LLM"} 已配置` : "未配置"),
      contextItem("当前来源", `${primarySource(panorama)} · ${panorama.status || "待确认"}`),
    ]),
    contextSection("快捷入口", [
      quickLink("创建策略", "strategy", "create"),
      quickLink("运行回测", "strategy", "backtest"),
      quickLink("添加持仓", "portfolio"),
      quickLink("启动观点挑战", "ai"),
    ]),
  ].join("");
}

function contextItem(title, body) {
  return `<div class="context-item"><strong>${html(title)}</strong>${html(body)}</div>`;
}

function contextSection(title, items) {
  return `<section class="context-section"><h3>${html(title)}</h3>${items.join("")}</section>`;
}

function quickLink(label, view, tab) {
  return `<button class="secondary" data-jump-view="${view}" ${tab ? `data-jump-tab="${tab}"` : ""}>${html(label)}</button>`;
}

function providerStatus(name) {
  const check = state.dataStatus?.checks?.[name];
  if (!check) return "未检查";
  return check.ok ? check.status : `${check.status} · ${check.error || "不可用"}`;
}

function errorCard(title, message) {
  return `<div class="error"><strong>${html(title)}</strong><br>${html(message)}<br><small>请检查数据源状态或重试。</small></div>`;
}

function emptyBlock(title, message) {
  return `<div class="empty-state"><span class="empty-cat cat-face"></span><h2>${html(title)}</h2><p>${html(message)}</p></div>`;
}

function money(value) {
  if (value === null || value === undefined || value === "") return "--";
  const n = Number(value);
  if (Number.isNaN(n)) return "--";
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(2)}万`;
  return n.toFixed(2);
}
function pct(value) {
  if (value === null || value === undefined || value === "") return "--";
  const n = Number(value);
  return Number.isNaN(n) ? "--" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function signedPct(value) {
  if (value === null || value === undefined || value === "") return "不可用";
  const n = Number(value);
  return Number.isNaN(n) ? "不可用" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || value === "") return "不可用";
  const n = Number(value);
  if (Number.isNaN(n)) return "不可用";
  return n.toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
function safeNum(value) {
  return value === null || value === undefined ? "不可用" : value;
}
function primarySource(payload) {
  const source = (payload?.provenance || []).find((item) => item.status === "ok")?.source;
  return source || payload?.source_status?.source || payload?.overview?.source || payload?.source || "来源待确认";
}
function indexColor(id, fallback = 0) {
  return { sh: "#d95d4f", sz: "#557fa8", cy: "#b58e65", hs300: "#3e9a70" }[id] || ["#d95d4f", "#557fa8", "#b58e65", "#3e9a70"][fallback % 4];
}
function sourceLine(payload) {
  if (!payload || payload.__error) return payload?.__error || "来源不可用";
  const s = payload.source_status?.status || payload.overview?.source || "source unknown";
  return `${s} · ${payload.overview?.as_of || "无日期"}`;
}
function statusClass(status) {
  return `status-pill ${status === "ok" ? "ok" : status === "degraded" || status === "partial" ? "warning" : "error"}`;
}
function toneFromNumber(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "info";
  return n >= 0 ? "up" : "down";
}
function dimensionLabel(key) {
  return {
    data_credibility: "数据可信度",
    backtest_credibility: "回测可信度",
    parameter_stability: "参数稳定性",
    cost_robustness: "成本鲁棒性",
    market_adaptability: "市场适应性",
    return_dispersion: "收益分散度",
  }[key] || key;
}
function diagnosticText(key) {
  return {
    data_credibility: "来源、样本和缺口决定，不由AI随意打分。",
    backtest_credibility: "检查交易约束和权益曲线口径。",
    parameter_stability: "P1将接入敏感性和Walk-forward。",
    cost_robustness: "衡量交易摩擦对策略的影响。",
    market_adaptability: "等待市场环境分组回测。",
    return_dispersion: "检查收益是否集中在少数股票或交易。",
  }[key] || "确定性规则评分。";
}

document.addEventListener("click", (event) => {
  const card = event.target.closest("[data-card-target]");
  if (card) setView(card.dataset.cardTarget, document.querySelector(`[data-view="${card.dataset.cardTarget}"]`)?.dataset.title, document.querySelector(`[data-view="${card.dataset.cardTarget}"]`)?.dataset.subtitle);
  const jump = event.target.closest("[data-jump-view]");
  if (jump) {
    const btn = document.querySelector(`[data-view="${jump.dataset.jumpView}"]`);
    setView(jump.dataset.jumpView, btn?.dataset.title, btn?.dataset.subtitle);
    if (jump.dataset.jumpTab) setTab(jump.dataset.jumpView === "strategy" ? "strategy" : jump.dataset.jumpView, jump.dataset.jumpTab);
  }
});

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2600);
}

init();
