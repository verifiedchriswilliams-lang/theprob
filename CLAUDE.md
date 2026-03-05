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
2. Not resolved (prob not >=95% or <=5%)
3. Not past close date (end_date_raw < today)
4. Not junk market
5. Not a range-bucket market
6. Sports: volume >= $25M

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
- Expired/near-resolved markets in feed — is_effectively_resolved() tightened to 95/5, is_past_close() added (Mar 3, 2026)
- Kalshi :: separator markets in movers/ticker — is_range_bucket_market() added to pick_movers() + pick_ticker() (Mar 3, 2026)
- Category page frontend — 3 toggle buttons, cat_rank sort, stale filter, signal badges (Mar 3, 2026)

Remaining:
- Topic key fingerprint cosmetic issue (low priority)
- Monitor rolling hero block — confirm ping-pong stays resolved

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
1. Beehiiv workaround — add "Copy HTML" button to newsletter/latest.html so morning workflow is: open URL → click Copy → paste into Beehiiv → Send (30 seconds). Beehiiv full automation requires Enterprise plan ($$$) — not worth it yet.
2. DST cron update — after Mar 8, 2026 change send-newsletter.yml cron from '50 11 * * *' → '50 10 * * *' (6:50am EDT = 10:50 UTC)
3. The Spread (Poly vs Kalshi divergence) — highest trader value feature not yet built
4. The Prob Portfolio tracker — flagship differentiator, full spec in roadmap below
5. Monitor rolling hero block — passive, confirm no ping-pong

### Recently Completed (Mar 4-5, 2026)
- Hero repeat penalty now cumulative: -40pts (1 day ago), -70pts (2 days ago), -90pts (3 days ago). Old flat -15pt penalty was too weak vs move_score.
- move_score capped at 20pts — prevents one monster move from dominating for days
- Volume-qualified staleness gate — markets with $500K+ 24h volume need only 1pt move to qualify for hero (captures high-volume/stable-price markets like Iran/Hormuz)
- Beehiiv automation attempted — POST /publications/{id}/posts endpoint requires Enterprise plan. Even draft creation is blocked. Code is in place (post_to_beehiiv() in send_newsletter.py, workflow updated with BEEHIIV_API_KEY + BEEHIIV_PUB_ID secrets) and gracefully falls back to manual if API fails. Workaround: Copy HTML button on newsletter preview page (next session).

### Recently Completed (Mar 3, 2026)
- Expired market filter — is_effectively_resolved() tightened to 95/5, is_past_close() added using end_date_raw, applied to hero/movers/ticker/catalog
- Kalshi :: separator filter — is_range_bucket_market() now applied in pick_movers() + pick_ticker() (was hero-only)
- Category page frontend — all 5 pages (politics, business, culture, sports, tech) updated with:
  - 3 toggle buttons: ⚡ Biggest Movers (cat_rank) | 🔥 Most Active (volume_24h) | ⚖ Knife Edge (knife_edge signal only)
  - Stale markets always hidden
  - Signal badges on each market card

### Recently Completed (Mar 1, 2026)
- Full SEO overhaul — all 7 HTML pages
- sitemap.xml + robots.txt deployed
- Google Search Console verified + sitemap submitted
- OG social image live (theprob_og_1200x630.jpg)

## Product Roadmap

Items carried forward from brainstorm sessions. Prioritized by impact vs. effort.

### P0 — Next Session
- **Beehiiv "Copy HTML" button** — Beehiiv API /posts endpoint requires Enterprise plan (confirmed Mar 4). Full automation blocked. Workaround: add a floating "Copy HTML to Clipboard" button to `newsletter/latest.html` (served at theprobnewsletter.com/newsletter/latest.html). Morning workflow becomes: open URL → click Copy → paste into Beehiiv → Send. ~30 minutes to build.

### P1 — High Value, Low Effort
- **The Prob Score** — proprietary ranking badge on every market card. Draft formula: `(|change_pts|*2) + (volume_rank*1.5) + (1/days_to_resolution capped)`. Compute in fetch_markets.py, store as `prob_score` field in markets.json, display as badge on cards. No new infrastructure needed.
- **Yesterday's Biggest Movers** — save `data/markets_yesterday.json` before overwriting each run, diff vs today, surface top swings in a "Yesterday's Biggest Swings" section on index.html. ~1-2 hours.
- **Probability Velocity** — store a mid-run snapshot (`prob_2h_ago`, `change_pts_2h`) to surface "fastest movers RIGHT NOW" separate from daily change. A market that moved 4pts in 2 hours is a very different signal than one that moved 4pts over 24 hours. Requires storing one intra-day snapshot per run alongside kalshi_snapshot. New site section: "Something's Brewing."
- **The Spread (Poly vs Kalshi Divergence)** — match markets across sources by title similarity, flag pairs where |poly_prob - kalshi_prob| > 8pts. Direct arbitrage signal — the single most actionable feature for active traders. Surface as dedicated "The Spread" section on index.html and in the daily email. Headline frame: "The crowd disagrees with itself — here's where."
- **"Act On This" framing** — every top mover should have a one-line trading implication, not just a description. Claude-generated hero take already does this; extend to top 3 movers in the email. Prompt orientation: "What would need to happen for this to resolve YES, and what is the market getting wrong right now?"
- **Site footer contact email** — add `contact@theprobnewsletter.com` to the footer-copy row on all 7 HTML pages (between copyright and disclaimer). Confirm actual address first.

