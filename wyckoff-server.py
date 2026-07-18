#!/usr/bin/env python3
"""Wyckoff 投资工作台 · 后端服务 v3
真实数据驱动：baostock 实时指数 + wyckoff screen 市场扫描 + LLM AI 分析
v3: 全部接口对接真实数据/命令，告别 mock
"""
import json
import copy
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from app.api.quant_workbench import register_quant_workbench
from config import ALLOWED_ORIGINS, PORT, PROJECT_DIR, PYTHON_BIN, WYCKOFF_BIN

app = Flask(
    __name__,
    static_folder=str(PROJECT_DIR / "app" / "static"),
    static_url_path="/static",
    template_folder=str(PROJECT_DIR / "app" / "templates"),
)
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})
register_quant_workbench(app)

# ============================================================
# CONSTANTS
# ============================================================
HOLDINGS_FILE = PROJECT_DIR / ".wyckoff_holdings.json"

# Always resolve configuration relative to this project, regardless of the
# directory from which the server is launched.
load_dotenv(PROJECT_DIR / ".env")

# —— LLM ——
LLM_URL = os.getenv("TOKENHUB_BASE_URL", "https://tokenhub.tencentmaas.com/v1").rstrip("/") + "/chat/completions"
LLM_API_KEY = os.getenv("TOKENHUB_API_KEY") or os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("TOKENHUB_MODEL", "deepseek-v4-pro")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))

# —— Cache ——
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = {"market": 180, "market_fast": 15, "screen_full": 300, "screen_events": 180,
             "stock_catalog": 86400}
_market_refreshing = False

def _cache_get(key):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < entry["ttl"]:
        return entry["data"]
    return None

def _cache_set(key, data, ttl_key="market"):
    _cache[key] = {"data": data, "ts": time.time(), "ttl": CACHE_TTL.get(ttl_key, 60)}

def _empty_market_data(data_source="refreshing"):
    return {
        "timestamp": datetime.now().isoformat(),
        "data_source": data_source,
        "ready": False,
        "indices": {
            "sh": {"name": "上证指数", "value": 0, "change_pct": 0, "amount_yi": 0, "date": ""},
            "sz": {"name": "深证成指", "value": 0, "change_pct": 0, "amount_yi": 0, "date": ""},
            "cy": {"name": "创业板指", "value": 0, "change_pct": 0, "amount_yi": 0, "date": ""},
        },
        "regime": None,
        "hot_sectors": [],
        "wyckoff_scan": None,
        "overview": {},
        "north_money": None,
        "volatility": None,
        "up_count": None,
        "down_count": None,
        "limit_up": None,
        "limit_down": None,
        "provenance": {
            "indices": {"status": "loading", "source": "baostock", "frequency": "1d", "as_of": None},
            "hot_sectors": {"status": "loading", "source": "wyckoff_cli:event_feed", "as_of": None},
            "regime": {"status": "unavailable", "source": None, "as_of": None},
        },
    }

def _kick_market_refresh():
    global _market_refreshing
    with _cache_lock:
        if _market_refreshing:
            return
        _market_refreshing = True

    def _runner():
        global _market_refreshing
        try:
            build_market_data(force=True)
        finally:
            with _cache_lock:
                _market_refreshing = False

    threading.Thread(target=_runner, daemon=True).start()

# —— Async tasks ——
_async_tasks = {}
tasks = {}  # alias for quant/agent endpoints

