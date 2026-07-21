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
  portfolioAnalytics: null,
  dataCoverage: null,
  watchlist: [],
  decisions: [],
  holdings: [],
  strategies: [],
  factors: [],
  health: [],
  portfolios: [],
  reviews: [],
  workflowPositions: [],
  transactions: [],
  importMethod: "manual",
  importPreview: null,
  committeeTask: null,
  strategyDraft: null,
  draftTimer: null,
  stockSearchTimer: null,
  selectedImportStock: null,
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
  aiTask: "市场",
  aiRunning: false,
  lastAiResult: null,
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
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
  refresh: '<svg viewBox="0 0 24 24"><path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M6.1 9a7 7 0 0 1 11.4-2.2L20 9M4 15l2.5 2.2A7 7 0 0 0 17.9 15"/></svg>',
  palette: '<svg viewBox="0 0 24 24"><path d="M12 3a9 9 0 0 0 0 18h1.5a2 2 0 0 0 0-4H12a2 2 0 0 1 0-4h5a4 4 0 0 0 4-4c0-3.3-4-6-9-6Z"/><circle cx="7.5" cy="10" r="1"/><circle cx="9.5" cy="6.5" r="1"/><circle cx="14" cy="6.5" r="1"/><circle cx="17" cy="9.5" r="1"/></svg>',
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
  renderLoadingShells();
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
  $("openImportBtn").addEventListener("click", openPositionImport);
  $("parseImportBtn").addEventListener("click", parsePositionImport);
  $("commitImportBtn").addEventListener("click", commitPositionImport);
  $("runCommitteeBtn").addEventListener("click", runCommittee);
  $("checkReviewsBtn").addEventListener("click", checkReviews);
  $("toggleAdvancedBt").addEventListener("click", () => $("advancedBt").classList.toggle("collapsed"));
  $("runAiBtn").addEventListener("click", runAiAnalysis);
  $("globalSearch").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    const query = event.currentTarget.value.trim();
    if (!query) return;
    handleGlobalSearch(query);
  });
  document.querySelectorAll("[data-tab-target='strategy']").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.tab === "factors") renderFactors();
      if (btn.dataset.tab === "library") renderStrategyLibrary();
    });
  });
  document.querySelectorAll("[data-import-method]").forEach((btn) => btn.addEventListener("click", () => {
    state.importMethod = btn.dataset.importMethod;
    document.querySelectorAll("[data-import-method]").forEach((node) => node.classList.toggle("active", node === btn));
    renderImportInput();
  }));
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
  const pageMessages = {
    overview: positions ? `先看市场结构，再照顾这 ${positions} 只持仓。` : "先看依据，再做决定。",
    market: "今天先回答市场为什么处在这个状态。",
    strategy: "把模糊想法翻译成可以检查的规则。",
    portfolio: positions ? `逐只检查这 ${positions} 只持仓有没有偏离原始逻辑。` : "没有持仓也没关系，先把记录方式搭好。",
    ai: "我会把结论、证据和不确定性分开写清楚。",
    reviews: "慢一点回看，才能知道判断错在了哪里。",
    system: "先确认数据和工具，再相信页面上的数字。",
  };
  $("headerGreeting").textContent = `${timeGreet}，${pageMessages[state.view] || pageMessages.overview}`;
}

function updatePageMood(view) {
  updateGreeting();
  renderMascotState(view);
}

const mascotStates = {
  observing: ["开盘前观察", "先确认隔夜信息与数据日期"],
  "risk-weak": ["风险偏弱", "下跌家数占优，暂不追高"],
  warming: ["市场转暖", "宽度改善，继续确认连续性"],
  researching: ["策略研究", "把结论拆回规则与证据"],
  reviewing: ["复盘中", "收盘后回看判断与执行偏差"],
  waiting: ["等待信号", "数据或规则尚未满足行动条件"],
  holding: ["持有观察", "持仓未触发明确退出条件"],
  empty: ["当前空仓", "可以导入持仓或建立模拟组合"],
  warning: ["回撤预警", "优先检查止损线与原始逻辑"],
  success: ["数据正常", "核心数据源与研究工具可用"],
  "no-record": ["暂无记录", "从一次明确决策开始积累记忆"],
  tracking: ["继续跟踪", "已有新信号，等待条件确认"],
};

function deriveMascotState(view = state.view) {
  if (view === "system") return state.dataStatus?.status === "ok" && state.systemStatus?.llm_configured ? "success" : "waiting";
  if (view === "reviews") return state.reviews.length ? "reviewing" : "no-record";
  if (view === "portfolio") {
    if (!state.holdings.length) return "empty";
    if (state.holdings.some((holding) => Number(holding.pnl_pct) <= -8)) return "warning";
    return "holding";
  }
  if (view === "strategy") return state.compiled ? "researching" : "waiting";
  if (view === "ai") return "researching";
  const now = new Date();
  const minute = now.getHours() * 60 + now.getMinutes();
  const weekend = now.getDay() === 0 || now.getDay() === 6;
  if (weekend || minute >= 15 * 60) return "reviewing";
  if (minute < 9 * 60 + 30) return "observing";
  const upRatio = Number(state.marketPanorama?.breadth?.up_ratio);
  if (!Number.isFinite(upRatio)) return "waiting";
  if (upRatio <= .42) return "risk-weak";
  if (upRatio >= .58) return "warming";
  return state.marketSignals.length ? "tracking" : "waiting";
}

function mascotMarkup(name, compact = false) {
  const [label, note] = mascotStates[name] || mascotStates.waiting;
  return `<div class="mascot-state-line"><span class="ragdoll-sticker ${html(name)} ${compact ? "compact" : ""}" role="img" aria-label="${html(label)}"></span>${compact ? "" : `<div><strong>${html(label)}</strong><span>${html(note)}</span></div>`}</div>`;
}

function renderMascotState(view = state.view) {
  const name = deriveMascotState(view);
  const title = document.querySelector(".rightbar-title");
  if (title) title.innerHTML = `<span>${html(mascotStates[name][0])}</span><small>${html(mascotStates[name][1])}</small>`;
}

function setView(view, title, subtitle, updateHistory = true) {
  state.view = view;
  document.querySelectorAll(".nav-item, .utility-btn").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((node) => node.classList.toggle("active", node.id === view));
  $("pageTitle").textContent = title || view;
  $("breadcrumbNow").textContent = title || view;
  $("pageSubtitle").textContent = subtitle || "";
  if (updateHistory && window.location.pathname !== "/") window.history.pushState({ view }, "", "/");
  updatePageMood(view);
  renderContext();
}

window.addEventListener("popstate", (event) => {
  const view = event.state?.view || "overview";
  const nav = document.querySelector(`[data-view="${view}"]`);
  setView(view, nav?.dataset.title, nav?.dataset.subtitle, false);
});

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
    loadDataCoverage(),
    loadSystem(),
    loadMarket(),
    loadPortfolio(),
    loadWatchlist(),
    loadStrategies(),
    loadFactors(),
    loadHealth(),
    loadPortfolios(),
    loadReviews(),
    loadStrategyDraft(),
  ]);
  renderOverview();
  renderMarket();
  renderStrategyLibrary();
  renderFactors();
  renderPortfolio();
  renderReviews();
  renderContext();
  renderMascotState();
  $("lastUpdated").textContent = `更新于 ${new Date().toLocaleTimeString()}`;
}

async function safeLoad(label, fn) {
  try {
    return await fn();
  } catch (error) {
    return { ...(error.payload || {}), __error: `${label}失败：${error.message}` };
  }
}

async function loadDataStatus() {
  state.dataStatus = await safeLoad("数据状态", () => api.get("/api/data/status"));
  updateSideStatus();
}

async function loadDataCoverage() {
  state.dataCoverage = await safeLoad("数据覆盖", () => api.get("/api/data/coverage"));
}

async function loadSystem() {
  state.systemStatus = await safeLoad("系统状态", () => api.get("/api/status"));
  renderSystem();
  updateSideStatus();
}

async function loadMarket() {
  const panoramaPromise = safeLoad("行情全景", () => api.get("/api/market/panorama")).then((panorama) => {
    state.marketPanorama = panorama;
    renderOverview();
    renderMarket();
    renderContext();
    renderMascotState();
    return panorama;
  });
  const legacyPromise = safeLoad("兼容市场", () => api.get("/api/market")).then((legacy) => { state.legacyMarket = legacy; return legacy; });
  const signalsPromise = safeLoad("市场信号", () => api.get("/api/signals")).then((signals) => { state.marketSignals = Array.isArray(signals) ? signals : []; return signals; });
  const actionsPromise = safeLoad("行动建议", () => api.get("/api/actions")).then((actions) => { state.marketActions = Array.isArray(actions) ? actions : []; return actions; });
  const [panorama] = await Promise.all([panoramaPromise, legacyPromise, signalsPromise, actionsPromise]);
  state.marketPanorama = panorama;
  if (panorama.__error) {
    state.marketOverview = panorama;
    state.marketRegime = panorama;
  } else {
    state.marketOverview = {
      ok: panorama.ok,
      overview: { ...(panorama.breadth || {}), source: primarySource(panorama) },
      source_status: { status: panorama.status, sources: panorama.provenance || [] },
    };
    state.marketRegime = { ok: panorama.ok, regime: panorama.regime || {} };
  }
  renderOverview();
  renderMarket();
  renderContext();
  renderMascotState();
}

async function loadPortfolio() {
  const settle = () => { renderPortfolio(); renderOverview(); updateSideStatus(); renderMascotState(); };
  const summaryPromise = safeLoad("持仓汇总", () => api.get("/api/portfolio/summary")).then((summary) => { state.portfolioSummary = summary; settle(); });
  const holdingsPromise = safeLoad("持仓列表", () => api.get("/api/portfolio")).then((holdings) => { state.holdings = Array.isArray(holdings) ? holdings : []; settle(); });
  const analyticsPromise = safeLoad("组合分析", () => api.get("/api/portfolio/analytics")).then((analytics) => { state.portfolioAnalytics = analytics; settle(); });
  const positionsPromise = safeLoad("持仓工作流", () => api.get("/api/workflow/positions?include_closed=true")).then((data) => { state.workflowPositions = data.items || []; });
  const transactionsPromise = safeLoad("交易流水", () => api.get("/api/workflow/transactions")).then((data) => { state.transactions = data.items || []; });
  await Promise.all([summaryPromise, holdingsPromise, analyticsPromise, positionsPromise, transactionsPromise]);
  renderPortfolio();
  renderTransactionLedger();
  renderCommitteePositionOptions();
  updateSideStatus();
  renderMascotState();
}

async function loadWatchlist() {
  const data = await safeLoad("观察池", () => api.get("/api/watchlist"));
  state.watchlist = data.items || [];
  renderWatchlist();
}

async function loadStrategies() {
  const data = await safeLoad("策略库", () => api.get("/api/strategies"));
  state.strategies = data.strategies || [];
  renderStrategyLibrary();
  updateSideStatus();
}

async function loadStrategyDraft() {
  const data = await safeLoad("策略草稿", () => api.get("/api/workflow/strategy-draft"));
  if (data.draft) {
    state.strategyDraft = data.draft;
    if (!state.compiled && data.draft.compiled) state.compiled = data.draft.compiled;
    if (state.strategyStep === 0) renderStrategyStep();
  }
}

async function loadFactors() {
  const data = await safeLoad("因子库", () => api.get("/api/factors"));
  state.factors = data.factors || [];
  renderFactors();
}

async function loadHealth() {
  const data = await safeLoad("策略健康", () => api.get("/api/strategy-health"));
  state.health = data.items || [];
}

async function loadPortfolios() {
  const data = await safeLoad("组合列表", () => api.get("/api/portfolios"));
  state.portfolios = data.portfolios || [];
  renderPortfolio();
}

async function loadReviews() {
  const reviews = await safeLoad("复盘列表", () => api.get("/api/reviews"));
  state.reviews = reviews.reviews || [];
  state.decisions = reviews.decisions || [];
  state.reviewStats = null;
  state.reviewMessage = reviews.message || null;
  renderReviews();
  updateSideStatus();
  renderMascotState();
}

