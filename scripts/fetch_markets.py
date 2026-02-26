#!/usr/bin/env python3
"""
The Prob — Market Data Fetcher
Pulls top movers from Polymarket and Kalshi, writes to data/markets.json
Runs hourly via GitHub Actions.
"""

import os
import json
import math
import base64
import time
import re
import requests
from datetime import datetime, timezone, timedelta

# ── HOUSE STYLE ──────────────────────────────────────────────────────────────
# Rules for ALL generated copy on The Prob.
# When using Claude API for editorial copy, inject HOUSE_STYLE_PROMPT as system prompt.
#
#   1. NO EM DASHES (—). Use a comma, colon, or new sentence instead.
#      Em dashes are a dead giveaway for AI-generated text.
#   2. Short sentences. Max ~20 words per sentence.
#   3. No hedging ("perhaps", "might", "could potentially").
#   4. Numbers as numerals ($2.8M not "two-point-eight million").
#   5. Active voice only.
#
HOUSE_STYLE_PROMPT = (
    "You write for The Prob, a prediction markets newsletter. "
    "Voice: sharp, confident, dry wit, slightly irreverent. Like The Hustle. "
    "Intelligent but not academic. Opinionated but not arrogant. "
    "NEVER use em dashes. Use a comma or start a new sentence instead. "
    "Short sentences. Active voice. Numbers as numerals ($2M, 47%). "
    "No hedging ('perhaps', 'might', 'could potentially'). No fluff. No filler. "
    "Undetectable as AI. Write like a smart human who finds this genuinely interesting."
)

# ── CONFIG ───────────────────────────────────────────────────────────────────
KALSHI_KEY_ID    = os.environ.get("KALSHI_KEY_ID", "")
KALSHI_PRIV_KEY  = os.environ.get("KALSHI_PRIVATE_KEY", "")
KALSHI_BASE      = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA_BASE       = "https://gamma-api.polymarket.com"

MIN_VOLUME_USD         = 50_000
KALSHI_MIN_VOL         = 1_000      # Kalshi volumes are much lower than Polymarket
TOP_MOVERS_COUNT       = 6
HERO_MIN_VOLUME        = 1_000_000   # Hero needs at least $1M total volume — no obscure markets
HERO_SPORTS_MIN_VOLUME = 25_000_000  # Only truly massive sports events as hero

# Minimum 24h volume to be worth showing — filters MrBeast/micro view-count markets
MIN_INTERESTING_VOLUME = 100_000

# Question substrings that identify low-quality micro-markets to exclude entirely
JUNK_MARKET_PATTERNS = [
    "million views",
    "million subscribers",
    "mrbeast",                        # Catches "MrBeast's", "mrbeast", etc after lowercasing
    "price of bitcoin be between",    # Micro price-band markets
    "price of bitcoin be above",
    "price of bitcoin be below",
    "price of eth be between",
    "price of eth be above",
    "opens up or down",               # Next-day open direction markets (trivial)
    "post 1", "post 2", "post 3",     # Catches "post 115-139", "post 360" etc (Elon tweet-count)
    "tweets from",                    # Elon weekly tweet-count markets
    "fdv above", "fdv below",         # Obscure token launch FDV markets
    "one day after launch",           # Token launch micro-markets
]

# ── HELPERS ─────────────────────────────────────────────────────────────────

def fmt_volume(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    elif v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"

def fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %-d")
    except Exception:
        return iso[:10]

def change_direction(change_pts: float) -> str:
    if change_pts > 0.5:
        return "up"
    elif change_pts < -0.5:
        return "down"
    return "neutral"

def is_effectively_resolved(m: dict) -> bool:
    """
    Returns True if a market has essentially settled (prob near 0 or 100).
    These generate huge change_pts but are no longer live/interesting.
    Also catches same-day sports results that resolved overnight.
    """
    prob = m.get("prob", 50)
    if prob >= 98 or prob <= 2:
        return True
    return False

def is_dated_game_market(m: dict) -> bool:
    """
    Catches 'Will X win on YYYY-MM-DD?' style markets that aren't
    caught by slug/keyword sports detection.
    """
    q = m.get("question", "")
    return bool(re.search(r'\b(win|beat|cover|score)\b.{0,40}\b20\d\d-\d\d-\d\d\b', q, re.IGNORECASE))

def is_junk_market(m: dict) -> bool:
    """
    Filter out low-quality markets: micro-markets, internal Polymarket tags,
    weather/temperature minutiae, tweet-count markets, etc.
    """
    q = m.get("question", "").lower()
    if any(pattern in q for pattern in JUNK_MARKET_PATTERNS):
        return True
    # Polymarket internal/operational tags signal markets not meant for display
    JUNK_TAG_SLUGS = {"hide-from-new", "opinion", "recurring", "rewards-500-4pt5-50", "pre-market"}
    tag_slugs = set(m.get("tag_slugs", []))
    if tag_slugs & JUNK_TAG_SLUGS:
        return True
    return False

def days_until_close(end_date_str: str) -> float | None:
    """Return how many days until market closes. None if unparseable."""
    try:
        dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - now).total_seconds() / 86400
    except Exception:
        return None

# ── KALSHI RSA SIGNING ───────────────────────────────────────────────────────

def make_kalshi_headers(method: str, path: str) -> dict:
    if not KALSHI_KEY_ID or not KALSHI_PRIV_KEY:
        return {}
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        private_key = serialization.load_pem_private_key(
            KALSHI_PRIV_KEY.encode("utf-8"),
            password=None,
        )
        timestamp_ms = str(int(time.time() * 1000))
        path_without_query = path.split('?')[0]
        message = f"{timestamp_ms}{method}{path_without_query}".encode("utf-8")
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        sig_b64 = base64.b64encode(signature).decode("utf-8")
        return {
            "KALSHI-ACCESS-KEY":       KALSHI_KEY_ID,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": sig_b64,
            "Content-Type":            "application/json",
        }
    except Exception as e:
        print(f"[WARN] Kalshi signing failed: {e}")
        return {}

