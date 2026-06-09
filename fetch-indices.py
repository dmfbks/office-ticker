#!/usr/bin/env python3
"""Fetch index + forex prices from Yahoo Finance v8 and write indices.json.

Runs server-side from a GitHub Action — server-side requests aren't subject to
the browser-side CORS / 429 issues we saw on Yahoo.

Output schema (indices.json):
  {
    "<DisplaySymbol>": { "price": <float>, "previous_close": <float> },
    ...
    "_updated_at": "<ISO8601 timestamp>"
  }
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

# Maps the display label (used in the page's ITEMS array) to the Yahoo symbol
SYMBOLS = {
    'S&P 500': '^GSPC',
    'NASDAQ':  '^NDX',
    'TA-35':   'TA35.TA',
    'USD':     'USDILS=X',     # USD/ILS forex rate; page formats this as "₪X.XX"
}

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15'


def fetch_yahoo(symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main() -> None:
    result: dict = {}
    fail_count = 0
    for display_name, yahoo_sym in SYMBOLS.items():
        try:
            data = fetch_yahoo(yahoo_sym)
            results = data.get('chart', {}).get('result')
            if not results:
                print(f"FAIL {display_name} ({yahoo_sym}): empty result", file=sys.stderr)
                fail_count += 1
                continue
            meta = results[0].get('meta', {})
            price = meta.get('regularMarketPrice')
            prev = meta.get('chartPreviousClose')
            if price is None or prev is None:
                print(f"FAIL {display_name} ({yahoo_sym}): null price/prev", file=sys.stderr)
                fail_count += 1
                continue
            result[display_name] = {'price': float(price), 'previous_close': float(prev)}
            print(f"OK   {display_name}: {price} (prev {prev})", file=sys.stderr)
        except Exception as e:
            print(f"FAIL {display_name} ({yahoo_sym}): {e}", file=sys.stderr)
            fail_count += 1

    result['_updated_at'] = datetime.now(timezone.utc).isoformat()

    with open('indices.json', 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(f"Wrote {len(result) - 1} items to indices.json ({fail_count} failures)", file=sys.stderr)


if __name__ == '__main__':
    main()
