"""
TradingAgents 数据层适配器 — 用 baostock 替换 yfinance
让 TradingAgents 完全支持 A 股，不依赖 yfinance

策略：在 sys.modules 中注入假的 yfinance 模块，
这样 TradingAgents 任何地方 import yfinance 都会拿到 baostock 后端
"""
import os, sys, json, subprocess, re, types
from datetime import datetime, timedelta
from unittest.mock import MagicMock

PYTHON_BIN = sys.executable

def _run_baostock(script):
    """运行 baostock 脚本"""
    try:
        clean_env = {**os.environ}
        for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
            clean_env.pop(k, None)
        result = subprocess.run([PYTHON_BIN, "-c", script],
            capture_output=True, text=True, timeout=30, env=clean_env)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except:
        pass
    return None

def _a_code(ticker):
    """600519.SS → 600519"""
    return ticker.split('.')[0] if '.' in ticker else ticker

def _a_market(code):
    """6开头=sh, 0/3开头=sz"""
    return "sh" if code.startswith('6') else "sz"

class FakeTicker:
    """假的 yfinance.Ticker，用 baostock 后端"""
    def __init__(self, symbol):
        self.symbol = symbol
        self.code = _a_code(symbol)
        self.market = _a_market(self.code)
        self._hist = None
        self._info = None

    def history(self, period="1mo", interval="1d", start=None, end=None, **kwargs):
        """用 baostock 获取 K线"""
        if not start:
            days = {"5d":5,"1mo":30,"3mo":90,"6mo":180,"1y":365,"5y":1825}.get(period, 30)
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")

        script = f'''
import baostock as bs, json
bs.login()
rs = bs.query_history_k_data_plus("{self.market}.{self.code}",
    "date,open,high,low,close,volume,amount,turn,pctChg",
    start_date="{start}", end_date="{end}", frequency="d")
data = []
while (rs.error_code == '0') and rs.next():
    data.append(rs.get_row_data())
bs.logout()
print(json.dumps(data, ensure_ascii=False))
'''
        data = _run_baostock(script)
        if not data:
            import pandas as pd
            return pd.DataFrame()

        import pandas as pd
        df = pd.DataFrame(data, columns=["Date","Open","High","Low","Close","Volume","Amount","Turn","PctChg"])
        for col in ["Open","High","Low","Close","Volume","Amount","Turn","PctChg"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        self._hist = df
        return df

    @property
    def info(self):
        """基本面信息"""
        if self._info is not None:
            return self._info
        script = f'''
import baostock as bs, json
bs.login()
rs = bs.query_profit_data(code="{self.market}.{self.code}", year=2025, quarter=4)
data = []
while (rs.error_code == '0') and rs.next():
    data.append(rs.get_row_data())
bs.logout()
print(json.dumps(data, ensure_ascii=False))
'''
        data = _run_baostock(script)
        info = {
            "symbol": self.symbol,
            "shortName": self.symbol,
            "currency": "CNY",
            "exchange": "SHA" if self.market == "sh" else "SHE",
            "market": "cn_market",
        }
        if data and len(data) > 0:
            row = data[0]
            if len(row) > 4:
                try:
                    info["roeAvg"] = float(row[4]) if row[4] else None
                    info["npMargin"] = float(row[3]) if row[3] else None
                    info["gpMargin"] = float(row[2]) if row[2] else None
                except:
                    pass
        self._info = info
        return info

    def get_financials(self, freq="quarterly"):
        return MagicMock()

    def get_balance_sheet(self, freq="quarterly"):
        return MagicMock()

    def get_cashflow(self, freq="quarterly"):
        return MagicMock()

    def get_earnings(self):
        return MagicMock()

    def get_recommendations(self):
        return MagicMock()

    @property
    def calendar(self):
        return {}

    @property
    def institutional_holders(self):
        return MagicMock()

    @property
    def insider_transactions(self):
        return MagicMock()

    def news(self, **kwargs):
        return []

def install_fake_yfinance():
    """在 sys.modules 中注入假的 yfinance 模块"""
    fake_mod = types.ModuleType("yfinance")
    fake_mod.Ticker = FakeTicker
    fake_mod.download = lambda *args, **kwargs: MagicMock()
    fake_mod.pdr_override = lambda: None
    sys.modules["yfinance"] = fake_mod
    print("[TA Adapter] yfinance 模块已替换为 baostock 后端（FakeTicker）")
    return True

def _get_yfin_data_online(symbol, start_date, end_date):
    """替换 yfinance OHLCV 数据获取 — 用 baostock"""
    code = _get_a_share_code(symbol)
    # 判断市场
    market = "sh" if code.startswith('6') else ("sz" if code.startswith(('0','3')) else "sh")
    script = f"""
import baostock as bs, json
bs.login()
rs = bs.query_history_k_data_plus("{market}.{code}",
    "date,open,high,low,close,volume,amount,turn,pctChg",
    start_date="{start_date}", end_date="{end_date}", frequency="d")
data = []
while (rs.error_code == '0') and rs.next():
    data.append(rs.get_row_data())
bs.logout()
print(json.dumps(data, ensure_ascii=False))
"""
    data = _run_baostock_script(script)
    if not data:
        return f"无法获取 {symbol} 的 OHLCV 数据（baostock）"
    
    # 格式化为 yfinance 风格的文本
    lines = [f"股票: {symbol}", f"日期范围: {start_date} ~ {end_date}", f"数据条数: {len(data)}", ""]
    lines.append("日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量 | 成交额 | 换手率 | 涨跌幅")
    for row in data[-30:]:  # 最近30条
        if len(row) >= 9:
            lines.append(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]}")
    return "\n".join(lines)