# ============================================================
# HELPERS
# ============================================================
def run_wyckoff(*args, timeout=120):
    """运行 wyckoff CLI 命令，返回 (stdout, stderr, returncode)"""
    try:
        result = subprocess.run(
            [WYCKOFF_BIN] + list(args),
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            cwd=str(PROJECT_DIR)
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return None, "命令执行超时", -1
    except FileNotFoundError:
        return None, f"Wyckoff CLI 未找到: {WYCKOFF_BIN}", -2
    except Exception as e:
        return None, str(e), -3

def run_python(code, timeout=30):
    """运行一段 Python 代码，使用项目 venv"""
    try:
        result = subprocess.run(
            [PYTHON_BIN, "-c", code],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        if result.returncode != 0:
            return None, result.stderr.strip() or result.stdout.strip()
        return result.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return None, "Python 代码执行超时"
    except Exception as e:
        return None, str(e)

def call_llm(messages, max_tokens=2000):
    """调用 TokenHub LLM（绕过系统代理）"""
    if not LLM_API_KEY:
        return None, "未配置 TOKENHUB_API_KEY/OPENAI_API_KEY"
    try:
        import urllib.request, urllib.error
        payload = json.dumps({
            "model": LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }).encode("utf-8")
        req = urllib.request.Request(LLM_URL, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        })
        # 创建不使用代理的 opener（系统代理会拦截 TokenHub 请求）
        no_proxy = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(no_proxy)
        with opener.open(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            msg = body["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if not content:
                return None, "模型未返回最终回答，请稍后重试"
            return content, None
    except Exception as e:
        return None, str(e)

# ---- 持仓文件 ----
def load_holdings():
    if HOLDINGS_FILE.exists():
        try:
            data = json.loads(HOLDINGS_FILE.read_text())
            return data if isinstance(data, list) else None
        except (OSError, json.JSONDecodeError):
            pass
    return None

def save_holdings(holdings):
    HOLDINGS_FILE.write_text(json.dumps(holdings, ensure_ascii=False, indent=2))


def _looks_like_legacy_demo(holdings):
    """识别旧版本曾写入用户文件的内置 7 条演示持仓。"""
    legacy_codes = {"603019", "300750", "600519", "002415", "300059", "600276", "601318"}
    return isinstance(holdings, list) and len(holdings) == 7 and {h.get("code") for h in holdings} == legacy_codes


def get_holdings_with_defaults():
    """只返回用户真实录入的持仓，旧演示文件永不进入业务数据。"""
    user = load_holdings()
    if user is not None and not _looks_like_legacy_demo(user):
        return user, True
    return [], False

# ============================================================
# DATA PROVIDERS
# ============================================================

def fetch_baostock_indices():
    """用 baostock 获取真实三大指数"""
    # baostock 会往 stdout 输出 "login success!" 等消息，需要过滤
    script = '''
import baostock as bs, json, sys
from datetime import datetime, timedelta
import io
# 吞掉 baostock 的 login/logout 消息
old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
    bs.login()
    idx_codes = {"sh":"sh.000001","sz":"sz.399001","cy":"sz.399006"}
    result = {}
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    for key, code in idx_codes.items():
        rs = bs.query_history_k_data_plus(code, "date,close,pctChg,volume,amount",
            start_date=start_date, end_date=end_date, frequency="d")
        rows = []
        while (rs.error_code == "0") and rs.next():
            rows.append(rs.get_row_data())
        if rows:
            latest = rows[-1]
            prev = rows[-2] if len(rows) >= 2 else latest
            result[key] = {
                "value": round(float(latest[1]), 2),
                "change_pct": round(float(latest[2]), 2),
                "volume": int(float(latest[3])),
                "amount_yi": round(int(float(latest[4])) / 1e8, 2),
                "prev_close": round(float(prev[1]), 2) if prev != latest else None,
                "date": latest[0],
            }
    bs.logout()
finally:
    sys.stdout = old_stdout
print(json.dumps(result, ensure_ascii=False))
'''
    script_path = Path("/tmp/_wyckoff_baostock.py")
    script_path.write_text(script)
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(script_path)],
            capture_output=True, text=True, timeout=45,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return None
    return None


def _to_baostock_code(code, market=""):
    code = str(code or "").strip().lower().replace("sh.", "").replace("sz.", "")
    if not code.isdigit() or len(code) != 6:
        return None
    market = str(market or "").upper()
    if market == "SH" or code.startswith(("5", "6", "9")):
        return f"sh.{code}"
    if market in {"SZ", "CY"} or code.startswith(("0", "1", "2", "3")):
        return f"sz.{code}"
    return None


def _stock_market(raw_code):
    raw_code = str(raw_code or "").lower()
    code = raw_code.split(".")[-1]
    if raw_code.startswith("sh.") and code.startswith("68"):
        return "KC", "科创板"
    if raw_code.startswith("sh."):
        return "SH", "上海主板"
    if raw_code.startswith("sz.") and code.startswith("30"):
        return "CY", "创业板"
    if raw_code.startswith("sz."):
        return "SZ", "深圳主板"
    return "", ""


def _normalize_stock_query(value):
    value = str(value or "").strip().lower().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return value.replace("sh.", "").replace("sz.", "").replace("股票", "").replace(" ", "")


def search_stock_catalog(query, limit=8):
    normalized = _normalize_stock_query(query)
    if not normalized:
        return []
    cache_key = "stock_search_" + hashlib.sha1(normalized.encode()).hexdigest()[:16]
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[:limit]

    if normalized.isdigit():
        if len(normalized) != 6:
            return []
        if normalized.startswith(("6", "9")):
            query_mode, query_value = "code", f"sh.{normalized}"
        elif normalized.startswith(("0", "3")):
            query_mode, query_value = "code", f"sz.{normalized}"
        else:
            return []
    else:
        query_mode, query_value = "name", normalized

    script = f'''
import baostock as bs, io, json, sys
mode = {json.dumps(query_mode)}
value = {json.dumps(query_value, ensure_ascii=False)}
old_stdout = sys.stdout
sys.stdout = io.StringIO()
rows = []
try:
    bs.login()
    rs = bs.query_stock_basic(code=value) if mode == "code" else bs.query_stock_basic(code_name=value)
    while (rs.error_code == "0") and rs.next():
        raw_code, name, _ipo, _out, stock_type, status = rs.get_row_data()
        if stock_type == "1" and status == "1" and raw_code.startswith(("sh.60", "sh.68", "sz.00", "sz.30")):
            rows.append({{"raw_code": raw_code, "code": raw_code.split(".")[-1], "name": name}})
    bs.logout()
finally:
    sys.stdout = old_stdout
print(json.dumps(rows, ensure_ascii=False))
'''
    stdout, error = run_python(script, timeout=12)
    if error or not stdout:
        return None
    try:
        rows = json.loads(stdout)
    except json.JSONDecodeError:
        return None

    ranked = []
    for row in rows:
        market, market_label = _stock_market(row.get("raw_code"))
        item = {
            "code": row.get("code"), "name": row.get("name"),
            "market": market, "market_label": market_label,
            "source": "baostock_stock_basic",
        }
        code = item["code"].lower()
        name = item["name"].lower().replace(" ", "")
        if code == normalized:
            rank = 0
        elif name == normalized:
            rank = 1
        elif code.startswith(normalized):
            rank = 2
        elif name.startswith(normalized):
            rank = 3
        elif normalized in name:
            rank = 4
        else:
            continue
        ranked.append((rank, len(name), code, item))
    ranked.sort(key=lambda entry: entry[:3])
    results = [entry[3] for entry in ranked]
    _cache_set(cache_key, results, "stock_catalog")
    return results[:limit]


def fetch_latest_closes(holdings):
    """批量读取用户持仓的最新真实日线收盘价。"""
    pairs = []
    for holding in holdings:
        raw_code = str(holding.get("code") or "").strip()
        bs_code = _to_baostock_code(raw_code, holding.get("market"))
        if raw_code and bs_code:
            pairs.append({"code": raw_code, "bs_code": bs_code})
    if not pairs:
        return {}

    cache_key = "quotes_" + hashlib.sha1(json.dumps(pairs, sort_keys=True).encode()).hexdigest()[:12]
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    script = f'''
import baostock as bs, io, json, sys
from datetime import datetime, timedelta
pairs = {json.dumps(pairs, ensure_ascii=False)}
old_stdout = sys.stdout
sys.stdout = io.StringIO()
result = {{}}
try:
    bs.login()
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    for item in pairs:
        rs = bs.query_history_k_data_plus(
            item["bs_code"], "date,close,pctChg,volume,amount,tradestatus",
            start_date=start_date, end_date=end_date, frequency="d", adjustflag="3"
        )
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        rows = [row for row in rows if row[1] and row[5] == "1"]
        if rows:
            latest = rows[-1]
            result[item["code"]] = {{
                "close": round(float(latest[1]), 2),
                "change_pct": round(float(latest[2]), 2),
                "volume": int(float(latest[3] or 0)),
                "amount_yi": round(float(latest[4] or 0) / 1e8, 2),
                "date": latest[0],
                "source": "baostock",
                "frequency": "1d"
            }}
    bs.logout()
finally:
    sys.stdout = old_stdout
print(json.dumps(result, ensure_ascii=False))
'''
    try:
        result = subprocess.run(
            [PYTHON_BIN, "-c", script], capture_output=True, text=True, timeout=45,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        quotes = json.loads(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        quotes = {}
    _cache_set(cache_key, quotes, "market")
    return quotes


def get_live_holdings():
    """用户成本和数量来自本地记录，现价只接受 Baostock 最新日线。"""
    raw_holdings, is_real = get_holdings_with_defaults()
    quotes = fetch_latest_closes(raw_holdings)
    resolved = []
    for raw in raw_holdings:
        holding = dict(raw)
        quote = quotes.get(str(holding.get("code") or ""))
        cost = float(holding.get("cost") or 0)
        shares = int(holding.get("shares") or 0)
        if quote:
            price = quote["close"]
            holding.update({
                "price": price,
                "price_date": quote["date"],
                "price_source": quote["source"],
                "price_frequency": quote["frequency"],
                "price_status": "ok",
                "daily_change_pct": quote["change_pct"],
                "pnl": round((price - cost) * shares, 2),
                "pnl_pct": round((price - cost) / cost * 100, 2) if cost > 0 else None,
                "market_value": round(price * shares, 2),
            })
        else:
            holding.update({
                "price": None, "price_date": None, "price_source": "baostock",
                "price_frequency": "1d", "price_status": "unavailable",
                "daily_change_pct": None, "pnl": None, "pnl_pct": None, "market_value": None,
            })
        resolved.append(holding)
    return resolved, is_real

def fetch_market_overview():
    """用 baostock 获取市场广度数据"""
    code = '''
import baostock as bs, json
bs.login()
try:
    # 沪深 A 股涨跌统计
    rs = bs.query_stock_basic()
    total = 0
    while rs.next(): total += 1
    # 日 K 涨跌概览：最近一天
    from datetime import datetime, timedelta
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    up = down = flat = 0
    total_vol = 0
    count = 0
    rs2 = bs.query_history_k_data_plus("sh.000001", "date,close,volume,amount",
        start_date=start, end_date=end, frequency="d")
    rows = []
    while rs2.next(): rows.append(rs2.get_row_data())
    if rows:
        latest = rows[-1]
        result = {
            "total_stocks": total,
            "sh_close": round(float(latest[1]), 2),
            "sh_volume": int(float(latest[2])),
            "sh_amount_yi": round(int(float(latest[3])) / 1e8, 2),
            "date": latest[0],
        }
    else:
        result = {"total_stocks": total, "error": "no_k_data"}
    print(json.dumps(result, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"error": str(e)}, ensure_ascii=False))
bs.logout()
'''
    stdout, err = run_python(code, timeout=25)
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except:
        return {}

def fetch_hot_sectors_from_screen():
    """从 wyckoff screen 的 stderr 里解析同花顺热点板块"""
    stdout, stderr, rc = run_wyckoff("screen", "--limit", "3", "--no-financial-metrics", timeout=60)
    sectors = []
    # 解析 "同花顺事件主线" 行
    if stdout:
        for line in (stdout + "\n" + (stderr or "")).split("\n"):
            # 格式: 商业航天(+7.4%, 热度91.3万, 涨停14)
            import re
            matches = re.findall(r'([\u4e00-\u9fa5\w]+)\(([+\-][\d.]+)%,?\s*热度([\d.]+)万?,?\s*涨停(\d+)\)', line)
            for m in matches:
                sectors.append({
                    "name": m[0],
                    "change_pct": float(m[1]),
                    "heat": float(m[2]),
                    "limit_up": int(m[3]),
                })
    # 如果没有解析到，用 baostock 实时板块
    if not sectors:
        code2 = '''
import baostock as bs, json
bs.login()
try:
    rs = bs.query_stock_industry()
    inds = {}
    while rs.next():
        row = rs.get_row_data()
        ind = row[2]
        inds[ind] = inds.get(ind, 0) + 1
    # top 热门
    top = sorted(inds.items(), key=lambda x: -x[1])[:8]
    result = [{"name": t[0], "stocks": t[1], "heat": round(t[1]/10, 1)} for t in top]
    print(json.dumps(result, ensure_ascii=False))
except Exception as e:
    print(json.dumps([], ensure_ascii=False))
bs.logout()
'''
        stdout2, err2 = run_python(code2, timeout=25)
        if stdout2:
            try:
                sectors = json.loads(stdout2)
            except:
                pass
    return sectors

def parse_screen_regime(stdout, stderr):
    """从真实 screen 输出提取派生市场状态，不制造温度分数。"""
    combined = (stdout or "") + "\n" + (stderr or "")
    import re
    match = re.search(r"regime=([A-Z_]+)", combined)
    regime = match.group(1) if match else None
    labels = {
        "RISK_OFF": "风险偏好偏弱", "RISK_ON": "风险偏好偏强",
        "BEAR_REBOUND": "熊市反抽", "NEUTRAL": "中性",
    }
    date_match = re.search(r"数据:\s*(\d{4}-\d{2}-\d{2})", combined)
    sample_match = re.search(r"breadth=\{[^}]*'sample_size':\s*(\d+)", combined)
    score_match = re.search(r"money_flow=\{[^}]*'score':\s*([-\d.]+)", combined)
    rotation = {}
    for line in combined.split("\n"):
        if "板块轮动温度计" in line:
            mm = re.findall(r'(分歧|健康|高潮|退潮|中性)=(\d+)', line)
            rotation = {m[0]: int(m[1]) for m in mm}
    return {
        "regime": regime,
        "regime_label": labels.get(regime, regime or "暂无"),
        "money_flow_score": float(score_match.group(1)) if score_match else None,
        "sample_size": int(sample_match.group(1)) if sample_match else None,
        "as_of": date_match.group(1) if date_match else None,
        "source": "wyckoff_cli",
        "is_derived": True,
        "rotation": rotation,
    }

def fetch_wyckoff_scan():
    """尚无可靠的全市场逐股阶段统计，明确返回不可用。"""
    return None

# ============================================================
# CACHED DATA BUILDERS
# ============================================================

def build_market_data(force=False):
    """构建完整市场数据（不阻塞：baostock 后台跑，screen 跑一次复用）"""
    cached = _cache_get("market_data")
    if cached and not force:
        return cached
    stale_entry = _cache.get("market_data")
    stale_data = copy.deepcopy(stale_entry["data"]) if stale_entry else None
    if not force:
        if stale_data and stale_data.get("ready"):
            stale_data["refreshing"] = True
            _cache_set("market_data", stale_data, "market_fast")
            _kick_market_refresh()
            return stale_data
        data = _empty_market_data()
        _cache_set("market_data", data, "market_fast")
        _kick_market_refresh()
        return data

    # 指数是首屏信息，先在几秒内写入缓存；耗时较长的全市场扫描随后补充。
    indices = fetch_baostock_indices() or {}
    if indices:
        data = _empty_market_data("baostock")
    elif stale_data and stale_data.get("ready"):
        data = stale_data
        data["data_source"] = "last_known"
        data["timestamp"] = datetime.now().isoformat()
    else:
        data = _empty_market_data("market_unavailable")
    data.setdefault("provenance", copy.deepcopy(_empty_market_data()["provenance"]))
    for key in ["sh", "sz", "cy"]:
        if indices.get(key):
            data["indices"][key].update({
                "value": indices[key].get("value", 0),
                "change_pct": indices[key].get("change_pct", 0),
                "amount_yi": indices[key].get("amount_yi", 0),
                "date": indices[key].get("date", ""),
            })
    index_dates = [item.get("date") for item in indices.values() if item.get("date")]
    data["provenance"]["indices"] = {
        "status": "ok" if indices else "unavailable",
        "source": "baostock", "frequency": "1d",
        "as_of": max(index_dates) if index_dates else None,
    }
    data["ready"] = bool(indices) or data.get("ready", False)
    data["refreshing"] = True
    _cache_set("market_data", data, "market" if indices else "market_fast")

    # 一次 screen 调用：同时拿热门板块 + 市场 regime
    hot_sectors = []
    regime_info = None
    screen_as_of = None
    screen_success = False
    try:
        # screen 需要 45+ 秒（首次冷启动），给足 60 秒
        stdout, stderr, rc = run_wyckoff("screen", "--limit", "2", "--no-financial-metrics", timeout=70)
        combined = (stdout or "") + "\n" + (stderr or "")
        # 解析热门板块
        import re
        seen_names = set()
        for line in combined.split("\n"):
            for m in re.findall(r'([\u4e00-\u9fa5\w]+)\(([+\-][\d.]+)%,?\s*热度([\d.]+)万?,?\s*涨停(\d+)\)', line):
                if m[0] not in seen_names:
                    seen_names.add(m[0])
                    hot_sectors.append({
                        "name": m[0], "change_pct": float(m[1]), "heat": float(m[2]),
                        "limit_up": int(m[3]), "source": "wyckoff_cli:event_feed"
                    })
        regime_info = parse_screen_regime(stdout, stderr)
        screen_as_of = regime_info.get("as_of") if regime_info else None
        screen_success = bool(hot_sectors or (regime_info and regime_info.get("regime")))
    except Exception:
        if stale_data:
            hot_sectors = stale_data.get("hot_sectors") or []
            regime_info = stale_data.get("regime")

    had_last_known = bool(data.get("ready"))
    data["provenance"]["hot_sectors"] = {
        "status": "ok" if hot_sectors else "unavailable",
        "source": "wyckoff_cli:event_feed", "as_of": screen_as_of,
    }
    data["provenance"]["regime"] = {
        "status": "ok" if regime_info and regime_info.get("regime") else "unavailable",
        "source": "wyckoff_cli" if regime_info else None,
        "as_of": screen_as_of,
        "is_derived": True,
    }

    data.update({
        "ready": bool(indices) or screen_success or had_last_known,
        "data_source": "+".join(source for source, available in (("baostock", bool(indices)), ("wyckoff_screen", screen_success)) if available) or ("last_known" if had_last_known else "market_unavailable"),
        "regime": regime_info,
        "hot_sectors": hot_sectors,
        "wyckoff_scan": None,
        "refreshing": False,
    })
    _cache_set("market_data", data, "market" if indices or screen_success else "market_fast")
    return data

# ============================================================
# API ROUTES
# ============================================================

# ——— 系统状态 ———
@app.route("/api/status")
def api_status():
    config_path = Path.home() / ".wyckoff" / "wyckoff.json"
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except:
            pass
    models = config.get("models", {})
    default_model = config.get("default_model", "deepseek")
    return jsonify({
        "ok": True, "version": "0.9.155",
        "default_model": default_model,
        "models_count": len(models),
        "llm_configured": bool(LLM_API_KEY),
        "llm_model": LLM_MODEL if LLM_API_KEY else None,
        "llm_provider": "TokenHub" if LLM_API_KEY else None,
        "wyckoff_cli_available": bool(WYCKOFF_BIN) and Path(WYCKOFF_BIN).exists(),
        "data_dir": str(Path.home() / ".wyckoff"),
        "timestamp": datetime.now().isoformat(),
    })

# ——— 市场数据（真实） ———
@app.route("/api/market")
def api_market():
    data = build_market_data()
    return jsonify(data)

# ——— 持仓 ———
@app.route("/api/portfolio")
def api_portfolio():
    holdings, _ = get_live_holdings()
    return jsonify(holdings)

@app.route("/api/portfolio/summary")
def api_portfolio_summary():
    holdings, is_real = get_live_holdings()
    priced = [h for h in holdings if h.get("price_status") == "ok"]
    total_value = sum(h["market_value"] for h in priced)
    total_pnl = sum(h["pnl"] for h in priced)
    total_cost = sum(float(h.get("cost") or 0) * int(h.get("shares") or 0) for h in priced)
    sc = {}
    for h in holdings:
        s = h.get("strategy", "hold")
        sc[s] = sc.get(s, 0) + 1
    return jsonify({
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else None,
        "positions": len(holdings),
        "priced_positions": len(priced),
        "quote_coverage": round(len(priced) / len(holdings) * 100, 1) if holdings else 100,
        "strategy_counts": sc,
        "profit_count": sum(1 for h in priced if h["pnl"] > 0),
        "loss_count": sum(1 for h in priced if h["pnl"] < 0),
        "is_real_data": is_real,
        "price_source": "baostock",
        "price_frequency": "1d",
    })

# ——— 信号 & 推荐操作 ———
@app.route("/api/signals")
def api_signals():
    """从真实持仓推导信号"""
    holdings, is_real = get_live_holdings()
    signal_label = "用户持仓记录"
    signals = []
    for h in holdings:
        phase = h.get("phase", "")
        name = h.get("name", h.get("code", ""))
        ks = h.get("key_signals", [])
        if phase == "markup":
            signals.append({
                "title": f"{name} · SOS 触发",
                "time": signal_label, "type": "entry",
                "desc": f"Markup 启动，{'，'.join(ks) if ks else '量能配合突破'}。",
                "source": "user_holding",
            })
        elif phase == "spring":
            signals.append({
                "title": f"{name} · Spring 完成",
                "time": signal_label, "type": "confirmed",
                "desc": f"回测支撑成功，{'，'.join(ks) if ks else '等待放量确认'}。",
                "source": "user_holding",
            })
        elif phase == "accum":
            signals.append({
                "title": f"{name} · ST 测试中",
                "time": signal_label, "type": "watching",
                "desc": f"Accumulation 阶段，{'，'.join(ks) if ks else '量价健康'}。",
                "source": "user_holding",
            })
        elif phase == "breakdown":
            signals.append({
                "title": f"{name} · 破位告警",
                "time": signal_label, "type": "alert",
                "desc": f"趋势破位，止损线已触发。",
                "source": "user_holding",
            })
    # 补充 screen 事件主线
    market = build_market_data()
    hot = market.get("hot_sectors", [])[:3]
    for s in hot:
        signals.append({
            "title": f"热点主线 · {s.get('name', '')} {s.get('change_pct', 0):+}%",
            "time": "市场扫描",
            "type": "watching",
            "desc": f"涨停 {s.get('limit_up', '?')} 家，热度 {s.get('heat', '?')} 万",
            "source": "wyckoff_cli:event_feed",
        })
    return jsonify(signals[:8])

@app.route("/api/actions")
def api_actions():
    """从真实持仓推导操作建议"""
    holdings, is_real = get_holdings_with_defaults()
    actions = []
    for h in holdings:
        s = h.get("strategy", "hold")
        name = h.get("name", h.get("code", ""))
        if s == "attack":
            actions.append({"title": f"{name} · ATTACK", "type": "attack", "desc": "SOS 信号确认 · 建议加仓"})
        elif s == "trim":
            actions.append({"title": f"{name} · TRIM", "type": "trim", "desc": "派发区间 · 建议减仓"})
        elif s == "exit":
            actions.append({"title": f"{name} · EXIT", "type": "exit", "desc": "趋势破位 · 止损离场"})
        elif s == "probe":
            actions.append({"title": f"{name} · PROBE", "type": "probe", "desc": "试探建仓 · 单票 ≤ 10%"})
        else:
            actions.append({"title": f"{name} · HOLD", "type": "hold", "desc": "持有观察 · 等待信号"})
    return jsonify(actions[:8])

# ——— 策略详情 ———
@app.route("/api/legacy/strategy-matrix")
def api_strategies():
    holdings, _ = get_live_holdings()
    def live_stats(strategy_id):
        group = [h for h in holdings if h.get("strategy", "hold") == strategy_id]
        priced = [h for h in group if h.get("price_status") == "ok" and h.get("pnl_pct") is not None]
        avg_pnl = round(sum(h["pnl_pct"] for h in priced) / len(priced), 1) if priced else None
        return {"count": len(group), "priced_count": len(priced), "avg_pnl": avg_pnl}

    strategies = [
        {"id": "exit", "label": "EXIT 退出", "icon": "door", "phase": "逻辑破产",
         "criteria": ["Spring 后无法突破阻力", "成交量持续萎缩 + 趋势破位", "基本面逻辑被破坏", "持仓亏损超过 8% 硬止损线"],
         "stats": live_stats("exit")},
        {"id": "trim", "label": "TRIM 减仓", "icon": "scissors", "phase": "派发区间",
         "criteria": ["Markup 中后期 · 进入派发区间", "成交量异常放大 + 长上影线", "RS 转弱 · 行业相对强度下滑", "突破阻力后回踩不破减仓"],
         "stats": live_stats("trim")},
        {"id": "hold", "label": "HOLD 持有", "icon": "shield", "phase": "Accumulation / Spring",
         "criteria": ["Accumulation 中段 · 量价健康", "ST 支撑位未破 · Cause 充分", "无明确买卖信号 · 等待突破"],
         "stats": live_stats("hold")},
        {"id": "probe", "label": "PROBE 试探", "icon": "search", "phase": "Spring 测试中",
         "criteria": ["Spring 完成后回测不破", "行业出现主线 · RS 走强信号", "首次建仓 · 单票 ≤ 10% 资金", "设置 -8% 硬止损 · 严格执行"],
         "stats": live_stats("probe")},
        {"id": "attack", "label": "ATTACK 攻击", "icon": "rocket", "phase": "Markup 启动",
         "criteria": ["Markup 启动信号 · SOS + JAC", "突破关键阻力 · 量能配合", "市场水温 RISK_ON · 顺势而为", "单票上限 20% · 行业分散 ≤ 5"],
         "stats": live_stats("attack")},
    ]
    return jsonify(strategies)

# ——— AI 分析（真实 LLM） ———
@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json() or {}
    focus = data.get("focus", "all")

    holdings, is_real = get_live_holdings()
    if not holdings:
        return jsonify({"ok": False, "error": "请先添加真实持仓"}), 400
    market = build_market_data()

    # 构建持仓摘要
    holding_lines = []
    for h in holdings:
        s = h.get("strategy", "hold")
        emoji = {"attack": "🚀", "trim": "✂️", "hold": "🛡️", "probe": "🔎", "exit": "🚪"}.get(s, "📊")
        price_text = f"¥{h['price']}（{h['price_date']} 日线收盘）" if h.get("price_status") == "ok" else "行情暂不可用"
        pnl_text = f"{h['pnl_pct']:+.1f}%" if h.get("pnl_pct") is not None else "不可计算"
        holding_lines.append(
            f"- {emoji} {h.get('name', '?')}（{h.get('code', '?')}）| {h.get('phase_label', '?')} | "
            f"成本 ¥{h.get('cost', 0)} → 最新价 {price_text} | "
            f"盈亏 {pnl_text} | 用户记录策略: {s.upper()} | "
            f"止损 ¥{h.get('stop_loss', '?')} | 信号: {', '.join(h.get('key_signals', []))}"
        )

    regime = market.get("regime")
    regime_label = regime.get("regime_label", "暂无") if isinstance(regime, dict) else "暂无"
    indices = market.get("indices", {})
    sh_idx = indices.get("sh", {})

    prompt = f"""你是威科夫量价分析专家「老布偶猫」，帮助我管理 A 股投资组合。

## 当前市场环境
- 市场状态: {regime_label}
- 上证指数: {sh_idx.get('value', 'N/A')}（{sh_idx.get('change_pct', 0):+.2f}%）
- 热门板块: {', '.join(s.get('name', '') for s in market.get('hot_sectors', [])[:5])}
- 指数来源: baostock 日线，日期 {sh_idx.get('date') or '暂无'}

## 我的持仓
{chr(10).join(holding_lines)}

## 任务
请用以下 JSON 格式输出分析结果（不要额外文字）:
{{
  "diagnosis": "组合整体诊断，200字以内，包含威科夫阶段分布评价和操作建议",
  "risk": "风险提示，150字以内，包含大盘风险、仓位建议、关键风控要点",
  "adjustments": [
    {{"stock": "股票名", "action": "加仓/减仓/清仓/持有/试探建仓", "reason": "具体威科夫分析依据"}}
  ],
  "score": 评分0-100的整数,
  "main_action": "ATTACK/HOLD/TRIM/DEFEND"
}}"""

    # 尝试调 LLM
    llm_output, llm_err = call_llm([
        {"role": "system", "content": "你是威科夫量价分析专家「老布偶猫」🐱。只用 JSON 格式回复，不要额外解释。"},
        {"role": "user", "content": prompt},
    ], max_tokens=3000)

    if llm_output and not llm_err:
        try:
            # 尝试提取 JSON（LLM 可能在前后加了文字）
            import re
            json_match = re.search(r'\{[\s\S]*\}', llm_output)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return jsonify({
                    "diagnosis": {"content": parsed.get("diagnosis", "分析完成")},
                    "risk": {"content": parsed.get("risk", "请注意市场风险")},
                    "adjustments": {"title": "调仓建议", "items": parsed.get("adjustments", [])},
                    "score": parsed.get("score"),
                    "main_action": parsed.get("main_action"),
                    "generated_at": datetime.now().isoformat(),
                    "model": LLM_MODEL,
                    "source": "llm",
                })
        except (json.JSONDecodeError, TypeError):
            llm_err = "模型返回格式无法解析"

    return jsonify({
        "ok": False,
        "error": llm_err or "AI 服务未配置或暂不可用",
        "source": "unavailable",
        "generated_at": datetime.now().isoformat(),
    }), 503

# ——— 全市场漏斗筛选（异步） ———
@app.route("/api/screen", methods=["POST"])
def api_screen():
    """异步执行 wyckoff screen"""
    data = request.get_json() or {}
    limit = int(data.get("limit", 10))
    board = data.get("board", "all")

    task_id = str(uuid.uuid4())[:8]
    _async_tasks[task_id] = {"status": "running", "created": time.time(), "result": None}

    def _run_screen():
        try:
            args = ["screen", "--limit", str(limit), "--no-financial-metrics"]
            if board != "all":
                args.extend(["--board", board])
            stdout, stderr, rc = run_wyckoff(*args, timeout=300)
            # 解析关键信息
            regime = parse_screen_regime(stdout or "", stderr or "")
            events = []
            import re
            combined = (stdout or "") + "\n" + (stderr or "")
            for line in combined.split("\n"):
                ms = re.findall(r'([\u4e00-\u9fa5\w]+)\(([+\-][\d.]+)%,?\s*热度([\d.]+)万?,?\s*涨停(\d+)\)', line)
                for m in ms:
                    events.append({"name": m[0], "change_pct": float(m[1]), "heat": float(m[2]), "limit_up": int(m[3])})
            # 找筛选结果
            candidates = []
            for line in combined.split("\n"):
                if "最终选入" in line:
                    import re
                    numbers = re.findall(r'(\w+)=(\d+)', line)
                    for n in numbers:
                        candidates.append({"group": n[0], "count": int(n[1])})
            _async_tasks[task_id] = {
                "status": "done",
                "created": _async_tasks[task_id]["created"],
                "result": {
                    "regime": regime,
                    "events": events[:10],
                    "candidates": candidates,
                    "raw_summary": (stdout or "")[-1500:],
                }
            }
        except Exception as e:
            _async_tasks[task_id] = {
                "status": "error",
                "created": _async_tasks[task_id]["created"],
                "result": {"error": str(e)}
            }

    threading.Thread(target=_run_screen, daemon=True).start()
    return jsonify({"task_id": task_id, "status": "running"})

@app.route("/api/screen/<task_id>")
def api_screen_result(task_id):
    task = _async_tasks.get(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)

@app.route("/api/screen/events")
def api_screen_events():
    """获取最近一次 screen 的事件主线（缓存 3 分钟）"""
    cached = _cache_get("screen_events")
    if cached:
        return jsonify(cached)
    # 跑一次快速 screen
    events = fetch_hot_sectors_from_screen()
    result = {"events": events, "timestamp": datetime.now().isoformat()}
    _cache_set("screen_events", result, "screen_events")
    return jsonify(result)

# ——— 回测 ———
@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """异步执行 wyckoff backtest"""
    data = request.get_json() or {}
    hold_days = int(data.get("hold_days", 10))
    months = int(data.get("months", 12))
    top_n = int(data.get("top_n", 4))

    task_id = str(uuid.uuid4())[:8]
    _async_tasks[task_id] = {"status": "running", "created": time.time(), "result": None}

    def _run_bt():
        try:
            stdout, stderr, rc = run_wyckoff(
                "backtest", "--hold-days", str(hold_days),
                "--months", str(months), "--top-n", str(top_n),
                timeout=300
            )
            _async_tasks[task_id] = {
                "status": "done",
                "created": _async_tasks[task_id]["created"],
                "result": {
                    "output": (stdout or "")[-2000:],
                    "stderr": (stderr or "")[-500:],
                }
            }
        except Exception as e:
            _async_tasks[task_id] = {
                "status": "error",
                "created": _async_tasks[task_id]["created"],
                "result": {"error": str(e)}
            }

    threading.Thread(target=_run_bt, daemon=True).start()
    return jsonify({"task_id": task_id, "status": "running"})

@app.route("/api/backtest/<task_id>")
def api_backtest_result(task_id):
    task = _async_tasks.get(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)

# ——— AI 研报 ———
@app.route("/api/report", methods=["POST"])
def api_report():
    """异步生成 AI 研报"""
    data = request.get_json() or {}
    codes = data.get("codes", "")
    focus = data.get("focus", "all")

    task_id = str(uuid.uuid4())[:8]
    _async_tasks[task_id] = {"status": "running", "created": time.time(), "result": None}

    def _run_report():
        try:
            if codes:
                stdout, stderr, rc = run_wyckoff("report", codes, timeout=120)
                content = stdout or ""
            else:
                # 用 LLM 生成研报
                holdings, is_real = get_holdings_with_defaults()
                market = build_market_data()
                holding_text = "\n".join(
                    f"- {h['name']}（{h['code']}）: {h.get('phase_label','?')}，盈亏 {h.get('pnl_pct',0):+.1f}%，策略 {h.get('strategy','?').upper()}"
                    for h in holdings
                )
                prompt = f"作为威科夫量价分析专家，请为以下投资组合生成一份简短的 AI 研报（300字以内），包含：市场环境、组合诊断、个股点评。\n\n市场：上证 {market['indices']['sh']['value']}\n持仓：\n{holding_text}"
                content, llm_err = call_llm([
                    {"role": "system", "content": "你是威科夫量价分析专家「老布偶猫」，生成简洁专业的投资研报。"},
                    {"role": "user", "content": prompt},
                ], max_tokens=600)
                if llm_err:
                    content = f"研报生成失败：{llm_err}"

            _async_tasks[task_id] = {
                "status": "done",
                "created": _async_tasks[task_id]["created"],
                "result": {
                    "title": f"威科夫研报 · {datetime.now().strftime('%Y-%m-%d')}",
                    "content": content,
                }
            }
        except Exception as e:
            _async_tasks[task_id] = {
                "status": "error",
                "created": _async_tasks[task_id]["created"],
                "result": {"error": str(e)}
            }

    threading.Thread(target=_run_report, daemon=True).start()
    return jsonify({"task_id": task_id, "status": "running"})

@app.route("/api/report/<task_id>")
def api_report_result(task_id):
    task = _async_tasks.get(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)

# ——— 股票搜索与持仓 CRUD ———
@app.route("/api/stocks/search")
def api_search_stocks():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": [], "source": "baostock_stock_basic"})
    try:
        limit = max(1, min(20, int(request.args.get("limit", 8))))
    except ValueError:
        limit = 8
    results = search_stock_catalog(query, limit)
    if results is None:
        return jsonify({"error": "股票列表数据源暂时不可用，请稍后重试"}), 503
    return jsonify({
        "results": results,
        "source": "baostock_stock_basic",
        "as_of": datetime.now().strftime("%Y-%m-%d"),
    })


@app.route("/api/portfolio/add", methods=["POST"])
def api_add_holding():
    data = request.get_json() or {}
    code = (data.get("code") or "").strip().upper()

    errors = []
    if not code: errors.append("请先搜索并选择一只股票")
    if not data.get("cost"): errors.append("成本价不能为空")
    if not data.get("shares"): errors.append("持股数量不能为空")
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    matches = search_stock_catalog(code, 1)
    if matches is None:
        return jsonify({"ok": False, "errors": ["股票列表数据源暂时不可用，请稍后重试"]}), 503
    if not matches or matches[0].get("code") != code:
        return jsonify({"ok": False, "errors": [f"未在当前上市 A 股中找到 {code}，请重新搜索选择"]}), 400
    identity = matches[0]
    name = identity["name"]
    market = identity["market"]

    holdings, is_real = get_holdings_with_defaults()
    if any(h.get("code") == code for h in holdings):
        return jsonify({"ok": False, "errors": [f"{code} 已在持仓列表中"]}), 400

    try:
        cost = float(data["cost"])
        shares = int(data["shares"])
        stop_loss = float(data["stop_loss"]) if data.get("stop_loss") not in (None, "") else None
        target = float(data["target"]) if data.get("target") not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"ok": False, "errors": ["成本价、数量、止损价和目标价必须是有效数字"]}), 400
    if cost <= 0 or shares <= 0:
        return jsonify({"ok": False, "errors": ["成本价和持股数量必须大于 0"]}), 400

    new_h = {
        "code": code, "name": name, "market": market,
        "identity_source": identity.get("source"),
        "cost": cost,
        "shares": shares, "sector": data.get("sector", "其他"),
        "phase": data.get("phase") or "unknown", "phase_label": data.get("phase_label") or "待判断",
        "strategy": data.get("strategy") or "review", "confidence": None,
        "key_signals": [], "suggestion": data.get("suggestion") or "等待补充投资假设",
        "stop_loss": stop_loss,
        "target": target, "weight": 0,
        "created_at": datetime.now().isoformat(),
    }
    holdings.append(new_h)
    save_holdings(holdings)
    return jsonify({"ok": True, "holding": new_h})

@app.route("/api/portfolio/update/<code>", methods=["PUT"])
def api_update_holding(code):
    data = request.get_json() or {}
    holdings = load_holdings()
    if not holdings:
        return jsonify({"ok": False, "errors": ["无持仓数据，请先添加持仓"]}), 404

    idx = next((i for i, h in enumerate(holdings) if h.get("code") == code), None)
    if idx is None:
        return jsonify({"ok": False, "errors": [f"未找到 {code}"]}), 404

    numeric_fields = {"cost": float, "shares": int, "confidence": float,
                      "stop_loss": float, "target": float}
    for key, caster in numeric_fields.items():
        if key not in data:
            continue
        if data[key] in (None, "") and key in {"confidence", "stop_loss", "target"}:
            data[key] = None
            continue
        try:
            data[key] = caster(data[key])
        except (TypeError, ValueError):
            return jsonify({"ok": False, "errors": [f"{key} 必须是有效数字"]}), 400
    if "cost" in data and data["cost"] <= 0:
        return jsonify({"ok": False, "errors": ["成本价必须大于 0"]}), 400
    if "shares" in data and data["shares"] <= 0:
        return jsonify({"ok": False, "errors": ["持股数量必须大于 0"]}), 400

    updatable = {"name", "cost", "shares", "sector", "phase", "phase_label",
                 "strategy", "confidence", "stop_loss", "target", "suggestion"}
    for key in updatable:
        if key in data:
            holdings[idx][key] = data[key]

    save_holdings(holdings)
    return jsonify({"ok": True})

@app.route("/api/portfolio/delete/<code>", methods=["DELETE"])
def api_delete_holding(code):
    holdings = load_holdings()
    if not holdings:
        return jsonify({"ok": False, "errors": ["无持仓数据"]}), 404

    idx = next((i for i, h in enumerate(holdings) if h.get("code") == code), None)
    if idx is None:
        return jsonify({"ok": False, "errors": [f"未找到 {code}"]}), 404

    removed = holdings.pop(idx)
    save_holdings(holdings)
    return jsonify({"ok": True, "removed": removed.get("name", code)})

# ——— 模型列表 ———
@app.route("/api/model/list")
def api_model_list():
    config_path = Path.home() / ".wyckoff" / "wyckoff.json"
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except:
            pass
    return jsonify({"models": config.get("models", {}), "default": config.get("default_model", "deepseek")})

# ============================================================
# QUANT STRATEGY BUILDER (量化选股策略定制器)
# ============================================================
QUANT_STRATEGIES_FILE = PROJECT_DIR / ".quant_strategies.json"

def load_quant_strategies():
    if QUANT_STRATEGIES_FILE.exists():
        try:
            return json.loads(QUANT_STRATEGIES_FILE.read_text())
        except:
            pass
    return []

def save_quant_strategies(strategies):
    QUANT_STRATEGIES_FILE.write_text(json.dumps(strategies, ensure_ascii=False, indent=2))

# 因子库定义
FACTOR_LIB = {
    "categories": [
        {"name": "trend", "label": "趋势类", "factors": [
            {"id": "ma20_angle", "name": "MA20角度", "type": "number", "desc": "MA20均线斜率，识别趋势强度", "params": [{"key": "threshold", "label": "角度阈值", "default": 30, "min": 0, "max": 90}]},
            {"id": "macd_cross", "name": "MACD金叉", "type": "bool", "desc": "DIF上穿DEA", "params": []},
            {"id": "ma_bullish", "name": "均线多头排列", "type": "bool", "desc": "短期均线在长期均线之上", "params": [{"key": "periods", "label": "均线周期", "default": "5,10,20,60"}]},
        ]},
        {"name": "momentum", "label": "动量类", "factors": [
            {"id": "rsi_range", "name": "RSI区间", "type": "range", "desc": "RSI在指定区间内", "params": [{"key": "min", "label": "下限", "default": 30}, {"key": "max", "label": "上限", "default": 50}]},
            {"id": "rsi_strong", "name": "RSI强势区间", "type": "bool", "desc": "RSI > 60", "params": [{"key": "threshold", "label": "阈值", "default": 60}]},
            {"id": "volume_breakout", "name": "成交量突破", "type": "bool", "desc": "成交量超过N倍均量", "params": [{"key": "multiplier", "label": "均量倍数", "default": 2.0}]},
        ]},
        {"name": "wyckoff", "label": "威科夫", "factors": [
            {"id": "spring_signal", "name": "Spring信号", "type": "bool", "desc": "弹簧信号，支撑位测试成功", "params": []},
            {"id": "sos_breakout", "name": "SOS突破", "type": "bool", "desc": "强势出现信号", "params": []},
            {"id": "accumulation", "name": "Accumulation阶段", "type": "bool", "desc": "处于吸筹阶段", "params": []},
            {"id": "markup", "name": "Markup启动", "type": "bool", "desc": "进入拉升阶段", "params": []},
        ]},
        {"name": "fundamental", "label": "基本面", "factors": [
            {"id": "pe_percentile", "name": "PE分位", "type": "range", "desc": "市盈率历史分位", "params": [{"key": "max", "label": "上限分位", "default": 30}]},
            {"id": "roe_filter", "name": "ROE过滤", "type": "number", "desc": "净资产收益率", "params": [{"key": "min", "label": "最小值%", "default": 15}]},
            {"id": "market_cap", "name": "市值过滤", "type": "number", "desc": "总市值（亿）", "params": [{"key": "min_yi", "label": "最小市值(亿)", "default": 50}]},
        ]},
        {"name": "filter", "label": "过滤类", "factors": [
            {"id": "exclude_st", "name": "排除ST/退市", "type": "bool", "desc": "自动跳过ST和退市股", "params": []},
            {"id": "north_flow", "name": "北向资金流入", "type": "bool", "desc": "北向资金连续净买入", "params": [{"key": "days", "label": "连续天数", "default": 3}]},
        ]},
    ]
}

@app.route("/api/quant/factors")
def api_quant_factors():
    supported = {"spring_signal", "sos_breakout", "accumulation", "markup", "exclude_st"}
    categories = []
    for category in FACTOR_LIB.get("categories", []):
        factors = [factor for factor in category.get("factors", []) if factor.get("id") in supported]
        if factors:
            categories.append({**category, "factors": factors})
    return jsonify({"categories": categories})

@app.route("/api/quant/strategy", methods=["GET"])
def api_quant_strategy_list():
    return jsonify(load_quant_strategies())

@app.route("/api/quant/strategy", methods=["POST"])
def api_quant_strategy_create():
    data = request.get_json() or {}
    strategies = load_quant_strategies()
    sid = data.get("id") or f"strategy_{len(strategies)+1}_{int(time.time())}"
    data["id"] = sid
    data["created_at"] = datetime.now().isoformat()
    # 替换或新增
    existing = [i for i, s in enumerate(strategies) if s.get("id") == sid]
    if existing:
        strategies[existing[0]] = data
    else:
        strategies.append(data)
    save_quant_strategies(strategies)
    return jsonify({"ok": True, "strategy": data})

@app.route("/api/quant/strategy/<sid>", methods=["GET"])
def api_quant_strategy_get(sid):
    strategies = load_quant_strategies()
    for s in strategies:
        if s.get("id") == sid:
            return jsonify(s)
    return jsonify({"error": "not found"}), 404

@app.route("/api/quant/strategy/<sid>", methods=["DELETE"])
def api_quant_strategy_delete(sid):
    strategies = load_quant_strategies()
    strategies = [s for s in strategies if s.get("id") != sid]
    save_quant_strategies(strategies)
    return jsonify({"ok": True, "removed": sid})

# 策略执行（异步）
@app.route("/api/quant/run", methods=["POST"])
def api_quant_run():
    data = request.get_json() or {}
    strategy_id = data.get("strategy_id", "")
    task_id = f"quant_{int(time.time()*1000)}"

    def _run_quant():
        tasks[task_id] = {"status": "running", "started_at": datetime.now().isoformat()}
        try:
            # 读取策略定义
            strategies = load_quant_strategies()
            strategy = None
            for s in strategies:
                if s.get("id") == strategy_id:
                    strategy = s
                    break
            if not strategy:
                tasks[task_id] = {"status": "error", "error": f"策略 {strategy_id} 不存在"}
                return

            # 用 wyckoff screen 获取候选池
            stdout, stderr, rc = run_wyckoff("screen", "--limit", "0", "--no-financial-metrics", timeout=90)
            # 解析 screen 输出获取候选股票列表
            import re as _re
            candidates = []
            for line in stdout.split("\n"):
                m = _re.match(r"(\d{6})\s+(.+?)\s+(.+)", line)
                if m:
                    candidates.append({"code": m.group(1), "name": m.group(2).strip(), "phase": m.group(3).strip()})

            # 如果 screen 没输出候选，用 portfolio 里的持仓做 fallback
            if not candidates:
                holdings, _ = get_holdings_with_defaults()
                candidates = [{"code": h.get("code",""), "name": h.get("name",""), "phase": h.get("phase","")} for h in holdings]

            # 按 steps 逐步过滤
            steps = strategy.get("steps", [])
            supported_factors = {
                "spring_signal", "sos_breakout", "accumulation", "markup", "exclude_st"
            }
            requested_factors = {
                condition.get("factor", "")
                for step in steps
                for condition in step.get("conditions", [])
                if condition.get("factor")
            }
            unsupported_factors = sorted(requested_factors - supported_factors)
            if unsupported_factors:
                tasks[task_id] = {
                    "status": "error",
                    "error": "当前数据源尚不能真实计算这些因子: " + ", ".join(unsupported_factors),
                }
                return
            step_results = []
            filtered = candidates

            for step in steps:
                conditions = step.get("conditions", [])
                logic = step.get("logic", "AND")
                step_label = step.get("label", "")

                if not conditions:
                    # 最后一步可能是排序+limit
                    if step.get("sort_by"):
                        sort_key = step["sort_by"]
                        filtered.sort(key=lambda x: float(x.get(sort_key, 0) or 0), reverse=(step.get("sort_order","desc")=="desc"))
                    if step.get("limit"):
                        filtered = filtered[:step["limit"]]
                    step_results.append({"step": step.get("step",0), "label": step_label, "count": len(filtered)})
                    continue

                # 简化过滤：基于 phase 字段匹配威科夫因子
                new_filtered = []
                for c in filtered:
                    matched = False
                    for cond in conditions:
                        fid = cond.get("factor","")
                        if fid in ("spring_signal", "sos_breakout", "accumulation", "markup"):
                            phase_str = (c.get("phase","") or "").lower()
                            if fid == "spring_signal" and "spring" in phase_str: matched = True
                            elif fid == "sos_breakout" and "sos" in phase_str: matched = True
                            elif fid == "accumulation" and "accumulation" in phase_str: matched = True
                            elif fid == "markup" and "markup" in phase_str: matched = True
                        elif fid == "exclude_st":
                            name = c.get("name","")
                            if "ST" not in name and "退" not in name: matched = True
                        if matched and logic == "OR": break
                        if not matched and logic == "AND": break
                    if matched:
                        new_filtered.append(c)

                filtered = new_filtered
                step_results.append({"step": step.get("step",0), "label": step_label, "count": len(filtered)})

            tasks[task_id] = {
                "status": "done",
                "strategy_id": strategy_id,
                "matched_count": len(filtered),
                "step_results": step_results,
                "results": filtered,
                "completed_at": datetime.now().isoformat(),
            }
        except Exception as e:
            tasks[task_id] = {"status": "error", "error": str(e)}

    tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_quant, daemon=True).start()
    return jsonify({"task_id": task_id})

@app.route("/api/quant/run/<task_id>")
def api_quant_run_result(task_id):
    return jsonify(tasks.get(task_id, {"status": "not_found"}))

# 自定义策略回测：当前 CLI 无法接收前端策略定义，因此明确返回未实现。
@app.route("/api/quant/backtest", methods=["POST"])
def api_quant_backtest():
    data = request.get_json() or {}
    strategy_id = data.get("strategy_id", "")
    months = data.get("months", 12)
    hold_days = data.get("hold_days", 10)
    top_n = data.get("top_n", 10)
    task_id = f"quantbt_{int(time.time()*1000)}"

    tasks[task_id] = {
        "status": "error",
        "strategy_id": strategy_id,
        "error": "自定义策略尚未接入真实回测执行器，未生成模拟指标",
    }
    return jsonify({"task_id": task_id})

@app.route("/api/quant/backtest/<task_id>")
def api_quant_backtest_result(task_id):
    return jsonify(tasks.get(task_id, {"status": "not_found"}))

# 真实执行前不虚构命中数。
@app.route("/api/quant/preview", methods=["POST"])
def api_quant_preview():
    return jsonify({
        "available": False,
        "estimated": None,
        "message": "运行后显示真实筛选结果",
    })

# ============================================================
# AI EVIDENCE CHALLENGE (基于真实可用数据的观点挑战)
# ============================================================

def _as_text_list(value, limit=5):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _clamped_number(value, low, high, default=0):
    try:
        return round(max(low, min(high, float(value))), 1)
    except (TypeError, ValueError):
        return default


def _parse_json_object(content):
    text = (content or "").strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S | re.I)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise ValueError("模型未返回可解析的结构化结果")