# ── POLYMARKET ───────────────────────────────────────────────────────────────

# Polymarket top-level category tag IDs (from /tags endpoint)
# These are the tags that appear on events, not granular entity tags
POLY_TAG_TO_CATEGORY = {
    # Politics
    "politics":        "Politics",
    "elections":       "Politics",
    "trump":           "Politics",
    "government":      "Politics",
    "geopolitics":     "Politics",
    "world":           "Politics",
    "middle-east":     "Politics",
    "ukraine":         "Politics",
    "us-politics":     "Politics",
    "global-politics": "Politics",
    # World / niche — fine to leave as World bucket
    "weather":         "World",
    "temperature":     "World",
    "natural-disasters": "World",
    "climate-science": "World",
    "new-york":        "World",
    "new-york-city":   "World",
    # Finance / Business
    "economics":       "Finance",
    "finance":         "Finance",
    "business":        "Finance",
    "economy":         "Finance",
    "stocks":          "Finance",
    "investing":       "Finance",
    "investment":      "Finance",
    "markets":         "Finance",
    "companies":       "Finance",
    # Crypto
    "crypto":          "Crypto",
    "cryptocurrency":  "Crypto",
    "bitcoin":         "Crypto",
    "ethereum":        "Crypto",
    "defi":            "Crypto",
    # Tech
    "technology":      "Technology",
    "tech":            "Technology",
    "ai":              "Technology",
    "science":         "Technology",
    "space":           "Technology",
    "artificial-intelligence": "Technology",
    "openai":          "Technology",
    "chatgpt":         "Technology",
    "spacex":          "Technology",
    "big-tech":        "Technology",
    "climate":         "Technology",
    "health":          "Technology",
    "biotech":         "Technology",
    # Sports
    "sports":          "Sports",
    "nba":             "Sports",
    "nfl":             "Sports",
    "mlb":             "Sports",
    "nhl":             "Sports",
    "soccer":          "Sports",
    "tennis":          "Sports",
    "golf":            "Sports",
    "mma":             "Sports",
    "esports":         "Sports",
    "formula-1":       "Sports",
    # Culture — Polymarket's nav uses "pop-culture" as the slug
    "pop-culture":     "Culture",
    "entertainment":   "Culture",
    "culture":         "Culture",
    "celebrities":     "Culture",
    "music":           "Culture",
    "awards":          "Culture",
    "movies":          "Culture",
    "film":            "Culture",
    "tv":              "Culture",
    "television":      "Culture",
    "oscars":          "Culture",
    "academy-awards":  "Culture",
}

def poly_category_from_tags(tags: list) -> str:
    """Map Polymarket event tags to our display_category. First match wins."""
    for t in tags:
        slug  = t.get("slug", "").lower()
        label = t.get("label", "").lower()
        cat = POLY_TAG_TO_CATEGORY.get(slug) or POLY_TAG_TO_CATEGORY.get(label)
        if cat:
            return cat
    return None   # caller will fall back to keyword logic or "World"

def fetch_polymarket() -> list[dict]:
    markets = []
    try:
        all_events = []
        seen_ids   = set()

        fetch_configs = [
            {"order": "volume24hr", "pages": 3},
            {"order": "volume",     "pages": 2},
        ]

        for cfg in fetch_configs:
            offset = 0
            for page in range(cfg["pages"]):
                try:
                    r = requests.get(
                        f"{GAMMA_BASE}/events",
                        params={
                            "active":    "true",
                            "closed":    "false",
                            "limit":     100,
                            "order":     cfg["order"],
                            "ascending": "false",
                            "offset":    offset,
                        },
                        timeout=15,
                    )
                    r.raise_for_status()
                    data = r.json()
                    if not data:
                        break
                    new = [e for e in data if e.get("id") not in seen_ids]
                    for e in new:
                        seen_ids.add(e.get("id"))
                    all_events.extend(new)
                    print(f"    Polymarket {cfg['order']} page {page+1}: {len(data)} fetched, {len(new)} new")
                    offset += 100
                except requests.RequestException as e:
                    print(f"    [WARN] Polymarket fetch failed (page {page+1}): {e}")
                    break

        print(f"  Polymarket unique events after dedup: {len(all_events)}")

        for event in all_events:
            # Category comes from the event-level tags
            event_tags  = event.get("tags", []) or []
            display_cat = poly_category_from_tags(event_tags)
            is_sports   = any(str(t.get("id")) == "1" for t in event_tags)
            if is_sports:
                display_cat = "Sports"
            tag_labels = [t.get("label", "").lower() for t in event_tags]

            for m in event.get("markets", []):
                try:
                    outcomes  = json.loads(m.get("outcomePrices", "[]"))
                    yes_price = float(outcomes[0]) if outcomes else None
                    if yes_price is None:
                        continue
                    volume     = float(m.get("volume", 0) or 0)
                    volume_24h = float(m.get("volume24hr", 0) or 0)
                    if volume < MIN_VOLUME_USD:
                        continue
                    change_raw = float(m.get("oneDayPriceChange", 0) or 0)
                    change_pts = round(change_raw * 100, 1)
                    end_date   = m.get("endDate", "") or m.get("endDateIso", "")

                    markets.append({
                        "source":           "Polymarket",
                        "question":         m.get("question", ""),
                        "slug":             m.get("slug", ""),
                        "url":              f"https://polymarket.com/event/{event.get('slug', m.get('slug', ''))}",
                        "prob":             round(yes_price * 100, 1),
                        "change_pts":       change_pts,
                        "direction":        change_direction(change_pts),
                        "volume":           volume,
                        "volume_fmt":       fmt_volume(volume),
                        "volume_24h":       volume_24h,
                        "end_date":         fmt_date(end_date) if end_date else "",
                        "end_date_raw":     end_date,
                        "liquidity":        float(m.get("liquidity", 0) or 0),
                        "category":         tag_labels[0] if tag_labels else "",
                        "is_sports":        is_sports,
                        "display_category": display_cat or "World",
                        "tags":             tag_labels,
                        "tag_slugs":        [t.get("slug","").lower() for t in event_tags],
                    })
                except (ValueError, IndexError, KeyError):
                    continue

        # Deduplicate by slug
        seen_slugs = set()
        deduped = []
        for m in markets:
            if m["slug"] not in seen_slugs:
                seen_slugs.add(m["slug"])
                deduped.append(m)
        markets = deduped

        cats = sorted(set(m["display_category"] for m in markets))
        print(f"  Polymarket display_categories: {cats}")
        # Debug: show tag slugs that fell through to World so we can catch gaps
        world_tags = set()
        for m in markets:
            if m["display_category"] == "World":
                for slug in m.get("tag_slugs", []):
                    if slug not in POLY_TAG_TO_CATEGORY:
                        world_tags.add(slug)
        if world_tags:
            print(f"  Unmapped tags falling to World: {sorted(world_tags)[:20]}")
    except Exception as e:
        print(f"[WARN] Polymarket fetch failed: {e}")
    print(f"  Got {len(markets)} Polymarket markets above volume threshold")
    return markets

