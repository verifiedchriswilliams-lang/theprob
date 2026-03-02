# CLAUDE.md — The Prob: AI Collaboration Guide

> Read this at the start of every session. Update the TODO section before ending each session.

---

## What Is The Prob

**URL:** https://theprobnewsletter.com  
**Repo:** https://github.com/verifiedchriswilliams-lang/theprob  
**Stack:** Static HTML/JS site hosted on GitHub Pages + Python data pipeline + Beehiiv newsletter  
**Mission:** Help prediction market traders make money by surfacing the most actionable market moves across Polymarket and Kalshi.

---

## Repo Structure

```
theprob/
├── index.html              # Home page
├── business.html           # Finance/Business category page
├── sports.html             # Sports category page
├── tech.html               # Technology category page
├── culture.html            # Culture category page
├── politics.html           # Politics category page
├── news.html               # News page
├── VOICE.md                # Editorial voice guide for AI-generated copy
├── CLAUDE.md               # This file
├── data/
│   ├── markets.json        # PRIMARY data file — rebuilt every hour by GitHub Actions
│   └── kalshi_snapshot.json # Kalshi price snapshot for delta calculation (committed hourly)
├── scripts/
│   ├── fetch_markets.py    # Main data pipeline (Polymarket + Kalshi fetch, hero/mover selection)
│   └── send_newsletter.py  # Beehiiv newsletter generation and send
├── newsletter/             # Newsletter templates and assets
└── .github/workflows/
    └── fetch-markets.yml   # Hourly GitHub Actions workflow
```

---

## Data Pipeline — fetch_markets.py

### How It Works
Runs hourly via GitHub Actions. Fetches ~2000+ markets from Polymarket and Kalshi, filters/scores/selects hero + movers + ticker, writes `data/markets.json`.

### Key Constants (top of file)
- `HERO_MIN_VOLUME = 250_000` — minimum $ total volume for hero eligibility
- `HERO_SPORTS_MIN_VOLUME = 25_000_000` — sports markets need massive volume to be hero
- `HERO_MIN_CHANGE_PTS = 3.0` — must have moved 3pts in 24h to enter hero pool
- `HERO_REPEAT_PENALTY = 15` — pts deducted from hero score for recently-won topics
- `KALSHI_MIN_VOL = 1_000` — minimum $ volume for Kalshi markets

### Data Flow
1. Fetch Polymarket (3 pages by 24h volume + 2 pages by total volume)
2. Deduplicate by event slug
3. **Date-ladder consolidation** — collapses "US strikes Iran by Feb 27/Mar 1/Mar 8" into single best contract
4. **Range-bucket consolidation** — collapses "PPLE seats: <120 / 120-134 / 135+" into highest-probability bucket
5. Fetch Kalshi (general + Technology category)
6. Load `kalshi_snapshot.json` → compute real `change_pts` for all 442 Kalshi markets (API returns `previous_price: 0`)
7. Rebuild `all_markets` with corrected Kalshi deltas
8. Load `markets.json` → extract rolling 3-day hero history for repeat penalty
9. Pick hero, movers (6), ticker (10)
10. Enrich catalog with `trading_signal` and `cat_rank` fields
11. Generate hero take + daily take via Claude API
12. Write `markets.json` + `kalshi_snapshot.json`

### markets.json Structure
```json
{
  "updated": "Mar 1, 2026 · 4:43 PM ET",
  "updated_iso": "2026-03-01T...",
  "hero": { ...market object... },
  "hero_history": ["topic_key_1", "topic_key_2", "topic_key_3"],
  "movers": [...6 market objects...],
  "ticker": [...10 market objects...],
  "daily_take": { "headline": "...", "body": "...", "take": "..." },
  "all_markets": [...full catalog sorted by cat_rank...]
}
```

### Market Object Fields
```json
{
  "source": "Polymarket" | "Kalshi",
  "question": "Will X happen?",
  "slug": "market-slug",
  "url": "https://...",
  "prob": 68.5,
  "change_pts": -10.0,
  "direction": "down" | "up" | "flat",
  "volume": 462000,
  "volume_fmt": "$462K",
  "volume_24h": 80000,
  "end_date": "Mar 15",
  "display_category": "Finance",
  "trading_signal": "knife_edge" | "momentum" | "volume_spike" | "active" | "stale",
  "cat_rank": 43.3
}
```