def run_evidence_challenge(stock_code, stock_name):
    holdings, _ = get_live_holdings()
    holding = next((item for item in holdings if item.get("code") == stock_code), None)
    if not holding:
        raise ValueError("请先将该股票添加到真实持仓，再发起观点挑战")
    if holding.get("price_status") != "ok":
        raise ValueError("该持仓的真实日线行情暂不可用，请稍后重试")

    market = build_market_data()
    indices = {}
    for key, item in (market.get("indices") or {}).items():
        if item.get("value"):
            indices[key] = {
                "name": item.get("name"), "value": item.get("value"),
                "change_pct": item.get("change_pct"), "date": item.get("date"),
            }
    regime = market.get("regime") or {}
    evidence = {
        "stock": {
            "code": stock_code,
            "name": stock_name,
            "cost": holding.get("cost"),
            "shares": holding.get("shares"),
            "latest_close": holding.get("price"),
            "close_date": holding.get("price_date"),
            "daily_change_pct": holding.get("daily_change_pct"),
            "pnl_pct": holding.get("pnl_pct"),
            "quote_source": holding.get("price_source"),
            "user_recorded_phase": holding.get("phase_label") or holding.get("phase"),
            "user_thesis": holding.get("suggestion"),
            "user_stop_loss": holding.get("stop_loss"),
            "user_target": holding.get("target"),
        },
        "market": {
            "indices": indices,
            "derived_regime": regime.get("regime_label") if isinstance(regime, dict) else None,
            "regime_sample_size": regime.get("sample_size") if isinstance(regime, dict) else None,
            "regime_as_of": regime.get("as_of") if isinstance(regime, dict) else None,
            "provenance": market.get("provenance"),
        },
        "missing": ["个股K线序列", "成交量序列", "RSI/MACD/均线", "公司财务与估值", "实时新闻"],
    }
    messages = [
        {"role": "system", "content": """你是投资观点审查助手。只能使用用户提供的结构化证据，不得调用常识补写公司事实，不得声称计算了缺失的技术指标、财务指标或新闻。你的任务是同时给出支持证据、反对证据和风险边界，结论是待用户核验的研究观点，不是投资建议。若证据不足，必须降低置信度并优先给出观望或持有。输出严格 JSON，不要 Markdown。"""},
        {"role": "user", "content": f"""请审查以下持仓观点：
{json.dumps(evidence, ensure_ascii=False)}

输出格式：
{{
  "supporting_evidence": ["仅引用输入证据"],
  "counter_evidence": ["仅引用输入证据或明确的数据缺口"],
  "risks": ["风险与需核验项"],
  "action": "买入|卖出|持有|观望",
  "position_pct": 0,
  "stop_loss_pct": 0,
  "target_pct": 0,
  "confidence": 0,
  "summary": "100字内，说明结论及证据限制"
}}"""},
    ]
    started = time.time()
    content, error = call_llm(messages, max_tokens=1400)
    if error:
        raise RuntimeError(f"AI 服务暂不可用：{error}")
    result = _parse_json_object(content)
    support = _as_text_list(result.get("supporting_evidence"))
    counter = _as_text_list(result.get("counter_evidence"))
    risks = _as_text_list(result.get("risks"))
    action = result.get("action") if result.get("action") in {"买入", "卖出", "持有", "观望"} else "观望"
    confidence = _clamped_number(result.get("confidence"), 0, 10, 3)
    if len(indices) == 0 or not support or not counter:
        confidence = min(confidence, 3)
    summary = str(result.get("summary") or "证据不足，建议补充数据后再判断。").strip()[:240]
    duration_ms = round((time.time() - started) * 1000)
    final_decision = {
        "action": action,
        "position_pct": _clamped_number(result.get("position_pct"), 0, 100),
        "stop_loss_pct": _clamped_number(result.get("stop_loss_pct"), 0, 100),
        "target_pct": _clamped_number(result.get("target_pct"), 0, 100),
        "confidence": confidence,
        "summary": summary,
    }
    return {
        "final_decision": final_decision,
        "trader_decision": {"action": action, "reason": summary},
        "trace": [
            {"layer": 1, "agent": "真实数据摘要", "content": f"{holding.get('price_date')} 收盘 {holding.get('price')} 元，持仓盈亏 {holding.get('pnl_pct')}%；行情源 {holding.get('price_source')}。", "duration_ms": 0},
            {"layer": 3, "agent": "多空证据审查", "content": "支持：" + "；".join(support or ["暂无充分支持证据"]) + "\n反对：" + "；".join(counter or ["证据不足"]), "duration_ms": duration_ms},
            {"layer": 5, "agent": "风险边界", "content": "；".join(risks or evidence["missing"]), "duration_ms": 0},
        ],
        "reports": {
            "wyckoff": f"用户记录阶段：{holding.get('phase_label') or holding.get('phase') or '未记录'}。当前未接入个股量价序列，系统不自行判断威科夫阶段。",
            "technical": "未接入个股 K 线与指标序列，本次未计算 RSI、MACD 或均线。",
            "fundamental": "未接入可核验财务与估值数据，本次不提供基本面结论。",
            "bull": "\n".join(support) or "暂无充分支持证据。",
            "bear": "\n".join(counter) or "证据不足，暂不能形成反方事实判断。",
            "debate": summary,
            "risk": "\n".join(risks) or "请补充个股量价、财务和事件数据后复核。",
        },
        "price_at_decision": holding.get("price"),
        "data_basis": evidence,
    }

