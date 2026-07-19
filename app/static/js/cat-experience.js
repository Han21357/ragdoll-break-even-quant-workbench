(() => {
  const copy = {
    市场: { title: "陪我看看今天的盘面", placeholder: "例如：今天市场偏强还是偏弱？哪些板块值得继续观察？" },
    策略: { title: "帮我挑挑策略里的刺", placeholder: "例如：这个策略最可能在哪种市场里失效？" },
    筛选: { title: "解释这次筛选结果", placeholder: "例如：为什么这些股票通过了，哪些条件最严格？" },
    回测: { title: "一起检查回测有没有骗人", placeholder: "例如：收益是否集中在少数交易？成本影响大吗？" },
    组合: { title: "看看组合里哪里最危险", placeholder: "例如：当前持仓有没有过度集中或信号偏离？" },
    决策: { title: "陪我做一次诚实复盘", placeholder: "例如：我最近最常犯的决策错误是什么？" },
  };

  let selectedKind = "市场";
  let pending = false;

  function catFace(size = "lg") {
    return `<span class="cat-avatar ${size}" aria-hidden="true"><i class="ear left"></i><i class="ear right"></i><i class="eye left"></i><i class="eye right"></i><i class="nose"></i><i class="mouth"></i></span>`;
  }

  function basisFor(kind) {
    const panorama = state.marketPanorama || {};
    const facts = {
      市场: [`日期 ${panorama.as_of || "待确认"}`, `市场环境 ${panorama.regime?.label || "待确认"}`, `上涨比例 ${panorama.breadth?.up_ratio != null ? (panorama.breadth.up_ratio * 100).toFixed(1) + "%" : "不可用"}`],
      策略: [`已保存策略 ${state.strategies.length} 个`, `因子 ${state.factors.length} 个`, "策略规则由Pydantic校验"],
      筛选: [state.screenResult ? "已有最近筛选结果" : "尚未运行筛选", "筛选解释基于漏斗和逐股因子值"],
      回测: [state.backtest ? "已有最近回测结果" : "尚未运行回测", state.backtest ? `可信度 ${state.backtest.diagnostics?.credibility_score ?? "--"}/100` : "无可信度评分"],
      组合: [`当前持仓 ${state.holdings.length} 只`, `持仓类型 ${state.portfolioSummary?.portfolio_kind || "待确认"}`, `行情覆盖 ${state.portfolioSummary?.quote_coverage ?? "--"}%`],
      决策: [`决策记录 ${state.reviews.length} 条`, `待复盘 ${state.reviewStats?.pending ?? 0} 条`, "仅使用真实记录生成复盘"],
    };
    return facts[kind] || [];
  }

  function renderAssistant(kind = selectedKind) {
    selectedKind = kind;
    const target = document.getElementById("aiOutput");
    if (!target) return;
    const info = copy[kind] || copy.市场;
    const status = state.systemStatus?.llm_configured
      ? `<span class="cat-online"><i></i>${html(state.systemStatus.llm_provider || "AI")} · ${html(state.systemStatus.llm_model || "已配置")}</span>`
      : `<span class="cat-offline"><i></i>模型未配置</span>`;
    target.innerHTML = `<section class="cat-ai-shell">
      <div class="cat-ai-chat">
        <header class="cat-chat-head">
          <div class="cat-helper">${catFace()}<div><strong>${html(info.title)}</strong><span>老布偶猫会先看数据，再给出待核验解释</span></div></div>
          ${status}
        </header>
        <div id="catConversation" class="cat-conversation">
          <article class="cat-message assistant">
            ${catFace("sm")}
            <div><strong>喵，我已经把依据摆在桌上了</strong><p>你可以直接追问。回答会标明数据依据、风险和不确定性，不会自动下单或写入决策记录。</p></div>
          </article>
        </div>
        <form id="catAskForm" class="cat-composer">
          <textarea id="catQuestion" rows="3" placeholder="${html(info.placeholder)}"></textarea>
          <div class="cat-composer-foot"><span>Enter换行 · 点击按钮提交</span><button type="submit" id="catAskBtn">问老布偶猫</button></div>
        </form>
      </div>
      <aside class="cat-ai-evidence">
        <div class="cat-note-title"><span>🐾</span><strong>本次依据</strong></div>
        ${basisFor(kind).map((line) => `<div class="cat-evidence-row"><i></i><span>${html(line)}</span></div>`).join("")}
        <div class="cat-paper-note"><strong>小猫原则</strong><p>先看来源，再看结论；先找反证，再谈行动。</p></div>
      </aside>
    </section>`;
    document.getElementById("catAskForm")?.addEventListener("submit", askCat);
  }

  async function askCat(event) {
    event.preventDefault();
    if (pending) return;
    const input = document.getElementById("catQuestion");
    const question = input?.value.trim();
    if (!question) return;
    const conversation = document.getElementById("catConversation");
    conversation.insertAdjacentHTML("beforeend", `<article class="cat-message user"><div><p>${html(question)}</p></div></article>`);
    input.value = "";
    pending = true;
    const button = document.getElementById("catAskBtn");
    button.disabled = true;
    button.textContent = "小猫思考中…";
    const loadingId = `cat-loading-${Date.now()}`;
    conversation.insertAdjacentHTML("beforeend", `<article id="${loadingId}" class="cat-message assistant loading">${catFace("sm")}<div><span class="cat-typing"><i></i><i></i><i></i></span><p>正在核对行情、持仓和数据来源…</p></div></article>`);
    conversation.scrollTop = conversation.scrollHeight;
    try {
      const result = await api.post("/api/analyze", { focus: selectedKind, question });
      document.getElementById(loadingId)?.remove();
      conversation.insertAdjacentHTML("beforeend", renderAnswer(result));
    } catch (error) {
      document.getElementById(loadingId)?.remove();
      conversation.insertAdjacentHTML("beforeend", `<article class="cat-message assistant error">${catFace("sm")}<div><strong>这次没能叫醒模型</strong><p>${html(error.message)}</p><small>请在数据状态页确认模型配置，或稍后重试。</small></div></article>`);
    } finally {
      pending = false;
      button.disabled = false;
      button.textContent = "问老布偶猫";
      conversation.scrollTop = conversation.scrollHeight;
    }
  }

  function renderAnswer(result) {
    const diagnosis = result?.diagnosis?.content || result?.diagnosis || "模型没有返回诊断。";
    const risk = result?.risk?.content || result?.risk || "暂无额外风险说明。";
    const items = result?.adjustments?.items || result?.adjustments || [];
    const adjustments = Array.isArray(items) && items.length
      ? `<div class="cat-answer-list">${items.map((item) => `<div><strong>${html(item.stock || "组合")}</strong><span>${html(item.action || "观察")}</span><p>${html(item.reason || "")}</p></div>`).join("")}</div>`
      : "";
    return `<article class="cat-message assistant answer">${catFace("sm")}<div>
      <div class="cat-answer-meta"><span>${html(result?.model || "老布偶猫AI")}</span><span>${html(result?.generated_at || "刚刚")}</span></div>
      <strong>我的判断</strong><p>${html(diagnosis)}</p>
      <div class="cat-risk"><b>需要防着的事</b><p>${html(risk)}</p></div>
      ${adjustments}
      <small>AI解释仅用于研究和复盘，请结合数据日期与自己的风险承受能力核验。</small>
    </div></article>`;
  }

  function enhanceTasks() {
    document.querySelectorAll("[data-ai-task]").forEach((node) => {
      node.addEventListener("click", () => {
        selectedKind = node.dataset.aiTask || "市场";
        queueMicrotask(() => renderAssistant(selectedKind));
      });
    });
    renderAssistant("市场");
  }

  function fixPanoramaNormalization() {
    const original = drawPanoramaChart;
    drawPanoramaChart = function patchedDrawPanoramaChart() {
      const data = state.marketPanorama?.indices || [];
      data.forEach((idx) => {
        const raw = (idx.series || []).slice(-state.panoramaRange);
        const base = raw[0]?.close;
        idx.__displaySeries = base ? raw.map((p) => ({ ...p, normalized: p.close / base * 100 })) : raw;
      });
      const originals = data.map((idx) => idx.series);
      data.forEach((idx) => { if (idx.__displaySeries) idx.series = idx.__displaySeries; });
      try { original(); } finally { data.forEach((idx, i) => { idx.series = originals[i]; }); }
    };
  }

  function addResizeHandling() {
    if (!("ResizeObserver" in window)) return;
    const chartNode = document.getElementById("panoramaChart");
    if (!chartNode) return;
    let timer;
    new ResizeObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (state.view === "overview") drawPanoramaChart();
      }, 100);
    }).observe(chartNode);
  }

  function initEnhancements() {
    fixPanoramaNormalization();
    loadFactors().then(() => { renderFactors(); renderStrategyStep(); }).catch(() => {});
    enhanceTasks();
    addResizeHandling();
    document.getElementById("catAssistantBtn")?.addEventListener("click", () => setTimeout(() => renderAssistant(selectedKind), 0));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initEnhancements, { once: true });
  else initEnhancements();
})();