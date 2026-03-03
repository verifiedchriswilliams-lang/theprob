# CLAUDE.md — The Prob: AI Collaboration Guide

> Read this at the start of every session. Update the TODO section before ending each session.

## What Is The Prob

URL: https://theprobnewsletter.com
Repo: https://github.com/verifiedchriswilliams-lang/theprob
Stack: Static HTML/JS site hosted on GitHub Pages + Python data pipeline + Beehiiv newsletter
Mission: Help prediction market traders make money by surfacing the most actionable market moves across Polymarket and Kalshi.

## Repo Structure

theprob/
  index.html              # Home page
  business.html           # Finance/Business category page
  sports.html             # Sports category page
  tech.html               # Technology category page
  culture.html            # Culture category page
  politics.html           # Politics category page
  news.html               # News page
  theprob_og_1200x630.jpg # OG social sharing image (1200x630px) - NEW
  sitemap.xml             # XML sitemap submitted to Google Search Console - NEW
  robots.txt              # Allows all crawlers, references sitemap - NEW
  VOICE.md                # Editorial voice guide
  CLAUDE.md               # This file
  data/
    markets.json          # PRIMARY data file - rebuilt every hour by GitHub Actions
    kalshi_snapshot.json  # Kalshi price snapshot for delta calculation
  scripts/
    fetch_markets.py      # Main data pipeline
    send_newsletter.py    # Beehiiv newsletter generation and send
  .github/workflows/
    fetch-markets.yml     # Hourly GitHub Actions workflow

## Data Pipeline — fetch_markets.py

Runs hourly via GitHub Actions. Fetches ~2000+ markets, filters/scores/selects hero + movers + ticker, writes markets.json.

Key Constants:
- HERO_MIN_VOLUME = 250_000
- HERO_SPORTS_MIN_VOLUME = 25_000_000
- HERO_MIN_CHANGE_PTS = 3.0
- HERO_REPEAT_PENALTY = 15
- KALSHI_MIN_VOL = 1_000

Data Flow:
1. Fetch Polymarket (3 pages 24h volume + 2 pages total volume)
2. Deduplicate by event slug
3. Date-ladder consolidation
4. Range-bucket consolidation
5. Fetch Kalshi
6. Load kalshi_snapshot.json, compute real change_pts
7. Rebuild all_markets with corrected Kalshi deltas
8. Load markets.json, extract rolling 3-day hero history
9. Pick hero, movers (6), ticker (10)
10. Enrich catalog with trading_signal and cat_rank
11. Generate hero take + daily take via Claude API
12. Write markets.json + kalshi_snapshot.json

Market Object Fields:
  source, question, slug, url, prob, change_pts, direction,
  volume, volume_fmt, volume_24h, end_date, display_category,
  trading_signal, cat_rank

Trading Signals:
- knife_edge: prob 40-60% AND volume >= $50K
- momentum: moved +-5pts+ today
- volume_spike: 24h vol >= 20% of total AND >= $10K
- active: moving but below thresholds
- stale: volume < $25K AND move < 2pts

cat_rank = (abs(change_pts)*3) + (log10(volume_24h+1)*2) + ke_bonus - stale_penalty

## Hero Selection Algorithm

Eligibility Gates (must pass all):
1. Total volume >= $250K
2. Not resolved (prob not >=98% or <=2%)
3. Not junk market
4. Not a range-bucket market
5. Sports: volume >= $25M

Scoring: hero_score = buzz_score - repeat_penalty (no category bonus)

Buzz Score: price move, 24h volume, total volume, prob interest, urgency, recency

Repeat Penalty: Rolling 3-day block, -15pts, stored in hero_history

## Known Issues

Fixed:
- Date-ladder corruption
- Range-bucket hero confusion
- Polymarket impossible delta validation
- Kalshi zeros (snapshot system)
- Category bonus removed
- Rolling 3-day hero block
- Kalshi debug logging silenced
- Trading signals + cat_rank added
- Mobile email optimization (26 improvements)
- SEO overhaul complete (Mar 1, 2026)

Remaining:
- EXPIRED MARKETS IN FEED: resolved/past-end-date markets appearing (e.g. "Trump named in Epstein files by Feb 28?" showed post-resolution). Fix: filter by end_date in fetch_markets.py. DO THIS FIRST NEXT SESSION.
- Kalshi :: separator markets still in movers/ticker (should be filtered like hero)
- Category pages need trading_signal filter, cat_rank sort, toggle buttons
- Topic key fingerprint cosmetic issue (low priority)

## SEO Implementation (Completed Mar 1, 2026)

All 7 HTML pages updated and deployed with:
- Keyword-rich title tags (60-70 chars, includes "Polymarket & Kalshi")
- Meta descriptions (150-160 chars)
- Meta keywords (8-10 per page)
- Canonical URLs
- Full Open Graph tags (including og:image:width/height)
- Twitter Card tags
- JSON-LD structured data (WebSite on index, WebPage on category pages)

New files in repo root:
- sitemap.xml (all 7 pages, hourly changefreq, priority weighted)
- robots.txt
- theprob_og_1200x630.jpg

Google Search Console: verified + sitemap submitted Mar 1, 2026.
Expect indexing within 1-2 days, ranking signals in 2-8 weeks.

Target keywords by page:
- Index: prediction markets, Polymarket, Kalshi, prediction market odds
- Business: business prediction markets, Polymarket finance, Fed prediction market
- Culture: culture prediction markets, Oscars prediction market
- News: Polymarket news, Kalshi news, prediction markets newsletter
- Politics: political prediction markets, election prediction market
- Sports: sports prediction markets, NFL/NBA prediction market
- Tech: crypto prediction markets, Bitcoin/AI prediction market

## GitHub Actions Workflow

File: .github/workflows/fetch-markets.yml
Schedule: Every hour
Secrets: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY, ANTHROPIC_API_KEY
Critical: Both markets.json AND kalshi_snapshot.json must be committed each run.

## Newsletter Pipeline

Platform: Beehiiv | Target: 7AM ET daily | Status: Semi-manual
Sections: Hero, Movers (6), Ticker (10), Daily Take
Beehiiv quirks: use div not h1/h2, all colors need !important, HTML arrow entities, no double dollar signs.
Automation goal: wire up Beehiiv API /publications/{id}/posts endpoint.

## Editorial Voice

See VOICE.md. Sharp, confident, trader-focused. Lead with the number. "The crowd is telling you something." No hedging.

## Session Handoff — TODO

### Pending Next Session
1. FIX EXPIRED MARKET FILTER FIRST — check end_date field in data/markets.json then filter in fetch_markets.py
2. Beehiiv automation — wire up API to eliminate manual send steps
3. Category page frontend — trading_signal filter, cat_rank sort, 3 toggle buttons (Biggest Movers / Most Active / Knife Edge)
4. Kalshi :: separator filter — exclude from movers/ticker (currently only excluded from hero)
5. Monitor rolling hero block — confirm ping-pong resolved

### Recently Completed (Mar 1, 2026)
- Full SEO overhaul — all 7 HTML pages
- sitemap.xml + robots.txt deployed
- Google Search Console verified + sitemap submitted
- OG social image live (theprob_og_1200x630.jpg)

## How to Start a New Session

1. Share this file or paste the TODO section
2. Key files for changes: scripts/fetch_markets.py, scripts/send_newsletter.py
3. Prior transcripts: /mnt/transcripts/[filename]