@app.route("/api/agent/analyze", methods=["POST"])
def api_agent_analyze():
    data = request.get_json() or {}
    stock_code = data.get("stock_code", "")
    stock_name = data.get("stock_name", stock_code)
    if not stock_code:
        return jsonify({"error": "stock_code is required"}), 400
    
    task_id = f"agent_{int(time.time()*1000)}"
    
    def _run_agent():
        tasks[task_id] = {"status": "running", "started_at": datetime.now().isoformat()}
        try:
            result = run_evidence_challenge(stock_code, stock_name)

            # AI 只生成待确认观点，用户确认后才写入决策复盘。
            tasks[task_id] = {
                "status": "done",
                "stock_code": stock_code,
                "stock_name": stock_name,
                "final_decision": result.get("final_decision", {}),
                "trader_decision": result.get("trader_decision", {}),
                "trace": result.get("trace", []),
                "reports": result.get("reports", {}),
                "started_at": tasks[task_id].get("started_at"),
                "completed_at": datetime.now().isoformat(),
                "completed_at_ts": datetime.now().isoformat(),
                "price_at_decision": result.get("price_at_decision"),
                "data_basis": result.get("data_basis"),
            }
        except Exception as e:
            import traceback
            tasks[task_id] = {"status": "error", "error": str(e), "traceback": traceback.format_exc()[-500:]}
    
    tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_agent, daemon=True).start()
    return jsonify({"task_id": task_id})

