"""Direct public-data adapters inspired by simonlin1212/a-stock-data (Apache-2.0)."""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..base import MarketDataProvider
from ..models import DataResult, SourceStatus
from .akshare_provider import _num, _plain_symbol

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class AStockDataProvider(MarketDataProvider):
    name = "a-stock-data"
    _lock = threading.Lock()
    _last_eastmoney_call = 0.0
    _cninfo_orgs: dict[str, str] = {}

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})
        retry = Retry(total=2, connect=2, read=2, backoff_factor=.6, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _status(self, source, status, message=None, as_of=None, latency_ms=None):
        return SourceStatus(source, status, as_of=as_of, message=message, latency_ms=latency_ms)

    def _get(self, url, *, params=None, headers=None, timeout=12):
        if "eastmoney.com" in url:
            with self._lock:
                wait = .8 - (time.time() - self._last_eastmoney_call)
                if wait > 0:
                    time.sleep(wait)
                response = self.session.get(url, params=params, headers=headers, timeout=timeout)
                self._last_eastmoney_call = time.time()
                response.raise_for_status()
                return response
        response = self.session.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    def get_stock_list(self) -> DataResult:
        return DataResult(False, [], [self._status(self.name, "unsupported")], "security master not provided")

    def get_stock_daily(self, symbol, start_date, end_date, adjustment="qfq") -> DataResult:
        return DataResult(False, [], [self._status(self.name, "unsupported")], "daily bars use AKShare/efinance/mootdx/BaoStock")

    def get_sector_snapshot(self) -> DataResult:
        source = "eastmoney:industry"
        started = time.time()
        try:
            response = self._get("https://push2.eastmoney.com/api/qt/clist/get", params={
                "pn": "1", "pz": "100", "po": "1", "np": "1", "fltt": "2", "invt": "2",
                "fid": "f3", "fs": "m:90+t:2", "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140",
            })
            items = (response.json().get("data") or {}).get("diff") or []
            today = datetime.now().date().isoformat()
            rows = [{
                "name": item.get("f14"), "code": item.get("f12"), "change_pct": _num(item.get("f3")),
                "up_count": _num(item.get("f104")), "down_count": _num(item.get("f105")),
                "leader": item.get("f140"), "leader_change_pct": _num(item.get("f136")),
                "source": source, "as_of": today, "status": "ok",
            } for item in items if item.get("f14") and _num(item.get("f3")) is not None]
            if not rows:
                raise ValueError("industry endpoint returned no usable rows")
            return DataResult(True, rows, [self._status(source, "ok", as_of=today, latency_ms=int((time.time()-started)*1000))], data_date=today)
        except Exception as exc:
            return DataResult(False, [], [self._status(source, "unavailable", str(exc))], str(exc))

    def get_fund_flow(self, symbol: str, days: int = 120) -> DataResult:
        source = "eastmoney:fund-flow"
        code = _plain_symbol(symbol)
        try:
            response = self._get("https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get", params={
                "secid": f"{1 if code.startswith(('5','6','9')) else 0}.{code}", "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57", "lmt": str(days),
            }, headers={"Referer": "https://quote.eastmoney.com/"})
            lines = (response.json().get("data") or {}).get("klines") or []
            rows = []
            for line in lines:
                parts = line.split(",")
                if len(parts) < 6:
                    continue
                rows.append({"symbol": code, "trade_date": parts[0], "main_net_inflow": _num(parts[1]), "small_net_inflow": _num(parts[2]), "medium_net_inflow": _num(parts[3]), "large_net_inflow": _num(parts[4]), "super_net_inflow": _num(parts[5]), "source": source})
            if not rows:
                raise ValueError("fund-flow endpoint returned no rows")
            return DataResult(True, rows, [self._status(source, "ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [self._status(source, "unavailable", str(exc))], str(exc))

    def get_stock_profile(self, symbol: str) -> DataResult:
        source = "eastmoney:stock-profile"
        code = _plain_symbol(symbol)
        try:
            response = self._get("https://push2.eastmoney.com/api/qt/stock/get", params={
                "fltt": "2", "invt": "2", "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43,f162,f167",
                "secid": f"{1 if code.startswith(('5','6','9')) else 0}.{code}",
            })
            raw = response.json().get("data") or {}
            if not raw.get("f57"):
                raise ValueError("stock profile returned no data")
            today = datetime.now().date().isoformat()
            data = {"symbol": code, "name": raw.get("f58"), "industry": raw.get("f127"), "total_shares": _num(raw.get("f84")), "float_shares": _num(raw.get("f85")), "market_cap": _num(raw.get("f116")), "float_market_cap": _num(raw.get("f117")), "list_date": str(raw.get("f189") or "") or None, "price": _num(raw.get("f43")), "pe_ttm": _num(raw.get("f162")), "pb": _num(raw.get("f167")), "source": source, "as_of": today}
            return DataResult(True, data, [self._status(source, "ok", as_of=today)], data_date=today)
        except Exception as exc:
            return DataResult(False, {}, [self._status(source, "unavailable", str(exc))], str(exc))

    def get_research_reports(self, symbol: str, limit: int = 20) -> DataResult:
        source = "eastmoney:research-report"
        code = _plain_symbol(symbol)
        try:
            response = self._get("https://reportapi.eastmoney.com/report/list", params={
                "industryCode": "*", "pageSize": str(limit), "industry": "*", "rating": "*", "ratingChange": "*",
                "beginTime": "2000-01-01", "endTime": "2030-01-01", "pageNo": "1", "qType": "0", "code": code,
            }, headers={"Referer": "https://data.eastmoney.com/"}, timeout=20)
            rows = response.json().get("data") or []
            normalized = [{"title": row.get("title"), "date": str(row.get("publishDate") or "")[:10], "institution": row.get("orgSName"), "rating": row.get("emRatingName"), "source": source} for row in rows]
            if not normalized:
                raise ValueError("no institutional reports returned; the stock may have no coverage")
            return DataResult(True, normalized, [self._status(source, "ok", as_of=normalized[0]["date"])], data_date=normalized[0]["date"])
        except Exception as exc:
            return DataResult(False, [], [self._status(source, "unavailable", str(exc))], str(exc))

    def get_stock_news(self, symbol: str, limit: int = 20) -> DataResult:
        source = "eastmoney:stock-news"
        code = _plain_symbol(symbol)
        try:
            callback = "jQuery_ragdoll"
            inner = json.dumps({"uid":"","keyword":code,"type":["cmsArticleWebOld"],"client":"web","clientType":"web","clientVersion":"curr","param":{"cmsArticleWebOld":{"searchScope":"default","sort":"default","pageIndex":1,"pageSize":limit,"preTag":"","postTag":""}}}, separators=(",", ":"))
            text = self._get("https://search-api-web.eastmoney.com/search/jsonp", params={"cb": callback, "param": inner}, headers={"Referer":"https://so.eastmoney.com/"}).text
            payload = json.loads(text[text.index("(")+1:text.rindex(")")])
            rows = [{"title": re.sub(r"<[^>]+>", "", item.get("title", "")), "summary": re.sub(r"<[^>]+>", "", item.get("content", ""))[:200], "date": item.get("date"), "publisher": item.get("mediaName"), "url": item.get("url"), "source": source} for item in (payload.get("result") or {}).get("cmsArticleWebOld", [])]
            if not rows:
                raise ValueError("news endpoint returned no articles or was rate limited")
            return DataResult(True, rows, [self._status(source, "ok", as_of=str(rows[0].get("date") or "")[:10])], data_date=str(rows[0].get("date") or "")[:10])
        except Exception as exc:
            return DataResult(False, [], [self._status(source, "unavailable", str(exc))], str(exc))

    def get_announcements(self, symbol: str, limit: int = 20) -> DataResult:
        source = "cninfo:announcements"
        code = _plain_symbol(symbol)
        try:
            org = self._cninfo_org_id(code)
            response = self.session.post("https://www.cninfo.com.cn/new/hisAnnouncement/query", data={"stock":f"{code},{org}","tabName":"fulltext","pageSize":str(limit),"pageNum":"1","column":"","category":"","plate":"","seDate":"","searchkey":"","secid":"","sortName":"","sortType":"","isHLtitle":"true"}, headers={"Content-Type":"application/x-www-form-urlencoded","Referer":"https://www.cninfo.com.cn/new/disclosure","Origin":"https://www.cninfo.com.cn"}, timeout=15)
            response.raise_for_status()
            rows = [{"title": re.sub(r"<[^>]+>", "", item.get("announcementTitle", "")), "type": item.get("announcementTypeName"), "date": _date_from_ms(item.get("announcementTime")), "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={item.get('announcementId','')}", "source": source} for item in response.json().get("announcements", [])]
            if not rows:
                raise ValueError("cninfo returned no announcements")
            return DataResult(True, rows, [self._status(source, "ok", as_of=rows[0]["date"])], data_date=rows[0]["date"])
        except Exception as exc:
            return DataResult(False, [], [self._status(source, "unavailable", str(exc))], str(exc))

    def _cninfo_org_id(self, code: str) -> str:
        if not self._cninfo_orgs:
            try:
                payload = self._get("https://www.cninfo.com.cn/new/data/szse_stock.json").json()
                self._cninfo_orgs = {item["code"]: item["orgId"] for item in payload.get("stockList", [])}
            except Exception:
                self._cninfo_orgs = {}
        return self._cninfo_orgs.get(code) or (f"gssh0{code}" if code.startswith("6") else f"gssz0{code}")


def _date_from_ms(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d")
    return str(value or "")[:10] or None