### Trading Signals (for category page filtering)
- `knife_edge` — prob 40-60% AND volume ≥ $50K (maximum uncertainty, liquid = most tradeable)
- `momentum` — moved ±5pts+ today (get in or fade)
- `volume_spike` — 24h volume ≥ 20% of total AND ≥ $10K (something is happening)
- `active` — moving but below above thresholds
- `stale` — volume < $25K AND move < 2pts (hide from traders)

### cat_rank Formula
```
cat_rank = (abs(change_pts) × 3) + (log10(volume_24h+1) × 2) + ke_bonus - stale_penalty
ke_bonus = +8 if knife_edge, stale_penalty = +20 if stale
```

---

## Hero Selection Algorithm

### Eligibility Gates (must pass all)
1. Total volume ≥ $250K
2. Not resolved (prob not ≥98% or ≤2%)
3. Not junk market (MrBeast bets, micro crypto price bands, tweet counts)
4. Not a range-bucket market (no single bucket tells the full story)
5. Sports markets: volume ≥ $25M (only truly massive events)

### Scoring
```
hero_score = buzz_score - repeat_penalty
```
**No category bonus** (removed — was causing Politics markets to dominate unfairly)

### Buzz Score Components
| Component | Formula |
|-----------|---------|
| Price move | `abs(change_pts) × 2.5` |
| 24h volume | `log10(volume_24h) / 10 × 3` |
| Total volume | `log10(volume) / 10` |
| Prob interest | `1 - abs(prob-50)/50` (sweet spot: 30-70%) |
| Urgency | up to 1.5pts if closes within 7 days |
| Recency | up to 3pts if 24h vol > 15% of total |

### Repeat Penalty
- Rolling **3-day** block: topics that won hero in last 3 days get **-15pts**
- Stored in `hero_history` array in `markets.json`

### Deduplication
- Date-ladder: "US strikes Iran by Mar 7" + "by Mar 14" → pick highest 24h volume contract
- Topic-level: coarse fingerprint via `get_topic_key()` — "iran strike" matches all Iran military variants
- Picks variant with largest absolute price move

---

## Known Issues & Fixes Applied

### Fixed This Week
- ✅ **Date-ladder corruption** — multiple expiry contracts for same event collapsed to hottest contract. Prevented -65pt impossible changes.
- ✅ **Range-bucket hero confusion** — "PPLE win fewer than 120 seats" appearing as hero. Now excluded from hero, consolidated in movers.
- ✅ **Polymarket change_pts validation** — impossible deltas (implied previous price outside 0-1%) set to 0.
- ✅ **Kalshi zeros** — `previous_price` field returns 0 from API. Fixed via `kalshi_snapshot.json` storing all 442 prices each run, computing delta on next run.
- ✅ **Category bonus removed** — Politics +18, Finance +12 etc. was overriding market signal. Now pure buzz score.
- ✅ **Rolling 3-day hero block** — was 1-day only, causing DHS/Bitcoin to ping-pong. Now 3-day window.
- ✅ **Kalshi debug logging silenced** — `[DEBUG Kalshi price fields]` no longer prints.
- ✅ **Trading signals + cat_rank** — all catalog markets now have `trading_signal` and `cat_rank` for frontend filtering/sorting.
- ✅ **Mobile email optimization** — 26 improvements to newsletter HTML (16px min text, 44px tap targets, dark mode lock, Outlook MSO conditionals, etc.)

### Known Remaining Issues
- **Kalshi range-bucket markets** still appear in movers/ticker (e.g., `How long will shutdown last?: :: Past 10AM`). The `::` separator markets should be filtered from movers/ticker, not just hero.
- **Category pages need frontend updates** to use `trading_signal` filter and `cat_rank` sort, plus three toggle buttons (Biggest Movers / Most Active / Knife Edge).
- **The Prob topic key fingerprint** for yesterday_topic sometimes includes parentheses from ticker symbols, e.g., `'(pple) party people's win'`. Low priority cosmetic issue.

---

## GitHub Actions Workflow