@app.route("/api/agent/analyze/<task_id>")
def api_agent_analyze_result(task_id):
    return jsonify(tasks.get(task_id, {"status": "not_found"}))

# ============================================================
# TRADINGAGENTS (66.5k星开源多Agent交易框架集成)
# ============================================================
_ta_graph = None

def get_ta_graph():
    """懒加载 TradingAgents 图（用 baostock 替换 yfinance 数据层）"""
    global _ta_graph
    if _ta_graph is None:
        import os
        # 清除代理（和 call_llm 一样的问题）
        for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
            os.environ.pop(k, None)
        # 用 TokenHub 作为 OpenAI 兼容端点
        os.environ['OPENAI_API_KEY'] = LLM_API_KEY
        os.environ['OPENAI_BASE_URL'] = os.getenv("TOKENHUB_BASE_URL", "https://tokenhub.tencentmaas.com/v1")
        # 关键：在 import tradingagents 之前注入假 yfinance 模块
        from ta_adapter import install_fake_yfinance
        install_fake_yfinance()
        # 初始化 TradingAgents（此时所有 import yfinance 都会拿到 FakeTicker）
        from tradingagents import TradingAgentsConfig, TradingAgentsGraph
        config = TradingAgentsConfig(
            llm_provider='openai',
            deep_think_llm=LLM_MODEL,
            quick_think_llm=LLM_MODEL,
            max_debate_rounds=1,
            max_risk_discuss_rounds=1,
            max_recur_limit=50,
            response_language='zh-CN',
        )
        _ta_graph = TradingAgentsGraph(debug=False, config=config)
    return _ta_graph

