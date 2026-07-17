#!/usr/bin/env python3
"""Fetch index + forex prices from Yahoo Finance v8 and write indices.json.

Runs server-side from a GitHub Action — server-side requests aren't subject to
the browser-side CORS / 429 issues we saw on Yahoo.

For each symbol we make TWO calls:
  1. interval=1d&range=2d  — current price + previous-day close (for the change badge)
  2. interval=15m&range=1d — intraday sparkline (~26 15-min points per session)

If the intraday call fails or returns no points (weekend, holiday), we fall back
to a 5-day daily series so the sparkline still has shape.

Output schema (indices.json):
  {
    "<DisplaySymbol>": {
      "price": <float>,
      "previous_close": <float>,
      "spark": [<float>, ...]
    },
    ...
    "_updated_at": "<ISO8601 timestamp>"
  }
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

SYMBOLS = {
    'S&P 500': '^GSPC',
    'NASDAQ':  '^IXIC',
    'TA-35':   'TA35.TA',
    'USD':     'USDILS=X',
}

SPARK_MAX_POINTS = 32  # cap so the JSON stays compact

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15'


def fetch_yahoo(symbol: str, interval: str, range_: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_}"
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def extract_closes(data: dict) -> list:
    """Pull the close[] array from a chart response, drop nulls, return floats."""
    results = data.get('chart', {}).get('result') or []
    if not results:
        return []
    quote = results[0].get('indicators', {}).get('quote', [{}])[0]
    closes = quote.get('close') or []
    return [float(c) for c in closes if c is not None]


def fetch_spark(symbol: str) -> list:
    """Intraday sparkline; fall back to daily if the intraday call is empty."""
    try:
        data = fetch_yahoo(symbol, '15m', '1d')
        closes = extract_closes(data)
        if closes:
            return [round(c, 4) for c in closes[-SPARK_MAX_POINTS:]]
    except Exception as e:
        print(f"WARN intraday fetch failed for {symbol}: {e}", file=sys.stderr)
    try:
        data = fetch_yahoo(symbol, '1d', '5d')
        closes = extract_closes(data)
        if closes:
            return [round(c, 4) for c in closes[-SPARK_MAX_POINTS:]]
    except Exception as e:
        print(f"WARN daily fallback failed for {symbol}: {e}", file=sys.stderr)
    return []


def main() -> None:
    result: dict = {}
    fail_count = 0
    for display_name, yahoo_sym in SYMBOLS.items():
        try:
            data = fetch_yahoo(yahoo_sym, '1d', '2d')
            results = data.get('chart', {}).get('result')
            if not results:
                print(f"FAIL {display_name} ({yahoo_sym}): empty result", file=sys.stderr)
                fail_count += 1
                continue
            r = results[0]
            meta = r.get('meta', {})
            # Prefer the chart's close[] array — meta.regularMarketPrice lags
            # for some international indices (notably TASE TA-35).
            closes = [c for c in (r.get('indicators', {}).get('quote', [{}])[0].get('close') or []) if c is not None]
            if len(closes) >= 2:
                price = float(closes[-1])
                prev = float(closes[-2])
                source = 'chart'
            else:
                price = meta.get('regularMarketPrice')
                prev = meta.get('chartPreviousClose')
                if price is None or prev is None:
                    print(f"FAIL {display_name} ({yahoo_sym}): no usable data", file=sys.stderr)
                    fail_count += 1
                    continue
                price = float(price)
                prev = float(prev)
                source = 'meta'

            spark = fetch_spark(yahoo_sym)
            # If we got nothing from the intraday/daily call, fall back to a flat
            # 2-point spark from prev → current so the chart still renders.
            if not spark:
                spark = [round(prev, 4), round(price, 4)]

            result[display_name] = {
                'price': price,
                'previous_close': prev,
                'spark': spark,
            }
            print(f"OK   {display_name}: {price} (prev {prev}) [{source}]  spark[{len(spark)}]", file=sys.stderr)
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

# last-nudged: 2026-07-17T23:58:10Z (staleness-watchdog)
