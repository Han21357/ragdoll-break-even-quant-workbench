const api = window.RagdollAPI;
let compiledDsl = null;
let savedStrategyId = null;
let chart = null;

const $ = (id) => document.getElementById(id);
const html = (value) => String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2600);
}

function card(content, kind = "notice") {
  return `<div class="${kind}">${content}</div>`;
}

async function init() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      btn.classList.add("active");
      $(btn.dataset.view).classList.add("active");
    });
  });
  $("btEnd").value = new Date().toISOString().slice(0, 10);
  bindActions();
  await Promise.allSettled([loadDataStatus(), loadMarket(), loadFactors(), loadPortfolios(), loadReviews()]);
}

function bindActions() {
  $("refreshMarket").addEventListener("click", loadMarket);
  $("compileBtn").addEventListener("click", compileIdea);
  $("validateBtn").addEventListener("click", validateDsl);
  $("saveStrategyBtn").addEventListener("click", saveStrategy);
  $("screenBtn").addEventListener("click", screenStrategy);
  $("runBacktestBtn").addEventListener("click", runBacktest);
  $("createPaperPortfolio").addEventListener("click", createPaperPortfolio);
}

async function loadDataStatus() {
  try {
    const data = await api.get("/api/data/status");
    $("dataBadge").textContent = data.status === "ok" ? "数据正常" : "数据降级";
  } catch (error) {
    $("dataBadge").textContent = "数据不可用";
  }
}

async function loadMarket() {
  try {
    const [overview, regime] = await Promise.all([api.get("/api/market/overview"), api.get("/api/market/regime")]);
    const o = overview.overview;
    $("marketGrid").innerHTML = [
      ["上涨家数", o.up_count],
      ["下跌家数", o.down_count],
      ["A股样本", o.total],
      ["成交额", o.amount ? `${(o.amount / 1e8).toFixed(1)}亿` : "待确认"],
    ].map(([k, v]) => `<article class="metric"><span>${k}</span><strong>${html(v)}</strong><small>${html(o.source)} · ${html(o.as_of)}</small></article>`).join("");
    $("regimeTrend").textContent = regime.regime.trend;
    $("regimeMeta").textContent = `${regime.regime.breadth}宽度 · ${regime.regime.risk_appetite}`;
    $("regimePanel").innerHTML = card(`趋势：${html(regime.regime.trend)}　波动：${html(regime.regime.volatility)}　宽度：${html(regime.regime.breadth)}　风险偏好：${html(regime.regime.risk_appetite)}　风格：${html(regime.regime.style)}<br><small>${html(regime.regime.method)}</small>`);
  } catch (error) {
    $("marketGrid").innerHTML = card(`市场数据不可用：${html(error.message)}`, "error");
  }
}

async function loadFactors() {
  const data = await api.get("/api/factors");
  const factors = data.factors;
  $("factorMiniList").innerHTML = factors.slice(0, 18).map((f) => `<div class="factor-pill"><span>${html(f.name)}</span><small>${html(f.status)}</small></div>`).join("");
  $("factorTable").innerHTML = `<table><thead><tr><th>ID</th><th>名称</th><th>分类</th><th>口径</th><th>来源</th><th>状态</th></tr></thead><tbody>${factors.map((f) => `<tr><td>${html(f.id)}</td><td>${html(f.name)}</td><td>${html(f.category)}</td><td>${html(f.formula)}</td><td>${html(f.data_source)}</td><td>${html(f.status)}</td></tr>`).join("")}</tbody></table>`;
}

async function compileIdea() {
  $("compileResult").innerHTML = card("正在生成策略翻译确认页...");
  try {
    const data = await api.post("/api/strategies/compile", { text: $("ideaInput").value });
    compiledDsl = data.dsl;
    $("compileResult").innerHTML = [
      card(`<strong>用户原始表达</strong><br>${html(data.original_text)}`),
      card(`<strong>语义拆解</strong><br>${data.semantic_breakdown.map((x) => `${html(x.text)} → <code>${html(x.definition)}</code>`).join("<br>")}`),
      card(`<strong>可执行DSL</strong><pre>${html(JSON.stringify(data.dsl, null, 2))}</pre>`),
      data.ambiguities.length ? card(`<strong>歧义与数据缺口</strong><br>${data.ambiguities.map((x) => `${html(x.term)}：${html(x.message || x.selected || "")}（${html(x.data_status || "待确认")}）`).join("<br>")}`, "error") : "",
    ].join("");
  } catch (error) {
    $("compileResult").innerHTML = card(error.message, "error");
  }
}

async function validateDsl() {
  if (!compiledDsl) await compileIdea();
  try {
    const data = await api.post("/api/strategies/validate", { dsl: compiledDsl });
    $("compileResult").insertAdjacentHTML("afterbegin", card(data.ok ? "策略校验通过，所有启用因子可进入筛选。" : data.errors.join("；"), data.ok ? "success" : "error"));
  } catch (error) {
    toast(error.message);
  }
}

async function saveStrategy() {
  if (!compiledDsl) await compileIdea();
  const data = await api.post("/api/strategies", { dsl: compiledDsl, version: "v1.0" });
  savedStrategyId = data.strategy.id;
  toast("策略v1.0已保存");
}