function renderLoadingShells() {
  const loadingCard = (label) => summaryCard(label, "加载中", "正在读取真实接口", "overview", "info");
  $("overviewMetrics").innerHTML = ["市场风险偏好", "市场宽度", "全市场成交额", "组合状态"].map(loadingCard).join("");
  $("dailyConclusion").innerHTML = `<div class="conclusion-copy"><span class="eyebrow">老布偶猫正在整理证据</span><h2>先把数据读完整，再给今天下结论</h2><p>市场、持仓和策略会分区更新，不需要等待所有接口同时完成。</p></div>`;
  $("marketRadarGrid").innerHTML = `<div class="notice">正在读取市场状态、宽度与指数数据...</div>`;
  $("marketRegimeCard").innerHTML = `<div class="notice">市场诊断计算中...</div>`;
  $("portfolioOverview").innerHTML = ["组合市值", "累计收益", "最大回撤", "组合风险"].map(loadingCard).join("");
  $("portfolioPanel").innerHTML = `<div class="notice">正在读取模拟组合...</div>`;
  $("holdingsPanel").innerHTML = `<div class="notice">正在读取持仓与行情...</div>`;
  $("portfolioCurvePanel").innerHTML = `<div class="notice">正在检查策略净值序列...</div>`;
  $("reviewMetrics").innerHTML = ["完整记录率", "到期完成率", "AI采纳率", "用户修改率"].map(loadingCard).join("");
  $("reviewTimeline").innerHTML = `<div class="notice">正在读取真实决策记录...</div>`;
  $("reviewInsight").innerHTML = `<div class="notice">样本量确认后再生成复盘提示。</div>`;
}

function updateSideStatus() {
  const dataOk = state.dataStatus && !state.dataStatus.__error && state.dataStatus.status === "ok";
  $("sideDataStatus").textContent = dataOk ? "数据正常" : "数据降级/待查";
  const llm = state.systemStatus && !state.systemStatus.__error && state.systemStatus.llm_configured;
  $("sideLlmStatus").textContent = llm ? "LLM 已配置" : "LLM 未配置";
  $("sidePositions").textContent = state.portfolioSummary?.positions ?? "未读取";
  $("sideStrategies").textContent = state.strategies?.length ?? "未读取";
  const pendingReviews = decisionReviewStats().pending;
  $("sideReviews").textContent = pendingReviews;
  $("badgeStrategy").textContent = String(state.strategies?.length ?? "未读取");
  $("badgePortfolio").textContent = String(state.portfolioSummary?.positions ?? "未读取");
  $("badgeReview").textContent = String(pendingReviews);
  $("badgeMarket").textContent = dataOk ? "正常" : "检查";
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
    p.positions ? summaryCard(p.portfolio_kind === "demo" ? "示例组合盈亏" : "我的组合盈亏", pct(p.total_pnl_pct), `${money(p.total_pnl)} · 行情覆盖 ${p.priced_positions ?? 0}/${p.positions ?? 0}`, "portfolio", (p.total_pnl || 0) >= 0 ? "up" : "down")
      : summaryCard("我的组合盈亏", "尚未添加真实持仓", "进入组合页添加持仓后显示盈亏和覆盖率", "portfolio", "warning"),
  ];
  $("overviewMetrics").innerHTML = cards.join("");
  renderDailyConclusion();
  renderMarketPanorama();
  renderPortfolioPreview();
  $("actionList").innerHTML = buildActionTasks().join("");
  $("strategyHealthList").innerHTML = renderHealthRows();
}

function renderDailyConclusion() {
  const panorama = state.marketPanorama || {};
  const breadth = panorama.breadth || {};
  const regime = panorama.regime || {};
  const portfolio = state.portfolioSummary || {};
  const upRatio = Number(breadth.up_ratio);
  const median = Number(breadth.median_change);
  const hasBreadth = Number.isFinite(upRatio);
  let title = "数据还在整理，先不急着下结论";
  let description = "市场宽度或指数数据尚未完整返回。刷新后再检查，不用缺失字段推导交易动作。";
  let action = "等待数据";
  let tone = "warning";
  if (hasBreadth && upRatio <= .4) {
    title = "今天不适合追高，先守住判断边界";
    description = `上涨比例仅 ${(upRatio * 100).toFixed(1)}%，下跌家数明显占优。当前更适合检查持仓风险与等待趋势确认。`;
    action = "检查持仓风险";
    tone = "down";
  } else if (hasBreadth && upRatio >= .6) {
    title = "市场正在转暖，但仍要确认热点连续性";
    description = `上涨比例达到 ${(upRatio * 100).toFixed(1)}%，市场扩散改善。优先观察主线是否连续，不把单日普涨当成趋势确认。`;
    action = "查看板块轮动";
    tone = "up";
  } else if (hasBreadth) {
    title = "市场分歧仍在，等待更明确的方向信号";
    description = `上涨比例 ${(upRatio * 100).toFixed(1)}%，暂未形成压倒性方向。当前持仓以跟踪原始逻辑为主。`;
    action = "查看今日信号";
    tone = "info";
  }
  const sector = marketSectors()[0];
  $("dailyConclusion").innerHTML = `<img class="integrated-mascot" src="/static/brand/ragdoll/mascot-cutout.png" alt="正在整理市场证据的老布偶猫"><div class="conclusion-copy">
    <span class="eyebrow">老布偶猫今日结论 · ${html(panorama.as_of || breadth.as_of || "日期待确认")}</span>
    <h2>${html(title)}</h2><p>${html(description)}</p>
    <div class="conclusion-actions"><span class="status-pill ${tone}">${html(regime.label || "市场状态待确认")}</span><button class="secondary" data-jump-view="${tone === "down" ? "portfolio" : "market"}">${html(action)}</button></div>
  </div><details class="evidence-details"><summary>为什么得出这个判断</summary><div class="evidence-list">
    <div><span>上涨比例</span><strong>${hasBreadth ? `${(upRatio * 100).toFixed(1)}%` : "数据缺失"}</strong></div>
    <div><span>涨跌中位数</span><strong>${Number.isFinite(median) ? pct(median) : "数据缺失"}</strong></div>
    <div><span>全市场成交额</span><strong>${breadth.amount ? `${(breadth.amount / 1e8).toFixed(1)}亿` : "数据缺失"}</strong></div>
    <div><span>热点扩散</span><strong>${html(sector?.name || "暂无可靠主线")}</strong></div>
    <div><span>组合暴露</span><strong>${portfolio.positions ? `${portfolio.positions} 只 · ${pct(portfolio.total_pnl_pct)}` : "未接入真实持仓"}</strong></div>
  </div></details>`;
}

function renderMarketPanorama() {
  const data = state.marketPanorama || {};
  const indices = Array.isArray(data.indices) ? data.indices : [];
  $("panoramaMeta").textContent = `${data.as_of || "日期待确认"} · ${primarySource(data)} · ${translateStatus(data.status || "loading")}`;
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
    <div class="meta">20日波动 ${idx.volatility_20d == null ? "样本不足" : riskPct(idx.volatility_20d)} · 60日波动 ${idx.volatility_60d == null ? "样本不足" : riskPct(idx.volatility_60d)}</div>
    <div class="meta">${html(idx.as_of || "日期待确认")} · ${html(idx.source || "来源待确认")}</div>
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
    const ratio = total && bucket.count != null ? `${(bucket.count / total * 100).toFixed(1)}%` : "缺少有效全A截面";
    const width = bucket.count == null ? 0 : Math.max(3, bucket.count / max * 100);
    return `<div class="breadth-row" title="${html(bucket.label)} · ${html(bucket.count ?? "不可用")} 只 · ${ratio}">
      <span>${html(bucket.label)}</span><div class="breadth-track"><i class="breadth-fill ${tone}" style="width:${width}%"></i></div><b>${html(bucket.count ?? "缺失")}</b>
    </div>`;
  }).join("");
  return `<div class="card-head"><h2>全市场涨跌结构</h2><span class="status-pill ${b.status === "ok" ? "ok" : "warning"}">${html(translateStatus(b.status || "partial"))}</span></div>
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
  const sectors = marketSectors().slice(0, 8);
  if (!sectors.length) {
    const refreshing = state.legacyMarket?.refreshing || state.legacyMarket?.provenance?.hot_sectors?.status === "loading";
    return `<div class="notice">${refreshing ? "板块扫描正在后台刷新；指数和市场宽度已先展示。" : "暂无真实板块主线数据；不会显示固定假板块。"}</div>`;
  }
  const intensity = (sector) => Number(sector.heat ?? sector.amount) || 0;
  const maxHeat = Math.max(...sectors.map(intensity), 1);
  return sectors.map((s) => {
    const pctValue = Number(s.change_pct);
    const bg = pctValue >= 0 ? `rgba(217, 93, 79, ${Math.min(.28, .08 + intensity(s) / maxHeat * .2)})` : "rgba(62, 154, 112, .18)";
    const detail = s.heat != null
      ? `热度 ${s.heat} · 涨停 ${s.limit_up ?? "涨停字段未返回"}`
      : `${s.stocks ?? "公司家数未返回"} · 龙头 ${s.leader || "龙头字段未返回"}`;
    return `<article class="sector-tile" title="${html(s.source || "source")} · ${html(detail)}" style="background:${bg}">
      <strong>${html(s.name || "未命名板块")}</strong><span class="${pctValue >= 0 ? "market-up" : "market-down"}">${signedPct(pctValue)}</span>
      <small>${html(detail)} · 连续性 ${s.rotation_persistence_days == null ? missingReason("rotation_persistence") : `${s.rotation_persistence_days}日`} · ${html(s.source || "来源待确认")}</small>
      <button class="secondary" data-watch-sector="${html(s.code || s.name)}" data-watch-name="${html(s.name)}">加入观察池</button>
    </article>`;
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
      <div>当日<small class="${toneFromNumber(h.daily_change_pct)}">${signedPct(h.daily_change_pct)}</small></div>
      <div>盈亏<small class="${toneFromNumber(pnlPct)}">${pct(pnlPct)}</small></div>
      <div>权重<small>${h.market_value ? `${(Number(h.market_value) / pricedValue * 100).toFixed(1)}%` : "不可用"}</small></div>
      <div>信号<small>${html(strategyLabel(signal))}</small></div>
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
    tasks.push(taskItem(priorityFromAction(item.type), localizeActionTitle(item.title || item.type || "持仓操作"), item.desc || "来自持仓动作接口", "portfolio", null, item.time || item.as_of || item.source, item.source || "actions"));
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
  const reviewStats = decisionReviewStats();
  if (reviewStats.duePending > 0) {
    tasks.push(taskItem("high", "有决策待复盘", `${reviewStats.duePending} 条到期记录尚未形成可核验结果。`, "reviews", null, new Date().toISOString().slice(0, 10), "decision_records"));
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
    <div><div class="task-title">${html(title)}</div><div class="task-meta">${html(meta)} · ${html(time || "获取时间")} · ${html(sourceLabel(source))}</div></div>
    <button class="secondary" data-jump-view="${view}" ${tab ? `data-jump-tab="${tab}"` : ""}>处理</button>
  </div>`;
}

function priorityFromAction(type) {
  return { exit: "high", trim: "high", attack: "medium", probe: "medium", hold: "low" }[String(type || "").toLowerCase()] || "medium";
}