# ── KALSHI ───────────────────────────────────────────────────────────────────

def fetch_kalshi() -> list[dict]:
    markets = []
    seen_tickers = set()

    def fetch_kalshi_page(extra_params={}):
        """Fetch one paginated pass of Kalshi events, return all qualifying markets."""
        results = []
        cursor = None
        pages = 0
        while pages < 15:
            params = {
                "limit":               100,
                "status":              "open",
                "with_nested_markets": "true",
                **extra_params,
            }
            if cursor:
                params["cursor"] = cursor
            try:
                resp = requests.get(f"{KALSHI_BASE}/events", params=params, timeout=15)
                resp.raise_for_status()
                data   = resp.json()
                events = data.get("events", [])
                if not events:
                    break
                for event in events:
                    category      = event.get("category", "")
                    event_title   = event.get("title", "")
                    series_ticker = event.get("series_ticker", event.get("event_ticker", ""))
                    for m in event.get("markets", []):
                        try:
                            ticker = m.get("ticker", "")
                            if ticker in seen_tickers:
                                continue
                            yes_bid = float(m.get("yes_bid", 0) or 0)
                            yes_ask = float(m.get("yes_ask", 0) or 0)
                            if yes_bid == 0 and yes_ask == 0:
                                continue
                            prob = round((yes_bid + yes_ask) / 2, 1)
                            if prob > 100 or prob < 0:
                                continue
                            volume_cents = float(m.get("volume", 0) or 0)
                            volume_usd   = volume_cents / 100
                            if volume_usd < KALSHI_MIN_VOL:
                                continue
                            volume_24h_cents = float(m.get("volume_24h", 0) or 0)
                            close_time = m.get("close_time", "") or ""

                            # Build question: combine event title + market subtitle if distinct
                            market_subtitle = m.get("subtitle", "") or m.get("title", "") or ""
                            if market_subtitle and market_subtitle.lower() != event_title.lower():
                                question = f"{event_title}: {market_subtitle}"
                            else:
                                question = event_title

                            # Calculate 24h change
                            last_price = float(m.get("last_price", 0) or 0)
                            prev_price = float(m.get("previous_yes_price", 0) or m.get("previous_price", 0) or 0)
                            change_pts = round(last_price - prev_price, 1) if last_price > 0 and prev_price > 0 else 0.0

                            disp_cat = KALSHI_CATEGORY_MAP.get(category, category or "World")
                            results.append({
                                "source":           "Kalshi",
                                "question":         question,
                                "slug":             ticker,
                                "url":              f"https://kalshi.com/markets/{series_ticker.lower()}",
                                "prob":             prob,
                                "change_pts":       change_pts,
                                "direction":        change_direction(change_pts),
                                "volume":           volume_usd,
                                "volume_fmt":       fmt_volume(volume_usd),
                                "volume_24h":       volume_24h_cents / 100,
                                "end_date":         fmt_date(close_time) if close_time else "",
                                "end_date_raw":     close_time,
                                "liquidity":        volume_usd * 0.1,
                                "category":         category,
                                "is_sports":        category.lower() == "sports",
                                "display_category": disp_cat,
                                "tags":             [category.lower()],
                            })
                            seen_tickers.add(ticker)
                        except (ValueError, KeyError):
                            continue
                cursor = data.get("cursor")
                if not cursor:
                    break
                pages += 1
                time.sleep(0.3)
            except requests.RequestException as e:
                print(f"[WARN] Kalshi fetch error: {e}")
                break
        return results

    try:
        # 1. General fetch (all categories, sorted by volume)
        markets += fetch_kalshi_page()
        print(f"  Kalshi general fetch: {len(markets)} markets")

        # 2. Category-specific fetches to ensure full coverage
        for cat in ["Sports", "Culture", "Crypto", "Technology"]:
            before = len(markets)
            markets += fetch_kalshi_page({"category": cat})
            added = len(markets) - before
            if added:
                print(f"  Kalshi {cat} fetch: +{added} markets")

    except Exception as e:
        print(f"[WARN] Kalshi fetch failed: {e}")

    print(f"  Got {len(markets)} Kalshi markets total")
    raw_cats  = sorted(set(m.get("category", "EMPTY") for m in markets))
    disp_cats = sorted(set(m.get("display_category", "UNSET") for m in markets))
    print(f"  Kalshi raw categories: {raw_cats}")
    print(f"  Kalshi display_categories: {disp_cats}")
    return markets

