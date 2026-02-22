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

# ── CONFIG ──────────────────────────────────────────────────────────────────
KALSHI_KEY_ID    = os.environ.get("KALSHI_KEY_ID", "")
KALSHI_PRIV_KEY  = os.environ.get("KALSHI_PRIVATE_KEY", "")
KALSHI_BASE      = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA_BASE       = "https://gamma-api.polymarket.com"

MIN_VOLUME_USD   = 50_000
KALSHI_MIN_VOL   = 10_000     # Kalshi volumes are generally lower
TOP_MOVERS_COUNT = 6
HERO_MIN_VOLUME        = 500_000
HERO_SPORTS_MIN_VOLUME = 25_000_000  # Only truly massive sports events (Super Bowl etc) as hero

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

# Expanded tag list to capture more breaking/buzzworthy markets
POLYMARKET_TAGS = [
    "trending",
    "politics",
    "crypto",
    "economics",
    "science",
    "technology",
    "world",
    "entertainment",
    "climate",
    "business",
    "health",
    "culture",
]

def fetch_polymarket() -> list[dict]:
    markets = []
    try:
        all_raw = []
        for tag in POLYMARKET_TAGS:
            try:
                r = requests.get(
                    f"{GAMMA_BASE}/markets",
                    params={
                        "active":    "true",
                        "closed":    "false",
                        "limit":     50,
                        "order":     "volume24hr",  # Sort by 24h volume = hottest right now
                        "ascending": "false",
                        "tag_slug":  tag,
                    },
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                all_raw.extend(data)
                print(f"    Polymarket tag '{tag}': {len(data)} markets")
            except requests.RequestException as e:
                print(f"    [WARN] Polymarket tag '{tag}' failed: {e}")
                continue

        raw = list({m["id"]: m for m in all_raw}.values())
        print(f"  Polymarket unique markets after dedup: {len(raw)}")

        for m in raw:
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
                    "source":     "Polymarket",
                    "question":   m.get("question", ""),
                    "slug":       m.get("slug", ""),
                    "url":        f"https://polymarket.com/event/{(m.get('events') or [{}])[0].get('slug', m.get('slug', ''))}",
                    "prob":       round(yes_price * 100, 1),
                    "change_pts": change_pts,
                    "direction":  change_direction(change_pts),
                    "volume":     volume,
                    "volume_fmt": fmt_volume(volume),
                    "volume_24h": volume_24h,
                    "end_date":   fmt_date(end_date) if end_date else "",
                    "end_date_raw": end_date,
                    "liquidity":  float(m.get("liquidity", 0) or 0),
                    "category":   " ".join([t.get("label","") for t in m.get("tags", [])]).lower(),
                    "is_sports":  any(str(t.get("id")) == "1" for t in m.get("tags", [])),
                    "tags":       [t.get("label","").lower() for t in m.get("tags", [])],
                })
            except (ValueError, IndexError, KeyError):
                continue
    except Exception as e:
        print(f"[WARN] Polymarket fetch failed: {e}")
    return markets

# ── KALSHI ───────────────────────────────────────────────────────────────────

