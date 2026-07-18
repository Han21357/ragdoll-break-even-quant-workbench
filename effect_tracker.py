"""投资决策记录与研究性回查指标。"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

EFFECT_FILE = Path(__file__).parent / ".ai_effect_tracker.json"
PYTHON_BIN = sys.executable
BUY_ACTIONS = {"买入", "加仓", "试探建仓"}
SELL_ACTIONS = {"卖出", "减仓", "清仓"}
HOLD_ACTIONS = {"持有", "观望"}
METRIC_VERSION = "2.0"
MIN_DIRECTIONAL_SAMPLE = 30


def _prediction_type(action):
    if action in BUY_ACTIONS:
        return "long"
    if action in SELL_ACTIONS:
        return "short"
    if action in HOLD_ACTIONS:
        return "hold"
    return "unknown"


def _strategy_return(pred):
    actual_return = pred.get("actual_return")
    if actual_return is None:
        return None
    pred_type = pred.get("prediction_type") or _prediction_type(pred.get("action", ""))
    if pred_type == "long":
        return actual_return
    if pred_type == "short":
        return -actual_return
    return None


def _load():
    if EFFECT_FILE.exists():
        try:
            return json.loads(EFFECT_FILE.read_text())
        except:
            pass
    return {"predictions": [], "stats": {}}


def _save(data):
    EFFECT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def record_prediction(stock_code, stock_name, action, position_pct, confidence,
                      price_at_decision, source="agent", notes="",
                      model_version="", prompt_version="",
                      decision_rule_version="directional_v2"):
    """记录一次待用户确认的 AI 决策观点。"""
    data = _load()
    pred_type = _prediction_type(action)
    pred = {
        "id": f"pred_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "stock_code": stock_code,
        "stock_name": stock_name,
        "action": action,
        "position_pct": position_pct,
        "confidence": confidence,
        "price_at_decision": price_at_decision,
        "source": source,
        "notes": notes,
        "prediction_type": pred_type,
        "metric_version": METRIC_VERSION,
        "model_version": model_version,
        "prompt_version": prompt_version,
        "decision_rule_version": decision_rule_version,
        "decision_date": datetime.now().strftime("%Y-%m-%d"),
        "check_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "status": "pending",
        "price_at_check": None,
        "actual_return": None,
        "strategy_return": None,
        "is_correct": None,
        "feedback": None,
        "check_attempts": 0,
    }
    data["predictions"].append(pred)
    _save(data)
    return pred


def _get_price_on_date(stock_code, date_str):
    """用 baostock 获取某只股票某天的收盘价"""
    code = stock_code.split(".")[0] if "." in stock_code else stock_code
    market = "sh" if code.startswith("6") else "sz"
    end_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=3)).strftime("%Y-%m-%d")
    script = f'''
import baostock as bs, json
bs.login()
rs = bs.query_history_k_data_plus("{market}.{code}",
    "date,close",
    start_date="{date_str}", end_date="{end_date}", frequency="d")
data = []
while (rs.error_code == '0') and rs.next():
    data.append(rs.get_row_data())
bs.logout()
print(json.dumps(data, ensure_ascii=False))
'''
    try:
        clean_env = {**os.environ}
        for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
            clean_env.pop(k, None)
        result = subprocess.run([PYTHON_BIN, "-c", script],
            capture_output=True, text=True, timeout=20, env=clean_env)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if data and len(data) > 0:
                return float(data[-1][1])
    except:
        pass
    return None


def get_reference_price(stock_code):
    """获取最近可用收盘价，供确认决策时固化价格基准。"""
    return _get_price_on_date(stock_code, datetime.now().strftime("%Y-%m-%d"))


def check_matured_predictions():
    """检查所有到期的预测，回查实际价格"""
    data = _load()
    today = datetime.now().strftime("%Y-%m-%d")
    updated = 0

    for pred in data["predictions"]:
        if pred.get("status") not in ("pending", "no_data"):
            continue
        if pred.get("check_date", today) > today:
            continue
        if pred.get("check_attempts", 0) >= 5:
            continue

        actual_price = _get_price_on_date(pred["stock_code"], pred["check_date"])
        pred["check_attempts"] = pred.get("check_attempts", 0) + 1
        pred["last_check_attempt"] = datetime.now().isoformat(timespec="seconds")
        if actual_price is None:
            pred["status"] = "no_data"
            continue

        pred["price_at_check"] = actual_price
        decision_price = pred["price_at_decision"]
        if decision_price and decision_price > 0:
            pred["actual_return"] = round((actual_price - decision_price) / decision_price * 100, 2)

        pred_type = pred.get("prediction_type") or _prediction_type(pred.get("action", ""))
        pred["prediction_type"] = pred_type
        pred["metric_version"] = METRIC_VERSION
        pred["strategy_return"] = _strategy_return(pred)

        is_correct = None
        if pred_type in ("long", "short"):
            is_correct = pred["strategy_return"] is not None and pred["strategy_return"] > 0
        elif pred_type == "hold":
            is_correct = pred["actual_return"] is not None and abs(pred["actual_return"]) < 5
        pred["is_correct"] = is_correct
        pred["status"] = "checked"
        updated += 1

    data["stats"] = _calc_stats(data["predictions"])
    _save(data)
    return updated


def _calc_stats(predictions):
    """分别计算方向观点和持有观点，避免混淆不同预测任务。"""
    checked = [p for p in predictions if p.get("status") == "checked"]
    directional = [
        p for p in checked
        if (p.get("prediction_type") or _prediction_type(p.get("action", ""))) in ("long", "short")
        and p.get("is_correct") is not None
    ]
    holds = [
        p for p in checked
        if (p.get("prediction_type") or _prediction_type(p.get("action", ""))) == "hold"
        and p.get("is_correct") is not None
    ]

    directional_correct = sum(1 for p in directional if p.get("is_correct"))
    hold_stable = sum(1 for p in holds if p.get("is_correct"))
    strategy_returns = [
        value for value in (_strategy_return(p) for p in directional)
        if value is not None
    ]
    avg_strategy_return = (
        sum(strategy_returns) / len(strategy_returns) if strategy_returns else 0
    )

    # 7 日观察窗按周频年化，仅作为研究性描述指标。
    import statistics
    if len(strategy_returns) > 1:
        std = statistics.stdev(strategy_returns)
        weekly_risk_free_pct = 3.0 / 52
        sharpe = ((avg_strategy_return - weekly_risk_free_pct) / std * (52 ** 0.5)
                  if std > 0 else 0)
        sharpe = round(sharpe, 2)
    else:
        sharpe = 0

    directional_count = len(directional)
    directional_accuracy = (
        round(directional_correct / directional_count * 100, 1)
        if directional_count else 0
    )
    hold_stability_rate = (
        round(hold_stable / len(holds) * 100, 1) if holds else 0
    )

    return {
        "stats_version": METRIC_VERSION,
        "total_predictions": len(predictions),
        "checked": len(checked),
        "directional_checked": directional_count,
        "hold_checked": len(holds),
        "pending": sum(1 for p in predictions if p.get("status") in ("pending", "no_data")),
        "directional_accuracy": directional_accuracy,
        "hold_stability_rate": hold_stability_rate,
        "avg_strategy_return": round(avg_strategy_return, 2),
        "sharpe_ratio": sharpe,
        "win_count": directional_correct,
        "loss_count": directional_count - directional_correct,
        "sample_sufficient": directional_count >= MIN_DIRECTIONAL_SAMPLE,
        "min_directional_sample": MIN_DIRECTIONAL_SAMPLE,
        # 兼容旧前端和外部调用，含义已统一为方向观点口径。
        "accuracy": directional_accuracy,
        "avg_return": round(avg_strategy_return, 2),
    }


def get_all_predictions():
    """获取所有决策观点记录。"""
    data = _load()
    return data["predictions"]


def get_stats():
    """获取统计"""
    data = _load()
    data["stats"] = _calc_stats(data["predictions"])
    _save(data)
    return data["stats"]


def add_feedback(pred_id, feedback, rating):
    """用户反馈"""
    data = _load()
    for p in data["predictions"]:
        if p["id"] == pred_id:
            p["feedback"] = feedback
            p["rating"] = rating
            _save(data)
            return p
    return None
