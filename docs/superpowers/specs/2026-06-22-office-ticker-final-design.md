# Fireblocks Office Ticker — Final Production Design

**Date:** 2026-06-22
**Status:** Locked / Production
**Owner:** dmagriso@fireblocks.com
**GitHub repo:** `dmfbks/office-ticker` (personal account, public)
**Pages base URL:** `https://dmfbks.github.io/office-ticker/`
**Supersedes:** [2026-05-28-office-ticker-design.md](2026-05-28-office-ticker-design.md) (original RSS-only design)

## Goal

Drive the LED ticker displays across three Fireblocks office floors with live financial data:

- **Top row (prices)**: brand corner (logo + greeting + time) + 5 cryptocurrencies (BTC, ETH, BNB, XRP, SOL) + 3 indices (S&P 500, NASDAQ Composite, TASE TA-35) + USD/ILS forex rate
- **Bottom row (news)**: editorially curated crypto news headlines, 12–15 at a time

All data updates automatically. No manual maintenance once the initial setup is in place. The system is designed to run indefinitely with no human in the loop.

## Hardware

Each office floor has two physical LED panel sections in each row, with different widths per floor:

| Floor | Left width | Right width |
|---|---|---|
| 8  | 3440px | 2752px |
| 9  | 3440px | 2236px |
| 10 | 3440px | 1376px |

Panel height for every section: **86px**. Confirmed via in-browser debug overlay (`window.innerWidth × window.innerHeight = 3440×86`, devicePixelRatio = 1.0). The Colorlight player respects the HTML `<meta name="viewport">` tag, so we drive layout dimensions from the URL parameter.

Each section is configured as a separate Colorlight Web/URL widget pointing at its own URL.

## Architecture

```
                    ┌────────────────────────────────────────────────────────────┐
                    │                  GitHub Pages (feed branch)                │
                    │                                                            │
                    │   indices.json    crypto.json    news.xml    prices.html   │
                    │                                              news.html     │
                    │                                              logo.svg      │
                    └────────────────────────────────────────────────────────────┘
                          ▲             ▲             ▲                  ▲
                          │             │             │                  │
                          │             │             │                  │ HTTP
                          │             │             │                  │ poll
            GH Action     │             │             │                  │
            every 10 min  │             │             │             ┌────┴──────┐
            (Yahoo v8)    │             │             │             │ Colorlight│
                          │             │             │             │ webview   │
            GH Action     │             │             │             │ (×12 per  │
            every 2 min   │             │             │             │  3 floors)│
            (CoinGecko)   │             │             │             └───────────┘
                                                      │
                                          Claude Code routine
                                          every 6h (5 RSS sources,
                                          LLM filter, push via PAT)
```

### Data pipelines

| Pipeline | Source | Output | Cadence | Mechanism |
|---|---|---|---|---|
| **Indices** | Yahoo Finance v8 `/chart` endpoint | `indices.json` | every 10 min | GitHub Action (`.github/workflows/refresh-indices.yml`) runs `fetch-indices.py`; commits to `feed` branch only when prices change |
| **Crypto** | CoinGecko free public API | `crypto.json` | every 2 min | GitHub Action (`.github/workflows/refresh-crypto.yml`) runs `fetch-crypto.py`; commits to `feed` branch only when prices change |
| **News headlines** | 5 RSS sources (CoinDesk, Cointelegraph, Decrypt, Blockworks, CryptoSlate) | `news.xml` | every 6 hours | Claude Code routine `office-ticker-news-refresh` — fetches feeds, pre-filters (8h freshness, sponsored-marker drop, Jaccard ≥ 0.7 dedupe), applies LLM editorial filter, rewrites to ≤140-char one-liners, pushes via fine-grained PAT |

Browsers poll each artifact independently. No centralized refresh logic; each panel section gets its own copy on its own schedule.

### Why server-side instead of direct browser fetches

Earlier prototypes had panels fetching CoinGecko / Yahoo directly from the browser. Problems:

- **Rate limiting**: 6 panel sections × 30s polling × Floor 8+9+10 = ~12 calls/min to CoinGecko, ~6 to Yahoo. Both hit free-tier soft limits intermittently, producing `429`s and "— —" no-data displays.
- **CORS**: Yahoo v8 returned `HTTP 429` to any request carrying an `Origin: https://dmfbks.github.io` header, even when server-side calls worked fine.
- **Inconsistency**: panels in different network conditions could show stale data while siblings showed fresh.

Moving the fetch to GitHub Actions:
- Centralizes the rate-limit budget: one API call per pipeline per cron tick, regardless of how many panels are running.
- Eliminates CORS concerns entirely.
- All panels read the same static JSON/XML file from GitHub Pages — guaranteed consistency.

