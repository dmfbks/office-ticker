#!/usr/bin/env python3
"""Fetch BTC/ETH/BNB/XRP/SOL prices + sparkline from CoinGecko and write crypto.json.

Uses /coins/markets with sparkline=true to get price, 24h change, AND the
last-7-days hourly sparkline in a single call. We trim the sparkline to the
last 24 hourly points so it reflects today's price action, not a week's.

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

SPARK_POINTS = 24  # last 24 hourly points ≈ 1 day of price action

URL = (
    'https://api.coingecko.com/api/v3/coins/markets'
    '?vs_currency=usd'
    f'&ids={",".join(COIN_IDS.values())}'
    '&order=market_cap_desc'
    '&sparkline=true'
    '&price_change_percentage=24h'
)
UA = 'Mozilla/5.0 (office-ticker; fireblocks-internal)'


def main() -> None:
    req = urllib.request.Request(URL, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    by_id = {item['id']: item for item in data}
    result: dict = {}
    for symbol, cg_id in COIN_IDS.items():
        d = by_id.get(cg_id)
        if not d:
            print(f"FAIL {symbol} ({cg_id}): missing from response", file=sys.stderr)
            continue
        price = float(d['current_price'])
        change = float(d.get('price_change_percentage_24h') or 0)
        spark_full = (d.get('sparkline_in_7d') or {}).get('price') or []
        spark = [round(float(p), 6) for p in spark_full[-SPARK_POINTS:]]
        result[symbol] = {
            'price': price,
            'change_24h': change,
            'spark': spark,
        }
        print(f"OK   {symbol}: ${price}  24h {change:.2f}%  spark[{len(spark)}]", file=sys.stderr)

    result['_updated_at'] = datetime.now(timezone.utc).isoformat()

    with open('crypto.json', 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()

# last-nudged: 2026-07-24T00:07:27Z (staleness-watchdog)
