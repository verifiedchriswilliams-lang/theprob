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
  archive.html            # Newsletter archive page - NEW (Mar 6, 2026)
  contact.html            # Contact form page (Web3Forms → verifiedchriswilliams@gmail.com) - NEW (Mar 6, 2026)
  prediction-markets-101.html  # Educational guide, SEO content page - NEW (Mar 6, 2026)
  portfolio.html              # The Prob Portfolio tracker page - NEW (Mar 6, 2026)
  theprob_og_1200x630.jpg # OG social sharing image (1200x630px)
  sitemap.xml             # XML sitemap submitted to Google Search Console
  robots.txt              # Allows all crawlers, references sitemap
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
- Newsletter design overhaul — contrast (#546e85→#8ba3bc), button sizing, footer deduplication, "From Chris" section (Mar 5, 2026)
- Beehiiv Copy HTML workflow — newsletter/latest.html preview page with Copy button, latest-copy.html (no-footer) for paste-to-Beehiiv (Mar 5, 2026)
- New site pages — archive.html, contact.html (Web3Forms), prediction-markets-101.html (Mar 6, 2026)
- Footer updated on all 7 existing pages — new order: Polymarket, Kalshi, Prediction Markets 101, Newsletter Archive, Contact (Mar 6, 2026)
- The Prob Portfolio — data/portfolio.json, portfolio.html, widget on index.html, email header line, fetch_markets.py logic (Mar 6, 2026)
- Portfolio decoupled: pick_trade() selects short-duration (≤14 days) markets separately from hero (Mar 11, 2026)
- Portfolio reframed as live public experiment with 30-day test periods and experiment log (Mar 11, 2026)
- Newsletter trade_html wired into inner_sections in send_newsletter.py (Mar 11, 2026)
- UnboundLocalError fix — local `change_color` variable in trade block shadowed module-level `change_color()` function. Renamed to `t_change_color` (Mar 13, 2026)
- archive.html made dynamic — replaced static hardcoded list with JS loader reading newsletter/index.json (Mar 13, 2026)
- newsletter/index.json created — auto-updating archive index, backfilled with all 16 editions (Feb 24–Mar 11). Deduplication: re-running same day replaces the entry. (Mar 13, 2026)
- Dynamic newsletter subtitle — generate_subtitle() in send_newsletter.py calls Claude API with hero + top 3 movers + daily take to write unique inbox preview each day. Falls back to static copy on failure. (Mar 13, 2026)
- FROM_THE_BUILDER externalized — moved from hardcoded dict in send_newsletter.py to data/builder_notes.json. Pipeline warns if > 7 days stale. Edit JSON file each session, not Python. (Mar 13, 2026)
- The Spread shipped — compute_spread() in fetch_markets.py matches Poly vs Kalshi markets by title similarity (Jaccard + SequenceMatcher blend), flags pairs with ≥8pt gap, scores by gap × volume × uncertainty. Surfaces top 8 pairs in "The Spread" section on index.html (purple/blue platform chips, amber gap badge) and as an HTML section in the newsletter between movers and news. Key: "the_spread" in markets.json. (Mar 13, 2026)
- Kalshi auth fix — make_kalshi_headers() was defined but never called in fetch_kalshi_page(). Kalshi API started requiring authentication, causing fetch_kalshi() to silently return 0 markets. Fixed by passing headers=make_kalshi_headers("GET", "/trade-api/v2/events") to the requests.get() call. kalshi_snapshot.json was empty as a result; will repopulate on next pipeline run. (Mar 13, 2026)

Remaining:
- Topic key fingerprint cosmetic issue (low priority)
- Monitor rolling hero block — confirm ping-pong stays resolved
- Test 1 review: Apr 10, 2026
- The Spread false-positive fix (Mar 17): added range-bucket/past-close/resolved filters to compute_spread(). Spread card now shows Kalshi question as subtitle. Monitor pair counts — expect 1–5 real pairs per run with current Kalshi data coverage (94 filterable markets). If < 2 pairs consistently, lower MATCH_THRESHOLD to 0.30.
- NCAA hero fix (Mar 20): base_candidates volume gate now allows sports markets with $50K+ 24h to bypass $250K minimum. NCAA team markets now eligible. Monitor March Madness games (starting Mar 20) — expect to see tournament hero picks during active game days.
- Kalshi NCAA gap: zero Kalshi college basketball markets in all_markets. Root cause unknown. Investigate via GitHub Actions logs during a pipeline run — look for Sports fetch count and whether basketball markets appear with a different Kalshi category string.

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
1. Monitor NCAA/March Madness hero — fix is live as of Mar 20. On non-game days (today), NCAA team markets score ~22-27 and lose to bigger financial/news movers. On game days with upsets (big price drops), they'll dominate. Confirm after first full round of games (March 20-23). Also: Kalshi NCAA markets are NOT appearing in our data at all — only 6 Kalshi Sports markets fetched, all tiny volume. Likely: either pagination doesn't reach them or they're categorized differently. Worth investigating in a future session by checking GitHub Actions logs during a pipeline run.
2. Monitor The Spread output after session 3 fixes — with filters applied, expect 1–5 real pairs (vs 8 false positives before). MATCH_THRESHOLD stays at 0.35; the range-bucket/resolved/past-close filters do the heavy lifting. If < 2 pairs consistently, tune MATCH_THRESHOLD DOWN (try 0.30). If too many mismatches, raise to 0.40. The spread-card now shows the Kalshi question as a subtitle, so readers can evaluate match quality.
3. Yesterday's Biggest Swings — save data/markets_yesterday.json before each overwrite, diff vs today, show on index.html as "Markets That Moved Most in 24h". Zero new data needed. ~1 hour.
4. Markets Closing Soon rail — filter days_to_resolution < 3 AND probability 35–65. Home page rail + newsletter section. High urgency signal for traders.
5. Weird Markets section — auto-surface absurd/niche/counterintuitive markets (low volume + unusual category + active). Best viral/sharing feature for casual readers.
6. Sparklines — start accumulating price_history.json now; display 7-day charts on cards in ~7 days once data exists.
7. Polymarket "breaking" tab signal — Option B: inspect Network tab on polymarket.com/breaking to find Gamma API ordering parameter.
8. Monitor Test 1 results — review Apr 10, 2026.
9. Update data/builder_notes.json each session — edit built_recently + coming_next directly in that file.

### Recently Completed (Mar 20, 2026) — Session 4
- **NCAA/March Madness hero fix** — root cause: the base `HERO_MIN_VOLUME = $250K` check blocked all NCAA team markets before the sports-specific 24h bypass gate was ever evaluated. Multi-team championship events split total event volume across 68+ team contracts — the Poly NCAA tournament is $22M total but no single team contract reaches $250K (Duke is $232K, Arizona $240K). Fix: restructured the `base_candidates` check in `pick_hero()` so sports markets with $50K+ 24h volume bypass the $250K base minimum (same threshold as the existing sports gate). Arizona (27.0), Duke (24.5), Florida (22.1), Houston (14.0), Michigan (12.9) now all enter the eligible pool. On non-game days they score 22-27 and lose to bigger news movers. On game days with upsets, the price drop generates 30pt move_scores and they'll dominate hero.
- **Kalshi NCAA markets still MIA** — 0 Kalshi college basketball markets in our data (only 6 Kalshi Sports total, all low volume). Root cause unclear: could be pagination, category mismatch, or market structure. Flagged for investigation via GitHub Actions logs.
- **Same-day trade fix** — `pick_trade()` and `pick_trade_b()` used `end_date < today` which allowed markets closing the same day the pipeline runs (resolves in 0d). Changed to `end_date <= today` in both functions. Markets closing today are already in progress — only tomorrow-or-later eligible now.
- **Volume-tiered move_score cap** — thin markets (German state election, $55K 24h) were hitting the 30pt move_score cap and beating high-volume culturally-relevant markets (NCAA tournament, $100K+ 24h). Fix: cap now scales with 24h volume: `<$75K → 12pts`, `$75K–$250K → 20pts`, `$250K+ → 30pts`. SPD +15pts/$55K goes from 30 → 12. Duke upset -14pts/$500K still gets full 30. Trends_bonus cap also raised 4pts → 8pts so US-trending topics (Wikipedia/Google Trends) carry real weight against thin-market movers.
- **US audience relevance signal (signal #11)** — non-US regional markets (German elections, French mayoral races) were competing with US/global markets despite having no relevance to our American audience. New `us_audience_bonus()` function added to `score_market()`: +4pts for US politics/sports/companies/economic indicators, +2pts for globally significant topics Americans follow (Iran, Ukraine, China, Bitcoin, AI), 0pts for everything else. Arizona NCAA: 24.1 (+4 us) +8 sports = 32.1 total. SPD Rhineland: stays 18.1. All 3 trade models and hero selection inherit this through score_market().

### Recently Completed (Mar 17, 2026) — Session 3
- **The Spread QA & fix** — diagnosed 8 false-positive pairs in live data. Root cause: compute_spread() wasn't filtering range-bucket (`::`) markets, past-close markets, or effectively-resolved markets from Kalshi before matching. Added `is_range_bucket_market()`, `is_past_close()`, and `is_effectively_resolved()` filters to both Poly and Kalshi sides of the inner loop. MATCH_THRESHOLD kept at 0.35; filters alone reduced false positives from 8 → 1–4 legitimate pairs. Spread card now shows Kalshi question as a subtitle so readers can evaluate match quality.
- **Section reorder on index.html** — moved "Daily Markets News" (brief-section with news items + signup) UP between "Today's Biggest Movers" and "The Spread". Previous order was Movers → Spread → Daily Take → News. New order: Movers → News/Signup → Spread → Daily Take.
- **Movers reduced 9 → 6** — TOP_MOVERS_COUNT constant in fetch_markets.py reverted to 6. Page was too long at 9.
- **3-model experiment announcement newsletter section** — added `experiment_html` block to send_newsletter.py that appears after trade_html in every email. Shows A/B/C model cards with strategy descriptions, current YTD, and a "Follow the race & vote" CTA. Wired into inner_sections assembly.
- **builder_notes.json updated** — announcement copy for the 3-model launch. Will appear in "From Chris" section of tomorrow's newsletter.

### Recently Completed (Mar 13, 2026) — Session 2
- The Spread shipped — full implementation: compute_spread() in fetch_markets.py, "The Spread" section on index.html, build_spread_section() in send_newsletter.py. Uses Jaccard + SequenceMatcher title matching, ≥8pt gap threshold, interest scoring by gap × volume × uncertainty proximity to 50%. Output key: "the_spread" in markets.json.
- Kalshi auth fix — make_kalshi_headers() was never being called in fetch_kalshi_page(). Auth header now passed on every Kalshi API request. This was silently returning 0 Kalshi markets and causing blank Kalshi columns on all category pages.
- CLAUDE.md updated — The Spread and Kalshi fix logged, TODO refreshed with new P1 priorities.

### Recently Completed (Mar 13, 2026) — Session 1
- Archive dynamic loading — archive.html now loads from newsletter/index.json instead of hardcoded HTML. Groups by month, marks latest issue with badge.
- newsletter/index.json — auto-updating index written by send_newsletter.py each morning run. Deduplication ensures one entry per day (re-run replaces, not appends). Backfilled with all 16 editions Feb 24–Mar 11.
- UnboundLocalError fixed — `change_color` local var in trade block shadowed module-level function. Renamed to `t_change_color`.
- Dynamic newsletter subtitle — generate_subtitle() calls Claude API with real hero/movers/take data each morning. Unique inbox preview line daily.
- FROM_THE_BUILDER externalized to data/builder_notes.json — staleness warning fires if > 7 days since last_updated.
- Session handoff: CLAUDE.md updated + comprehensive new-session prompt written.

### Recently Completed (Mar 11, 2026) — Session 3
- Dynamic newsletter subtitle: generate_subtitle() added to send_newsletter.py. Claude writes a unique inbox preview each day based on the actual hero market, top 3 movers, and daily take. Falls back to static copy if Claude call fails.
- "Recently:" label fixed — was "Yesterday:" which was misleading when notes were a few days old.
- FROM_THE_BUILDER moved out of send_newsletter.py into data/builder_notes.json. Newsletter reads it fresh each run. Pipeline prints [WARN] if notes are > 7 days stale. Edit the JSON file each session, not the Python.
- builder_notes.json updated with current session copy: portfolio experiment launch + trade/hero decoupling as built_recently; The Spread as coming_next.

### Recently Completed (Mar 11, 2026) — Session 2
- Paper portfolio reframed as live public experiment on portfolio.html:
  - Title/hero: "We're building a prediction market trading system in public"
  - "What We're Testing" section: current ruleset + question being tested
  - "Experiment Log" section: dated changelog, Test 1 Mar 11–Apr 10 pre-populated
  - "How It Works" updated: 30-day test periods, no retroactive edits framing
  - Disclaimer updated to reflect transparency/accountability framing
- Portfolio reset to clean slate: $1,000 / 0 trades / start date Mar 11, 2026. Wiped old long-duration trades that had no resolution visibility.
- Test 1 defined: Mar 11–Apr 10, 2026. Rules: 65/35 gate, ≤14-day trade duration, $100 flat sizing, one trade/day max. Question: does following crowd conviction make money?
- Strategy discussion: current 65/35 system follows crowd with no inherent edge. Longshot bias (crowds overprice low-probability events) is the documented edge to explore in future tests. The Spread remains the highest-value feature.
- Start date references updated Mar 7 → Mar 11 in portfolio.html, index.html, send_newsletter.py.

### Recently Completed (Mar 11, 2026) — Session 1
- Trends matching precision fixes: expanded TRENDS_STOPWORDS with year tokens (2024-2030), 'world', and ~40 common 4-letter words that were passing the length filter but producing false positives. Matches dropped from 1,379 → ~180 (from 63% of all markets to ~8%).
- Sports cross-context filter: single-keyword trending topics (bare country/person names) no longer boost Sports category markets. Fixes false positive where "Iran" trending for geopolitical reasons was boosting "Will Iran win the FIFA World Cup?"
- Google Trends cleanup: both RSS endpoints (daily + realtime) confirmed dead — Google deprecated all public programmatic access. Replaced noisy retry loop with silent fallback. pytrends kept in code to auto-recover if Google re-enables. Wikipedia alone carries the trending signal.
- Hero 24h volume gate: added HERO_MIN_24H_VOLUME = 2_500. Markets with < $2.5K traded today are no longer hero-eligible, even with big historical moves. Fixed Anduril ($286K total, $20 today) winning hero incorrectly.
- Movers 6→9 bug fixed: slot_categories list only had 6 slots, so TOP_MOVERS_COUNT=9 was being ignored. Added post-slot fill loop that pulls next best markets until count reaches TOP_MOVERS_COUNT.
- FROM_THE_BUILDER updated in send_newsletter.py — was stuck on Mar 6 "launched portfolio" copy. Now reflects trending signal and hero scoring upgrades.
- Polymarket "breaking" tab investigated — Option A (API field) not available; `breaking` not a field on event objects. Option B needed (separate fetch with change-ordering).
- Decoupled Market of the Day from The Prob Trade: pick_trade() new function selects markets resolving ≤14 days (TRADE_MAX_DAYS=14), separate from hero. update_portfolio() now takes trade_market not hero. markets.json includes "trade" key alongside "hero".
- send_newsletter.py: trade_html block wired into inner_sections (was defined but not assembled — the missing piece). Newsletter now shows "Today's Trade" section between hero and movers.

### Recently Completed (Mar 10, 2026)
- Hero repeat block extended 3→7 days: Ubisoft appeared as hero 4/6 days — the 3-day penalty was expiring too quickly and letting the same stale topic cycle back in. Days 1-3 keep existing penalties [40, 70, 90pts]. Days 4-7 get -100pts (near-absolute block). hero_history stored in markets.json now capped at 7 keys instead of 3.
- featured_bonus raised +2→+6pts: At +2pts the Polymarket editorial curation signal couldn't overcome a 10pt daily move from a non-featured market. At +6pts, a featured market with a modest 4pt move now scores competitively against a non-featured market with a 6pt move, better reflecting what is actually trending and newsworthy.
- get_topic_key() price stripping: Bitcoin variants ("dip to $45K", "reach $120K", "above $80K") all produced different topic keys because dollar amounts survived as distinct tokens. Fix: strip $-amounts and bare numbers before tokenizing, and normalize price-direction verbs (dip/reach/hit/surge/above/below → "price") so all Bitcoin price questions collapse to "bitcoin price" and the 7-day block fires correctly.
- Category diversity penalty added to hero_score(): -10pts if same display_category won yesterday, -5pts if it won 2 days ago. Soft nudge — a big enough move can still overcome it, but prevents Crypto or any single category from dominating back-to-back days via different-but-thematically-identical markets. hero_category_history (last 3 days) stored in markets.json.
- Movers expanded 6→9: more markets on home page per run.
- Trending topics signal added to score_market() (signal #10): fetch_trending_topics() pulls from Wikipedia top articles (yesterday, via Wikimedia API) and Google Trends daily RSS (US). extract_trend_keywords() tokenizes each title. compute_trends_bonus() scores each market: +2pts per matching trend topic, capped at +4pts. trends_bonus injected into each market dict before scoring. trending_topics[:30] stored in markets.json for debug/newsletter use. Both sources fail independently with no pipeline disruption. Design intent: strong enough to lift a relevant market over a similarly-scored non-trending market, but not enough to override a genuine big mover.

### Recently Completed (Mar 8, 2026)
- Platform curation signals added to score_market() (2 new signals in fetch_markets.py):
  - Polymarket featured flag: fetch_polymarket() now captures `event.get("featured")` → stored as `"featured": bool` on each market dict. score_market() adds +6.0pts for featured markets (raised from +2 on Mar 10). Polymarket's editorial team curates this — strong signal for timeliness.
  - Kalshi bid-ask spread: fetch_kalshi() now captures `yes_ask - yes_bid` → stored as `"spread"` field. score_market() adds up to +1.0pt for tight spreads: `max(0, 1 - spread/10)`. Tight spread = liquid, actively traded market. Kalshi-specific.
  - Kalshi open_interest: fetch_kalshi() now captures `m.get("open_interest", 0) / 100` → stored as `"open_interest"` field. Not yet used in scoring but available for future features (e.g., The Spread, volume_vs_OI ratio signal).
- score_market() docstring updated with Mar 8 upgrade notes

### Recently Completed (Mar 7, 2026)
- 65/35 probability gate added to portfolio trade logic — no coin flips (35-65% zone forces NO_PLAY regardless of Claude's call)
- Portfolio reset to clean slate — wiped 5 bad trades logged before gate was in place (all were in coin-flip zone or had wrong direction). New start date Mar 7, 2026, balance $1,000.
- portfolio.html copy updated — subtitle, "How It Works" cards now explain the 65/35 conviction rule explicitly
- index.html widget start date updated to Mar 7, 2026
- score_market() hero scoring upgraded (4 changes):
  - move_score cap raised 20→30pts: better discrimination between noise moves and breaking news
  - vol_24h_score weight doubled (×3→×6): 24h volume is the best real-time relevance signal
  - prob_interest reshaped: OLD formula peaked at 50% (rewarded coin flips). NEW U-shape rewards conviction markets at 65%+ or 35%- where crowd has picked a side
  - trade_bonus added: +1.5pts if market qualifies for paper portfolio (prob ≥65 or ≤35), aligning hero selection with portfolio gate

### Recently Completed (Mar 6, 2026) — Session 3
- Paper Portfolio naming — replaced "Hypothetical Track Record" with "Paper Portfolio" (eyebrow on portfolio.html) and "The Running Score" (index.html widget subheading). "Hypothetical" framing was underselling the concept.
- FROM_THE_BUILDER updated — "built_yesterday": Portfolio tracker launched; "coming_next": The Spread
- sitemap.xml — added portfolio.html (priority 0.7, daily changefreq)
- Git push workflow fully documented in CLAUDE.md — stash, pull --rebase, push, stash pop. Conflict resolution for newsletter/latest*.html files documented.
- PAT workflow scope added — push to .github/workflows/ files requires 'workflow' scope on GitHub Personal Access Token

### Recently Completed (Mar 6, 2026) — Session 2
- The Prob Portfolio tracker launched:
  - data/portfolio.json — ledger file, starts at $1,000, $100/trade
  - fetch_markets.py — generate_hero_take() now returns {"take", "direction"} dict; update_portfolio() closes resolved trades + opens new ones each hourly run; portfolio summary written to markets.json
  - Trade gate: prob must be >= 65% (trade YES) or <= 35% (trade NO). Anything in the 35-65% coin-flip zone is forced to NO_PLAY regardless of Claude's call. Claude still picks direction within those bounds and can also return NO_PLAY on qualifying markets if signal is unclear.
  - portfolio.html — full page with stats (balance, YTD, W/L record, open positions), trade ledger table, "How It Works" section
  - index.html — portfolio widget between hero and movers sections, loads from markets.json
  - send_newsletter.py — portfolio line added to email header (balance, YTD%, W/L, link to portfolio.html)
  - fetch-markets.yml — now commits data/portfolio.json alongside markets.json each run
- DST cron updated — send-newsletter.yml changed from '50 11 * * *' to '50 10 * * *' (EDT)
- sitemap.xml — added prediction-markets-101.html (0.8), archive.html (0.5), contact.html (0.3)

### Recently Completed (Mar 6, 2026) — Session 1
- New site pages launched:
  - archive.html — newsletter archive, month-grouped, links to newsletter/YYYY-MM-DD.html files
  - contact.html — contact form via Web3Forms (free tier, 250/month), delivers to verifiedchriswilliams@gmail.com. Access key set in GitHub editor.
  - prediction-markets-101.html — educational guide: what are prediction markets, how to read odds, Poly vs Kalshi comparison table, FAQ. Written in brand voice. Targets "what is a prediction market" keyword cluster.
- Footer updated on all 7 existing HTML pages — new Sources link order: Polymarket, Kalshi, Prediction Markets 101, Newsletter Archive, Contact
- Git push workflow issue resolved — root cause: GitHub Actions pushes data files every hour; local commits get rejected with "fetch first". Fix: `git stash --include-untracked && git pull --rebase && git push && git stash pop`. If rebase creates conflicts in newsletter/latest*.html files, resolve with `git checkout --theirs <file> && git add <file>`.

### Recently Completed (Mar 5, 2026)
- Newsletter design overhaul:
  - Contrast fix — all secondary text bumped from #546e85 → #8ba3bc, passes WCAG AA across all sections
  - CTA button right-sized — padding reduced (16px 40px → 14px 28px), no longer oversized/distorted
  - Footer duplication eliminated — Copy HTML button delivers html_no_ftr (Beehiiv adds its own footer); preview page shows html_full for accurate email preview
  - "From Chris" personal section added to every email — amber eyebrow, Yesterday/Next copy, signed signature. Updates via FROM_THE_BUILDER dict in send_newsletter.py.
- Beehiiv Copy HTML workflow built:
  - newsletter/latest.html → now a preview wrapper page with floating "Copy Email HTML" button
  - newsletter/latest-email.html → full email HTML (iframe source for preview)
  - newsletter/latest-copy.html → no-footer email HTML (what gets copied to clipboard)
  - JS uses fetch() → navigator.clipboard.writeText() with graceful error state
  - Morning workflow: open theprobnewsletter.com/newsletter/latest.html → click "Copy Email HTML" → paste into Beehiiv → Send (30 seconds)

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

### P1 — High Value, Low Effort
- **Manual Hero Override** — ability to pin a specific market as hero regardless of scoring. Use case: breaking news, editorially obvious picks (e.g. Super Bowl day, election night), or when the algorithm surfaces something clearly wrong. Implementation: `data/hero_override.json` with fields `{ "url": "...", "question": "...", "expires": "YYYY-MM-DD" }`. Pipeline checks for this file first; if present and not expired, uses it as hero and skips normal selection. Edit the file manually each time. Auto-expires so it doesn't get forgotten. ~30 min.
- **The Prob Score** — proprietary ranking badge on every market card. Draft formula: `(|change_pts|*2) + (volume_rank*1.5) + (1/days_to_resolution capped)`. Compute in fetch_markets.py, store as `prob_score` field in markets.json, display as badge on cards. No new infrastructure needed.
- **Yesterday's Biggest Movers** — save `data/markets_yesterday.json` before overwriting each run, diff vs today, surface top swings in a "Yesterday's Biggest Swings" section on index.html. ~1-2 hours.
- **Probability Velocity** — store a mid-run snapshot (`prob_2h_ago`, `change_pts_2h`) to surface "fastest movers RIGHT NOW" separate from daily change. A market that moved 4pts in 2 hours is a very different signal than one that moved 4pts over 24 hours. Requires storing one intra-day snapshot per run alongside kalshi_snapshot. New site section: "Something's Brewing."
- **The Spread (Poly vs Kalshi Divergence)** — match markets across sources by title similarity, flag pairs where |poly_prob - kalshi_prob| > 8pts. Direct arbitrage signal — the single most actionable feature for active traders. Surface as dedicated "The Spread" section on index.html and in the daily email. Headline frame: "The crowd disagrees with itself — here's where."
- **"Act On This" framing** — every top mover should have a one-line trading implication, not just a description. Claude-generated hero take already does this; extend to top 3 movers in the email. Prompt orientation: "What would need to happen for this to resolve YES, and what is the market getting wrong right now?"
- **Site footer contact email** — add `contact@theprobnewsletter.com` to the footer-copy row on all 7 HTML pages (between copyright and disclaimer). Confirm actual address first.

### P1.5 — The Prob Portfolio (LIVE — Test 1 running)
**Status:** Live as of Mar 11, 2026. Test 1 runs Mar 11–Apr 10, 2026.

**Current architecture:**
- `data/portfolio.json` — full trade ledger, $1,000 starting balance, $100/trade
- `pick_trade()` in fetch_markets.py — selects markets resolving ≤14 days (TRADE_MAX_DAYS=14), separate from hero pick
- Trade gate: prob ≥65% → YES, prob ≤35% → NO, everything else → NO_PLAY
- `portfolio.html` — live experiment page with ruleset, experiment log, full ledger
- Index.html widget: current balance, YTD%, W/L record
- Newsletter header: portfolio line on every email
- Email: "Today's Trade" section between hero and movers

**Test 1 question:** Does following crowd conviction (65/35 gate) generate any edge over 30 days?

**Next evolution (Test 2, starting ~Apr 10):**
- Option A: flip direction on low-end — always fade longshots (bet NO when prob ≤35%), exploit longshot bias
- Option B: add The Spread as primary signal — trade the Poly/Kalshi cross-market disagreement
- Option C: raise gate to 70/30 for stricter conviction filter
- Decision based on Test 1 win rate vs. implied probability

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
Technical SEO done (Mar 1). sitemap.xml fully updated as of Mar 6 — all 10 pages included (index, 5 category, news, prediction-markets-101, archive, contact, portfolio). Content SEO is the real moat:
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

GitHub Desktop doesn't reliably detect terminal commits. Always push via Mac Terminal.

Standard push (no uncommitted local changes):
```
cd ~/theprob
git pull --rebase && git push
```

If you have unstaged/untracked local changes (send_newsletter.py edits, newsletter files, etc.):
```
git stash --include-untracked
git pull --rebase
git push
git stash pop
```

If rebase creates merge conflicts in newsletter/latest*.html or latest-subject.txt (GitHub Actions overwrites these each hour):
```
git checkout --theirs newsletter/latest-subject.txt newsletter/latest.html
git add newsletter/latest-subject.txt newsletter/latest.html
git commit -m "resolve merge conflicts in newsletter latest files"
git push
```

If rebase creates a merge conflict in data/portfolio.json (GitHub Actions writes this every hour):
```
git checkout --theirs data/portfolio.json
git add data/portfolio.json
GIT_EDITOR=true git rebase --continue
git push
```

Note: `GIT_EDITOR=true` skips the vim commit message editor entirely — critical when Chris is running the rebase interactively. Always use it for `git rebase --continue` to avoid the vim trap.