### P1.5 — The Prob Portfolio (flagship differentiator)
This is the feature that turns The Prob from a data aggregator into a **track record**. Frame: "The Prob puts its money where its mouth is."

**Concept:** Every time a market is selected as the daily hero, The Prob automatically logs a $100 hypothetical trade (YES or NO, based on Claude's directional take) in `data/portfolio.json`. When the market resolves, the position closes and P&L is calculated. The running portfolio — starting balance $1,000 — updates live on the site and appears in every email header.

**Why it works:**
- A trader seeing "+31% YTD (vs. S&P +11%)" subscribes immediately
- Creates genuine accountability — bad picks hurt the number visibly
- Compounding over months becomes the single most compelling proof of value
- "You would have made $47 if you'd followed our last 5 picks" is the most powerful FOMO line in prediction markets

**Implementation (all static, no backend needed):**
- `data/portfolio.json` — ledger of all trades: market_id, question, url, entry_prob, direction (YES/NO), amount ($100), entry_date, status (open/closed), exit_prob, pnl
- In fetch_markets.py: when hero is selected, append new open trade to portfolio.json
- On each run: check open trades against current prob; if market is resolved (prob >= 95 or <= 5 and past end_date), close the position and calculate P&L
- P&L formula: if bought YES at entry_prob p and resolved YES → pnl = $100 * (1/p - 1). If resolved NO → pnl = -$100. Vice versa for NO positions.
- New page: `portfolio.html` — full trade ledger, running balance chart, win rate, avg return per trade, YTD vs S&P benchmark
- Index.html widget: current balance, YTD return %, last 3 closed trades
- Email header line: "The Prob Portfolio: $X,XXX (+XX% YTD)"

**Direction logic:** Use Claude's hero take sentiment. If the take is bullish (expects YES), log YES. If bearish, log NO. If neutral/uncertain, skip the trade that day (log as "no play").

### P2 — Medium Effort, High Value
- **Market Narratives (Claude-generated)** — for top 5 markets, call Claude API with: "In 2 sentences, explain the story behind this prediction market to a smart non-trader." Save as `narrative` field in markets.json. Display inline or as expandable text on cards. ANTHROPIC_API_KEY already in GitHub secrets.
- **Daily email GitHub Action** — cron 6:50am ET. Run generate_email.py: pull from markets.json, render HTML template, write to `email/draft_YYYY-MM-DD.html`. If Beehiiv API supports send → POST directly. If not → commit draft for one-click manual send.
- **email.html polish** — improve text contrast (WCAG AA), remove redundant footer (Beehiiv adds its own), inline all CSS (email clients strip `<style>` blocks), test dark mode rendering.

### P3 — Bigger Features
- **Market Search** — client-side fuzzy search using Fuse.js (~10kb). New search.html or modal on index. Already pulling 2,500+ markets into markets.json. ~3-4 hours, no backend needed.
- **RSS feed** — generate `feed.xml` daily alongside email draft. Contains: headline, deck, top 3 markets, top 3 news items. Canonical URL back to theprobnewsletter.com. Enables Substack auto-import, Feedly, Apple News, Google News.
- **Substack cross-posting** — once RSS feed exists, configure Substack Settings → Import to auto-pull feed. Zero daily effort after setup. Each post creates a backlink to theprobnewsletter.com.
- **Twitter/X thread automation** — daily 4-tweet thread at 7:05am via GitHub Action. Requires Twitter Developer App + API keys in secrets. Thread format: (1) top 3 markets with odds, (2) biggest mover + why it matters, (3) Poly vs Kalshi spread if one exists, (4) subscribe link with portfolio YTD return.

### P4 — Later
- **Personal Watchlist** — localStorage-based, no backend. Star any market, persists across sessions. ~2 hours once other features stable.
- **"What's Your Take?" Daily Poll** — yes/no vote on hero market. Store results in Cloudflare Workers KV. Show live % agreement with crowd. ~3-4 hours including backend.
- **"Alert Me" emails** — threshold-based alerts requiring subscription + storage. Most complex feature — defer.

### SEO Content Track (ongoing)
Technical SEO done (Mar 1). Content SEO is the real moat:
- `/what-is-prediction-market.html` — targets "what is a prediction market" (high volume, informational)
- `/polymarket-vs-kalshi.html` — comparison page (high commercial intent)
- `/how-prediction-markets-work.html` — educational, links to live market data
- Each page: 600-800 words, one keyword cluster, links back to live data
- Link building: submit to newsletter directories (Paved, Who Sponsors Stuff), post in r/predictionmarkets and Manifold Discord
- Monitor Google Search Console weekly for impression share on target keywords

---

## How to Start a New Session

1. Share this file or paste the TODO section
2. Key files for changes: scripts/fetch_markets.py, scripts/send_newsletter.py
3. Prior transcripts: /mnt/transcripts/[filename]

## Git Push Workflow

GitHub Desktop doesn't reliably detect terminal commits. Always push via Mac Terminal:
```
cd ~/theprob
git pull --rebase && git push
```
