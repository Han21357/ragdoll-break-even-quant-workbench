import os
import pytest

if os.getenv("RUN_LIVE_TESTS") != "1":
    pytest.skip("live baostock smoke test; set RUN_LIVE_TESTS=1 to run", allow_module_level=True)

import baostock as bs, json, sys
from datetime import datetime, timedelta

bs.login()
codes = "603019,600519,300750".split(",")
months = 6
end = datetime.now().strftime("%Y-%m-%d")
start = (datetime.now() - timedelta(days=months*30+10)).strftime("%Y-%m-%d")
result = {}
for code in codes:
    c = code.split(".")[0] if "." in code else code
    market = "sh" if c.startswith("6") else "sz"
    rs = bs.query_history_k_data_plus(f"{market}.{c}",
        "date,close,pctChg", start_date=start, end_date=end, frequency="d")
    rows = []
    while (rs.error_code == "0") and rs.next():
        rows.append(rs.get_row_data())
    result[code] = len(rows)
bs.logout()
print(json.dumps(result, ensure_ascii=False))