function localizeActionTitle(value) {
  return String(value || "").replace(/\b(HOLD|EXIT|TRIM|PROBE|ATTACK)\b/g, (match) => strategyLabel(match));
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
    $("marketEvidencePanel").innerHTML = "";
    $("rotationPanel").innerHTML = "";
    return;
  }
  $("marketRadarGrid").innerHTML = [
    summaryCard("A股样本", safeNum(m.total), `${m.source || "来源待确认"} · ${m.as_of || "无日期"}`, "market", "brand"),
    summaryCard("上涨家数", safeNum(m.up_count), "来自市场快照；不可用则显示缺失", "market", "up"),
    summaryCard("下跌家数", safeNum(m.down_count), "A股红涨绿跌，绿色代表下跌", "market", "down"),
    summaryCard("成交额", m.amount ? `${(m.amount / 1e8).toFixed(1)}亿` : "不可用", sourceLine(state.marketOverview), "market", "info"),
    summaryCard("市场宽度", r?.breadth || "待确认", r?.method || "等待市场环境接口", "market", "warning"),
    summaryCard("风险偏好", r?.risk_appetite || "待确认", `风格：${r?.style || "待确认"}`, "market", "info"),
  ].join("");
  const indices = state.marketPanorama?.indices || [];
  const validIndices = indices.filter((index) => index.status === "ok");
  const trendScore = validIndices.length ? validIndices.filter((index) => Number(index.change_pct) > 0).length / validIndices.length * 100 : null;
  const breadthScore = m.up_ratio != null ? Number(m.up_ratio) * 100 : null;
  const sectorCount = marketSectors().length;
  $("marketRegimeCard").innerHTML = `<div class="card-head"><div><h2 class="section-title">市场状态诊断</h2><p class="card-subtitle">从趋势、宽度、波动、流动性、风格与轮动速度回溯结论。</p></div><span class="status-pill info">确定性派生</span></div>
    <div class="radar-meter">
      ${radarAxis("趋势", trendScore, r?.trend || "待确认")}
      ${radarAxis("宽度", breadthScore, m.up_ratio != null ? `${(Number(m.up_ratio) * 100).toFixed(1)}%` : "数据缺失")}
      ${radarAxis("波动", marketVolatilityScore(), marketVolatilityText())}
      ${radarAxis("流动性", null, m.amount ? `当日成交额 ${(m.amount / 1e8).toFixed(1)}亿；缺少历史全市场成交额序列，不能计算环比评分` : missingReason("amount"))}
      ${radarAxis("风格", null, "指数与行业风格映射暂无可靠来源")}
      ${radarAxis("轮动", sectorCount ? Math.min(100, marketSectors().filter((x) => x.rotation_persistence_days >= 2).length / sectorCount * 100) : null, sectorCount ? `${marketSectors().filter((x) => x.rotation_persistence_days >= 2).length}/${sectorCount} 个板块连续同向` : missingReason("sectors"))}
    </div>`;
  $("marketBreadthPanel").innerHTML = `<div class="card-head"><h2>指数与市场宽度</h2><span class="${statusClass(state.marketOverview?.source_status?.status)}">${html(translateStatus(state.marketOverview?.source_status?.status))}</span></div>
    <div class="notice">上涨家数、下跌家数和成交额来自数据接口；缺失字段不会用估算填充。样本范围：${html(m.total || "待确认")} 只。</div>`;
  $("marketEvidencePanel").innerHTML = `<div class="card-head"><h2 class="section-title">判断证据</h2><span class="status-pill ${m.up_ratio < .45 ? "warning" : "ok"}">${html(r?.label || "状态待确认")}</span></div>
    <div class="evidence-cards">
      ${evidenceCard("上涨 / 下跌", `${safeNum(m.up_count)} / ${safeNum(m.down_count)}`, "市场快照")}
      ${evidenceCard("涨跌中位数", pct(m.median_change), "全市场截面")}
      ${evidenceCard("成交额", m.amount ? `${(m.amount / 1e8).toFixed(1)}亿` : "缺失", "暂无环比")}
      ${evidenceCard("指数方向", validIndices.length ? `${validIndices.filter((x) => Number(x.change_pct) > 0).length}/${validIndices.length} 上涨` : "缺失", "四大指数")}
      ${evidenceCard("板块持续性", sectorCount ? `${marketSectors().filter((x) => x.rotation_persistence_days >= 2).length}/${sectorCount} 连续同向` : missingReason("sectors"), "本地每日增量快照")}
      ${evidenceCard("数据日期", m.as_of || state.marketPanorama?.as_of || "待确认", m.source || primarySource(state.marketPanorama))}
    </div>`;
  $("rotationPanel").innerHTML = renderRotationPanel();
}

function radarAxis(label, value, note) {
  const available = value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
  return `<div class="radar-axis"><strong>${html(label)}</strong><div class="radar-track"><i style="width:${available ? Math.max(4, Math.min(100, Number(value))) : 0}%"></i></div><span title="${html(note)}">${available ? Math.round(Number(value)) : "缺"}</span></div>`;
}

function evidenceCard(label, value, source) {
  return `<div class="evidence-card"><span>${html(label)}</span><strong>${html(value)}</strong><span>${html(source)}</span></div>`;
}

function renderRotationPanel() {
  const sectors = marketSectors().slice(0, 6);
  if (!sectors.length) return `<div class="card-head"><h2 class="section-title">板块轮动</h2><span class="status-pill warning">数据缺失</span></div>${emptyBlock("暂无可靠板块主线", "后台扫描尚未返回板块连续性、扩散和龙头数据。")}`;
  return `<div class="card-head"><h2 class="section-title">板块轮动</h2><span class="status-pill info">${sectors.length} 个样本</span></div><div class="task-list">${sectors.map((sector, index) => `<div class="task priority-${index < 2 ? "high" : "medium"}"><div class="task-icon">${icons.market}</div><div><div class="task-title">${html(sector.name || "未命名板块")}</div><div class="task-meta">涨跌 ${signedPct(sector.change_pct)} · 持续 ${sector.rotation_persistence_days == null ? missingReason("rotation_persistence") : `${sector.rotation_persistence_days}日`} · ${html(sector.source || "来源未返回")}</div></div><button class="secondary" data-watch-sector="${html(sector.code || sector.name)}" data-watch-name="${html(sector.name)}">观察</button></div>`).join("")}</div>`;
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
  renderMascotState("strategy");
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
  return `<div class="strategy-input-composition"><img class="integrated-mascot" src="/static/brand/ragdoll/mascot-cutout.png" alt="陪伴梳理策略规则的老布偶猫"><div><h2>表达投资想法</h2>
    <p class="notice">示例只会填充输入框，不会自动生成股票或收益。</p>
    <div class="example-list">${examples.map((x) => `<button class="example-chip" data-example="${html(x)}">${html(x)}</button>`).join("")}</div>
    <textarea id="ideaInput">${html(state.strategyDraft?.idea || "找价格低于100元、最近没有进入下行通道、近5日没有大涨、行业景气较强、机构关注增加的股票。")}</textarea>
    <div class="card-head"><div><button id="compileBtn">生成策略翻译确认页</button><button id="clearDraftBtn" class="text-btn">清空草稿</button></div><span class="status-pill warning">${state.strategyDraft ? `已恢复 ${html(state.strategyDraft.updated_at)}` : "输入将自动保存"}</span></div></div></div>`;
}

function renderRuleStep() {
  if (!state.compiled) return emptyBlock("还没有策略草案", "请先在第一步输入投资想法并生成 DSL。");
  const conditions = state.compiled.dsl.entry_conditions.conditions || [];
  const cards = conditions.map((c, idx) => ruleCard(c, idx)).join("");
  const dsl = state.compiled.dsl;
  return `<div class="card-head"><div><h2 class="section-title">策略翻译确认</h2><p class="card-subtitle">逐项确认量化定义；默认值来自明确假设，不等同于投资建议。</p></div><button id="validateBtn" class="secondary">校验规则</button></div>
    <div class="strategy-structure-grid">
      ${structuredField("股票池", "universe.market", dsl.universe?.market || "A股", "A股市场；默认排除 ST")}
      ${structuredField("调仓频率", "execution.rebalance_frequency", dsl.execution?.rebalance_frequency || "weekly", "daily / weekly / monthly")}
      ${structuredField("持有周期", "execution.holding_days", dsl.execution?.holding_days ?? 20, "交易日")}
      ${structuredField("止损规则", "risk.stop_loss", dsl.risk?.stop_loss ?? .08, "小数，例如 0.08")}
      ${structuredField("止盈规则", "risk.take_profit", dsl.risk?.take_profit ?? .20, "小数，例如 0.20")}
      ${structuredField("最大持仓", "portfolio.max_positions", dsl.portfolio?.max_positions ?? 10, "股票数量")}
    </div>
    <div class="card-head"><h3>价格、趋势、基本面与机构条件</h3><span class="status-pill warning">逐项检查数据质量</span></div>
    <div class="rule-grid">${cards}</div>
    <div class="notice"><strong>排除条件：</strong>${dsl.universe?.exclude_st ? "排除 ST" : "未排除 ST"} · 上市不足 ${html(dsl.universe?.min_listed_days ?? 120)} 日标的默认排除。基本面条件未从当前描述中识别时不会自动补造；机构关注字段未接入时默认禁用。</div>
    <details><summary>查看技术定义 DSL</summary><pre>${html(JSON.stringify(state.compiled.dsl, null, 2))}</pre></details>`;
}

function structuredField(label, path, value, hint) {
  const control = path === "execution.rebalance_frequency"
    ? `<select data-dsl-path="${html(path)}"><option value="daily" ${value === "daily" ? "selected" : ""}>每日</option><option value="weekly" ${value === "weekly" ? "selected" : ""}>每周</option><option value="monthly" ${value === "monthly" ? "selected" : ""}>每月</option></select>`
    : `<input data-dsl-path="${html(path)}" value="${html(value)}">`;
  return `<label class="structured-field"><span>${html(label)}</span>${control}<small>${html(hint)}</small></label>`;
}