async function screenStrategy() {
  if (!compiledDsl && !savedStrategyId) await compileIdea();
  if (!savedStrategyId) await saveStrategy();
  const symbols = $("symbolsInput").value.split(",").map((x) => x.trim()).filter(Boolean);
  $("screenResult").innerHTML = card("正在读取真实日线并执行筛选漏斗...");
  try {
    const data = await api.post(`/api/strategies/${savedStrategyId}/screen`, { dsl: compiledDsl, symbols });
    $("screenResult").innerHTML = [
      card(`<strong>筛选漏斗</strong><br>${data.funnel.map((x) => `${html(x.label)}：${x.count}`).join("<br>")}`, "success"),
      ...data.results.map((x) => card(`<strong>${html(x.symbol)}</strong> 第${x.rank}名　收盘 ${html(x.close)}　${html(x.source)} ${html(x.as_of)}<br>${x.explanation.passed.map((p) => `✓ ${html(p.factor)}=${html(p.actual)} / ${html(p.operator)} ${html(p.threshold)}`).join("<br>")}`)),
    ].join("") || card("无入选股票。");
  } catch (error) {
    $("screenResult").innerHTML = card(error.message, "error");
  }
}

async function runBacktest() {
  const payload = {
    stocks: $("btStocks").value.split(",").map((x) => x.trim()).filter(Boolean),
    start_date: $("btStart").value,
    end_date: $("btEnd").value,
    initial_capital: Number($("btCapital").value),
    hold_days: Number($("btHoldDays").value),
    max_positions: Number($("btMaxPositions").value),
  };
  $("backtestMeta").innerHTML = card("任务已提交：读取行情 → 撮合成交 → 计算权益曲线 → 生成体检");
  const task = await api.post("/api/backtests", payload);
  $("backtestState").textContent = "运行中";
  pollBacktest(task.task_id);
}

async function pollBacktest(taskId) {
  const data = await api.get(`/api/backtests/${taskId}`);
  if (data.status === "running") {
    setTimeout(() => pollBacktest(taskId), 1200);
    return;
  }
  if (data.status === "error") {
    $("backtestState").textContent = "失败";
    $("backtestResult").innerHTML = card(data.error || "回测失败", "error");
    return;
  }
  const result = data.result;
  $("backtestState").textContent = "已完成";
  renderBacktest(result);
}

function renderBacktest(result) {
  const m = result.metrics;
  $("backtestMeta").innerHTML = card(`引擎：AKQuant适配器（compatibility_runner_used=${result.engine.compatibility_runner_used}）<br>${result.limitations.join("<br>")}`);
  $("backtestResult").innerHTML = [
    card(`累计收益 ${m.total_return}%　年化 ${m.annual_return}%　最大回撤 ${m.max_drawdown}%　Sharpe ${m.sharpe}　交易级胜率 ${m.trade_win_rate}%　收益周期正收益率 ${m.positive_period_rate}%`, "success"),
    card(`<strong>策略体检：${result.diagnostics.credibility_score}/100</strong><br>${result.diagnostics.main_risks.join("<br>") || "未发现主要风险"}<br><small>评分来自确定性规则。</small>`),
    card(`<strong>最近成交</strong><br>${result.trades.slice(-8).map((t) => `${html(t.symbol)} ${html(t.entry_date)}→${html(t.exit_date)} PnL ${html(t.pnl)} 成本 ${html(t.cost)} 持有${html(t.hold_days)}天`).join("<br>") || "无成交"}`),
  ].join("");
  drawEquity(result.equity_curve);
}

function drawEquity(points) {
  const node = $("equityChart");
  node.innerHTML = "";
  if (!window.LightweightCharts || !points.length) return;
  chart = LightweightCharts.createChart(node, { layout: { background: { color: "#fffdf7" }, textColor: "#27302a" }, grid: { vertLines: { color: "#eee6d6" }, horzLines: { color: "#eee6d6" } }, rightPriceScale: { borderColor: "#ded5c5" }, timeScale: { borderColor: "#ded5c5" } });
  const series = chart.addLineSeries({ color: "#7a8f68", lineWidth: 2 });
  series.setData(points.map((p) => ({ time: p.date, value: p.equity })));
  chart.timeScale().fitContent();
}

async function loadPortfolios() {
  const data = await api.get("/api/portfolios");
  $("portfolioPanel").innerHTML = data.portfolios.length ? data.portfolios.map((p) => card(`${html(p.name)} · ${html(p.kind)}`)).join("") : card("暂无组合。");
}

async function createPaperPortfolio() {
  await api.post("/api/portfolios", { name: "策略观察池", kind: "paper", holdings: [] });
  toast("模拟组合已创建");
  loadPortfolios();
}

async function loadReviews() {
  const data = await api.get("/api/reviews");
  $("reviewPanel").innerHTML = card(data.message || "复盘记录待创建。");
  $("aiPanel").innerHTML = card("AI输出必须引用工具返回数据；策略执行只经过DSL白名单或受控模板。");
}

init();