**File:** `.github/workflows/fetch-markets.yml`  
**Schedule:** Every hour (`0 * * * *`)  
**Secrets required:** `KALSHI_KEY_ID`, `KALSHI_PRIVATE_KEY`, `ANTHROPIC_API_KEY`

### Critical: Files Committed Each Run
```yaml
git add data/markets.json data/kalshi_snapshot.json
```
Both files must be committed or the Kalshi snapshot system breaks.

---

## Newsletter Pipeline — send_newsletter.py

**Platform:** Beehiiv  
**Target send time:** 7AM ET daily  
**Current status:** Semi-manual — script generates HTML, requires manual copy/paste into Beehiiv

### Newsletter Sections
1. **Hero** — main story with prob, change, volume, take
2. **Movers** — 6-market grid with category color chips
3. **Ticker** — 10-market table
4. **Daily Take** — Claude-generated 2-paragraph editorial

### Key Functions
- `estimate_read_time()` — shows "3 min read" in header
- `truncate_summary()` — caps news summaries at 2 sentences
- `category_chip()` — colored pills (red=Politics, green=Finance, purple=Sports, etc.)
- `generate_hero_take()` — Claude API call for hero market analysis

### Beehiiv HTML Quirks
- Use `<div>` not semantic tags (`<h1>`, `<h2>`) — Beehiiv overrides heading styles
- All colors need `!important` — Beehiiv's CSS has higher specificity
- Arrow characters as HTML entities: `&#9650;` / `&#9660;` (Outlook safe)
- No double dollar signs in volume formatting

### Automation Goal (In Progress)
Reduce manual intervention to near-zero. Current blocker: Beehiiv API for programmatic post creation needs to be wired up. See Beehiiv API docs for `/publications/{id}/posts` endpoint.

---

## SEO Strategy (TODO — Next Session)

**Target keywords:**
- Polymarket news, Polymarket newsletter
- Kalshi news, Kalshi newsletter  
- Prediction markets news, prediction markets newsletter
- Prediction markets today, prediction market odds
- Political prediction markets, sports prediction markets
- Business prediction markets, tech prediction markets

**Pages needing SEO work:** All HTML files (index, business, sports, tech, culture, politics, news)

**Items needed:**
- Unique `<title>` tags per page with keywords
- `<meta name="description">` per page
- Open Graph tags for social sharing
- Structured data (JSON-LD) for news/article schema
- Canonical URLs
- Sitemap.xml
- robots.txt

---

## Editorial Voice

See `VOICE.md` in repo root. Key principles:
- Sharp, confident, trader-focused
- Lead with the number and what it means
- "The crowd is telling you something" framing
- No hedging, no "could potentially maybe"
- Treat readers as sophisticated adults who trade for alpha

---

## Session Handoff — TODO

*(Update this section at the end of each session)*

### Pending Next Session
1. **SEO optimization** — Add meta tags, titles, OG tags, JSON-LD schema to all HTML pages targeting prediction market keywords
2. **Beehiiv automation** — Wire up Beehiiv API to reduce/eliminate manual newsletter send steps
3. **Category page frontend** — Implement `trading_signal` filter (hide `stale`), `cat_rank` sort, and three toggle buttons (Biggest Movers / Most Active / Knife Edge) using new fields already in `markets.json`
4. **Kalshi range-bucket movers filter** — Markets with `::` in question (e.g., `How long will shutdown last?: :: Past 10AM`) should be excluded from movers/ticker, same as they're excluded from hero
5. **Rolling hero block** — working but only has 1 day of history right now. Will naturally accumulate over next 2-3 days of hourly runs. Monitor to confirm DHS/Bitcoin ping-pong stops.

### Recently Completed (This Session — Mar 1, 2026)
- Date-ladder consolidation
- Range-bucket hero exclusion
- Polymarket impossible delta validation  
- Category bonus removed
- Kalshi zeros fixed (snapshot system)
- Trading signals + cat_rank added to catalog
- Rolling 3-day hero block
- Kalshi debug logging silenced

---

## How to Start a New Claude Session Efficiently

1. Share this file: "Read CLAUDE.md in my repo before we start"
2. Or paste the TODO section above
3. Optionally reference prior transcript: `/mnt/transcripts/[filename]`
4. Key files to share if making changes: `scripts/fetch_markets.py`, `scripts/send_newsletter.py`
