# Fireblocks Office Crypto Ticker — Design

**Date:** 2026-05-28
**Status:** Design — pending user review before plan
**Owner:** dmagriso@fireblocks.com
**GitHub repo:** `dmfbks/office-ticker` (personal account, public)
**Pages base URL:** `https://dmfbks.github.io/office-ticker/`

## Goal

Drive the horizontal LED display in the Fireblocks office with two live RSS feeds:

1. **Prices** — BTC, ETH, SOL, XRP with current USD price and 24h signed % change.
2. **News** — a curated, lightly-editorialized one-liner stream from CoinDesk, The Block, and Cointelegraph.

The screen is managed by Colorlight Cloud (`sea.colorlightcloud.com`), which polls RSS URLs and displays the items as scrolling text. Two separate widgets on the screen consume the two feeds independently.

## Constraints discovered during testing

A throwaway test phase (see `crypto-ticker-test/`) established the following facts about Colorlight's RSS widget. The production design works within these:

| # | Fact | Design implication |
|---|---|---|
| 1 | Widget is strictly text-only. Ignores `<enclosure>`, `<media:content>`, `<itunes:image>`, and HTML `<img>` tags inside CDATA `<description>`. | No images, no icons. Pure text format. |
| 2 | Widget concatenates `<title>` + space + `<description>` into one rendered string. | Don't use `<description>` — put everything in `<title>`. |
| 3 | Widget auto-prefixes a timestamp parsed from `<pubDate>` and/or `<lastBuildDate>`. | Omit both. Items have only `<title>` and `<guid>`. |
| 4 | Emoji rendering is inconsistent: 🔴 renders, 🟢 renders as tofu, 📈/📉 render as low-resolution pixelated squares. | Avoid emoji. Use ASCII/Unicode-geometric symbols only — and even those add little value. |
| 5 | Default poll interval is **600s (10 min)**. Configurability not confirmed. | Match the update cadence to the floor: prices every 10 min, not 5. |
| 6 | The panel is monochrome white-on-black. No per-item color via XML. | No "red for down / green for up." Convey direction via the `+`/`-` sign in the % field. |
| 7 | Unicode geometric arrows `▲ ▼` render small and clean. Bullet characters `•`, `·`, `○`, `●` all render. | Available if needed, but the final design uses neither — whitespace gaps proved cleanest. |

## Visual format (final)

Both feeds use the same scheme: title-only, no symbols, whitespace separator between items.

**Prices feed** — `prices.xml`:

```
       BTC  $67,432  +1.84%       ETH  $3,521  -0.92%       SOL  $164.27  +3.47%       XRP  $0.52  -2.13%
```

Per-item title format:

```
       <SYMBOL>  $<PRICE>  <SIGNED_PCT>%
```

- **Leading whitespace** (7 spaces) provides the visual separator between items as the ticker scrolls.
- **`<SYMBOL>`** is uppercase 3-letter ticker (BTC, ETH, SOL, XRP).
- **`<PRICE>`** is USD price with thousands separator. No decimals for BTC and ETH. Two decimals for SOL and XRP.
- **`<SIGNED_PCT>`** is the 24h percent change with explicit sign (`+1.84` or `-0.92`), two decimal places.

**News feed** — `news.xml`:

```
       SEC approves spot ETH ETF; first U.S. fund to trade Monday under ticker ETHA       Coinbase posts $1.6B Q1 revenue, up 24% YoY...
```

Per-item title format:

```
       <REWRITTEN_HEADLINE>
```

- Same leading whitespace separator.
- `<REWRITTEN_HEADLINE>` is the LLM-rewritten one-liner. Max 140 chars. Wire-service neutral tone.

Each `<item>` carries only `<title>` and `<guid>`. No description, no pubDate, no link, no enclosure.

## Architecture

Two completely independent pipelines, each publishing one XML file to the same GitHub Pages repo. If either pipeline fails, the other keeps running.

