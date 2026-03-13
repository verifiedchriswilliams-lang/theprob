# New Session Handoff Prompt — The Prob
## Copy and paste this entire prompt to start a new Claude conversation

---

You are picking up an ongoing build of **The Prob** — a prediction markets newsletter and data site. Start by reading two files in the repo to get full context:

1. `CLAUDE.md` — architecture, data pipeline, roadmap, full session history
2. `VOICE.md` — editorial voice guide

Repo: https://github.com/verifiedchriswilliams-lang/theprob
Live site: https://theprobnewsletter.com
Owner: Chris Williams (verifiedchriswilliams@gmail.com)

---

## What The Prob Is

Static HTML/JS site on GitHub Pages + hourly Python data pipeline (GitHub Actions) + Beehiiv newsletter.
Mission: Help prediction market traders make money AND be the most entertaining destination for prediction market-curious readers.

**Two audiences, one product:**
1. **Traders** — want actionable signals: what's moving, why, what to do about it
2. **Curious readers** — want to know what the most fascinating/weird/high-stakes things people are betting on right now

Stack:
- `scripts/fetch_markets.py` — main pipeline, runs hourly, fetches ~2000+ markets from Polymarket + Kalshi, scores/selects hero + movers + ticker, writes `data/markets.json`
- `scripts/send_newsletter.py` — morning newsletter generator, reads markets.json, calls Claude API for hero take + daily take + unique subtitle, writes HTML to `newsletter/`
- `data/markets.json` — primary data file, rebuilt every hour
- `data/portfolio.json` — paper trade ledger
- `data/builder_notes.json` — FROM_THE_BUILDER copy (update each session!)
- `newsletter/index.json` — auto-updating archive index (one entry per day, deduplicates on re-run)

---

## Current State as of Mar 13, 2026

### What's live and working:
- Hourly data pipeline fetching 2000+ markets, scoring with 10+ signals
- Hero market selection with 7-day repeat block, category diversity penalty, trending topics boost
- 9 movers + 10-item ticker on home page
- 5 category pages with toggle filters (⚡ Biggest Movers / 🔥 Most Active / ⚖ Knife Edge)
- Morning newsletter generator: hero take, trade pick, 9 movers, ticker, daily take, dynamic subtitle, "From Chris" section
- Paper portfolio (Test 1 live Mar 11–Apr 10): 65/35 gate, ≤14-day trades, $100 flat sizing
- Portfolio page reframed as live public experiment with experiment log
- Archive page loads dynamically from newsletter/index.json (16 editions backfilled)
- Contact page (Web3Forms), Prediction Markets 101 SEO page
- Full SEO overhaul complete (Mar 1): title tags, OG, JSON-LD, sitemap, robots.txt

### Key constants in fetch_markets.py:
- `HERO_MIN_VOLUME = 250_000`
- `HERO_SPORTS_MIN_VOLUME = 25_000_000`
- `HERO_MIN_CHANGE_PTS = 3.0`
- `HERO_MIN_24H_VOLUME = 2_500`
- `TRADE_MAX_DAYS = 14`
- Hero repeat block: -40pts (1 day ago), -70pts (2 days ago), -90pts (3 days ago), -100pts (days 4-7)

