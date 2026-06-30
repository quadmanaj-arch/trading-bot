from datetime import datetime
import utils

def run():
    acct      = utils.alp_get('/account')
    positions = utils.alp_get('/positions')

    equity = float(acct['equity'])
    bp     = float(acct['buying_power'])
    today  = datetime.now().strftime('%m/%d/%Y')

    pos_lines = []
    for p in positions:
        pl  = float(p['unrealized_pl'])
        plp = float(p['unrealized_plpc']) * 100
        pos_lines.append(f"  {p['symbol']}: {plp:+.1f}% (${pl:+.2f})")

    pos_section = '\n'.join(pos_lines) if pos_lines else '  No overnight holds'
    risk_per_trade = equity * 0.03

    msg = (
        f"Equity: ${equity:.2f} | BP: ${bp:.2f}\n"
        f"Max risk/trade: ${risk_per_trade:.2f}\n\n"
        f"Overnight positions:\n{pos_section}\n\n"
        f"Scanning market at open.\n"
        f"Wait for first 15-min range before entry."
    )

    utils.pushover(f'☀️ PRE-MARKET {today}', msg)
    print(f"Pre-market sent | Equity: ${equity:.2f}")

if __name__ == '__main__':
    run()
