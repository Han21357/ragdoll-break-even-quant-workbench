"""
老布偶猫回本之路 · 多Agent决策链路
基于 LangGraph StateGraph，5层决策：扫描→分析→辩论→交易→风控
"""
import json
import time
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

# ---- 复用服务端的函数 ----
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# ---- State 定义 ----
class AgentState(TypedDict):
    # 输入
    stock_code: str          # 分析的股票代码
    stock_name: str          # 股票名称
    # Layer 1: 市场数据
    market_data: Dict        # baostock + screen 数据
    indices: Dict            # 大盘指数
    regime: Dict             # 市场状态
    # Layer 2: 三分析师报告
    wyckoff_report: str      # 威科夫分析报告
    technical_report: str    # 技术面分析报告
    fundamental_report: str  # 基本面分析报告
    # Layer 3: 多空辩论
    bull_argument: str       # 多头论点
    bear_argument: str       # 空头论点
    debate_summary: str      # 辩论总结
    # Layer 4: 交易员决策
    trader_decision: Dict    # 方向+仓位+置信度
    # Layer 5: 风控+最终决策
    risk_assessment: str     # 风控评估
    final_decision: Dict     # 最终决策
    # 元数据
    trace: List[Dict]        # 全链路推理日志
    started_at: str
    completed_at: str