```
┌─────────────────┐
│ GitHub Action   │  every 10 min
│ prices.yml      │ ──▶  CoinGecko (BTC/ETH/SOL/XRP)
│                 │      │ fallback: Coinbase, Binance public tickers
│                 │      ▼
│                 │   build prices.xml (RSS 2.0, title-only)
│                 │      │
│                 │      ▼
│                 │   force-push to orphan `feed` branch
└─────────────────┘      │
                         ▼
                  https://dmfbks.github.io/office-ticker/prices.xml

┌─────────────────┐
│ Claude Code     │  every 30 min  (via /schedule routine)
│ scheduled       │ ──▶  CoinDesk, The Block, Cointelegraph RSS
│ routine         │      │
│                 │      ▼
│                 │   dedupe + drop sponsored/stale
│                 │      │
│                 │      ▼
│                 │   LLM filter + rewrite (≤140 chars, ≤10 items)
│                 │      │
│                 │      ▼
│                 │   build news.xml
│                 │      │
│                 │      ▼
│                 │   force-push to orphan `feed` branch
└─────────────────┘      │
                         ▼
                  https://dmfbks.github.io/office-ticker/news.xml

           Colorlight Cloud (two widgets) polls both URLs every 600s
```

**Key properties:**

- No secrets handled by us. Prices uses GitHub Actions' built-in `GITHUB_TOKEN`. News uses Claude Code's existing auth — no Anthropic API key.
- Repo is **public** (free Actions minutes, free Pages, no Fireblocks-internal data in it).
- The `feed` branch is **orphan and force-pushed** each refresh — no history bloat. The `main` branch holds the code and is normal git history.

## Repo layout

```
office-ticker/
├── README.md                          # overview + URLs + how to update
├── LICENSE                            # MIT
├── .github/
│   └── workflows/
│       └── prices.yml                 # cron every 10 min
├── src/
│   ├── prices/
│   │   ├── fetch.py                   # CoinGecko + fallback chain
│   │   ├── format.py                  # build prices.xml
│   │   └── publish.py                 # write + force-push to feed branch
│   └── news/
│       ├── fetch.py                   # 3 source feeds, dedupe, pre-filter
│       ├── filter_rewrite.py          # LLM step
│       ├── format.py                  # build news.xml
│       └── publish.py                 # write + force-push to feed branch
├── prompts/
│   └── news-rewrite.md                # the LLM prompt — versioned
├── tests/
│   ├── test_prices_format.py          # golden-file XML tests
│   ├── test_news_filter.py            # fixture headlines → expected output
│   └── fixtures/                      # CoinGecko + RSS sample responses
├── docs/
│   └── superpowers/specs/             # this design + future specs
├── pyproject.toml                     # pinned deps
├── uv.lock                            # lockfile committed (uv-managed)
├── .gitignore                         # standard Python + .env*
└── .env.example                       # placeholders only
```

**Language:** Python. Native `xml.etree.ElementTree` for XML build; `feedparser` for RSS parsing; `requests` for HTTP. No new infrastructure beyond what GitHub Actions provides out of the box.

## Prices pipeline

**Trigger:** GitHub Action on cron `*/10 * * * *` (every 10 min, matching the Colorlight poll interval).

**Steps each run:**

1. **Fetch** — single batched call:
   ```
   GET https://api.coingecko.com/api/v3/simple/price
       ?ids=bitcoin,ethereum,solana,ripple
       &vs_currencies=usd
       &include_24hr_change=true
   ```
   No auth. Free tier comfortably covers 6 calls/hour.

2. **Fallback chain** — if CoinGecko returns non-200 or times out (>5s), try in order:
   - Coinbase public spot price endpoint (`/v2/prices/<symbol>-USD/spot`)
   - Binance public 24hr ticker (`/api/v3/ticker/24hr?symbol=<symbol>USDT`)
   All three are keyless. If all three fail, **keep the previous `prices.xml`** in place (no push), exit non-zero so the Action shows red in the UI.

3. **Format** — build `prices.xml` as RSS 2.0:
   - Channel: `<title>`, `<link>`, `<description>`, `<language>en-us</language>`, `<ttl>10</ttl>`. No `<lastBuildDate>`.
   - One `<item>` per coin (4 total), in order: BTC, ETH, SOL, XRP.
   - Each item has `<title>` (formatted as above) and `<guid isPermaLink="false">`. Guid is stable per coin (e.g., `prices-btc`) — the widget uses it for dedup.

4. **Stale-data safeguard** — if the previous successful run was >30 min ago (timestamp tracked in a small JSON file on the `feed` branch), prepend a 5th item: `       Prices delayed — last update <N>m ago`. Lets viewers see when the feed has stalled without us building a separate alerting system.

5. **Publish** — write `prices.xml` to a worktree of the `feed` branch, then `git push --force` to origin. The push step uses the runner's built-in `GITHUB_TOKEN` (scoped to push to this single repo only — no broader credentials).

## News pipeline

**Trigger:** Claude Code `/schedule` routine on cron `*/30 * * * *` (every 30 min).

**Steps each run:**