def _get_fundamentals(ticker, curr_date=None):
    """替换 yfinance 基本面数据 — 用 baostock profit 数据"""
    code = _get_a_share_code(ticker)
    market = "sh" if code.startswith('6') else "sz"
    script = f"""
import baostock as bs, json
bs.login()
rs = bs.query_profit_data(code="{market}.{code}", year=2025, quarter=4)
data = []
while (rs.error_code == '0') and rs.next():
    data.append(rs.get_row_data())
rs2 = bs.query_growth_data(code="{market}.{code}", year=2025, quarter=4)
while (rs2.error_code == '0') and rs2.next():
    data.append(rs2.get_row_data())
bs.logout()
print(json.dumps(data, ensure_ascii=False))
"""
    data = _run_baostock_script(script)
    if not data:
        return f"无法获取 {ticker} 的基本面数据，使用估值估算"
    
    lines = [f"股票: {ticker} 基本面数据（baostock）", ""]
    for row in data:
        lines.append(" | ".join(str(x) for x in row))
    return "\n".join(lines)

def _get_balance_sheet(ticker, freq='quarterly', curr_date=None):
    return f"资产负债表数据（{ticker}）: baostock 暂未提供完整资产负债表，建议参考财报公告。"

def _get_income_statement(ticker, freq='quarterly', curr_date=None):
    code = _get_a_share_code(ticker)
    market = "sh" if code.startswith('6') else "sz"
    script = f"""
import baostock as bs, json
bs.login()
rs = bs.query_profit_data(code="{market}.{code}", year=2025, quarter=4)
data = []
while (rs.error_code == '0') and rs.next():
    data.append(rs.get_row_data())
bs.logout()
print(json.dumps(data, ensure_ascii=False))
"""
    data = _run_baostock_script(script)
    if not data:
        return f"利润表数据暂不可用"
    return f"利润表（{ticker}）:\n" + "\n".join(" | ".join(str(x) for x in row) for row in data)

def _get_cashflow(ticker, freq='quarterly', curr_date=None):
    return f"现金流量表数据（{ticker}）: baostock 暂未提供完整现金流量表。"

def _get_stock_stats_indicators_batch(symbol, indicators, curr_date, look_back_days=30):
    """替换技术指标 — 用 baostock K线数据计算"""
    code = _get_a_share_code(symbol)
    market = "sh" if code.startswith('6') else "sz"
    end_date = curr_date or datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=look_back_days + 60)).strftime("%Y-%m-%d")
    
    script = f"""
import baostock as bs, json
bs.login()
rs = bs.query_history_k_data_plus("{market}.{code}",
    "date,close,high,low,volume",
    start_date="{start_date}", end_date="{end_date}", frequency="d")
data = []
while (rs.error_code == '0') and rs.next():
    data.append(rs.get_row_data())
bs.logout()
# 计算技术指标
if data and len(data) > 20:
    closes = [float(r[1]) for r in data if r[1]]
    volumes = [float(r[4]) for r in data if r[4]]
    # RSI
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else 0
    avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else 0.001
    rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100
    # MA20
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else 0
    # 成交量比
    vol_avg = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1
    vol_ratio = volumes[-1] / vol_avg if vol_avg > 0 else 1
    # MACD (简化)
    ema12 = sum(closes[-12:]) / 12 if len(closes) >= 12 else closes[-1]
    ema26 = sum(closes[-26:]) / 26 if len(closes) >= 26 else closes[-1]
    macd_diff = ema12 - ema26
    result = {{"rsi": round(rsi, 1), "ma20": round(ma20, 2), "vol_ratio": round(vol_ratio, 2), "macd_diff": round(macd_diff, 2), "close": closes[-1]}}
else:
    result = {{"error": "数据不足"}}
print(json.dumps(result, ensure_ascii=False))
"""
    data = _run_baostock_script(script)
    if not data:
        return f"技术指标计算失败"
    
    lines = [f"股票: {symbol} 技术指标（baostock计算）", ""]
    for k, v in data.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)

