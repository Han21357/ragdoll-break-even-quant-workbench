import inspect
from tradingagents.dataflows.yfinance import get_yfin_data_online
src = inspect.getsource(get_yfin_data_online)
print(src[:1000])
print("\n=== type ===")
print(type(get_yfin_data_online))
print("\n=== has func attr ===")
print(hasattr(get_yfin_data_online, 'func'))
if hasattr(get_yfin_data_online, 'func'):
    print("func:", get_yfin_data_online.func)