# ── SPORTS DETECTION ─────────────────────────────────────────────────────────

# Slug prefixes that definitively identify sports markets
SPORTS_SLUG_PREFIXES = [
    "epl-", "nba-", "nfl-", "mlb-", "nhl-", "mwoh-", "wwoh-",
    "uefa-", "lck-", "lol-", "cs2-", "dota-", "fifa-", "ncaa-",
    "mls-", "pga-", "ufc-", "f1-", "wwe-", "boxing-",
]

# Keywords that identify sports questions
SPORTS_KEYWORDS = [
    " vs ", " vs.", " v ",
    "nba", "nfl", "nhl", "mlb", "epl", "mls",
    "premier league", "bundesliga", "serie a", "la liga",
    "champions league", "europa league",
    "stanley cup", "super bowl", "world series", "march madness",
    "ncaa", "knockout", "bo3)", "bo5)", "lol:", "lck",
    "esports", "valorant", "overwatch",
    "fc win", "will win on 20",
    # ── ADDED: Olympic / winter sports ──
    "ice hockey", "gold medal", "olympic", "olympics",
    "world cup", "tour de france", "wimbledon",
    "grand slam", "formula 1", "formula one",
    "ufc", "mma", "boxing match", "fight night",
]

def is_sports_market(m: dict) -> bool:
    # Kalshi: trust category field
    if m["source"] == "Kalshi":
        return m.get("is_sports", False)
    # Polymarket: trust tag ID=1
    if m.get("is_sports", False):
        return True
    q    = m["question"].lower()
    slug = m.get("slug", "").lower()
    # Slug prefix check (most reliable for Polymarket)
    if any(slug.startswith(p) for p in SPORTS_SLUG_PREFIXES):
        return True
    # Dated game pattern: "Will X win on 2026-02-22?" → always sports
    if is_dated_game_market(m):
        return True
    # Keyword check
    return any(w in q for w in SPORTS_KEYWORDS)

# ── BUZZ / INTEREST SCORING ──────────────────────────────────────────────────

def score_market(m: dict) -> float:
    """
    Composite buzz score prioritising:
      1. Big absolute price moves (breaking news signal)
      2. High 24h volume (money rushing in = hot topic)
      3. Total volume (legitimacy / market size)
      4. Interesting probability (not near 0% or 100% = still debatable)
      5. Closing soon (urgency)
    """
    abs_change  = abs(m["change_pts"])
    volume      = m["volume"]
    volume_24h  = m.get("volume_24h", 0) or 0
    prob        = m["prob"]

    # 1. Price-move signal (0–25+ pts)
    move_score = abs_change * 2.5

    # 2. 24h volume surge — normalised log scale (0–6 pts)
    #    A market with $500K in last 24h is very hot
    vol_24h_score = math.log10(max(volume_24h, 1)) / 10 * 3

    # 3. Total volume legitimacy (0–2 pts)
    vol_total_score = math.log10(max(volume, 1)) / 10

    # 4. Probability interest — sweet spot 30–70% (0–1 pt)
    prob_interest = 1 - abs(prob - 50) / 50

    # 5. Urgency bonus — closing within 7 days gets up to 1.5 pts
    urgency = 0.0
    raw_end = m.get("end_date_raw", "")
    if raw_end:
        days = days_until_close(raw_end)
        if days is not None and 0 < days <= 7:
            urgency = 1.5 * (1 - days / 7)

    # 6. Recency bonus for Polymarket — markets trending on 24h vs total
    #    High ratio = suddenly getting lots of attention
    recency_bonus = 0.0
    if volume > 0 and volume_24h > 0:
        ratio = volume_24h / volume
        if ratio > 0.15:   # >15% of all volume in last 24h = breaking
            recency_bonus = min(ratio * 5, 3.0)

    return move_score + vol_24h_score + vol_total_score + prob_interest + urgency + recency_bonus

# ── HERO SELECTION ───────────────────────────────────────────────────────────

def pick_hero(markets: list[dict]) -> dict | None:
    """
    The hero is the single most buzzworthy non-sports market.
    Priority order: Politics > Finance > World > Technology > Culture > Crypto
    Sports require very high volume. Resolved markets excluded.
    """
    HERO_CATEGORY_PRIORITY = {
        "Politics":   1,
        "Finance":    2,
        "World":      3,
        "Technology": 4,
        "Culture":    5,
        "Crypto":     6,
    }
    candidates = [
        m for m in markets
        if m["volume"] >= HERO_MIN_VOLUME
        and not is_effectively_resolved(m)
        and not is_junk_market(m)
        and (not is_sports_market(m) or m["volume"] >= HERO_SPORTS_MIN_VOLUME)
    ]
    # Must have real price movement to be hero
    movers = [c for c in candidates if abs(c["change_pts"]) >= 2]
    pool   = movers if movers else candidates
    if not pool:
        return None
    # Sort: first by category priority, then by buzz score within each tier
    def hero_score(m):
        cat      = m.get("display_category", "World")
        priority = HERO_CATEGORY_PRIORITY.get(cat, 7)
        return (-priority, score_market(m))
    return max(pool, key=hero_score)