def create_agent_chain(call_llm_fn, get_market_fn, get_holdings_fn):
    """
    创建 Agent 链路
    call_llm_fn: 调用LLM的函数 (messages, max_tokens) -> (content, error)
    get_market_fn: 获取市场数据的函数 () -> dict
    get_holdings_fn: 获取持仓的函数 () -> list
    """
    
    def _log(state, layer, agent, content, duration_ms=0):
        """记录推理日志"""
        entry = {
            "layer": layer,
            "agent": agent,
            "content": content[:500] if isinstance(content, str) else str(content)[:500],
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
        }
        state["trace"].append(entry)
        return state

    def _llm(system_prompt, user_prompt, max_tokens=1500):
        """封装LLM调用"""
        content, err = call_llm_fn([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens=max_tokens)
        if err:
            return f"[LLM错误: {err}]"
        return content or "[LLM返回空]"

    # ============================
    # Layer 1: 市场扫描 Agent
    # ============================
    def market_scanner(state: AgentState) -> dict:
        t0 = time.time()
        market = get_market_fn()
        indices = market.get("indices", {})
        regime = market.get("regime", {})
        sectors = market.get("hot_sectors", [])[:5]
        
        summary = f"大盘: {regime.get('regime_label','中性')} 温度{regime.get('temperature',48)}°\n"
        for k, label in [("sh","上证"),("sz","深证"),("cy","创业板")]:
            idx = indices.get(k, {})
            if idx.get("value"):
                summary += f"{label}: {idx['value']} ({idx.get('change_pct',0):+.2f}%)\n"
        summary += f"热门板块: {', '.join(s.get('name','') for s in sectors)}"
        
        state = _log(state, 1, "市场扫描Agent", summary, int((time.time()-t0)*1000))
        return {
            "market_data": market,
            "indices": indices,
            "regime": regime,
        }

    # ============================
    # Layer 2: 三分析师并行
    # ============================
    def wyckoff_analyst(state: AgentState) -> dict:
        t0 = time.time()
        code = state.get("stock_code", "")
        name = state.get("stock_name", "")
        regime = state.get("regime", {})
        
        # 获取持仓信息（如果有）
        holdings = get_holdings_fn()
        holding = None
        for h in holdings:
            if h.get("code") == code:
                holding = h
                break
        
        holding_info = ""
        if holding:
            holding_info = f"成本:{holding.get('cost','?')} 现价:{holding.get('price','?')} 阶段:{holding.get('phase_label','?')} 策略:{holding.get('strategy','?')} 信号:{holding.get('key_signals',[])}"
        
        prompt = f"""分析股票 {name}({code}) 的威科夫量价状态。

市场环境: {regime.get('regime_label','中性')} 温度{regime.get('temperature',48)}°
持仓信息: {holding_info or '无持仓'}

请从威科夫方法角度分析:
1. 当前处于哪个阶段（Accumulation/Spring/Markup/Distribution/Break）
2. 关键量价信号（SOS/SOW/JAC/LPS/UT等）
3. 相对强弱（RS）评估
4. 操作建议

用200字以内简洁输出。"""

        report = _llm(
            "你是威科夫量价分析专家。专注 Spring/SOS/Markup 等威科夫信号识别。简洁专业。",
            prompt, max_tokens=800
        )
        state = _log(state, 2, "威科夫分析师", report, int((time.time()-t0)*1000))
        return {"wyckoff_report": report}

    def technical_analyst(state: AgentState) -> dict:
        t0 = time.time()
        code = state.get("stock_code", "")
        name = state.get("stock_name", "")
        
        prompt = f"""分析股票 {name}({code}) 的技术面指标。

请从以下角度分析（基于一般A股技术面特征）:
1. RSI 超买/超卖状态
2. MACD 金叉/死叉趋势
3. 均线排列（多头/空头/纠缠）
4. 成交量趋势（放量/缩量）
5. 关键支撑/压力位

用200字以内简洁输出，给出技术面评分（1-10）。"""

        report = _llm(
            "你是技术面分析师。擅长 RSI、MACD、均线系统分析。用数据说话。",
            prompt, max_tokens=800
        )
        state = _log(state, 2, "技术面分析师", report, int((time.time()-t0)*1000))
        return {"technical_report": report}

    def fundamental_analyst(state: AgentState) -> dict:
        t0 = time.time()
        code = state.get("stock_code", "")
        name = state.get("stock_name", "")
        
        prompt = f"""分析股票 {name}({code}) 的基本面。

请从以下角度评估:
1. 估值水平（PE/PB分位）
2. 盈利能力（ROE/净利率）
3. 成长性（营收/利润增速）
4. 行业地位和竞争格局
5. 潜在催化剂或风险

用200字以内简洁输出，给出基本面评分（1-10）。"""

        report = _llm(
            "你是基本面分析师。擅长估值、财务分析和行业研究。客观中立。",
            prompt, max_tokens=800
        )
        state = _log(state, 2, "基本面分析师", report, int((time.time()-t0)*1000))
        return {"fundamental_report": report}

    # ============================
    # Layer 3: 多空辩论
    # ============================
    def bull_researcher(state: AgentState) -> dict:
        t0 = time.time()
        name = state.get("stock_name", "")
        regime = state.get("regime", {})
        
        prompt = f"""你是多头研究员，为股票 {name} 寻找买入理由。

已知信息:
- 市场状态: {regime.get('regime_label','中性')}
- 威科夫分析: {state.get('wyckoff_report','')[:300]}
- 技术面: {state.get('technical_report','')[:300]}
- 基本面: {state.get('fundamental_report','')[:300]}

请列出3个最强的买入理由，每个用一句话概括。"""

        argument = _llm(
            "你是多头研究员，Always look for reasons to BUY. 积极但理性。",
            prompt, max_tokens=600
        )
        state = _log(state, 3, "多头研究员", argument, int((time.time()-t0)*1000))
        return {"bull_argument": argument}

    def bear_researcher(state: AgentState) -> dict:
        t0 = time.time()
        name = state.get("stock_name", "")
        regime = state.get("regime", {})
        
        prompt = f"""你是空头研究员，为股票 {name} 寻找风险信号。

已知信息:
- 市场状态: {regime.get('regime_label','中性')}
- 威科夫分析: {state.get('wyckoff_report','')[:300]}
- 技术面: {state.get('technical_report','')[:300]}
- 基本面: {state.get('fundamental_report','')[:300]}
- 多头观点: {state.get('bull_argument','')[:200]}

请反驳多头观点，列出3个最大的风险，每个用一句话概括。"""

        argument = _llm(
            "你是空头研究员，Always look for risks. 谨慎但客观。",
            prompt, max_tokens=600
        )
        state = _log(state, 3, "空头研究员", argument, int((time.time()-t0)*1000))
        return {"bear_argument": argument}

    def debate_summarizer(state: AgentState) -> dict:
        t0 = time.time()
        name = state.get("stock_name", "")
        
        prompt = f"""总结关于股票 {name} 的多空辩论。

多头观点: {state.get('bull_argument','')}
空头观点: {state.get('bear_argument','')}

请客观总结:
1. 多方核心逻辑（1句）
2. 空方核心逻辑（1句）
3. 争议焦点（1句）
4. 综合倾向（偏多/偏空/中性）"""

        summary = _llm(
            "你是中立的辩论主持人。客观总结双方观点。",
            prompt, max_tokens=400
        )
        state = _log(state, 3, "辩论总结", summary, int((time.time()-t0)*1000))
        return {"debate_summary": summary}

    # ============================
    # Layer 4: 交易员 Agent
    # ============================
    def trader_agent(state: AgentState) -> dict:
        t0 = time.time()
        name = state.get("stock_name", "")
        regime = state.get("regime", {})
        
        prompt = f"""你是交易员，基于以下信息对 {name} 做出交易决策。

市场状态: {regime.get('regime_label','中性')} 温度{regime.get('temperature',48)}°
辩论总结: {state.get('debate_summary','')}

请输出JSON格式（不要其他文字）:
{{"direction": "买入/卖出/持有/观望", "position_pct": 仓位建议百分比数字, "confidence": 置信度1-10数字, "reasoning": "决策理由50字"}}"""

        result = _llm(
            "你是专业交易员。基于多空辩论和市场状态做决策。只输出JSON。",
            prompt, max_tokens=400
        )
        
        # 尝试解析JSON
        decision = {"direction": "持有", "position_pct": 0, "confidence": 5, "reasoning": result[:100]}
        try:
            import re
            m = re.search(r'\{[\s\S]*\}', result)
            if m:
                decision = json.loads(m.group(0))
        except:
            pass
        
        state = _log(state, 4, "交易员", json.dumps(decision, ensure_ascii=False), int((time.time()-t0)*1000))
        return {"trader_decision": decision}

    # ============================
    # Layer 5: 风控 + 基金经理
    # ============================
    def risk_manager(state: AgentState) -> dict:
        t0 = time.time()
        name = state.get("stock_name", "")
        decision = state.get("trader_decision", {})
        regime = state.get("regime", {})
        
        prompt = f"""你是风控经理，审核对 {name} 的交易决策。

交易员建议: {json.dumps(decision, ensure_ascii=False)}
市场状态: {regime.get('regime_label','中性')} 温度{regime.get('temperature',48)}°

请评估:
1. 仓位是否过大（建议上限）
2. 止损建议
3. 风险等级（低/中/高）
4. 是否批准此交易

用100字以内输出。"""

        assessment = _llm(
            "你是风控经理。保守、严谨。可以否决交易员的建议。",
            prompt, max_tokens=300
        )
        state = _log(state, 5, "风控经理", assessment, int((time.time()-t0)*1000))
        return {"risk_assessment": assessment}

    def portfolio_manager(state: AgentState) -> dict:
        t0 = time.time()
        name = state.get("stock_name", "")
        decision = state.get("trader_decision", {})
        risk = state.get("risk_assessment", "")
        
        prompt = f"""你是基金经理，做最终决策。

股票: {name}
交易员建议: {json.dumps(decision, ensure_ascii=False)}
风控评估: {risk}

请输出最终决策JSON（不要其他文字）:
{{"action": "买入/卖出/持有/观望", "position_pct": 最终仓位, "stop_loss_pct": 止损百分比, "target_pct": 目标收益百分比, "confidence": 置信度1-10, "summary": "一句话总结"}}"""

        result = _llm(
            "你是基金经理。综合交易员和风控意见做最终决策。只输出JSON。",
            prompt, max_tokens=400
        )
        
        final = {"action": "观望", "position_pct": 0, "stop_loss_pct": -8, "target_pct": 15, "confidence": 5, "summary": result[:80]}
        try:
            import re
            m = re.search(r'\{[\s\S]*\}', result)
            if m:
                final = json.loads(m.group(0))
        except:
            pass
        
        state = _log(state, 5, "基金经理", json.dumps(final, ensure_ascii=False), int((time.time()-t0)*1000))
        return {"final_decision": final, "completed_at": datetime.now().isoformat()}

    # ============================
    # 构建 LangGraph
    # ============================
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("market_scanner", market_scanner)
    graph.add_node("wyckoff_analyst", wyckoff_analyst)
    graph.add_node("technical_analyst", technical_analyst)
    graph.add_node("fundamental_analyst", fundamental_analyst)
    graph.add_node("bull_researcher", bull_researcher)
    graph.add_node("bear_researcher", bear_researcher)
    graph.add_node("debate_summarizer", debate_summarizer)
    graph.add_node("trader", trader_agent)
    graph.add_node("risk_manager", risk_manager)
    graph.add_node("portfolio_manager", portfolio_manager)
    
    # Layer 1 → Layer 2 (fan-out to 3 analysts)
    graph.add_edge(START, "market_scanner")
    graph.add_edge("market_scanner", "wyckoff_analyst")
    graph.add_edge("market_scanner", "technical_analyst")
    graph.add_edge("market_scanner", "fundamental_analyst")
    
    # Layer 2 → Layer 3 (fan-in to bull, then bear, then summary)
    graph.add_edge("wyckoff_analyst", "bull_researcher")
    graph.add_edge("technical_analyst", "bull_researcher")
    graph.add_edge("fundamental_analyst", "bull_researcher")
    
    graph.add_edge("bull_researcher", "bear_researcher")
    graph.add_edge("bear_researcher", "debate_summarizer")
    
    # Layer 3 → Layer 4 → Layer 5
    graph.add_edge("debate_summarizer", "trader")
    graph.add_edge("trader", "risk_manager")
    graph.add_edge("risk_manager", "portfolio_manager")
    graph.add_edge("portfolio_manager", END)
    
    return graph.compile()


def run_agent_chain(compiled_graph, stock_code, stock_name):
    """执行Agent链路"""
    initial_state = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "market_data": {},
        "indices": {},
        "regime": {},
        "wyckoff_report": "",
        "technical_report": "",
        "fundamental_report": "",
        "bull_argument": "",
        "bear_argument": "",
        "debate_summary": "",
        "trader_decision": {},
        "risk_assessment": "",
        "final_decision": {},
        "trace": [],
        "started_at": datetime.now().isoformat(),
        "completed_at": "",
    }
    
    result = compiled_graph.invoke(initial_state)
    return result