function ruleCard(c, idx) {
  const ambiguity = (state.compiled.ambiguities || []).find((a) => c.factor.includes("analyst") || a.term?.includes("行业"));
  const factor = state.factors.find((item) => item.id === c.factor);
  return `<article class="rule-card ${c.enabled ? "" : "disabled"}">
    <strong>${html(factor?.name || c.factor)}</strong>
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
  $("ideaInput")?.addEventListener("input", scheduleStrategyDraftSave);
  $("clearDraftBtn")?.addEventListener("click", clearStrategyDraft);
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
    scheduleStrategyDraftSave();
    renderStrategyStep();
  }));
  document.querySelectorAll("[data-apply-rule]").forEach((btn) => btn.addEventListener("click", () => {
    const i = Number(btn.dataset.applyRule);
    const cond = state.compiled.dsl.entry_conditions.conditions[i];
    const input = document.querySelector(`[data-rule-value="${i}"]`);
    const value = input?.value;
    if (value !== undefined && value !== "") {
      cond.value = Number.isNaN(Number(value)) ? value : Number(value);
      scheduleStrategyDraftSave();
      renderStrategyStep();
    }
  }));
  document.querySelectorAll("[data-dsl-path]").forEach((input) => input.addEventListener("change", () => {
    const value = input.value.trim();
    setNestedValue(state.compiled.dsl, input.dataset.dslPath, value !== "" && !Number.isNaN(Number(value)) ? Number(value) : value);
    scheduleStrategyDraftSave();
    toast(`${input.closest("label")?.querySelector("span")?.textContent || "规则"}已更新`);
  }));
}

function setNestedValue(target, path, value) {
  const parts = path.split(".");
  const key = parts.pop();
  const parent = parts.reduce((node, part) => (node[part] ||= {}), target);
  parent[key] = value;
}

async function compileIdea() {
  const input = $("ideaInput");
  $("strategyStepContent").insertAdjacentHTML("beforeend", `<div class="notice" id="compileLoading">正在生成策略翻译确认页...</div>`);
  try {
    const data = await api.post("/api/strategies/compile", { text: input.value });
    state.compiled = data;
    await saveStrategyDraft(input.value);
    state.strategyStep = 1;
    toast("策略草案已生成");
    renderStrategyStep();
  } catch (error) {
    $("compileLoading")?.remove();
    $("strategyStepContent").insertAdjacentHTML("beforeend", errorCard("策略编译失败", error.message));
  }
}

function scheduleStrategyDraftSave() {
  clearTimeout(state.draftTimer);
  state.draftTimer = setTimeout(() => saveStrategyDraft($("ideaInput")?.value || state.strategyDraft?.idea || ""), 500);
}

async function saveStrategyDraft(idea) {
  try {
    const data = await api.put("/api/workflow/strategy-draft", { id: "current", idea, compiled: state.compiled });
    state.strategyDraft = data.draft;
  } catch (error) {
    toast(`草稿保存失败：${error.message}`);
  }
}

async function clearStrategyDraft() {
  if (!window.confirm("确认清空当前策略草稿？已保存的正式策略不会删除。")) return;
  await api.delete("/api/workflow/strategy-draft");
  state.strategyDraft = null;
  state.compiled = null;
  state.strategyStep = 0;
  renderStrategyStep();
  toast("草稿已清空");
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
    <details><summary>查看入选原因</summary>${(x.explanation?.passed || []).map((p) => `<div class="rule-meta">${html(p.factor)}=${html(p.actual)} / ${html(p.operator)} ${html(p.threshold)} · ${html(p.source)} ${html(p.data_date)}</div>`).join("")}</details><button class="secondary" data-watch-symbol="${html(x.symbol)}">加入观察池</button>
  </article>`).join("")}</div>` : emptyBlock("无入选股票", "筛选条件下没有股票通过，系统没有补造候选。");
  const failures = data.failures?.length ? `<div class="partial">部分股票数据失败：${data.failures.map((f) => `${html(f.symbol)} ${html(f.reason)}`).join("；")}</div>` : "";
  const create = data.results.length ? `<button class="primary-action" data-create-portfolio-from-screen>用入选结果创建模拟组合</button>` : "";
  return `${funnel}${stocks}${failures}${create}`;
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
  $("factorTable").innerHTML = `<table><thead><tr><th>ID</th><th>名称</th><th>分类</th><th>公式</th><th>来源</th><th>覆盖</th><th>状态</th></tr></thead><tbody>${factors.map((f) => `<tr data-factor-id="${html(f.id)}"><td>${html(f.id)}</td><td>${html(f.name)}</td><td>${html(f.category)}</td><td>${html(f.formula)}</td><td>${html(f.data_source)}</td><td>${html(f.coverage)}</td><td><span class="chip ${f.status === "available" ? "ok" : f.status === "unavailable" ? "error" : "partial"}">${html(factorStatusLabel(f.status))}</span></td></tr>`).join("")}</tbody></table>`;
  $("factorDetail").innerHTML = factorDetail(factors[0]);
  document.querySelectorAll("[data-factor-id]").forEach((row) => row.addEventListener("click", () => {
    $("factorDetail").innerHTML = factorDetail(factors.find((f) => f.id === row.dataset.factorId));
  }));
}

function factorDetail(f) {
  if (!f) return emptyBlock("暂无因子", "因子接口没有返回数据。");
  return `<div class="card-head"><h2>${html(f.name)}</h2><span class="chip ${f.status === "available" ? "ok" : f.status === "unavailable" ? "error" : "partial"}">${html(factorStatusLabel(f.status))}</span></div>
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
  const summary = state.portfolioSummary || {};
  const analytics = state.portfolioAnalytics || {};
  const metrics = analytics.metrics || {};
  $("portfolioOverview").innerHTML = `<article class="portfolio-mascot-insight"><img src="/static/brand/ragdoll/mascot-cutout.png" alt="正在检查组合风险的老布偶猫"><div><strong>${html(portfolioRiskLabel())}</strong><p>${html(portfolioRiskExplanation())}</p></div></article>` + [
    summaryCard("组合市值", metrics.market_value != null ? money(metrics.market_value) : "无法计算", `${summary.priced_positions ?? 0}/${summary.positions ?? 0} 只行情可用`, "portfolio", "brand"),
    summaryCard("累计收益", metrics.cumulative_return_pct != null ? pct(metrics.cumulative_return_pct) : "无法计算", `今日 ${metrics.today_return_pct == null ? missingReason("today_return_pct", analytics) : pct(metrics.today_return_pct)}`, "portfolio", toneFromNumber(metrics.cumulative_return_pct)),
    summaryCard("最大回撤", metrics.max_drawdown_pct != null ? pct(metrics.max_drawdown_pct) : "无法计算", metrics.max_drawdown_pct == null ? missingReason("price", analytics) : `截至 ${analytics.as_of}`, "portfolio", "warning"),
    summaryCard("组合波动率", metrics.annualized_volatility_pct != null ? riskPct(metrics.annualized_volatility_pct) : "无法计算", metrics.annualized_volatility_pct == null ? missingReason("annualized_volatility_pct", analytics) : "复权日收益年化，数值越高波动越大", "portfolio", "warning"),
    summaryCard("行业集中度", metrics.industry_concentration_pct != null ? pct(metrics.industry_concentration_pct) : "无法计算", metrics.industry_concentration_pct == null ? missingReason("industry_concentration_pct", analytics) : "最大行业权重", "portfolio", "info"),
    summaryCard("单股最大暴露", metrics.max_single_exposure_pct != null ? pct(metrics.max_single_exposure_pct) : "无法计算", "按最新复权收盘价计算", "portfolio", "info"),
  ].join("");
  $("portfolioPanel").innerHTML = state.portfolios.length ? state.portfolios.map((p) => `<div class="portfolio-row">
    <div class="row-title"><strong>${html(p.name)}</strong><span>${html(p.kind)} · ${html(p.updated_at || "无更新时间")}</span></div>
    <div class="row-cell">当前市值<small>${p.payload?.initial_capital ? money(p.payload.initial_capital) : "未保存初始资金与份额"}</small></div>
    <div class="row-cell">收益<small>${p.payload?.equity_curve?.length ? pct((p.payload.equity_curve.at(-1).value / p.payload.equity_curve[0].value - 1) * 100) : "没有组合净值记录"}</small></div>
    <div class="row-cell">持仓数量<small>${html((p.payload?.holdings || []).length)}</small></div>
    <div class="row-cell">数据状态<small>${p.payload?.evidence_snapshot_id ? "已保存筛选证据" : "缺少来源证据快照"}</small></div>
    <button class="secondary" data-jump-view="portfolio" data-jump-tab="analysis">分析</button>
  </div>`).join("") : emptyBlock("暂无模拟组合", "创建模拟组合后，策略候选和持仓血缘会在这里汇总。");
  $("holdingsPanel").innerHTML = renderHoldings();
  $("portfolioCurvePanel").innerHTML = renderPortfolioCurve();
  $("lineagePanel").innerHTML = renderLineage();
}

function portfolioRiskLabel() {
  if (!state.holdings.length) return "尚无持仓";
  const risky = state.holdings.filter((holding) => Number(holding.pnl_pct) <= -8).length;
  if (risky) return `${risky} 只触及预警`;
  const concentration = state.portfolioAnalytics?.metrics?.industry_concentration_pct;
  if (concentration != null && concentration >= 50) return "行业集中度偏高";
  if (state.holdings.length <= 3) return "单股集中度待关注";
  return "已完成历史风险计算";
}

function portfolioRiskExplanation() {
  if (!state.holdings.length) return "导入持仓后计算暴露";
  const metrics = state.portfolioAnalytics?.metrics || {};
  return metrics.max_single_exposure_pct == null ? missingReason("price", state.portfolioAnalytics) : `最大单股 ${pct(metrics.max_single_exposure_pct)} · 最大行业 ${metrics.industry_concentration_pct == null ? missingReason("industry_concentration_pct", state.portfolioAnalytics) : pct(metrics.industry_concentration_pct)}`;
}

function portfolioRiskTone() {
  return state.holdings.some((holding) => Number(holding.pnl_pct) <= -8) ? "down" : "info";
}

function renderHoldings() {
  if (!state.holdings.length) return emptyBlock("暂无真实持仓", "可以导入持仓，或从模拟组合开始记录。", ["导入真实持仓", "创建模拟组合", "从策略结果创建"]);
  const demoOnly = state.holdings.every((h) => h.is_demo);
  const worst = [...state.holdings].sort((a, b) => Number(a.pnl_pct || 0) - Number(b.pnl_pct || 0))[0];
  const best = [...state.holdings].sort((a, b) => Number(b.pnl_pct || 0) - Number(a.pnl_pct || 0))[0];
  return `<div class="card-head"><h2>${demoOnly ? "示例持仓" : "真实持仓"}</h2><span class="status-pill ${demoOnly ? "warning" : "muted"}">${state.holdings.length} 只${demoOnly ? " · 明确标记为示例" : ""}</span></div>
    <div class="notice">组合解释：当前收益贡献较高的是 ${html(best?.name || best?.code || "待确认")}；优先检查 ${html(worst?.name || worst?.code || "待确认")} 的原始买入逻辑。行业集中度、单股暴露和收益曲线均来自统一数据层。</div>
    ${state.holdings.map((h) => `<div class="holding-row">
    <div class="row-title"><strong>${html(h.name || h.code)}</strong><span>${html(h.code)} · ${html(h.price_source || "无来源")} ${html(h.price_date || "")}</span></div>
    <div class="row-cell">现价<small>${html(h.price ?? "不可用")}</small></div>
    <div class="row-cell">成本<small>${html(h.cost ?? "成本记录缺失")}</small></div>
    <div class="row-cell">浮动收益<small class="${h.pnl_pct == null ? "" : Number(h.pnl_pct) >= 0 ? "market-up" : "market-down"}">${html(h.pnl_pct == null ? "现价缺失，无法计算" : pct(h.pnl_pct))}</small></div>
    <div class="row-cell">当前信号<small>${html(strategyLabel(h.strategy || "未关联"))}</small></div>
    ${h.id ? `<div class="holding-actions"><button class="secondary" data-review-position="${html(h.id)}">投委会审查</button><button class="secondary" data-close-position="${html(h.id)}">清仓</button><button class="text-btn danger-text" data-remove-position="${html(h.id)}">删除</button></div>` : `<span class="status-pill warning">示例不可修改</span>`}
  </div>`).join("")}`;
}

function renderTransactionLedger() {
  const panel = $("transactionPanel");
  if (!panel) return;
  $("transactionCount").textContent = `${state.transactions.length} 条`;
  panel.innerHTML = state.transactions.length ? `<div class="table-wrap"><table><thead><tr><th>日期</th><th>股票</th><th>类型</th><th>数量</th><th>价格</th><th>费用</th><th>来源</th></tr></thead><tbody>${state.transactions.map((item) => `<tr><td>${html(item.trade_date)}</td><td>${html(item.symbol)}</td><td>${html(transactionTypeLabel(item.transaction_type))}</td><td>${html(item.quantity ?? "未记录")}</td><td>${html(item.price ?? "未记录")}</td><td>${html(item.fees ?? 0)}</td><td>${html(item.source)}</td></tr>`).join("")}</tbody></table></div>` : emptyBlock("暂无交易流水", "导入、增减仓、清仓和人工修正都会在此留下记录。", ["导入真实持仓"]);
}

function transactionTypeLabel(type) {
  return ({ buy: "买入", add: "加仓", sell: "卖出", import_correction: "导入修正", manual_adjust: "人工调整", remove: "删除记录" }[type] || type);
}

function openPositionImport() {
  state.importPreview = null;
  state.importMethod = "manual";
  document.querySelectorAll("[data-import-method]").forEach((node) => node.classList.toggle("active", node.dataset.importMethod === "manual"));
  renderImportInput();
  $("importPreviewPanel").innerHTML = `<div class="notice">导入前只做解析和校验，不会写入持仓。</div>`;
  $("commitImportBtn").disabled = true;
  $("positionImportDialog").showModal();
}