@app.route("/api/agent/tradingagents", methods=["POST"])
def api_ta_analyze():
    """TradingAgents 多Agent分析（7角色：4分析师+多空+交易员+风控+PM）"""
    data = request.get_json() or {}
    ticker = data.get("ticker", "")
    date = data.get("date", "")
    if not ticker:
        return jsonify({"error": "ticker is required (e.g. 600519.SS)"}), 400
    if not date:
        from datetime import datetime as _dt
        date = _dt.now().strftime("%Y-%m-%d")

    task_id = f"ta_{int(time.time()*1000)}"

    def _run_ta():
        tasks[task_id] = {"status": "running", "ticker": ticker, "date": date, "started_at": datetime.now().isoformat()}
        try:
            graph = get_ta_graph()
            state, decision = graph.propagate(ticker, date)
            tasks[task_id] = {
                "status": "done",
                "ticker": ticker,
                "date": date,
                "decision": decision,
                "completed_at": datetime.now().isoformat(),
            }
        except Exception as e:
            import traceback
            tasks[task_id] = {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()[-800:],
            }

    tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_ta, daemon=True).start()
    return jsonify({"task_id": task_id})

@app.route("/api/agent/tradingagents/<task_id>")
def api_ta_result(task_id):
    return jsonify(tasks.get(task_id, {"status": "not_found"}))