1. **Fetch** — pull RSS from all three sources in parallel with a 5-second per-source timeout. If a source fails, continue with the remaining two. Sources:
   - CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/`
   - The Block: `https://www.theblock.co/rss.xml`
   - Cointelegraph: `https://cointelegraph.com/rss`

2. **Dedupe + pre-filter** — across all sources:
   - Drop items older than 6 hours (`pubDate`-based).
   - Drop near-duplicates across sources (case-insensitive Jaccard ≥ 0.8 on tokenized titles).
   - Drop items with sponsored-content markers in title or URL (`/press-release/`, `/sponsored/`, "Press Release:", "Sponsored:", "PR:").

   Expected output: ~20–40 candidate items per run.

3. **LLM filter + rewrite** — single Claude Code call with the candidate list and the prompt from `prompts/news-rewrite.md`. The prompt instructs Claude to:

   - **Filter out**:
     - Pure price-prediction / "X could 10x" content
     - Single-token listing announcements for non-major tokens
     - Op-eds and personal-opinion pieces
     - Stories that wouldn't be relevant to an institutional crypto-infra audience
   - **Rewrite the survivors** to ≤140 chars, wire-service neutral. No editorialization. No price predictions. No mention of Fireblocks, Fireblocks customers, or named competitors. If uncertain whether to drop, drop.
   - **Return** a JSON array of strings, max 10 items, ordered by editorial significance.

   Output is validated as JSON before use. Malformed output → keep previous `news.xml`, log, exit non-zero.

4. **Format** — build `news.xml`. One `<item>` per surviving headline. Each item has only `<title>` and `<guid>`. Guid is `sha256` of the original article URL — stable across runs so the widget can dedupe items it's already shown.

5. **Publish** — same orphan `feed` branch, force-push.

## Operational concerns

**Failure modes (handled):**

| Failure | Behavior |
|---|---|
| CoinGecko + Coinbase + Binance all down | Don't push. Previous `prices.xml` remains live. Action exits red. |
| Single news source down | Continue with remaining two. Log the failure. |
| All three news sources down | Don't push. Previous `news.xml` remains live. Routine exits with error. |
| LLM returns malformed JSON | Don't push. Previous `news.xml` remains live. Log and exit. |
| GitHub push fails (rare — auth, network) | Next run retries. Current file stays live. |
| Prices pipeline frozen >30 min | Stale-data warning prepended to next successful push. |

**Monitoring:**

- GitHub Actions: default email-on-failure stays on. No PagerDuty/Slack.
- Repo README carries a job-status badge for at-a-glance health checks.
- No metrics dashboard. The screen breaking is not a paging event.

**Security posture (Fireblocks-aligned):**

- **No hardcoded secrets.** Only credential used is `GITHUB_TOKEN` (auto-injected by Actions, scoped to single repo).
- `pyproject.toml` pins exact versions. Lockfile committed. CI runs `pip-audit` on every push.
- `.gitignore` excludes `.env*`, `*.pem`, `secrets*`. `.env.example` ships with placeholder values only.
- All HTTP calls use HTTPS with TLS verification on.
- News rewrite prompt explicitly forbids inventing facts, predicting prices, or mentioning Fireblocks / customers / competitors. (The screen carries implicit Fireblocks endorsement.)
- Repo is **public** by design (so we get free Actions + free Pages). Public is safe: no internal data, no customer info, no secrets in the published content.

**Editorial guardrails (baked into the LLM prompt):**

- No price predictions, ever.
- No promotional language about any project.
- No mention of Fireblocks, Fireblocks customers, or competitors by name.
- When uncertain, drop.

## What's explicitly NOT in scope

- No user-facing UI or dashboard.
- No history archive (`feed` branch is force-pushed; old states irrelevant).
- No analytics on what the screen shows.
- No additional coins or sources beyond the four/three listed.
- No custom domain. Default `*.github.io` URL.
- No Slack/PagerDuty/etc. alerts.
- No color / per-item styling (the widget doesn't support it).
- No images / icons / charts (the widget doesn't support them).

## Open questions (non-blocking — to confirm during setup)

- **Polling interval ceiling**: confirm via the Colorlight widget config whether 600s is the floor or just the default. If lower is allowed, we may revisit the 10-min price cadence. The current design works at the floor; faster is a bonus.
- **Claude Code `/schedule` availability**: confirm `/schedule` works in your Fireblocks-managed Claude Code subscription. If unavailable, we fall back to running the news job as a second GitHub Action (uses more Actions minutes but still free on public repos).