# ── CATEGORY MAPPING ─────────────────────────────────────────────────────────

KALSHI_CATEGORY_MAP = {
    # Politics
    "Politics":               "Politics",
    "Elections":              "Politics",
    # Business/Finance
    "Economics":              "Finance",
    "Finance":                "Finance",
    "Financials":             "Finance",
    "Companies":              "Finance",
    # Tech
    "Technology":             "Technology",
    "Science and Technology": "Technology",
    "Tech & Science":         "Technology",
    "Tech and Science":       "Technology",
    "Science":                "Technology",
    # Crypto
    "Crypto":                 "Crypto",
    "Cryptocurrency":         "Crypto",
    # Sports
    "Sports":                 "Sports",
    # Culture
    "Culture":                "Culture",
    "Entertainment":          "Culture",
    "Social":                 "Culture",
    "Mentions":               "Culture",
    # World/Other
    "Climate and Weather":    "World",
    "Climate":                "World",
    "Weather":                "World",
    "World":                  "World",
    "Health":                 "World",
}

POLITICS_KEYWORDS = [
    "president", "congress", "senate", "election", "vote",
    "trump", "biden", "harris", "republican", "democrat",
    "government", "prime minister", "minister", "parliament",
    "tariff", "executive order", "supreme court", "impeach",
    "fed chair", "cabinet", "orbán", "orban", "zelensky",
    "ceasefire", "sanctions", "nato", "un security",
]
FINANCE_KEYWORDS = [
    "fed ", "interest rate", "inflation", "gdp", "recession",
    "unemployment", "treasury", "rate cut", "rate hike",
    "fomc", "cpi", "jobs report", "s&p", "nasdaq", "dow",
    "ipo", "acquisition", "merger", "stock price", "market cap",
    "earnings", "revenue", "valuation", "bankrupt",
]
TECH_KEYWORDS = [
    "artificial intelligence", "chatgpt", "gpt", "openai",
    "spacex", "starship", "apple", "google", "microsoft",
    "tesla", "meta ", "nvidia", "semiconductor", "chip",
    "self-driving", "autonomous", "deepmind", "anthropic",
]
CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
    "crypto", "token", "altcoin", "defi", "nft", "blockchain",
    "coinbase", "binance", "stablecoin", "memecoin", "web3",
]
CULTURE_KEYWORDS = [
    "oscar", "academy award", "emmy", "grammy", "golden globe",
    "bafta", "tony award", "best picture", "best actor", "best actress",
    "best director", "best supporting", "best costume", "best score",
    "survivor", "bachelor", "bachelorette", "reality tv",
    "super bowl halftime", "world cup winner", "miss universe",
    "box office", "box-office", "movie", "film", "album",
    "chart", "billboard", "spotify", "streaming",
    "frankenstein", "sinners", "hamnet", "wicked",
    "nfl draft", "nba draft", "mlb draft",
    "pope", "dalai lama", "king charles", "royal",
    "taylor swift", "beyonce", "kanye", "drake",
]
WORLD_KEYWORDS = [
    "strike", "war", "ceasefire", "military", "troops",
    "iran", "russia", "ukraine", "china", "north korea",
    "missile", "nuclear", "sanctions", "treaty",
]

def get_category_label(m: dict) -> str:
    """Fallback only — Polymarket markets should already have display_category from poly_category_from_tags."""
    if m["source"] == "Kalshi":
        raw = m.get("category", "World")
        return KALSHI_CATEGORY_MAP.get(raw, "World")
    # Polymarket safety net
    if is_sports_market(m):
        return "Sports"
    slug = m.get("slug", "").lower()
    if any(slug.startswith(p) for p in ["btc-","eth-","crypto-","bitcoin-","solana-","xrp-"]):
        return "Crypto"
    return "World"

# ── MOVER SELECTION ──────────────────────────────────────────────────────────

def pick_movers(markets: list[dict], exclude_slug: str = "") -> list[dict]:
    candidates = [
        m for m in markets
        if m["slug"] != exclude_slug
        and not is_effectively_resolved(m)
        and not is_junk_market(m)
        and (abs(m["change_pts"]) > 0 or m["source"] == "Kalshi")
    ]
    candidates.sort(key=score_market, reverse=True)

    # Deduplicate by event series
    seen_series = {}
    deduped = []
    for c in candidates:
        slug = c.get("slug", "")
        if c["source"] == "Kalshi":
            # Use the event URL as series key — all candidates in same event share the same URL
            series_key = c.get("url", slug)
        else:
            series_key = re.sub(
                r'-(20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]|january|february|march|'
                r'april|may|june|july|august|september|october|november|december).*$',
                '', slug
            )
        if not series_key:
            series_key = " ".join(c["question"].lower().split()[:5])
        if series_key not in seen_series:
            seen_series[series_key] = True
            c["display_category"] = c.get("display_category") or get_category_label(c)
            deduped.append(c)

    # Slot layout: Politics, Sports, Finance, World, Technology, Sports
    # Hard cap: max 2 sports in movers. Fallback slots must also respect this.
    slot_categories = ["Politics", "Sports", "Finance", "World", "Technology", "Sports"]
    result = []
    used_slugs = set()
    sports_count = 0
    MAX_SPORTS_IN_MOVERS = 2

    for slot_cat in slot_categories:
        filled = False
        # Try to fill with the intended category
        for c in deduped:
            if c["slug"] in used_slugs:
                continue
            if c["display_category"] == slot_cat:
                # Enforce sports cap even for intended sports slots
                if slot_cat == "Sports" and sports_count >= MAX_SPORTS_IN_MOVERS:
                    break
                result.append(c)
                used_slugs.add(c["slug"])
                if slot_cat == "Sports":
                    sports_count += 1
                filled = True
                break
        if not filled:
            # Fallback: pick best unused non-sports market (never use fallback to add sports)
            for c in deduped:
                if c["slug"] not in used_slugs and c["display_category"] != "Sports":
                    result.append(c)
                    used_slugs.add(c["slug"])
                    filled = True
                    break
            if not filled:
                # Last resort: any unused market, still respecting sports cap
                for c in deduped:
                    if c["slug"] not in used_slugs:
                        if is_sports_market(c) and sports_count >= MAX_SPORTS_IN_MOVERS:
                            continue
                        result.append(c)
                        used_slugs.add(c["slug"])
                        if is_sports_market(c):
                            sports_count += 1
                        break

    # Guarantee at least 2 Kalshi markets (contractual for newsletter variety)
    kalshi_count = sum(1 for m in result if m["source"] == "Kalshi")
    if kalshi_count < 2:
        kalshi_needed = 2 - kalshi_count
        for c in deduped:
            if c["slug"] not in used_slugs and c["source"] == "Kalshi":
                # Replace the lowest-scoring non-Kalshi slot
                non_kalshi_slots = [
                    (i, m) for i, m in enumerate(result)
                    if m["source"] != "Kalshi"
                ]
                if non_kalshi_slots:
                    worst_idx = min(non_kalshi_slots, key=lambda x: score_market(x[1]))[0]
                    used_slugs.discard(result[worst_idx]["slug"])
                    result[worst_idx] = c
                    used_slugs.add(c["slug"])
                    kalshi_needed -= 1
            if kalshi_needed == 0:
                break

    return result[:TOP_MOVERS_COUNT]