# ============================================================
# DECISION REVIEW TRACKER (决策复盘系统)
# ============================================================
@app.route("/api/effect/record", methods=["POST"])
def api_effect_record():
    """记录一次待用户确认的 AI 决策观点。"""
    from effect_tracker import get_reference_price, record_prediction
    data = request.get_json() or {}
    stock_code = data.get("stock_code", "").strip()
    action = data.get("action", "").strip()
    if not stock_code or not action:
        return jsonify({"ok": False, "error": "stock_code and action are required"}), 400

    price_at_decision = data.get("price_at_decision", 0) or 0
    if price_at_decision <= 0:
        price_at_decision = get_reference_price(stock_code) or 0
    if price_at_decision <= 0:
        return jsonify({"ok": False, "error": "无法获取决策基准价，请稍后重试"}), 503

    pred = record_prediction(
        stock_code=stock_code,
        stock_name=data.get("stock_name", ""),
        action=action,
        position_pct=data.get("position_pct", 0),
        confidence=data.get("confidence", 5),
        price_at_decision=price_at_decision,
        source=data.get("source", "agent"),
        notes=data.get("notes", ""),
        model_version=data.get("model_version", LLM_MODEL),
        prompt_version=data.get("prompt_version", "manual_v1"),
        decision_rule_version=data.get("decision_rule_version", "directional_v2"),
    )
    return jsonify({"ok": True, "prediction": pred})