Browsers never call CoinGecko or Yahoo directly. They only fetch JSON/XML/HTML files from the same GitHub Pages origin as the page itself.

## Visual format (locked)

### Prices row

```
[Logo] Happy <Weekday>! · 14:32       BTC $63,103 +0.91%   ETH $1,681 +1.70%   BNB $601.04 +1.16%   XRP $1.16 +2.33%   SOL $66.91 +2.40%       S&P 500 7,500 -0.14%   NASDAQ 25,500 +0.50%   TA-35 4,142 -0.06%   USD ₪2.97 +0.02%
                                      └────────────────────── Left section (3440px, ?part=crypto) ──────────────┘    └─────────────────── Right section (variable, ?part=indices) ───────────────┘
```

- **Static layout** — no scrolling. We exhaustively tested 11 different scrolling architectures (CSS keyframes, JS pixel-aligned, canvas blit, marquee, scrollLeft, native resolution, Web Package, etc) and confirmed that the Colorlight webview has fundamental motion-blur limits below the panel's native 60Hz refresh capability. Static rendering eliminates the entire class of smudge/jitter problems.
- **Brand corner** (left side only): logo (28px square, 90% opacity), greeting text, ` · ` dot separator with 10px margin, time `HH:MM` with blinking colon (CSS animation, on 500ms / off 500ms).
- **Items**: distributed evenly across the remaining width using `justify-content: space-around`. If items can't fit (e.g., narrow right section on Floor 10), trailing items are hidden one at a time via JS until everything fits.
- **Greeting logic**:
  - Israel time < 11:00am → `"Good morning Fireblocks!"`
  - Matches a holiday in the calendar → that greeting (e.g., `"Yom HaAtzmaut Sameach"`, `"Chag Hanukkah Sameach"`, `"Happy Pride Month"` for first week of June, etc)
  - Otherwise → `"Happy <Weekday>!"` (e.g., `"Happy Monday!"`)
- **Price format**:
  - Crypto: `$60,401` (≥$1000, integer + commas) or `$0.52` (< $1000, 2 decimals)
  - Indices (S&P/NASDAQ/TA-35): integer with commas, no prefix (`7,500`, `25,578`)
  - USD/ILS: `₪2.97` (shekel sign prefix, 2 decimals)
  - Change %: signed (`+1.84%` / `-0.92%`), 2 decimals, green text for positive / red for negative
- **Per-digit flash on price change**: when a price ticks, the JS diffs the old and new strings; characters that differ (plus the digit immediately to the right of each diff) get briefly wrapped in a `dchg-up` or `dchg-down` span that animates the color from green/red back to white over 1 second. So a `60,401 → 60,402` change flashes only the `1` and `2`.
- **Anti-dance**: `font-variant-numeric: tabular-nums` on `.price`, `.change`, `.time` so 0–9 all have the same width — digit changes produce zero layout shift.

### News row

```
[Stack: row-current is visible, row-next is positioned above viewport]
      Mt. Gox trustee moves 10,422 BTC ($739M) from cold wallets    SEC approves spot ETH ETF; first U.S. fund to trade Monday    OpenAI confidentially files for US IPO    ...
                                                                                                                                                                              
[Every 10 seconds, both rows slide down — current goes off-bottom, next slides into visible position]
```

- **Vertical-swipe rotation**: each "page" of headlines is shown for 10 seconds, then swaps via a 600ms downward CSS transform. Old page slides off bottom; new page slides in from above.
- **Page composition**: greedy fit. Each rotation builds a page by adding headlines starting from `currentIdx` until the next one wouldn't fit. Variable items per page depending on headline lengths and panel width.
- **Wrap-around**: when `currentIdx + pageSize` exceeds the headlines list, it wraps back to index 0. Every page is full.
- **Per-section offset**: left and right news panels use different starting offsets (`?offset=0` and `?offset=5`) so the two halves of the screen show different headlines at any moment (eliminates the doubled-content problem on multi-panel installs).
- **News reload**: each browser fetches `news.xml` every 5 minutes via `fetch()`. Picks up Claude routine updates automatically (the next refresh after a 6-hour cron tick lands a new `news.xml`).

### Typography