def get_series_key(m: dict) -> str:
    """
    Normalize a market to its parent series for deduplication.
    """
    slug = m.get("slug", "")

    if m["source"] == "Kalshi":
        # All markets under the same Kalshi event share the same URL — use it
        return m.get("url", slug)

    # Polymarket: strip date/price suffixes
    key = re.sub(
        r'-(20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]|january|february|march|'
        r'april|may|june|july|august|september|october|november|december).*$',
        '', slug
    )
    key = re.sub(r'-(above|below|between|over|under)[-0-9a-z]*$', '', key)
    key = re.sub(r'-[0-9]+-[0-9]+.*$', '', key)
    key = re.sub(r'-[0-9]+.*$', '', key)
    key = re.sub(r'-(reach|dip|hit|drop|fall|rise|surge|crash|pump|dump)(-to|-by)?$', '', key)

    return key or " ".join(m.get("question", "").lower().split()[:5])

# ── TICKER SELECTION ─────────────────────────────────────────────────────────

def pick_ticker(markets: list[dict]) -> list[dict]:
    """
    Ticker: 10 markets by buzz score with:
    - Series dedup (no duplicate date/price variants of same event)
    - Max 3 sports
    - Max 2 from any single category (max 1 for Tech to prevent AI model flood)
    - Resolved and junk markets excluded
    """
    MAX_SPORTS_IN_TICKER = 3
    # Per-category caps — tighter categories get capped lower
    CATEGORY_CAPS = {
        "Technology": 1,   # Only best AI/tech market, not a whole cluster
        "Crypto":     2,
        "Politics":   2,
        "Finance":    2,
        "World":      2,
        "Culture":    1,
        "Sports":     3,   # Handled separately above
    }
    DEFAULT_CAP = 2

    scored = sorted(
        [m for m in markets if not is_effectively_resolved(m) and not is_junk_market(m)],
        key=score_market, reverse=True
    )

    seen_slugs      = set()
    seen_series     = set()
    category_counts = {}
    sports_count    = 0
    ticker          = []

    for m in scored:
        slug       = m.get("slug", "")
        series_key = get_series_key(m)

        if slug in seen_slugs or series_key in seen_series:
            continue

        is_sport = is_sports_market(m)
        cat      = get_category_label(m)

        if is_sport and sports_count >= MAX_SPORTS_IN_TICKER:
            continue
        cat_cap = CATEGORY_CAPS.get(cat, DEFAULT_CAP)
        if not is_sport and category_counts.get(cat, 0) >= cat_cap:
            continue

        ticker.append(m)
        seen_slugs.add(slug)
        seen_series.add(series_key)
        if is_sport:
            sports_count += 1
        else:
            category_counts[cat] = category_counts.get(cat, 0) + 1

        if len(ticker) >= 10:
            break

    return ticker

# ── HERO EDITORIAL TAKE ──────────────────────────────────────────────────────

def strip_em_dashes(text: str) -> str:
    """House style: never use em dashes. Replace with comma, colon, or period."""
    # Replace ' — ' (spaced em dash) with a comma-space
    text = text.replace(" \u2014 ", ", ")
    # Replace any remaining em dashes
    text = text.replace("\u2014", ", ")
    return text