@app.route("/api/effect/list")
def api_effect_list():
    """获取所有决策观点记录。"""
    from effect_tracker import get_all_predictions
    return jsonify(get_all_predictions())

@app.route("/api/effect/stats")
def api_effect_stats():
    """获取聚合统计"""
    from effect_tracker import get_stats
    return jsonify(get_stats())

@app.route("/api/effect/check", methods=["POST"])
def api_effect_check():
    """检查到期预测的实际涨跌"""
    from effect_tracker import check_matured_predictions
    updated = check_matured_predictions()
    return jsonify({"ok": True, "updated": updated})

@app.route("/api/effect/feedback", methods=["POST"])
def api_effect_feedback():
    """用户反馈"""
    from effect_tracker import add_feedback
    data = request.get_json() or {}
    result = add_feedback(data.get("pred_id", ""), data.get("feedback", ""), data.get("rating", 3))
    return jsonify({"ok": True, "prediction": result} if result else {"ok": False})

# ============================================================
# PORTFOLIO REPLAY (组合历史回放)
# ============================================================
@app.route("/api/backtest/run", methods=["POST"])
def api_backtest_run():
    """兼容旧入口：内部转到新版回测引擎。"""
    from app.services.backtest.engine import run_backtest
    data = request.get_json() or {}
    stock_codes = data.get("stocks", [])
    if not stock_codes:
        return jsonify({
            "deprecated": True,
            "ok": False,
            "error": "旧 /api/backtest/run 仍保留，但必须传入明确股票池；系统不会生成默认股票。请优先使用 POST /api/backtests。",
        }), 400
    months = int(data.get("months", 12))
    hold_days = int(data.get("hold_days", 10))

    task_id = f"bt_{int(time.time()*1000)}"

    def _run_real_bt():
        tasks[task_id] = {"status": "running", "started_at": datetime.now().isoformat()}
        try:
            end = datetime.now().date()
            start = (end - timedelta(days=months * 31)).isoformat()
            result = run_backtest({
                "stocks": stock_codes,
                "start_date": data.get("start_date", start),
                "end_date": data.get("end_date", end.isoformat()),
                "hold_days": hold_days,
                "max_positions": int(data.get("top_n", 5)),
                "initial_capital": float(data.get("initial_capital", 100000)),
                "commission_rate": float(data.get("commission_rate", 0.0003)),
                "min_commission": float(data.get("min_commission", 5)),
                "stamp_tax_rate": float(data.get("stamp_tax_rate", 0.001)),
                "transfer_fee_rate": float(data.get("transfer_fee_rate", 0.00001)),
                "slippage": float(data.get("slippage", 0.0005)),
                "lot_size": int(data.get("lot_size", 100)),
                "sellable_after_days": int(data.get("sellable_after_days", 1)),
            })
            if not result.get("ok"):
                tasks[task_id] = {"status": "error", "deprecated": True, "error": result.get("error"), "result": result}
                return
            tasks[task_id] = {"status": "done", "deprecated": True, "backtest": result, "completed_at": datetime.now().isoformat()}
        except Exception as e:
            import traceback
            tasks[task_id] = {"status": "error", "error": str(e), "traceback": traceback.format_exc()[-500:]}

    tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_real_bt, daemon=True).start()
    return jsonify({"task_id": task_id})

@app.route("/api/backtest/run/<task_id>")
def api_real_backtest_result(task_id):
    return jsonify(tasks.get(task_id, {"status": "not_found"}))

# ============================================================
# STATIC
# ============================================================
@app.route("/")
def serve_index():
    return render_template("index.html")

@app.route("/assets/<path:path>")
def serve_assets(path):
    if path.startswith(".") or ".." in Path(path).parts:
        abort(404)
    return send_from_directory(str(PROJECT_DIR / "assets"), path)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("🐱 威科夫投资工作台 v3 · 真实数据驱动 · 老布偶猫主题")
    print("   数据源: baostock + wyckoff screen")
    print("   LLM: deepseek-v4-pro")
    port = PORT
    print(f"   http://localhost:{port}")
    # 启动后预热市场数据（不阻塞服务启动）
    def _warmup():
        time.sleep(2)
        _kick_market_refresh()
    threading.Thread(target=_warmup, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
