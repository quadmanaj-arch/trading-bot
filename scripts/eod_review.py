from datetime import datetime
import utils

def run():
    acct      = utils.alp_get('/account')
    positions = utils.alp_get('/positions')
    orders    = utils.alp_get('/orders?status=all&limit=50&direction=desc')

    equity    = float(acct['equity'])
    last_eq   = float(acct['last_equity'])
    day_pnl   = equity - last_eq
    day_pnl_p = day_pnl / last_eq * 100 if last_eq > 0 else 0
    today     = datetime.now().strftime('%Y-%m-%d')
    today_fmt = datetime.now().strftime('%m/%d')

    # Count today's filled orders
    today_fills = [o for o in orders if o['status'] == 'filled' and today in (o.get('filled_at') or '')]
    sells = [o for o in today_fills if o['side'] == 'sell']

    # Close options with DTE <= 3
    closes = []
    for pos in positions:
        sym    = pos['symbol']
        is_opt = any(c.isdigit() for c in sym)
        if not is_opt:
            continue
        try:
            # OCC format: SYMBOLyymmddC/P00000000
            # Find where digits start for the date portion
            i = next(k for k, c in enumerate(sym) if c.isdigit())
            exp_str = sym[i:i+6]
            exp_date = datetime.strptime('20' + exp_str, '%Y%m%d')
            dte = (exp_date - datetime.now()).days
            if dte <= 3:
                qty = int(abs(float(pos['qty'])))
                utils.alp_post('/orders', {'symbol': sym, 'qty': str(qty), 'side': 'sell', 'type': 'market', 'time_in_force': 'day'})
                closes.append(f'{sym} (DTE {dte})')
                print(f'Closed {sym} — DTE {dte} <= 3')
        except Exception as e:
            print(f'Could not check DTE for {sym}: {e}')

    # Cancel remaining day orders, preserve GTC stops
    open_orders = utils.alp_get('/orders?status=open')
    for o in open_orders:
        if o.get('time_in_force') == 'day':
            utils.alp_delete(f'/orders/{o["id"]}')

    # Current overnight holds
    updated  = utils.alp_get('/positions')
    holds    = []
    for p in updated:
        plp = float(p['unrealized_plpc']) * 100
        holds.append(f"{p['symbol']}: {plp:+.1f}%")

    holds_str  = ', '.join(holds) if holds else 'FLAT'
    closes_str = ', '.join(closes) if closes else 'None'

    msg = (
        f"Equity: ${equity:.2f} | Day: ${day_pnl:+.2f} ({day_pnl_p:+.2f}%)\n"
        f"Trades: {len(today_fills)} | EOD closes: {closes_str}\n"
        f"Overnight: {holds_str}"
    )
    utils.pushover(f'📋 EOD {today_fmt}', msg)

    # Journal entry
    entry = (
        f"\n### {today} — Day P&L: ${day_pnl:+.2f} ({day_pnl_p:+.2f}%)\n\n"
        f"**Equity:** ${equity:.2f} (opened ${last_eq:.2f})\n"
        f"**Fills today:** {len(today_fills)} | **EOD closes:** {closes_str}\n"
        f"**Overnight holds:** {holds_str}\n\n---\n"
    )
    try:
        utils.journal_append(entry, f'EOD {today}')
        print('Journal updated')
    except Exception as e:
        print(f'Journal failed: {e}')

    print(f'EOD done | Equity: ${equity:.2f} | Day: ${day_pnl:+.2f}')

if __name__ == '__main__':
    run()