def generate_daily_take(hero: dict, movers: list[dict]) -> dict:
    """
    Generate 'The Prob's Daily Take' using Claude API.
    Returns a dict with: headline, deck, category, sidebar (list of 3 items),
    and date. Falls back to template if API unavailable.
    """
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    q      = hero.get("question", "")
    prob   = hero.get("prob", 50)
    change = hero.get("change_pts", 0)
    vol    = hero.get("volume_fmt", "")
    cat    = hero.get("display_category", "World")
    source = hero.get("source", "")

    # Build sidebar context from top movers
    sidebar_context = ""
    for i, m in enumerate(movers[:3], 1):
        sidebar_context += (
            f"{i}. {m['question']} | "
            f"{m['prob']}% ({'+' if m['change_pts'] > 0 else ''}{m['change_pts']}pts) | "
            f"${m['volume_fmt']} vol | {m.get('display_category','')}\n"
        )

    prompt = f"""You are writing today's featured editorial for The Prob, a prediction markets newsletter.

Today's hero market:
- Question: {q}
- Current odds: {prob}%
- 24h change: {'+' if change > 0 else ''}{change} pts
- Total volume: ${vol}
- Category: {cat}
- Source: {source}

Today's other notable markets:
{sidebar_context}

Write the following in The Prob's voice (sharp, confident, dry wit, no em dashes, active voice):

1. HEADLINE: A punchy, specific headline for this market's story today (not just restating the question). Make it feel like a smart take, not a data readout. 10-15 words max.

2. DECK: 2-3 sentences. What happened, why it moved, what it means. Hook the reader. No em dashes. No hedging.

3. CATEGORY_LABEL: One short label like "Deep Dive · Politics" or "Market Watch · Crypto"

4. SIDEBAR_1_HEADLINE: A sharp 1-sentence editorial angle on market 1 above (not just the question). 
5. SIDEBAR_1_LABEL: Short label like "Fed Cut March: 72%"

6. SIDEBAR_2_HEADLINE: Same for market 2.
7. SIDEBAR_2_LABEL: Short label.

8. SIDEBAR_3_HEADLINE: Same for market 3.
9. SIDEBAR_3_LABEL: Short label.

Respond in this exact format, one item per line:
HEADLINE: ...
DECK: ...
CATEGORY_LABEL: ...
SIDEBAR_1_HEADLINE: ...
SIDEBAR_1_LABEL: ...
SIDEBAR_2_HEADLINE: ...
SIDEBAR_2_LABEL: ...
SIDEBAR_3_HEADLINE: ...
SIDEBAR_3_LABEL: ..."""

    if ANTHROPIC_API_KEY:
        try:
            import requests as req
            r = req.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 600,
                    "system":     HOUSE_STYLE_PROMPT,
                    "messages":   [{"role": "user", "content": prompt}],
                },
                timeout=25,
            )
            if r.ok:
                raw = r.json()["content"][0]["text"].strip()

                # Parse structured response — keys are ALL_CAPS, values follow ": "
                # Use regex to handle colons inside values (e.g. "47%: here's why")
                parsed = {}
                # Match lines starting with a known key
                key_pattern = re.compile(
                    r'^(HEADLINE|DECK|CATEGORY_LABEL|'
                    r'SIDEBAR_1_HEADLINE|SIDEBAR_1_LABEL|'
                    r'SIDEBAR_2_HEADLINE|SIDEBAR_2_LABEL|'
                    r'SIDEBAR_3_HEADLINE|SIDEBAR_3_LABEL)'
                    r':\s*(.+)$',
                    re.MULTILINE
                )
                for m in key_pattern.finditer(raw):
                    parsed[m.group(1)] = strip_em_dashes(m.group(2).strip())


                now_et = datetime.now(timezone.utc) + timedelta(hours=-5)
                return {
                    "headline":        parsed.get("HEADLINE", q),
                    "deck":            parsed.get("DECK", ""),
                    "category_label":  parsed.get("CATEGORY_LABEL", f"Market Watch · {cat}"),
                    "date":            now_et.strftime("%b %-d, %Y"),
                    "hero_url":        hero.get("url", ""),
                    "sidebar": [
                        {
                            "headline": parsed.get("SIDEBAR_1_HEADLINE", movers[0]["question"] if len(movers) > 0 else ""),
                            "label":    parsed.get("SIDEBAR_1_LABEL", ""),
                            "url":      movers[0].get("url", "") if len(movers) > 0 else "",
                        },
                        {
                            "headline": parsed.get("SIDEBAR_2_HEADLINE", movers[1]["question"] if len(movers) > 1 else ""),
                            "label":    parsed.get("SIDEBAR_2_LABEL", ""),
                            "url":      movers[1].get("url", "") if len(movers) > 1 else "",
                        },
                        {
                            "headline": parsed.get("SIDEBAR_3_HEADLINE", movers[2]["question"] if len(movers) > 2 else ""),
                            "label":    parsed.get("SIDEBAR_3_LABEL", ""),
                            "url":      movers[2].get("url", "") if len(movers) > 2 else "",
                        },
                    ],
                }
            else:
                print(f"  [WARN] Daily Take API failed: {r.status_code} {r.text[:100]}")
        except Exception as e:
            import traceback
            print(f"  [WARN] Daily Take generation failed: {e}")
            traceback.print_exc()

    # Fallback: construct from raw data if API unavailable
    now_et = datetime.now(timezone.utc) + timedelta(hours=-5)
    direction = "up" if change > 0 else "down"
    deck = (
        f"The crowd has ${vol} riding on this one. "
        f"Odds are {prob}%, {abs(change)} points {direction} today. "
        f"Here's what the market is telling you."
    )
    return {
        "headline":       q,
        "deck":           strip_em_dashes(deck),
        "category_label": f"Market Watch · {cat}",
        "date":           now_et.strftime("%b %-d, %Y"),
        "sidebar": [
            {
                "headline": m["question"],
                "label":    f"{m['prob']}% {'▲' if m['change_pts'] > 0 else '▼' if m['change_pts'] < 0 else ''}",
                "url":      m.get("url", ""),
            }
            for m in movers[:3]
        ],
    }