function renderImportInput() {
  const panel = $("importInputPanel");
  const manual = `<div class="stock-picker"><label>搜索股票<input id="importStockSearch" autocomplete="off" placeholder="输入代码、中文名、拼音或首字母，例如：茅台 / maotai / 6005"></label><input id="importSymbol" type="hidden"><input id="importName" type="hidden"><input id="importMarket" type="hidden"><div id="importStockResults" class="stock-search-results"></div><div id="importStockSelected" class="stock-selected">尚未选择股票</div></div><div class="form-grid"><label>持仓数量<input id="importQuantity" type="number" min="1"></label><label>可用数量<input id="importAvailable" type="number" min="0"></label><label>成本价<input id="importCost" type="number" min="0" step="0.001"></label><label>买入日期<input id="importBuyDate" type="date"></label><label>手续费<input id="importFees" type="number" min="0" step="0.01" value="0"></label><label>计划复盘日期<input id="importReviewDate" type="date"></label></div><label>原始买入理由<textarea id="importThesis" rows="2" placeholder="记录当时为什么买入，供未来复盘"></textarea></label>`;
  const paste = `<label>粘贴券商持仓表<textarea id="importPaste" rows="9" placeholder="股票代码,股票名称,持仓数量,可用数量,成本价,买入日期\n600519,贵州茅台,100,100,1480.00,2026-06-01"></textarea></label>`;
  const file = `<label>选择持仓文件<input id="importFile" type="file" accept=".csv,.xlsx,.xls"></label><p class="field-hint">支持 CSV、XLSX、XLS；系统会自动识别中英文列名。</p>`;
  const options = state.portfolios.filter((item) => item.kind === "paper").map((item) => `<option value="${html(item.id)}">${html(item.name)} · ${(item.payload?.holdings || []).length}只</option>`).join("");
  const paper = `<label>模拟组合<select id="importPaper"><option value="">请选择</option>${options}</select></label><p class="field-hint">模拟组合仍需包含数量和成本价；缺失字段会在预览中明确报错。</p>`;
  panel.innerHTML = ({ manual, paste, file, paper })[state.importMethod];
  state.selectedImportStock = null;
  $("importStockSearch")?.addEventListener("input", scheduleImportStockSearch);
  $("importPreviewPanel").innerHTML = "";
  $("commitImportBtn").disabled = true;
}

async function parsePositionImport() {
  try {
    $("parseImportBtn").disabled = true;
    let data;
    if (state.importMethod === "manual") {
      if (!state.selectedImportStock) throw new Error("请先搜索并选择一只股票，不需要自己记代码和名称");
      data = await api.post("/api/workflow/positions/import/preview", { rows: [{ symbol: $("importSymbol").value, name: $("importName").value, market: $("importMarket").value, quantity: $("importQuantity").value, available_quantity: $("importAvailable").value, cost_price: $("importCost").value, buy_date: $("importBuyDate").value, fees: $("importFees").value, original_thesis: $("importThesis").value, review_date: $("importReviewDate").value }] });
    } else if (state.importMethod === "paste") {
      data = await api.post("/api/workflow/positions/import/preview", { text: $("importPaste").value });
    } else if (state.importMethod === "file") {
      const file = $("importFile").files[0];
      if (!file) throw new Error("请先选择 CSV 或 Excel 文件");
      const form = new FormData(); form.append("file", file);
      data = await api.upload("/api/workflow/positions/import/preview", form);
    } else {
      const portfolio = state.portfolios.find((item) => item.id === $("importPaper").value);
      if (!portfolio) throw new Error("请选择模拟组合");
      data = await api.post("/api/workflow/positions/from-paper/preview", { holdings: portfolio.payload?.holdings || [], strategy_id: portfolio.payload?.strategy_id });
    }
    state.importPreview = data;
    renderImportPreview();
  } catch (error) {
    $("importPreviewPanel").innerHTML = errorCard("解析失败", error.message);
  } finally {
    $("parseImportBtn").disabled = false;
  }
}

function scheduleImportStockSearch(event) {
  state.selectedImportStock = null;
  $("importSymbol").value = "";
  $("importName").value = "";
  $("importMarket").value = "";
  $("importStockSelected").textContent = "尚未选择股票";
  clearTimeout(state.stockSearchTimer);
  const query = event.currentTarget.value.trim();
  if (!query) { $("importStockResults").innerHTML = ""; return; }
  $("importStockResults").innerHTML = `<div class="stock-search-status">正在搜索本地股票目录...</div>`;
  state.stockSearchTimer = setTimeout(() => searchImportStocks(query), 220);
}

async function searchImportStocks(query) {
  try {
    const data = await api.get(`/api/stocks/search?q=${encodeURIComponent(query)}&limit=8`);
    const results = data.results || [];
    $("importStockResults").innerHTML = results.length ? results.map((item) => `<button type="button" class="stock-search-option" data-select-import-stock="${html(item.code)}" data-stock-name="${html(item.name)}" data-stock-market="${html(item.market)}" data-stock-source="${html(item.source)}"><strong>${html(item.name)}</strong><span>${html(item.code)} · ${html(item.market_label || item.market)}</span></button>`).join("") : `<div class="stock-search-status">未找到匹配股票。可换用代码片段、中文名或拼音搜索。</div>`;
  } catch (error) {
    $("importStockResults").innerHTML = `<div class="stock-search-status error">股票目录暂不可用：${html(error.message)}</div>`;
  }
}

function selectImportStock(button) {
  state.selectedImportStock = { code: button.dataset.selectImportStock, name: button.dataset.stockName, market: button.dataset.stockMarket, source: button.dataset.stockSource };
  $("importSymbol").value = state.selectedImportStock.code;
  $("importName").value = state.selectedImportStock.name;
  $("importMarket").value = state.selectedImportStock.market;
  $("importStockSearch").value = `${state.selectedImportStock.name} · ${state.selectedImportStock.code}`;
  $("importStockSelected").innerHTML = `<strong>${html(state.selectedImportStock.name)}</strong><span>${html(state.selectedImportStock.code)} · ${html(state.selectedImportStock.market)} · ${html(state.selectedImportStock.source)}</span>`;
  $("importStockResults").innerHTML = "";
}

function renderImportPreview() {
  const data = state.importPreview;
  const mapping = Object.entries(data.mapping || {}).map(([field, column]) => `${field} ← ${column}`).join(" · ") || "没有识别到字段";
  $("importPreviewPanel").innerHTML = `<div class="import-summary"><strong>${data.summary.valid}/${data.summary.total} 行可导入</strong><span>${data.summary.invalid} 行错误 · ${data.summary.conflicts} 项冲突</span><small>字段映射：${html(mapping)}</small></div><div class="table-wrap"><table><thead><tr><th>行</th><th>股票</th><th>数量</th><th>成本</th><th>状态与原因</th></tr></thead><tbody>${data.rows.map((row) => `<tr class="${row.valid ? "" : "row-error"}"><td>${row.row_number}</td><td>${html(row.symbol)} ${html(row.name || "")}</td><td>${html(row.quantity ?? "缺失")}</td><td>${html(row.cost_price ?? "缺失")}</td><td>${row.errors.length ? html(row.errors.join("；")) : row.conflict ? "与已有持仓冲突" : "校验通过"}<small>${html((row.warnings || []).join("；"))}</small></td></tr>`).join("")}</tbody></table></div><label>已有持仓冲突处理<select id="importConflict"><option value="merge">合并数量并加权成本</option><option value="overwrite">覆盖现有记录</option><option value="skip">跳过冲突行</option><option value="new_portfolio">新建真实组合</option></select></label>`;
  $("commitImportBtn").disabled = data.summary.valid !== data.summary.total || !data.summary.total;
}

async function commitPositionImport() {
  if (!state.importPreview || !window.confirm(`确认导入 ${state.importPreview.summary.valid} 条真实持仓？此操作会写入交易流水。`)) return;
  try {
    $("commitImportBtn").disabled = true;
    const result = await api.post("/api/workflow/positions/import/commit", { confirm: true, rows: state.importPreview.rows, conflict_policy: $("importConflict")?.value || "skip" });
    $("positionImportDialog").close();
    await loadPortfolio();
    setTab("portfolio", "real");
    toast(`已导入 ${result.imported.length} 条，跳过 ${result.skipped.length} 条`);
  } catch (error) {
    $("importPreviewPanel").insertAdjacentHTML("afterbegin", errorCard("导入失败", error.message));
    $("commitImportBtn").disabled = false;
  }
}

function renderCommitteePositionOptions() {
  const select = $("committeePosition");
  if (!select) return;
  const current = select.value;
  select.innerHTML = `<option value="">选择真实持仓</option>${state.workflowPositions.filter((item) => item.status === "open").map((item) => `<option value="${html(item.id)}">${html(item.name || item.symbol)} · ${html(item.symbol)}</option>`).join("")}`;
  select.value = current;
}

async function runCommittee(positionId = null) {
  const id = positionId || $("committeePosition").value;
  if (!id) return toast("请先选择一个真实持仓");
  setView("ai", document.querySelector('[data-view="ai"]')?.dataset.title, document.querySelector('[data-view="ai"]')?.dataset.subtitle);
  $("committeePosition").value = id;
  $("committeePanel").innerHTML = `<div class="notice">投委会正在分角色取证，页面会显示每一步状态。</div>`;
  try {
    const data = await api.post("/api/workflow/committee/tasks", { task_type: "holding_logic", position_id: id });
    state.committeeTask = data.task;
    renderCommitteeTask();
    pollCommittee(data.task.id);
  } catch (error) {
    $("committeePanel").innerHTML = errorCard("投委会启动失败", error.message);
  }
}

async function pollCommittee(taskId) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const data = await api.get(`/api/workflow/committee/tasks/${taskId}`);
    state.committeeTask = data.task;
    renderCommitteeTask();
    if (["completed", "failed", "cancelled"].includes(data.task.status)) return;
  }
}

function renderCommitteeTask() {
  const task = state.committeeTask;
  if (!task) return;
  const result = task.result || {};
  $("committeePanel").innerHTML = `<div class="card-head"><div><strong>持仓逻辑审查</strong><p class="card-subtitle">${html(task.id)} · ${html(translateStatus(task.status))}</p></div><span class="status-pill ${task.status === "completed" ? "ok" : task.status === "failed" ? "error" : "info"}">${html(task.status)}</span></div><div class="role-run-grid">${(task.role_runs || []).map((run) => `<article class="role-run"><div><strong>${html(run.label)}</strong><span>${html(run.status)}</span></div><p>${html(run.conclusion || "等待执行")}</p>${(run.evidence || []).slice(0, 3).map((item) => `<small>${html(item.field)}：${html(item.value ?? "缺失")} · ${html(item.date || "无日期")} · ${html(item.source || "无来源")}</small>`).join("")}</article>`).join("")}</div>${task.status === "completed" ? `<div class="committee-result"><strong>${html(result.action)} · ${html(result.conclusion)}</strong><p>证据完整度 ${html(result.evidence_completeness_pct)}% · ${html(result.disclaimer)}</p><button data-save-committee-decision="${html(task.id)}">确认并记录决策</button></div>` : task.error ? errorCard("任务失败", task.error) : ""}`;
}

async function saveCommitteeDecision(taskId) {
  if (!window.confirm("确认将主席结论记录为你的正式决策？AI 不会自动交易。")) return;
  try {
    await api.post(`/api/workflow/committee/tasks/${taskId}/decision`, { confirm: true });
    await loadReviews();
    toast("决策和完整角色证据已保存");
  } catch (error) { toast(`保存失败：${error.message}`); }
}

async function closePosition(positionId) {
  const priceText = window.prompt("请输入实际卖出价格；留空则只记录数量状态，收益会标记缺失。", "");
  if (priceText === null || !window.confirm("确认清仓并写入卖出流水？")) return;
  try { await api.post(`/api/workflow/positions/${positionId}/close`, { confirm: true, price: priceText || null }); await loadPortfolio(); toast("清仓记录已保存"); }
  catch (error) { toast(`清仓失败：${error.message}`); }
}

async function removePosition(positionId) {
  if (!window.confirm("仅在持仓记录确实错误时删除。确认删除并保留审计流水？")) return;
  try { await api.post(`/api/workflow/positions/${positionId}/remove`, { confirm: true, reason: "用户在组合页确认删除" }); await loadPortfolio(); toast("持仓已移出计算，审计流水仍保留"); }
  catch (error) { toast(`删除失败：${error.message}`); }
}