### Known issues / low priority:
- Topic key fingerprint cosmetic issue (low priority, doesn't affect output)
- Monitor rolling hero block for ping-pong regression

---

## Active Roadmap (prioritized)

### P1 — Build next (high value, low effort):
1. **The Spread (Poly vs Kalshi Divergence)** — HIGHEST PRIORITY. Match markets across platforms by title similarity, flag pairs where |poly_prob - kalshi_prob| > 8pts. Kalshi `open_interest` field already captured. Surface as "The Spread" section on index.html and in daily email. Headline: "The crowd disagrees with itself — here's where."
2. **The Prob Score** — proprietary badge on every card. Draft: `(|change_pts|*2) + (volume_rank*1.5) + (1/days_to_resolution)`. Store as `prob_score` in markets.json.
3. **"Act On This" framing** — extend Claude-generated hero take to top 3 movers in email. "What would need to happen for this to resolve YES, and what is the market getting wrong?"
4. **Yesterday's Biggest Movers** — save `data/markets_yesterday.json` before overwriting, diff vs today, surface "Yesterday's Biggest Swings" on index.html.
5. **Probability Velocity** — mid-run snapshot for "fastest movers RIGHT NOW." New site section: "Something's Brewing."

### P2 — Medium effort:
- Market Narratives (Claude-generated 2-sentence explainers for top 5 markets)
- Polymarket "breaking" tab signal (Option B: inspect Network tab on polymarket.com/breaking, find Gamma API ordering param)
- Twitter/X thread automation via GitHub Action (daily 4-tweet thread, 7:05am)

### P3 — Bigger:
- Market Search (client-side Fuse.js, no backend needed)
- RSS feed → Substack cross-posting
- Polymarket "breaking" tab as hero signal

### P4 — Later:
- Personal Watchlist (localStorage)
- "What's Your Take?" daily poll (Cloudflare Workers KV)

### SEO Content Track (ongoing):
- `/polymarket-vs-kalshi.html` — comparison page (high commercial intent)
- `/what-is-prediction-market.html` — informational
- Monitor Google Search Console weekly

---

## Portfolio Experiment Status

**Test 1: Mar 11–Apr 10, 2026**
- Rules: 65/35 probability gate, ≤14-day duration, $100 flat sizing, one trade/day max
- Question: Does following crowd conviction make money?
- Review date: Apr 10, 2026
- Test 2 options (post-review): fade longshots (flip on ≤35%), add The Spread as signal, raise gate to 70/30

---

## Git Push Workflow (IMPORTANT — Chris runs this in Mac Terminal)

Standard (no local changes):
```
cd ~/theprob && git pull --rebase && git push
```

With unstaged local changes:
```
cd ~/theprob
git stash --include-untracked
git pull --rebase
git push
git stash pop
```

Conflict in data/portfolio.json (GitHub Actions writes this hourly):
```
git checkout --theirs data/portfolio.json
git add data/portfolio.json
GIT_EDITOR=true git rebase --continue
git push
```

Conflict in newsletter/latest*.html or latest-subject.txt:
```
git checkout --theirs newsletter/latest-subject.txt newsletter/latest.html
git add newsletter/latest-subject.txt newsletter/latest.html
git commit -m "resolve merge conflicts in newsletter latest files"
git push
```

Note: `GIT_EDITOR=true` is critical — skips vim entirely during `git rebase --continue`. Always use it.

---

## What I Need From You This Session

**Start by reviewing the live repo and CLAUDE.md, then do two things:**

**1. Strategic review:** Give me your top 10 recommendations for how to make The Prob more valuable — ranked by impact. Weight toward:
   - Trader value: features that genuinely help someone make money on Polymarket or Kalshi
   - Entertainment/buzz: features that make casual readers say "wait, people are betting on THAT?" and share it

   For each recommendation: what it is, why it matters for the audience, rough effort, and where it fits in the current roadmap (gap, already planned, or contradicts something).

**2. Then let's build:** After the strategic review, pick the highest-impact item we haven't built yet and let's ship it this session. My instinct is The Spread, but override me if you see something better.

---

## Notes for Claude

- Always read CLAUDE.md + VOICE.md before touching any code
- Key files to modify: `scripts/fetch_markets.py`, `scripts/send_newsletter.py`
- `data/builder_notes.json` — update `built_recently` + `coming_next` before ending session
- Newsletter re-runs are safe: one entry per day (deduplication in index.json + HTML filename overwrites)
- Beehiiv quirks: use div not h1/h2, all colors need `!important`, HTML arrow entities, no double dollar signs
- ANTHROPIC_API_KEY is already in GitHub secrets (used for hero take, daily take, subtitle generation)
- GitHub Actions pushes data files every hour — always use the git stash workflow to avoid "fetch first" rejections
