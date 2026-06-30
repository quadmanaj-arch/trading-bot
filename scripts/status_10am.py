from datetime import datetime
import utils

def run():
    acct      = utils.alp_get('/account')
    positions = utils.alp_get('/positions')

    equity    = float(acct['equity'])
    last_eq   = float(acct['last_equity'])
    day_pnl   = equity - last_eq
    day_pnl_p = day_pnl / last_eq * 100 if last_eq > 0 else 0
    loss_pct  = max(0, -day_pnl / last_eq * 100) if last_eq > 0 else 0

    if loss_pct >= 8:
        status = 'HALTED ⛔'
    elif loss_pct >= 5:
        status = 'CAUTION ⚠️'
    else:
        status = 'CLEAR ✅'

    lines = [
        f"Equity: ${equity:.2f} | Day: ${day_pnl:+.2f} ({day_pnl_p:+.2f}%)",
        f"Status: {status}",
        f"Buying Power: ${float(acct['buying_power']):.2f}",
        "",
        "Positions:"
    ]

    if positions:
        for p in positions:
            pl  = float(p['unrealized_pl'])
            plp = float(p['unrealized_plpc']) * 100
            lines.append(f"  {p['symbol']}: {plp:+.2f}% (${pl:+.2f})")
    else:
        lines.append("  No open positions")

    today = datetime.now().strftime('%m/%d')
    utils.pushover(f'📊 10AM STATUS {today}', '\n'.join(lines))

if __name__ == '__main__':
    run()