def generate_hero_take(hero: dict) -> str:
    """
    Generate a 2-sentence Hustle-style take on the hero market via Claude API.
    Falls back to a clean template if API is unavailable.
    """
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    q      = hero.get("question", "")
    prob   = hero.get("prob", 50)
    change = hero.get("change_pts", 0)
    vol    = hero.get("volume_fmt", "")
    cat    = hero.get("display_category", "World")
    source = hero.get("source", "")

    if ANTHROPIC_API_KEY:
        try:
            import requests as req
            prompt = (
                f"Market: {q}\n"
                f"Odds: {prob}%\n"
                f"24h change: {'+' if change > 0 else ''}{change} points\n"
                f"Volume: ${vol}\n"
                f"Category: {cat}\n"
                f"Source: {source}\n\n"
                "Write exactly 2 sentences for The Prob's hero market card.\n"
                "Sentence 1: what the market is saying right now (use the odds and movement).\n"
                "Sentence 2: why it matters or what to watch.\n"
                "No em dashes. No hedging. No 'This market' opener. Confident, sharp, human. Just the 2 sentences."
            )
            r = req.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 120,
                    "system":     HOUSE_STYLE_PROMPT,
                    "messages":   [{"role": "user", "content": prompt}],
                },
                timeout=15,
            )
            if r.ok:
                text = r.json()["content"][0]["text"].strip()
                return strip_em_dashes(text)
            else:
                print(f"  [WARN] Hero take API failed: {r.status_code}")
        except Exception as e:
            print(f"  [WARN] Hero take generation failed: {e}")

    # Fallback template
    money_line = f"${vol}" if vol else "real money"
    odds_word  = "likely" if prob > 65 else "unlikely" if prob < 35 else "a toss-up"
    direction  = f"up {change} pts" if change > 5 else f"down {abs(change)} pts" if change < -5 else "steady"
    s1 = f"The crowd has {money_line} on this at {prob}%, calling it {odds_word}."
    s2 = f"Odds are {direction} today. Worth watching."
    return strip_em_dashes(f"{s1} {s2}")

# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    now_utc     = datetime.now(timezone.utc)
    now_et      = now_utc + timedelta(hours=-5)
    updated_str = now_et.strftime("%b %-d, %Y · %-I:%M %p ET")

    print("Fetching Polymarket…")
    poly_markets = fetch_polymarket()

    print("Fetching Kalshi…")
    kalshi_markets = fetch_kalshi()

    all_markets = poly_markets + kalshi_markets
    print(f"  Total: {len(all_markets)} markets")

    if not all_markets:
        print("ERROR: No markets fetched. Aborting.")
        return

    # Debug: show top 10 by buzz score with filtering decisions
    top_by_buzz = sorted(all_markets, key=score_market, reverse=True)[:15]
    print("\n  Top 15 by buzz score (pre-filter):")
    for i, m in enumerate(top_by_buzz, 1):
        is_sport   = is_sports_market(m)
        resolved   = is_effectively_resolved(m)
        junk       = is_junk_market(m)
        hero_ok    = not is_sport or m["volume"] >= HERO_SPORTS_MIN_VOLUME
        flags = []
        if is_sport:    flags.append("SPORTS")
        if resolved:    flags.append("RESOLVED")
        if junk:        flags.append("JUNK")
        if not hero_ok: flags.append("HERO-BLOCKED")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"    {i}. [{m['source']}] {m['question'][:55]}{flag_str}")
        print(f"       prob={m['prob']}% Δ={m['change_pts']}pts vol={m['volume_fmt']} 24h={fmt_volume(m['volume_24h'])} score={score_market(m):.2f}")

    hero      = pick_hero(all_markets)
    hero_slug = hero["slug"] if hero else ""
    movers    = pick_movers(all_markets, exclude_slug=hero_slug)
    ticker    = pick_ticker(all_markets)

    print(f"\n  Hero:   {hero['question'][:70] if hero else 'none'}")
    print(f"  Movers ({len(movers)}):")
    for m in movers:
        print(f"    [{m['display_category']}] {m['question'][:55]} ({m['source']})")
    print(f"  Ticker ({len(ticker)}):")
    for m in ticker:
        print(f"    [{m.get('display_category', '?')}] {m['question'][:55]} ({m['source']})")

    # Build full market catalog for category pages
    # Dedup: for Kalshi, one market per event URL (best by score). For Polymarket, one per slug.
    catalog = []
    seen_poly_slugs  = set()
    seen_kalshi_urls = set()

    all_sorted = sorted(all_markets, key=score_market, reverse=True)
    for m in all_sorted:
        if is_junk_market(m):
            continue
        if is_effectively_resolved(m):
            continue
        if m["source"] == "Kalshi":
            url = m.get("url", m.get("slug", ""))
            if url in seen_kalshi_urls:
                continue
            seen_kalshi_urls.add(url)
        else:
            slug = m.get("slug", "")
            if slug in seen_poly_slugs:
                continue
            seen_poly_slugs.add(slug)
        # Use display_category already set during fetch; fallback only if missing
        if not m.get("display_category"):
            m["display_category"] = get_category_label(m)
        catalog.append(m)

    # Generate hero "The Prob's Take" — 2-sentence card blurb
    if hero:
        hero["prob_take"] = generate_hero_take(hero)

    # Generate "The Prob's Daily Take" — full editorial section
    print("\nGenerating Daily Take (Claude API)...")
    daily_take = generate_daily_take(hero, movers) if hero else None
    if daily_take:
        print(f"  Headline: {daily_take['headline'][:70]}")

    output = {
        "updated":     updated_str,
        "updated_iso": now_utc.isoformat(),
        "hero":        hero,
        "movers":      movers,
        "ticker":      ticker,
        "daily_take":  daily_take,
        "all_markets": catalog,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/markets.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Wrote data/markets.json")
    print(f"  Updated: {updated_str}")

if __name__ == "__main__":
    main()