- **Font family**: Figtree (Google Fonts), weights 400–900
- **Weight**: 600 (medium-bold) across all elements — symbol, price, change, headline, time
- **Size**: 32px on all elements (matches the panel's 86px height — ~37% of vertical space, fits comfortably)
- **Color**: white text on near-black background (`#010101` to avoid Colorlight's "pure black = transparent" treatment)
- **Anti-aliasing**: standard browser anti-aliasing (`-webkit-font-smoothing: antialiased` for crisp pixel rendering on LED)

## Repo layout

```
office-ticker/   (https://github.com/dmfbks/office-ticker)
├── README.md
├── LICENSE                                # MIT
├── .gitignore                             # Python + .env*
│
├── fetch-indices.py                       # On main branch. Fetches Yahoo v8 for SPX/IXIC/TA35.TA/USDILS=X
├── fetch-crypto.py                        # On main branch. Fetches CoinGecko top-5
│
├── .github/workflows/                     # On main branch
│   ├── refresh-indices.yml                #   Cron */10, runs fetch-indices.py, commits indices.json to feed
│   └── refresh-crypto.yml                 #   Cron */2, runs fetch-crypto.py, commits crypto.json to feed
│
└── docs/superpowers/specs/                # This design doc + history
    ├── 2026-05-28-office-ticker-design.md  # Original RSS-only design (historical)
    └── 2026-06-22-office-ticker-final-design.md  # This document
```

```
feed branch (separate from main — what GitHub Pages serves):
├── prices.html         # Production prices ticker (parameterized via URL)
├── news.html           # Production news ticker (parameterized via URL)
├── logo.svg            # Fireblocks logomark (white-on-transparent)
├── indices.json        # Written every 10 min by refresh-indices.yml
├── crypto.json         # Written every 2 min by refresh-crypto.yml
└── news.xml            # Written every 6 hours by the Claude Code routine
```

The `main` branch holds code (fetch scripts, GH Action workflows, the spec docs). The `feed` branch is what GitHub Pages serves and what panels read. Actions check out `feed` to write JSON files; the Claude routine clones `feed` to write `news.xml`.

## URL parameters

Both `prices.html` and `news.html` are single files driven entirely by URL params, so all 12 panel configurations across 3 floors use exactly two files.

### prices.html

- `?w=NNNN` — panel width in pixels. Sets `<meta viewport>` and body width to exactly NNNN. **Required for each non-default panel size.**
- `?part=crypto` — left side: brand corner + 5 cryptocurrencies
- `?part=indices` — right side: 3 indices + USD/ILS (no brand corner)
- `?part=full` — both sets + brand corner (testing only, single-display case)

### news.html

- `?w=NNNN` — panel width
- `?offset=N` — starting headline index for rotation. Left sections use `offset=0`, right sections use `offset=5` so the two halves stay desynced.

## Production URLs by floor

| Floor | Position | Width | Type | URL |
|---|---|---|---|---|
| 8 | Top-Left  | 3440 | Prices | `prices.html?w=3440&part=crypto` |
| 8 | Top-Right | 2752 | Prices | `prices.html?w=2752&part=indices` |
| 8 | Bot-Left  | 3440 | News   | `news.html?w=3440&offset=0` |
| 8 | Bot-Right | 2752 | News   | `news.html?w=2752&offset=5` |
| 9 | Top-Left  | 3440 | Prices | `prices.html?w=3440&part=crypto` |
| 9 | Top-Right | 2236 | Prices | `prices.html?w=2236&part=indices` |
| 9 | Bot-Left  | 3440 | News   | `news.html?w=3440&offset=0` |
| 9 | Bot-Right | 2236 | News   | `news.html?w=2236&offset=5` |
| 10 | Top-Left  | 3440 | Prices | `prices.html?w=3440&part=crypto` |
| 10 | Top-Right | 1376 | Prices | `prices.html?w=1376&part=indices` |
| 10 | Bot-Left  | 3440 | News   | `news.html?w=3440&offset=0` |
| 10 | Bot-Right | 1376 | News   | `news.html?w=1376&offset=5` |

All URLs prefixed with `https://dmfbks.github.io/office-ticker/`.

## Operational concerns

### Failure modes (handled)

| Failure | Behavior |
|---|---|
| Yahoo Finance returns 429 / 5xx | indices.json keeps last successful values until next 10-min tick; Action exits non-zero (visible in Actions UI) |
| CoinGecko rate-limits the Action | crypto.json keeps last values; Action exits red; recovers on next 2-min tick |
| One RSS source down | Routine logs and continues with the remaining 4 (we proved this resilient when The Block + Bitcoin Magazine hit Cloudflare blocks) |
| All RSS sources down | Routine cannot generate news.xml; pre-condition fails; no commit; old news.xml stays live |
| Claude routine fails entirely | Old news.xml stays live; next 6-hour tick retries |
| GitHub push fails (auth, network) | Action / routine exits red; next tick retries |
| Panel webview loses network | Each panel keeps showing the last successfully fetched JSON/XML until network returns |
| PAT expires (90-day cycle) | Routine push fails; news goes stale. Mitigation: rotate PAT before expiry (see below) |

### Monitoring

- **GitHub Actions**: email-on-failure is the default; visible at https://github.com/dmfbks/office-ticker/actions
- **Claude routine**: status at https://claude.ai/code/routines/trig_0188w5TevLwYDDKY5ex2sMKr
- **Live data freshness**: each JSON file has `"_updated_at"`; visible at the URLs (e.g., open `indices.json` in browser)
- **No PagerDuty / Slack alerts**. The screens being briefly stale is not a paging event.

### Security posture (Fireblocks-aligned)

- **Fine-grained PAT** scoped to a single repo (`dmfbks/office-ticker`) with `contents: write` only. Stored encrypted in the Claude routine config (Anthropic's cloud) and as a local `.env` file with 600 permissions for backup.
- **PAT expires every 90 days.** Rotation procedure:
  1. Generate new PAT at https://github.com/settings/tokens?type=beta with the same scope
  2. Update routine via `/schedule` skill — replace the PAT string in the prompt's `PAT='...'` line
  3. Delete or rotate the local `.env` if applicable
- **Repo is public** by design (free Actions minutes + free Pages). Safe: contains no internal data, no customer info, no secrets in the published files. The fetch scripts are intentionally simple — no API keys for any data source.
- All HTTP calls use HTTPS with TLS verification on.

### Editorial guardrails (enforced by the LLM filter in the Claude routine)

- No price predictions, ever.
- No editorialization or "experts say".
- No mention of Fireblocks, Fireblocks customers, or named direct competitors.
- Wire-service neutral tone, ≤140 char one-liners.
- Active voice, concrete facts.

## Differences from the original 2026-05-28 design

The original design was RSS-only:
- Both prices and news rendered through Colorlight's native RSS widget
- Plain-text, single-color, no logo, no styling
- News pulled directly from 3 RSS sources, no LLM filtering
- Prices pushed to a `prices.xml` via GitHub Action

Why we diverged:

1. **The Colorlight "Web" content type accepts a URL** — discovered mid-project, enables full HTML/CSS rendering instead of plain text. This was the foundational pivot from RSS-only to HTML-based.
2. **The LED panel can't smoothly scroll webview content** — we tested 11 different scrolling architectures, all hit motion-blur ceilings. Static layout sidesteps the entire problem.
3. **The screen is 2 panels per row, not 1** — discovered mid-project (each floor's row is two separate panels with different widths). Required parameterizing the HTML by width and content-part.
4. **Per-floor sizing** — each floor has different right-panel widths (2752/2236/1376). Single parameterized file handles all 12 configurations.
5. **Twelve Data free tier didn't cover indices** — initial plan was browser-side fetch via Twelve Data API key, but their free tier excluded S&P/NASDAQ/TA-35. Pivoted to GitHub Action + Yahoo Finance v8 server-side.
6. **Rate-limit risk on browser-side CoinGecko** — moved crypto to the same GitHub Action pattern as indices.
7. **News with LLM filter via Claude Code routine** — the cloud routine (instead of a local script or GH Action+API key) enables LLM-quality filtering without the user needing an Anthropic API key.

## Known limitations and future work

### Limitations we live with

- **Hourly news refresh ceiling**: Claude routines have a 1-hour minimum cron interval. We chose every 6 hours for cost efficiency — headlines are slow-changing enough that 6h is plenty for an office ticker.
- **No order-of-magnitude anti-dance**: tabular-nums prevents layout shift when `60,401 → 60,402`, but not when `$999 → $1,000` (a digit is added). Acceptable for crypto/indices in normal trading ranges.
- **TA-35 currency quirk**: Yahoo's `^TA125.TA` symbol works but `^TA35.TA` doesn't (returns null). We use `TA35.TA` (no caret) which works. If Yahoo's symbol mapping changes, the Action will start logging failures.

### Reasonable future enhancements

| Enhancement | Effort | When to consider |
|---|---|---|
| Holiday calendar via Hebcal API | small | Once the hardcoded 2026 dates start drifting (early 2027) |
| Slack alert on persistent (>2 hour) data-stale state | small | If panels ever appear visibly stale to the office and we don't catch it |
| Custom domain (ticker.fireblocks.com) instead of `*.github.io` | medium (DNS + Pages config + IT approval) | If "branded URL" matters for any reason |
| Multi-language news (Hebrew / English split) | medium | If office composition shifts |
| Custom fonts (self-hosted instead of Google Fonts) | small | If Colorlight's network ever blocks `fonts.googleapis.com` |

## Locked architecture summary

This is the production state as of 2026-06-22:

- **Two HTML files** (`prices.html`, `news.html`) parameterized via URL, serving all 12 panel configurations across 3 floors
- **Three data pipelines**, all running automatically:
  - Indices: GitHub Action every 10 min
  - Crypto: GitHub Action every 2 min
  - News: Claude Code routine every 6 hours
- **One PAT** (90-day rotation) for the routine's GitHub push
- **One repo** (public, free tier) hosting code on `main` and serving content on `feed` via GitHub Pages
- **Zero ongoing cost**, zero manual maintenance

The system is designed to be left running indefinitely.
