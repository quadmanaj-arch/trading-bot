import utils

WATCHLIST = ['SPY','QQQ','AAPL','MSFT','NVDA','TSLA','AMZN','META','AMD','NFLX','COIN','PLTR','UBER','JPM','BAC']

def sma(prices, n):
    if len(prices) < n:
        return None
    return sum(prices[-n:]) / n

def rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100
    return 100 - (100 / (1 + ag / al))

def get_bars_bulk():
    syms = ','.join(WATCHLIST)
    try:
        d = utils.alp_get(f'/stocks/bars?symbols={syms}&timeframe=1Hour&limit=100&feed=iex', utils.DATA)
        return d.get('bars', {})
    except Exception as e:
        print(f'Bars fetch error: {e}')
        return {}

def analyze(symbol, bars):
    if len(bars) < 25:
        return None
    closes  = [b['c'] for b in bars]
    volumes = [b['v'] for b in bars]
    price   = closes[-1]
    sma20   = sma(closes, 20)
    rsi_val = rsi(closes)
    avg_vol = sum(volumes[-20:]) / 20
    vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1

    if price > sma20 and 42 <= rsi_val <= 65 and vol_ratio >= 1.5:
        entry = round(price * 1.002, 2)
        stop  = round(min(sma20 * 0.99, price * 0.97), 2)
        risk  = entry - stop
        if risk <= 0 or entry < 10:
            return None
        target = round(entry + 2 * risk, 2)
        return {'symbol': symbol, 'signal': 'BUY', 'price': price,
                'entry': entry, 'stop': stop, 'target': target,
                'rsi': rsi_val, 'vol_ratio': vol_ratio, 'sma20': sma20}

    if price < sma20 and 35 <= rsi_val <= 58 and vol_ratio >= 1.5:
        entry = round(price * 0.998, 2)
        stop  = round(max(sma20 * 1.01, price * 1.03), 2)
        risk  = stop - entry
        if risk <= 0 or entry < 10:
            return None
        target = round(entry - 2 * risk, 2)
        return {'symbol': symbol, 'signal': 'SHORT', 'price': price,
                'entry': entry, 'stop': stop, 'target': target,
                'rsi': rsi_val, 'vol_ratio': vol_ratio, 'sma20': sma20}

    return None

def scan():
    all_bars = get_bars_bulk()
    signals  = []
    for sym, bars in all_bars.items():
        try:
            result = analyze(sym, bars)
            if result:
                signals.append(result)
        except Exception as e:
            print(f'Scan error {sym}: {e}')
    return sorted(signals, key=lambda x: x['vol_ratio'], reverse=True)