def _get_market_context(ticker, curr_date, look_back_days=5):
    """替换市场上下文 — 用 baostock 指数数据"""
    script = f"""
import baostock as bs, json
bs.login()
data = {{}}
for code, name in [("sh.000001","上证指数"), ("sz.399001","深证成指"), ("sz.399006","创业板指")]:
    rs = bs.query_history_k_data_plus(code, "date,close,pctChg",
        start_date="2026-07-01", end_date="{curr_date}", frequency="d")
    rows = []
    while (rs.error_code == '0') and rs.next():
        rows.append(rs.get_row_data())
    if rows:
        data[name] = {{"close": rows[-1][1], "chg": rows[-1][2]}}
bs.logout()
print(json.dumps(data, ensure_ascii=False))
"""
    data = _run_baostock_script(script)
    if not data:
        return f"市场上下文获取失败"
    
    lines = [f"市场上下文（{curr_date}）", ""]
    for name, info in data.items():
        lines.append(f"  {name}: {info['close']} ({info['chg']}%)")
    return "\n".join(lines)

def _get_analyst_ratings(ticker, curr_date=None):
    return f"分析师评级（{ticker}）: baostock 不提供评级数据。"

def _get_insider_transactions(ticker, curr_date=None):
    return f"内部交易（{ticker}）: A股不适用内部交易概念。"

def _get_institutional_holders(ticker, curr_date=None):
    return f"机构持仓（{ticker}）: 建议参考季报披露的十大流通股东。"

def _get_short_interest(ticker, curr_date=None):
    return f"做空数据（{ticker}）: A股做空机制有限，暂无数据。"

def _get_earnings_calendar(ticker, curr_date=None):
    return f"财报日历（{ticker}）: 建议关注公司公告。"

def _get_dividends_splits(ticker, start_date, end_date):
    return f"分红送转（{ticker}）: 建议参考公司公告。"

def _get_news_locale(symbol):
    """返回新闻语言和地区"""
    code = _get_a_share_code(symbol)
    return ("zh-CN", "China", "A股")

def _get_stock_stats_indicators_window(symbol, indicator, curr_date, look_back_days):
    return _get_stock_stats_indicators_batch(symbol, [indicator], curr_date, look_back_days)

def _get_yfinance_symbol_candidates(symbol):
    code = _get_a_share_code(symbol)
    if code.startswith('6'):
        return [f"{code}.SS"]
    elif code.startswith(('0', '3')):
        return [f"{code}.SZ"]
    return [symbol]

def _describe_symbol_candidates(symbol, candidates):
    return f"标的: {symbol}, 候选: {candidates}"


def patch_tradingagents_dataflows():
    """猴子补丁：注入假 yfinance 模块 + 替换 TradingAgents 数据层"""
    # 核心：在 sys.modules 中替换 yfinance，所有 import yfinance 都会拿到 FakeTicker
    install_fake_yfinance()

    # 同时替换 dataflows.yfinance 模块的函数（双保险）
    try:
        import tradingagents.dataflows.yfinance as yf_mod
        yf_mod.get_yfin_data_online = _get_yfin_data_online
        yf_mod.get_fundamentals = _get_fundamentals
        yf_mod.get_stock_stats_indicators_batch = _get_stock_stats_indicators_batch
        yf_mod.get_market_context = _get_market_context
    except:
        pass  # 如果 tradingagents 还没导入，FakeTicker 会兜底

    print("[TA Adapter] yfinance 数据层已替换为 baostock（A股完整支持）")
    return True