function renderPortfolioCurve() {
  const analytics = state.portfolioAnalytics || {};
  if (!analytics.curve?.length) return `<div class="card-head"><h2 class="section-title">持仓收益曲线</h2><span class="status-pill warning">无法计算</span></div>${emptyBlock("没有可核验的组合曲线", missingReason("price", analytics))}`;
  const returns = analytics.curve.map((point) => ({ date: point.date, value: (point.value / analytics.curve[0].value - 1) * 100 }));
  const values = returns.map((point) => point.value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = Math.max(max - min, 1);
  const width = 760;
  const height = 220;
  const pad = { left: 48, right: 18, top: 18, bottom: 30 };
  const x = (index) => pad.left + (index / Math.max(returns.length - 1, 1)) * (width - pad.left - pad.right);
  const y = (value) => pad.top + ((max - value) / span) * (height - pad.top - pad.bottom);
  const line = returns.map((point, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
  const baseline = y(0).toFixed(1);
  const area = `${line} L${x(returns.length - 1).toFixed(1)},${baseline} L${x(0).toFixed(1)},${baseline} Z`;
  const latest = returns.at(-1);
  const tone = latest.value >= 0 ? "up" : "down";
  return `<div class="card-head"><div><h2 class="section-title">持仓收益曲线</h2><p class="card-subtitle">静态持仓回溯 · 前复权收盘价 · ${html(analytics.as_of)}</p></div><span class="status-pill ok">${analytics.curve.length} 个共同交易日</span></div>
    <div class="curve-chart" role="img" aria-label="组合累计收益从 0% 变化到 ${latest.value.toFixed(2)}%">
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <line class="curve-zero" x1="${pad.left}" y1="${baseline}" x2="${width - pad.right}" y2="${baseline}"></line>
        <path class="curve-area ${tone}" d="${area}"></path>
        <path class="curve-line ${tone}" d="${line}"></path>
        <circle class="curve-dot ${tone}" cx="${x(returns.length - 1).toFixed(1)}" cy="${y(latest.value).toFixed(1)}" r="4"></circle>
        <text x="6" y="${Math.max(y(max), 13).toFixed(1)}">${max.toFixed(1)}%</text>
        <text x="6" y="${Math.min(y(min) + 4, height - pad.bottom).toFixed(1)}">${min.toFixed(1)}%</text>
        <text x="${pad.left}" y="${height - 7}">${html(returns[0].date)}</text>
        <text text-anchor="end" x="${width - pad.right}" y="${height - 7}">${html(latest.date)}</text>
      </svg>
      <strong class="curve-latest ${tone === "up" ? "market-up" : "market-down"}">${latest.value >= 0 ? "+" : ""}${latest.value.toFixed(2)}%</strong>
    </div>`;
}

function renderWatchlist() {
  const panel = $("watchlistPanel");
  if (!panel) return;
  if (!state.watchlist.length) {
    panel.innerHTML = emptyBlock("观察池暂无真实标的", "从市场板块或策略筛选结果加入；每条记录会保存当时的日期、来源和证据。", ["从策略生成"]);
    return;
  }
  panel.innerHTML = `<div class="card-head"><div><h2>自选观察池</h2><p class="card-subtitle">${state.watchlist.length} 条带证据记录</p></div><button class="secondary" data-watch-to-strategy>生成策略</button></div>${state.watchlist.map((item) => `<div class="holding-row"><div class="row-title"><strong>${html(item.name || item.symbol)}</strong><span>${html(item.symbol)} · ${html(item.source_context)}</span></div><div class="row-cell">记录日期<small>${html(item.created_at)}</small></div><div class="row-cell">来源<small>${html(item.evidence?.source || item.source_context)}</small></div><div class="row-cell">证据值<small>${html(item.evidence?.change_pct == null ? "记录中未包含涨跌幅" : signedPct(item.evidence.change_pct))}</small></div></div>`).join("")}`;
}

function renderLineage() {
  const linked = state.portfolios.filter((item) => item.payload?.evidence_snapshot_id);
  if (!linked.length) return `<div class="card-head"><h2>策略血缘</h2><span class="status-pill warning">缺少来源证据</span></div>${emptyBlock("没有可还原的组合血缘", "现有组合未保存策略版本和筛选证据；从新的筛选结果创建模拟组合后即可还原。", ["去建策略"])}`;
  return `<div class="card-head"><h2>策略血缘</h2><span class="status-pill ok">${linked.length} 个组合已关联证据</span></div>${linked.map((item) => `<div class="timeline-row"><div class="row-title"><strong>${html(item.name)}</strong><span>证据快照 ${html(item.payload.evidence_snapshot_id)}</span></div><div class="row-cell">策略来源<small>${html(item.payload.strategy_id || "记录在证据快照中")}</small></div><div class="row-cell">入选数量<small>${html((item.payload.holdings || []).length)}</small></div><div class="row-cell">组合类型<small>${html(item.kind)}</small></div><div class="row-cell">更新时间<small>${html(item.updated_at)}</small></div></div>`).join("")}`;
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
  $("aiTaskGrid").innerHTML = tasks.map(([obj, title, desc], i) => `<article class="ai-task ${i === 0 ? "active" : ""}" data-ai-task="${obj}" data-ai-title="${html(title)}"><strong>${html(title)}</strong><p>${html(desc)}</p></article>`).join("");
  document.querySelectorAll("[data-ai-task]").forEach((node) => node.addEventListener("click", () => {
    document.querySelectorAll(".ai-task").forEach((x) => x.classList.remove("active"));
    node.classList.add("active");
    state.aiTask = node.dataset.aiTask;
    $("aiPrompt").value = node.dataset.aiTitle;
    renderAiOutput(state.aiTask);
    if (!state.aiRunning) runAiAnalysis();
  }));
  $("aiTranscript").innerHTML = `<div class="ai-welcome"><img src="/static/brand/ragdoll/mascot-cutout.png" alt="等待研究任务的老布偶猫"><div><span class="eyebrow">老布偶猫研究员</span><h3>今天想先研究什么？</h3><p>选择一个快捷任务，或直接写下问题。我会调用统一数据层，并把证据值、日期、来源、缺失项和需要确认的动作分开列出。</p></div></div>`;
  renderAiOutput("市场");
}

function renderAiOutput(kind) {
  const basis = {
    市场: ["数据来源：统一 DataProvider → /api/market/panorama", `数据时间：${state.marketPanorama?.as_of || "数据日期缺失"}`, `使用来源：${primarySource(state.marketPanorama)}`, "使用字段：指数、20/60日波动率、宽度、成交额、板块持续性"],
    策略: ["数据来源：/api/strategies、/api/factors", `策略数量：${state.strategies.length}`, "使用字段：DSL、因子状态、复权方式"],
    筛选: ["数据来源：/api/strategies/<id>/screen", `最近筛选：${state.screenResult ? "已运行" : "未运行"}`, "使用字段：漏斗步骤、逐股因子值、失败原因"],
    回测: ["数据来源：/api/backtests/<id>/result", `最近回测：${state.backtest ? "已完成" : "未运行"}`, "使用字段：权益曲线、成交记录、策略体检"],
    组合: ["数据来源：统一 DataProvider → /api/portfolio/analytics", `持仓数量：${state.holdings.length}`, `数据时间：${state.portfolioAnalytics?.as_of || "有效共同交易日缺失"}`, "使用字段：复权价、收益、回撤、波动率、行业与单股暴露"],
    决策: ["数据来源：SQLite 决策与证据快照", `决策记录：${state.decisions.length}`, "使用字段：用户确认行动、原始证据、到期行情与持仓结果"],
  }[kind];
  $("aiOutput").innerHTML = `<div class="data-check-grid ai-evidence-grid">
    ${sectionBlock("使用数据", basis)}
    ${sectionBlock("工具与确定性结果", deterministicPoints(kind))}
    ${sectionBlock("数据缺口", missingPoints(kind))}
    ${sectionBlock("执行边界", ["不会自动买卖", "不会自动修改组合", "保存与记录必须二次确认"])}
  </div>`;
}

async function runAiAnalysis() {
  if (state.aiRunning) {
    state.aiAbortController?.abort();
    return;
  }
  const prompt = $("aiPrompt").value.trim();
  if (!prompt) return toast("请先输入研究问题");
  state.aiRunning = true;
  state.aiAbortController = new AbortController();
  $("runAiBtn").textContent = "取消分析";
  $("aiRunStatus").className = "status-pill warning";
  $("aiRunStatus").textContent = "分析中";
  $("aiTranscript").insertAdjacentHTML("beforeend", `<div class="ai-message user"><span class="message-label">你的问题 · ${html(state.aiTask)}</span><p>${html(prompt)}</p></div><div id="aiThinking" class="ai-message assistant"><span class="message-label">老布偶猫 · 正在读取持仓与市场证据</span><p>正在调用已配置模型，长任务可以取消。</p></div>`);
  $("aiThinking")?.scrollIntoView({ block: "nearest" });
  try {
    const data = await api.request("/api/analyze", { method: "POST", body: JSON.stringify({ focus: state.aiTask, question: prompt }), signal: state.aiAbortController.signal });
    state.lastAiResult = data;
    $("aiThinking")?.remove();
    const adjustments = data.adjustments?.items || [];
    const actions = adjustments.length ? adjustments.map((item) => `${item.stock || "持仓"}：${item.action || "继续观察"}，${item.reason || "依据待确认"}`) : ["当前没有生成具体持仓动作。"];
    $("aiTranscript").insertAdjacentHTML("beforeend", `<div class="ai-message assistant"><span class="message-label">老布偶猫 · ${html(data.model || state.systemStatus?.llm_model || "已配置模型")} · ${data.holdings_kind === "demo" ? "示例持仓" : "真实持仓"} · ${html(data.generated_at || "刚刚")}</span>
      <h3>结论</h3><p>${html(data.diagnosis?.content || "分析完成，但没有返回结论文本。")}</p>
      <h3>关键证据与动作</h3><p>${actions.map(html).join("\n")}</p>
      <h3>风险与不确定性</h3><p>${html(data.risk?.content || "仍需核验数据完整性与模型结论。")}\n${(data.data_limits || []).map((item) => `· ${item}`).map(html).join("\n")}</p>
      <div class="notice"><strong>研究免责</strong><br>${html(data.disclaimer || "这是基于有限数据的模型研究意见，不构成收益承诺；执行前请自行核验并确认。")}</div>
      <div class="conclusion-actions"><span class="status-pill info">证据充分度 ${html(data.score ?? "待模型说明")}</span><button class="secondary" data-confirm-ai="record">记录为待确认决策</button><button class="secondary" data-confirm-ai="watch">加入观察池</button></div>
    </div>`);
    $("aiRunStatus").className = "status-pill ok";
    $("aiRunStatus").textContent = "分析完成";
    toast("AI 分析已完成，请核验后再记录");
  } catch (error) {
    $("aiThinking")?.remove();
    if (error.name === "AbortError") {
      $("aiTranscript").insertAdjacentHTML("beforeend", `<div class="notice">分析已取消，没有执行任何后续动作。</div>`);
      $("aiRunStatus").textContent = "已取消";
    } else {
      $("aiTranscript").insertAdjacentHTML("beforeend", errorCard("AI 分析失败", error.message));
      $("aiRunStatus").className = "status-pill error";
      $("aiRunStatus").textContent = "分析失败";
    }
  } finally {
    state.aiRunning = false;
    state.aiAbortController = null;
    $("runAiBtn").textContent = "开始分析";
    $("aiTranscript").scrollTop = $("aiTranscript").scrollHeight;
  }
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
  if (kind === "市场") return missingEntries(state.marketPanorama?.missing_fields);
  if (kind === "组合") return missingEntries(state.portfolioAnalytics?.missing_fields);
  if (kind === "策略") return ["机构调研没有稳定免鉴权主源；研报覆盖通过东财按标的查询", "Tushare 未配置时不会参与启动"];
  if (kind === "决策") return state.decisions.length ? ["仅到期且有有效行情的记录会生成结果"] : ["尚无用户确认决策，因此不生成复盘结论"];
  return ["按当前任务展示统一数据层返回的 missing_fields，不补造缺失值"];
}

function renderReviews() {
  const decisions = state.decisions || [];
  const stats = decisionReviewStats();
  $("reviewMetrics").innerHTML = [
    summaryCard("完整决策记录", String(decisions.length), decisions.length ? "均关联原始证据快照" : "尚无用户确认记录", "reviews", decisions.length ? "ok" : "warning"),
    summaryCard("到期复盘完成率", stats.due ? pct(stats.completionRate) : "尚无到期记录", stats.due ? `${stats.completed}/${stats.due} 条已用真实行情核验` : "到期后按复权行情计算", "reviews", stats.duePending ? "warning" : "info"),
    summaryCard("待复盘", String(stats.pending), stats.duePending ? `${stats.duePending} 条已到期但缺少可核验行情` : "包含尚未到期记录", "reviews", stats.duePending ? "warning" : "brand"),
    summaryCard("可归因样本", String(stats.completed), stats.completed < 30 ? "少于 30 条，不生成有效性结论" : "可进行分组归因", "reviews", "info"),
  ].join("");
  $("reviewTimeline").innerHTML = decisions.length ? decisions.map((p) => `<div class="timeline-row">
    <div class="row-title"><strong>${html(p.symbol || p.portfolio_id || "市场决策")}</strong><span>${html(p.created_at)} · 证据 ${html(p.evidence_snapshot_id)}</span></div>
    <div class="row-cell">行动<small>${html(p.action)}</small></div>
    <div class="row-cell">原始判断<small>${html(p.thesis)}</small></div>
    <div class="row-cell">到期日<small>${html(p.due_at || "未设置到期日")}</small></div>
    <div class="row-cell">结果<small>${p.result ? html(JSON.stringify(p.result)) : "尚无可核验到期结果"}</small></div>
    <div class="holding-actions"><button class="secondary" data-view-evidence="${html(p.evidence_snapshot_id)}">查看证据</button>${p.review_id ? `<span class="status-pill ok">已复盘</span>` : `<button data-review-decision="${html(p.id)}">完成复盘</button>`}</div>
  </div>`).join("") : state.reviews.length ? state.reviews.map((p) => `<div class="timeline-row">
    <div class="row-title"><strong>${html(p.stock_name || p.stock_code)}</strong><span>${html(p.decision_date)} · ${html(p.stock_code)}</span></div>
    <div class="row-cell">当时价格<small>${html(p.price_at_decision)}</small></div>
    <div class="row-cell">AI观点<small>${html(p.action)} · 置信度 ${html(p.confidence)}</small></div>
    <div class="row-cell">观察期<small>${html(p.check_date)}</small></div>
    <div class="row-cell">结果<small>${html(p.status)} / ${html(p.actual_return ?? "待回查")}</small></div>
    <button class="secondary">复盘</button>
  </div>`).join("") : `<div class="review-empty-composition"><img src="/static/brand/ragdoll/mascot-cutout.png" alt="等待真实决策记录的老布偶猫"><div><h2>暂无决策记录</h2><p>${html(state.reviewMessage || "只有用户确认后记录的观点才会进入复盘；没有记录时不会生成虚假总结。")}</p></div></div>`;
  $("reviewInsight").innerHTML = [
    insight("样本量提示", stats.completed < 30 ? `真实到期样本 ${stats.completed}/30，当前只能逐条复盘，不能输出策略有效性结论。` : `已有 ${stats.completed} 条真实到期样本，可按市场环境与行动类型分组。`),
    insight("偏差分类", "信息错误、规则错误、参数错误、市场环境变化、执行错误、未遵循信号。"),
    insight("月度总结", "当前仅基于真实记录生成；没有记录时不生成模板化总结。"),
  ].join("");
}

function decisionReviewStats() {
  const decisions = state.decisions || [];
  const today = new Date().toISOString().slice(0, 10);
  const due = decisions.filter((item) => item.due_at && item.due_at <= today);
  const completed = due.filter((item) => item.result?.status === "checked").length;
  return {
    due: due.length,
    completed,
    duePending: due.length - completed,
    pending: decisions.length - completed,
    completionRate: due.length ? completed / due.length * 100 : null,
  };
}

function insight(title, text) {
  return `<div class="insight-card"><strong>${html(title)}</strong><p>${html(text)}</p></div>`;
}

async function checkReviews() {
  try {
    const before = decisionReviewStats().completed;
    await loadReviews();
    const after = decisionReviewStats().completed;
    toast(`已检查真实到期记录：${Math.max(after - before, 0)} 条新增结果`);
  } catch (error) {
    $("reviewTimeline").insertAdjacentHTML("afterbegin", errorCard("到期检查失败", error.message));
  }
}

async function viewEvidenceSnapshot(snapshotId) {
  try {
    const data = await api.get(`/api/workflow/evidence/${snapshotId}`);
    const snapshot = data.snapshot;
    $("reviewTimeline").insertAdjacentHTML("afterbegin", `<details class="evidence-inspector" open><summary>证据快照 ${html(snapshot.id)} · ${html(snapshot.created_at)}</summary><pre>${html(JSON.stringify(snapshot.payload, null, 2))}</pre></details>`);
  } catch (error) { toast(`读取证据失败：${error.message}`); }
}

async function completeDecisionReview(decisionId) {
  const actualAction = window.prompt("实际采取了什么行动？例如 HOLD、SELL、TRIM", "HOLD");
  if (!actualAction) return;
  const decisionCorrect = window.confirm("回看结果后，你认为原判断基本正确吗？");
  const executionCorrect = window.confirm("你认为实际执行基本正确吗？");
  const biasType = window.prompt("偏差类型：信息错误 / 规则错误 / 参数错误 / 市场变化 / 执行错误 / 未遵循信号", "市场变化");
  if (!biasType) return;
  const nextAdjustment = window.prompt("下次具体调整什么？", "补充失效条件并缩短复盘周期");
  if (!nextAdjustment || !window.confirm("确认保存这次复盘？记录保存后仍可继续形成新策略版本。")) return;
  const payload = { confirm: true, actual_action: actualAction, decision_correct: decisionCorrect, execution_correct: executionCorrect, bias_type: biasType, next_adjustment: nextAdjustment };
  if (state.savedStrategyId && state.compiled?.dsl && window.confirm("是否同时把当前规则保存为一个复盘修订版本？")) {
    payload.create_strategy_version = { strategy_id: state.savedStrategyId, dsl: state.compiled.dsl, version: `review-${new Date().toISOString().slice(0, 10)}-${Date.now().toString().slice(-4)}`, note: nextAdjustment };
  }
  try {
    await api.post(`/api/workflow/decisions/${decisionId}/review`, payload);
    await loadReviews();
    toast("复盘已保存，原始决策与调整项可追溯");
  } catch (error) { toast(`复盘保存失败：${error.message}`); }
}

function renderSystem() {
  $("systemPanel").innerHTML = [
    sectionBlock("数据源", Object.entries(state.dataStatus?.checks || {}).map(([k, v]) => `${k}: ${v.status === "optional_missing" ? `可选依赖未安装，不影响启动（${v.error}）` : v.ok ? translateStatus(v.status) : v.error}`)),
    sectionBlock("缓存与降级", ["主源失败自动重试并顺序切换备源", "本地原子JSON缓存可在上游失败时返回最近可核验快照", "响应包含数据日期、更新时间、来源、完整度和错误原因"]),
    sectionBlock("LLM", [state.systemStatus?.llm_configured ? `${state.systemStatus.llm_provider} · ${state.systemStatus.llm_model}` : "未配置，不会泄露Key到前端"]),
    sectionBlock("安全", ["根目录静态文件不暴露", "CORS按本地可信来源限制", "不连接券商，不自动下单"]),
  ].join("");
}

function renderContext() {
  const panorama = state.marketPanorama || {};
  const b = panorama.breadth || {};
  const r = panorama.regime || {};
  const sectors = marketSectors().slice(0, 3);
  const signals = state.marketSignals.slice(0, 3);
  const commonStatus = contextSection("数据状态", [
    contextItem("行情来源", `${primarySource(panorama)} · ${translateStatus(panorama.status)}`),
    contextItem("数据日期", panorama.as_of || b.as_of || "待确认"),
    contextItem("AI", state.systemStatus?.llm_configured ? `${state.systemStatus.llm_provider || "LLM"} 已配置` : "未配置"),
  ]);
  const sections = {
    overview: [
      contextSection("市场状态", [contextItem("环境", `${r.label || "待确认"} · ${r.trend || "趋势待确认"}`), contextItem("上涨比例", b.up_ratio != null ? `${(b.up_ratio * 100).toFixed(1)}% · ${safeNum(b.up_count)} 涨 / ${safeNum(b.down_count)} 跌` : "数据缺失")]),
      contextSection("今日必看", (state.marketActions.slice(0, 3).map((item) => contextItem(localizeActionTitle(item.title || item.type || "持仓动作"), item.desc || "等待详细说明"))).length ? state.marketActions.slice(0, 3).map((item) => contextItem(localizeActionTitle(item.title || item.type || "持仓动作"), item.desc || "等待详细说明")) : [contextItem("暂无高优先级动作", "当前接口没有返回需要立即处理的事项。")]),
      contextSection("最新信号", signals.length ? signals.map((item) => contextItem(item.title || "信号", `${item.desc || ""} · ${item.time || "时间待确认"}`)) : [contextItem("暂无新信号", "继续按现有规则跟踪。")]),
      commonStatus,
    ],
    market: [
      contextSection("市场异常", [contextItem("宽度", b.up_ratio == null ? "数据缺失" : b.up_ratio < .4 ? "下跌家数显著占优" : b.up_ratio > .6 ? "上涨扩散明显" : "多空分歧"), contextItem("指数分化", indexDispersionText())]),
      contextSection("板块轮动", sectors.length ? sectors.map((sector) => contextItem(sector.name || "未命名板块", `涨跌 ${signedPct(sector.change_pct)} · 热度 ${sector.heat ?? "待确认"}`)) : [contextItem("暂无可靠主线", "板块扫描尚未返回。")]),
      contextSection("数据源状态", [contextItem("AKShare", providerStatus("akshare")), contextItem("Baostock", providerStatus("baostock")), contextItem("样本日期", panorama.as_of || "待确认")]),
    ],
    strategy: [
      contextSection("当前策略规则", [contextItem("流程", strategySteps[state.strategyStep]?.title || "表达想法"), contextItem("已启用规则", state.compiled ? `${(state.compiled.dsl?.entry_conditions?.conditions || []).filter((item) => item.enabled).length} 条` : "尚未生成 DSL")]),
      contextSection("数据可用性", strategyDataStatusItems()),
      contextSection("运行记录", [contextItem("最近筛选", state.screenResult ? `命中 ${state.screenResult.results?.length || 0} 只` : "尚未运行"), contextItem("最近回测", state.backtest ? "已完成，可查看体检" : "尚未运行")]),
      contextSection("下一步", [quickLink("检查数据字段", "strategy", "create"), quickLink("运行回测", "strategy", "backtest")]),
    ],
    portfolio: [
      contextSection("组合风险", [contextItem("风险等级", portfolioRiskLabel()), contextItem("最大风险来源", riskiestHoldingText()), contextItem("行业集中度", state.portfolioAnalytics?.metrics?.industry_concentration_pct == null ? missingReason("industry_concentration_pct", state.portfolioAnalytics) : pct(state.portfolioAnalytics.metrics.industry_concentration_pct))]),
      contextSection("待处理动作", state.marketActions.length ? state.marketActions.slice(0, 3).map((item) => contextItem(item.title || "持仓动作", item.desc || "等待说明")) : [contextItem("暂无强制动作", "继续检查持仓是否偏离原始逻辑。")]),
      contextSection("持仓提醒", state.holdings.length ? state.holdings.slice(0, 3).map((holding) => contextItem(holding.name || holding.code, `${pct(holding.pnl_pct)} · ${strategyLabel(holding.strategy || "未关联策略")}`)) : [contextItem("暂无真实持仓", "可以导入持仓或创建模拟组合。")]),
    ],
    ai: [
      contextSection("分析范围", [contextItem("当前任务", state.aiTask), contextItem("持仓样本", `${state.holdings.length} 只`), contextItem("市场日期", panorama.as_of || "待确认")]),
      contextSection("引用数据", [contextItem("市场", "/api/market/panorama"), contextItem("组合", "/api/portfolio"), contextItem("模型", state.systemStatus?.llm_model || "未配置")]),
      contextSection("确认动作", [contextItem("保存为策略", "需要二次确认"), contextItem("加入观察池", "需要二次确认"), contextItem("记录为决策", "需要真实基准价并确认")]),
    ],
    reviews: [
      contextSection("待复盘记录", [contextItem("待检查", `${decisionReviewStats().pending} 条`), contextItem("真实到期样本", `${decisionReviewStats().completed}/30`)]),
      contextSection("近期偏差", state.reviews.length ? [contextItem("从真实记录归因", "信息、规则、参数、环境与执行偏差")]: [contextItem("暂无可归因记录", "先记录一条已确认决策。")]),
      contextSection("到期检查", [quickLink("检查到期记录", "reviews"), contextItem("月度总结", decisionReviewStats().completed >= 30 ? "样本达到最低门槛" : "样本不足，不生成结论")]),
    ],
    system: [commonStatus, contextSection("工具链", [contextItem("Wyckoff CLI", state.systemStatus?.wyckoff_cli_available ? "可用" : "未发现"), contextItem("本地版本", state.systemStatus?.version || "待确认")])],
  };
  $("contextBody").innerHTML = (sections[state.view] || sections.overview).join("");
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
  return check.ok ? translateStatus(check.status) : `${translateStatus(check.status)} · ${check.error || "不可用"}`;
}

function translateStatus(status) {
  return ({ ok: "数据正常", installed: "已安装", optional_missing: "可选未安装", optional_unconfigured: "可选未配置", disabled: "未配置", partial: "部分数据", degraded: "降级可用", stale: "数据陈旧", loading: "计算中", waiting: "等待执行", running: "执行中", completed: "已完成", cancelled: "已取消", failed: "执行失败", error: "数据错误", unavailable: "来源不可用" }[status] || status || "待确认");
}

function marketSectors() {
  const legacy = state.legacyMarket?.hot_sectors;
  if (Array.isArray(legacy) && legacy.length) return legacy;
  const panorama = state.marketPanorama?.sectors;
  return Array.isArray(panorama) ? panorama : [];
}

function factorStatusLabel(status) {
  return ({ available: "数据完整", partial: "部分缺失", unavailable: "暂不可计算", disabled: "已禁用" }[status] || "待检查");
}

function strategyLabel(value) {
  const key = String(value || "").toLowerCase();
  return ({ hold: "持有观察", exit: "退出", trim: "减仓", probe: "试探", attack: "进攻", watching: "继续跟踪", breakdown: "趋势破位" }[key] || value || "待确认");
}

function sourceLabel(source) {
  const value = String(source || "");
  return ({ actions: "持仓动作接口", signals: "市场信号接口", strategies: "策略库", portfolio: "组合接口", workbench: "工作台", "data/status": "数据状态接口", "effect/stats": "复盘统计接口", "strategy-health": "策略体检接口" }[value] || value || "来源待确认");
}

function indexDispersionText() {
  const values = (state.marketPanorama?.indices || []).filter((item) => item.status === "ok").map((item) => Number(item.change_pct)).filter(Number.isFinite);
  if (values.length < 2) return "有效指数样本不足";
  const spread = Math.max(...values) - Math.min(...values);
  return `${spread.toFixed(2)} 个百分点 · ${spread >= 2 ? "分化较大" : "分化有限"}`;
}

function strategyDataStatusItems() {
  if (!state.compiled) return [contextItem("尚未检查", "先生成策略翻译，再核对因子字段。")];
  const conditions = state.compiled.dsl?.entry_conditions?.conditions || [];
  const statuses = conditions.map((condition) => state.factors.find((factor) => factor.id === condition.factor)?.status || "unavailable");
  return [
    contextItem("数据完整", `${statuses.filter((value) => value === "available").length} 条`),
    contextItem("部分缺失", `${statuses.filter((value) => value === "partial").length} 条`),
    contextItem("暂不可计算", `${statuses.filter((value) => value === "unavailable").length} 条`),
  ];
}

function riskiestHoldingText() {
  if (!state.holdings.length) return "暂无持仓";
  const holding = [...state.holdings].sort((a, b) => Number(a.pnl_pct || 0) - Number(b.pnl_pct || 0))[0];
  return `${holding.name || holding.code} · ${pct(holding.pnl_pct)}`;
}

function handleGlobalSearch(query) {
  const normalized = query.toLowerCase();
  const strategy = state.strategies.find((item) => `${item.name} ${item.id}`.toLowerCase().includes(normalized));
  const holding = state.holdings.find((item) => `${item.name} ${item.code}`.toLowerCase().includes(normalized));
  if (holding) {
    const nav = document.querySelector('[data-view="portfolio"]');
    setView("portfolio", nav.dataset.title, `已定位持仓：${holding.name || holding.code}`);
    setTab("portfolio", "real");
    return toast(`已定位持仓 ${holding.name || holding.code}`);
  }
  if (strategy) {
    const nav = document.querySelector('[data-view="strategy"]');
    setView("strategy", nav.dataset.title, `已定位策略：${strategy.name}`);
    setTab("strategy", "library");
    return toast(`已定位策略 ${strategy.name}`);
  }
  if (/市场|指数|宽度|成交|板块/.test(query)) {
    const nav = document.querySelector('[data-view="market"]');
    setView("market", nav.dataset.title, nav.dataset.subtitle);
    return toast("已进入市场诊断");
  }
  toast("当前数据中没有匹配项，可尝试股票代码或策略名称");
}

function errorCard(title, message) {
  return `<div class="error"><strong>${html(title)}</strong><br>${html(message)}<br><small>请检查数据源状态或重试。</small></div>`;
}

function emptyBlock(title, message, actions = []) {
  return `<div class="empty-state"><h2>${html(title)}</h2><p>${html(message)}</p>${actions.length ? `<div class="empty-actions">${actions.map((action) => `<button class="secondary" data-empty-action="${html(action)}">${html(action)}</button>`).join("")}</div>` : ""}</div>`;
}

function money(value) {
  if (value === null || value === undefined || value === "") return "数据缺失";
  const n = Number(value);
  if (Number.isNaN(n)) return "数据格式错误";
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(2)}万`;
  return n.toFixed(2);
}
function pct(value) {
  if (value === null || value === undefined || value === "") return "数据缺失";
  const n = Number(value);
  return Number.isNaN(n) ? "数据格式错误" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function riskPct(value) {
  if (value === null || value === undefined || value === "") return "数据缺失";
  const n = Number(value);
  return Number.isNaN(n) ? "数据格式错误" : `${n.toFixed(2)}%`;
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

function missingEntries(fields) {
  const entries = Object.entries(fields || {});
  return entries.length ? entries.map(([field, reason]) => `${field}：${reason}`) : ["当前任务所需核心字段已返回；仍需核验日期与来源"];
}

function missingReason(field, payload = state.marketPanorama) {
  const fields = payload?.missing_fields || {};
  if (fields[field]) return fields[field];
  const fuzzy = Object.entries(fields).find(([key]) => key.includes(field));
  return fuzzy?.[1] || "主备数据源均未返回可计算数据";
}

function marketVolatilityScore() {
  const values = (state.marketPanorama?.indices || []).map((item) => Number(item.volatility_20d)).filter(Number.isFinite);
  if (!values.length) return null;
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  return Math.max(0, Math.min(100, 100 - average * 2));
}

function marketVolatilityText() {
  const values = (state.marketPanorama?.indices || []).map((item) => Number(item.volatility_20d)).filter(Number.isFinite);
  return values.length ? `四大指数20日年化波动均值 ${(values.reduce((a, b) => a + b, 0) / values.length).toFixed(2)}%` : missingReason("volatility_20d");
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
  const raw = payload.source_status?.status;
  const s = raw ? translateStatus(raw) : payload.overview?.source || "来源待确认";
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
  const confirmAi = event.target.closest("[data-confirm-ai]");
  if (confirmAi) confirmAiAction(confirmAi.dataset.confirmAi);
  const watchSector = event.target.closest("[data-watch-sector]");
  if (watchSector) {
    const sector = marketSectors().find((item) => item.name === watchSector.dataset.watchName) || {};
    addWatchItem({ symbol: `sector:${watchSector.dataset.watchSector}`, name: watchSector.dataset.watchName, source_context: "market_sector", evidence: { change_pct: sector.change_pct, source: sector.source, as_of: state.marketPanorama?.as_of } });
  }
  const watchSymbol = event.target.closest("[data-watch-symbol]");
  if (watchSymbol) addWatchItem({ symbol: watchSymbol.dataset.watchSymbol, source_context: "strategy_screen", evidence: { strategy_id: state.savedStrategyId, screened_at: new Date().toISOString(), source: "strategy_screen" } });
  if (event.target.closest("[data-watch-to-strategy]")) createStrategyFromWatchlist();
  if (event.target.closest("[data-create-portfolio-from-screen]")) createPortfolioFromScreen();
  const reviewPosition = event.target.closest("[data-review-position]");
  if (reviewPosition) runCommittee(reviewPosition.dataset.reviewPosition);
  const close = event.target.closest("[data-close-position]");
  if (close) closePosition(close.dataset.closePosition);
  const remove = event.target.closest("[data-remove-position]");
  if (remove) removePosition(remove.dataset.removePosition);
  const committeeDecision = event.target.closest("[data-save-committee-decision]");
  if (committeeDecision) saveCommitteeDecision(committeeDecision.dataset.saveCommitteeDecision);
  const reviewDecision = event.target.closest("[data-review-decision]");
  if (reviewDecision) completeDecisionReview(reviewDecision.dataset.reviewDecision);
  const evidence = event.target.closest("[data-view-evidence]");
  if (evidence) viewEvidenceSnapshot(evidence.dataset.viewEvidence);
  const selectedStock = event.target.closest("[data-select-import-stock]");
  if (selectedStock) selectImportStock(selectedStock);
  const emptyAction = event.target.closest("[data-empty-action]");
  if (emptyAction) {
    const action = emptyAction.dataset.emptyAction;
    if (action.includes("回测")) {
      const btn = document.querySelector('[data-view="strategy"]');
      setView("strategy", btn.dataset.title, btn.dataset.subtitle);
      setTab("strategy", "backtest");
    } else if (action.includes("导入真实持仓") || action.includes("导入持仓")) {
      openPositionImport();
    } else if (action.includes("模拟组合")) {
      createPaperPortfolio();
    } else {
      toast(`${action}：请先完成上游数据或策略步骤`);
    }
  }
});

async function addWatchItem(payload) {
  try {
    await api.post("/api/watchlist", payload);
    await loadWatchlist();
    toast("已加入观察池，并保存当时证据");
  } catch (error) {
    toast(`加入观察池失败：${error.message}`);
  }
}

async function createStrategyFromWatchlist() {
  try {
    const data = await api.post("/api/watchlist/to-strategy", {});
    state.compiled = data;
    state.strategyStep = 1;
    const nav = document.querySelector('[data-view="strategy"]');
    setView("strategy", nav.dataset.title, nav.dataset.subtitle);
    setTab("strategy", "create");
    renderStrategyStep();
    toast("已从观察池生成策略草案，请确认规则");
  } catch (error) {
    toast(`生成策略失败：${error.message}`);
  }
}

async function createPortfolioFromScreen() {
  if (!state.screenResult?.results?.length) return toast("当前没有入选结果");
  try {
    await api.post("/api/portfolios/from-screen", { strategy_id: state.savedStrategyId, strategy_version: "v1.0", selected: state.screenResult.results, source_status: state.screenResult.source_status });
    await loadPortfolios();
    const nav = document.querySelector('[data-view="portfolio"]');
    setView("portfolio", nav.dataset.title, nav.dataset.subtitle);
    toast("模拟组合已创建，筛选证据已保存");
  } catch (error) {
    toast(`创建组合失败：${error.message}`);
  }
}

async function confirmAiAction(action) {
  if (!state.lastAiResult) return toast("当前没有可记录的AI分析");
  if (action === "watch") {
    const holding = state.holdings[0];
    if (!holding) return toast("没有明确股票代码，无法加入股票观察池");
    return addWatchItem({ symbol: holding.code, name: holding.name, source_context: "ai_analysis", evidence: state.lastAiResult.evidence || {} });
  }
  try {
    await api.post("/api/decisions", { symbol: state.holdings[0]?.code || null, portfolio_id: "current_holdings", action: state.lastAiResult.main_action || "WAIT", thesis: state.lastAiResult.diagnosis?.content || "", evidence: state.lastAiResult.evidence || {}, due_at: new Date(Date.now() + 20 * 86400000).toISOString().slice(0, 10) });
    await loadReviews();
    toast("决策与原始证据已记录，等待到期复盘");
  } catch (error) {
    toast(`记录决策失败：${error.message}`);
  }
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2600);
}

init();