def fetch_kalshi() -> list[dict]:
    markets = []
    try:
        cursor = None
        pages_fetched = 0
        while pages_fetched < 10:
            params = {
                "limit":               100,
                "status":              "open",
                "with_nested_markets": "true",
            }
            if cursor:
                params["cursor"] = cursor
            resp = requests.get(
                f"{KALSHI_BASE}/events",
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data   = resp.json()
            events = data.get("events", [])
            if not events:
                break
            for event in events:
                category = event.get("category", "")
                for m in event.get("markets", []):
                    try:
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
                        markets.append({
                            "source":       "Kalshi",
                            "question":     event.get("title", m.get("title", "")),
                            "slug":         m.get("ticker", ""),
                            "url":          f"https://kalshi.com/markets/{event.get('series_ticker', event.get('event_ticker', '')).lower()}",
                            "prob":         prob,
                            "change_pts":   0.0,  # Kalshi doesn't expose 24h change via public API
                            "direction":    "neutral",
                            "volume":       volume_usd,
                            "volume_fmt":   fmt_volume(volume_usd),
                            "volume_24h":   volume_24h_cents / 100,
                            "end_date":     fmt_date(close_time) if close_time else "",
                            "end_date_raw": close_time,
                            "liquidity":    volume_usd * 0.1,
                            "category":     category,
                            "is_sports":    category == "Sports",
                            "display_category": category,
                            "tags":         [category.lower()],
                        })
                    except (ValueError, KeyError):
                        continue
            cursor = data.get("cursor")
            if not cursor:
                break
            pages_fetched += 1
            time.sleep(0.5)  # Avoid 429 rate limiting
    except requests.RequestException as e:
        print(f"[WARN] Kalshi fetch failed: {e}")
    print(f"  Got {len(markets)} Kalshi markets")
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
    Sports require a very high volume bar ($5M+) to appear here,
    preventing niche game results from dominating the front page.
    Resolved/settled markets (prob ≥98% or ≤2%) are excluded entirely.
    """
    candidates = [
        m for m in markets
        if m["volume"] >= HERO_MIN_VOLUME
        and not is_effectively_resolved(m)
        and (not is_sports_market(m) or m["volume"] >= HERO_SPORTS_MIN_VOLUME)
    ]
    # Prefer markets with actual price movement
    movers = [c for c in candidates if abs(c["change_pts"]) >= 2]
    if movers:
        return max(movers, key=score_market)
    if candidates:
        return max(candidates, key=score_market)
    return None

# ── CATEGORY MAPPING ─────────────────────────────────────────────────────────

KALSHI_CATEGORY_MAP = {
    "Politics":               "Politics",
    "Economics":              "Finance",
    "Finance":                "Finance",
    "Financials":             "Finance",
    "Technology":             "Technology",
    "Science and Technology": "Technology",
    "Climate and Weather":    "World",
    "Science":                "Technology",
    "World":                  "World",
    "Sports":                 "Sports",
    "Culture":                "Culture",
    "Entertainment":          "Culture",
    "Health":                 "World",
}

POLITICS_KEYWORDS = [
    "president", "congress", "senate", "election", "vote",
    "trump", "biden", "harris", "republican", "democrat",
    "government", "prime minister", "minister", "parliament",
    "tariff", "executive order", "supreme court", "impeach",
    "fed chair", "cabinet",
]
FINANCE_KEYWORDS = [
    "fed", "interest rate", "inflation", "gdp", "recession",
    "unemployment", "treasury", "tariff", "trade", "rate cut",
    "rate hike", "fomc", "cpi", "jobs report", "s&p",
    "nasdaq", "dow", "ipo", "acquisition", "merger",
]
TECH_KEYWORDS = [
    "ai", "artificial intelligence", "chatgpt", "gpt", "openai",
    "spacex", "apple", "google", "microsoft", "tesla", "meta",
    "amazon", "nvidia", "semiconductor", "chip", "tech",
]

def get_category_label(m: dict) -> str:
    if m["source"] == "Kalshi":
        raw = m.get("category", "World")
        return KALSHI_CATEGORY_MAP.get(raw, "World")
    if is_sports_market(m):
        return "Sports"
    slug = m.get("slug", "").lower()
    q    = m["question"].lower()
    if any(slug.startswith(p) for p in ["btc-","eth-","crypto-","bitcoin-","solana-","xrp-"]):
        return "Crypto"
    if any(w in q for w in POLITICS_KEYWORDS):
        return "Politics"
    if any(w in q for w in FINANCE_KEYWORDS):
        return "Finance"
    if any(w in q for w in TECH_KEYWORDS):
        return "Technology"
    return "World"

# ── MOVER SELECTION ──────────────────────────────────────────────────────────

def pick_movers(markets: list[dict], exclude_slug: str = "") -> list[dict]:
    candidates = [
        m for m in markets
        if m["slug"] != exclude_slug
        and not is_effectively_resolved(m)
        # For Polymarket, require actual movement; Kalshi included regardless
        and (abs(m["change_pts"]) > 0 or m["source"] == "Kalshi")
    ]
    candidates.sort(key=score_market, reverse=True)

    # Deduplicate by event series
    seen_series = {}
    deduped = []
    for c in candidates:
        slug = c.get("slug", "")
        if c["source"] == "Kalshi":
            series_key = re.sub(r'-[A-Z0-9]+$', '', slug) or slug
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
            c["display_category"] = get_category_label(c)
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
    """Normalize a market slug to its parent series for deduplication."""
    slug = m.get("slug", "")
    if m["source"] == "Kalshi":
        return re.sub(r'-[A-Z0-9]+$', '', slug) or slug
    # Strip date suffixes from Polymarket slugs
    key = re.sub(
        r'-(20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]|january|february|march|'
        r'april|may|june|july|august|september|october|november|december).*$',
        '', slug
    )
    return key or " ".join(m.get("question", "").lower().split()[:5])

# ── TICKER SELECTION ─────────────────────────────────────────────────────────

def pick_ticker(markets: list[dict]) -> list[dict]:
    """
    Ticker: 10 markets by buzz score with:
    - Series dedup (no duplicate Iran/Fed/etc date variants)
    - Max 3 sports
    - Max 3 from any single non-sports category
    - Resolved markets excluded
    """
    MAX_SPORTS_IN_TICKER = 3
    MAX_PER_CATEGORY     = 3

    scored = sorted(
        [m for m in markets if not is_effectively_resolved(m)],
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
        if not is_sport and category_counts.get(cat, 0) >= MAX_PER_CATEGORY:
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

# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    now_utc     = datetime.now(timezone.utc)
    now_et      = now_utc + timedelta(hours=-5)
    updated_str = now_et.strftime("%b %-d, %Y · %-I:%M %p ET")

    print("Fetching Polymarket…")
    poly_markets = fetch_polymarket()
    print(f"  Got {len(poly_markets)} Polymarket markets above volume threshold")

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
        hero_ok    = not is_sport or m["volume"] >= HERO_SPORTS_MIN_VOLUME
        flags = []
        if is_sport:   flags.append("SPORTS")
        if resolved:   flags.append("RESOLVED")
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
        cat = get_category_label(m)
        print(f"    [{cat}] {m['question'][:55]} ({m['source']})")

    output = {
        "updated":     updated_str,
        "updated_iso": now_utc.isoformat(),
        "hero":        hero,
        "movers":      movers,
        "ticker":      ticker,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/markets.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Wrote data/markets.json")
    print(f"  Updated: {updated_str}")

if __name__ == "__main__":
    main()
