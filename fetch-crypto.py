#!/usr/bin/env python3
"""Fetch BTC/ETH/BNB/XRP/SOL prices from CoinGecko and write crypto.json.

Server-side fetch eliminates the per-panel IP rate-limit risk.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

COIN_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'BNB': 'binancecoin',
    'XRP': 'ripple',
    'SOL': 'solana',
}

URL = (
    'https://api.coingecko.com/api/v3/simple/price'
    f'?ids={",".join(COIN_IDS.values())}'
    '&vs_currencies=usd&include_24hr_change=true'
)
UA = 'Mozilla/5.0 (office-ticker; fireblocks-internal)'


def main() -> None:
    req = urllib.request.Request(URL, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    result: dict = {}
    for symbol, cg_id in COIN_IDS.items():
        d = data.get(cg_id)
        if not d:
            print(f"FAIL {symbol} ({cg_id}): missing from response", file=sys.stderr)
            continue
        result[symbol] = {
            'price': float(d['usd']),
            'change_24h': float(d.get('usd_24h_change') or 0),
        }
        print(f"OK   {symbol}: ${d['usd']}  24h {d.get('usd_24h_change'):.2f}%", file=sys.stderr)

    result['_updated_at'] = datetime.now(timezone.utc).isoformat()

    with open('crypto.json', 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
