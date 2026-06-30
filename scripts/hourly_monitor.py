import sys
from datetime import datetime, timezone
import utils, scan

def run():
    now_et = datetime.now()
    print(f"=== Hourly Monitor {now_et.strftime('%Y-%m-%d %H:%M')} UTC ===")

    # ── STEP 1: Daily loss gate ──────────────────────────────────────────────
    acct       = utils.alp_get('/account')
    equity     = float(acct['equity'])
    last_eq    = float(acct['last_equity'])
    day_pnl    = equity - last_eq
    day_pnl_p  = day_pnl / last_eq * 100 if last_eq > 0 else 0
    loss_pct   = max(0, -day_pnl / last_eq) if last_eq > 0 else 0

    print(f"Equity: ${equity:.2f} | Day P&L: ${day_pnl:+.2f} ({day_pnl_p:+.2f}%) | Loss: {loss_pct*100:.2f}%")

    if loss_pct >= 0.08:
        utils.alp_delete('/orders')
        utils.pushover('⛔ TRADING HALTED',
            f'Daily loss limit hit.\nLoss: {loss_pct*100:.1f}% (limit: 8%)\nEquity: ${equity:.2f}\nAll orders cancelled. No new trades today.',
            priority=1)
        print("HALTED")
        return

    caution    = loss_pct >= 0.05
    size_mult  = 0.5 if caution else 1.0
    if caution:
        print("CAUTION mode: position sizes halved")

    # ── STEP 2: Manage existing positions ───────────────────────────────────
    positions   = utils.alp_get('/positions')
    open_orders = utils.alp_get('/orders?status=open')
    actions     = []

    for pos in positions:
        sym    = pos['symbol']
        is_opt = any(c.isdigit() for c in sym)
        qty    = float(pos['qty'])
        entry  = float(pos['avg_entry_price'])
        curr   = float(pos['current_price'])

        if is_opt:
            # Options auto-exit rules
            cost     = float(pos.get('avg_entry_price', 0))
            gain_pct = (curr - cost) / cost if cost > 0 else 0

            if gain_pct <= -0.50:
                r = utils.alp_post('/orders', {'symbol': sym, 'qty': str(int(abs(qty))), 'side': 'sell', 'type': 'market', 'time_in_force': 'day'})
                actions.append(f'🔴 OPTIONS STOP\n{sym} — 50% loss rule\nP&L: {gain_pct*100:.1f}%')
            elif gain_pct >= 2.0:
                r = utils.alp_post('/orders', {'symbol': sym, 'qty': str(int(abs(qty))), 'side': 'sell', 'type': 'market', 'time_in_force': 'day'})
                actions.append(f'🟢 OPTIONS TARGET\n{sym} — +200% hit, closed all\nP&L: +{gain_pct*100:.1f}%')
            elif gain_pct >= 1.0:
                half = max(1, int(abs(qty) // 2))
                r = utils.alp_post('/orders', {'symbol': sym, 'qty': str(half), 'side': 'sell', 'type': 'market', 'time_in_force': 'day'})
                actions.append(f'🟡 OPTIONS PROFIT\n{sym} — +100% hit, sold 50%\nP&L: +{gain_pct*100:.1f}%')

        elif qty > 0:
            # Stock trailing stop rules (long only)
            gain_pct = (curr - entry) / entry
            new_stop = None

            if gain_pct >= 0.10:
                new_stop = round(entry * 1.07, 2)
            elif gain_pct >= 0.06:
                new_stop = round(entry * 1.02, 2)
            elif gain_pct >= 0.03:
                new_stop = round(entry, 2)

            if new_stop:
                for o in open_orders:
                    if o['symbol'] == sym and o['type'] in ('stop', 'stop_limit'):
                        utils.alp_delete(f'/orders/{o["id"]}')
                utils.alp_post('/orders', {'symbol': sym, 'qty': str(int(qty)), 'side': 'sell', 'type': 'stop', 'time_in_force': 'gtc', 'stop_price': str(new_stop)})
                actions.append(f'📌 STOP MOVED\n{sym} stop → ${new_stop:.2f}\nCurrent: ${curr:.2f} | Gain: +{gain_pct*100:.1f}%')

            elif gain_pct < -0.03:
                # Stop may have failed — force close
                r = utils.alp_post('/orders', {'symbol': sym, 'qty': str(int(qty)), 'side': 'sell', 'type': 'market', 'time_in_force': 'day'})
                actions.append(f'🔴 FORCE CLOSE\n{sym} — stop failure, manual close\nLoss: {gain_pct*100:.1f}%')

    # ── STEP 3: Scan for new setups ─────────────────────────────────────────
    if len(positions) < 5:
        held    = {p['symbol'] for p in positions}
        pending = {o['symbol'] for o in open_orders if o['status'] in ('new', 'pending_new', 'accepted')}
        occupied = held | pending

        signals = [s for s in scan.scan() if s['symbol'] not in occupied]

        for sig in signals[:2]:
            if len(positions) >= 5:
                break

            sym   = sig['symbol']
            entry = sig['entry']
            stop  = sig['stop']
            tgt   = sig['target']
            risk  = abs(entry - stop)
            side  = 'buy' if sig['signal'] == 'BUY' else 'sell'

            shares = int((0.03 * equity * size_mult) / risk)
            shares = min(shares, int((0.20 * equity) / entry))

            if shares < 1:
                print(f'Skipping {sym}: position too small at ${equity:.2f} equity')
                continue

            body = {
                'symbol': sym, 'qty': str(shares), 'side': side,
                'type': 'limit', 'time_in_force': 'gtc',
                'limit_price': str(entry),
                'order_class': 'bracket',
                'stop_loss': {'stop_price': str(stop)},
                'take_profit': {'limit_price': str(tgt)}
            }
            r = utils.alp_post('/orders', body)

            if 'error' not in r:
                risk_d = shares * risk
                actions.append(
                    f'🟢 NEW TRADE\n{sym} {"BUY" if side=="buy" else "SELL"} {shares} @ ${entry}\n'
                    f'Stop: ${stop} | Target: ${tgt}\n'
                    f'Risk: ${risk_d:.2f} ({risk_d/equity*100:.1f}%)\n'
                    f'RSI: {sig["rsi"]:.0f} | Vol: {sig["vol_ratio"]:.1f}x avg'
                )
                positions.append({'symbol': sym})
            else:
                print(f'Order error {sym}: {r}')

    # ── STEP 4: Notifications ────────────────────────────────────────────────
    for a in actions:
        utils.pushover('💼 Wealth Advisor', a)

    print(f'\nPositions: {len(positions)} | Actions: {len(actions)}')
    print(f'Equity: ${equity:.2f} | Day: ${day_pnl:+.2f} ({day_pnl_p:+.2f}%)')

if __name__ == '__main__':
    run()
