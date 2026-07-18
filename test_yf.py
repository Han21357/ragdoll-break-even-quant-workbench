import os
for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy','ALL_PROXY']:
    os.environ.pop(k, None)
import yfinance as yf
t = yf.Ticker('600519.SS')
h = t.history(period='5d')
print('rows:', len(h))
if len(h) > 0:
    print('close:', h['Close'].iloc[-1])
    print('volume:', h['Volume'].iloc[-1])
else:
    print('no data - yfinance cannot reach A-shares')
