#!/usr/bin/env python3
"""
The Prob — Market Data Fetcher
Pulls top movers from Polymarket and Kalshi, writes to data/markets.json
Runs 4x/day via GitHub Actions.
"""

import os
import json
import math
import requests
from datetime import datetime, timezone, timedelta

# ── CONFIG ──────────────────────────────────────────────────────────────────
KALSHI_API_KEY   = os.environ.get("KALSHI_API_KEY", "")
KALSHI_BASE      = "https://trading-api.kalshi.com/trade-api/v2"
POLY_BASE        = "https://clob.polymarket.com"
GAMMA_BASE       = "https://gamma-api.polymarket.com"  # richer market metadata

MIN_VOLUME_USD   = 50_000   # ignore thin markets below this volume
TOP_MOVERS_COUNT = 6        # cards shown in the movers grid
HERO_MIN_VOLUME  = 500_000  # hero card should be a high-volume market

# ── HELPERS ─────────────────────────────────────────────────────────────────

def fmt_volume(v: float) -> str:
    """Format a dollar volume as $1.2M or $450K."""
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    elif v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"

def fmt_date(iso: str) -> str:
    """Turn an ISO date string into 'Mar 19' format."""
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

# ── POLYMARKET ───────────────────────────────────────────────────────────────

def fetch_polymarket() -> list[dict]:
    """
    Fetch active markets from Gamma API (richer data than CLOB).
    Returns a list of normalized market dicts.
    """
    markets = []
    try:
        # Fetch active markets sorted by volume, with 24h price history
        resp = requests.get(
            f"{GAMMA_BASE}/markets",
            params={
                "active":    "true",
                "closed":    "false",
                "limit":     100,
                "order":     "volume24hr",
                "ascending": "false",
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()

        for m in raw:
            try:
                # Polymarket binary markets have outcomes; grab YES price
                outcomes     = json.loads(m.get("outcomePrices", "[]"))
                yes_price    = float(outcomes[0]) if outcomes else None
                if yes_price is None:
                    continue

                volume       = float(m.get("volume", 0) or 0)
                volume_24h   = float(m.get("volume24hr", 0) or 0)
                if volume < MIN_VOLUME_USD:
                    continue

                # 24h change — Polymarket returns oneDayPriceChange as a decimal
                change_raw   = float(m.get("oneDayPriceChange", 0) or 0)
                change_pts   = round(change_raw * 100, 1)   # convert to percentage points

                end_date     = m.get("endDate", "") or m.get("endDateIso", "")

                markets.append({
                    "source":      "Polymarket",
                    "question":    m.get("question", ""),
                    "slug":        m.get("slug", ""),
                    "url":         f"https://polymarket.com/event/{m.get('slug', '')}",
                    "prob":        round(yes_price * 100, 1),
                    "change_pts":  change_pts,
                    "direction":   change_direction(change_pts),
                    "volume":      volume,
                    "volume_fmt":  fmt_volume(volume),
                    "volume_24h":  volume_24h,
                    "end_date":    fmt_date(end_date) if end_date else "",
                    "liquidity":   float(m.get("liquidity", 0) or 0),
                })
            except (ValueError, IndexError, KeyError):
                continue

    except requests.RequestException as e:
        print(f"[WARN] Polymarket fetch failed: {e}")

    return markets


# ── KALSHI ───────────────────────────────────────────────────────────────────

def fetch_kalshi() -> list[dict]:
    """
    Fetch active markets from Kalshi v2 API.
    Returns a list of normalized market dicts.
    """
    markets = []
    headers = {}
    if KALSHI_API_KEY:
        headers["Authorization"] = f"Token {KALSHI_API_KEY}"

    try:
        cursor = None
        pages_fetched = 0

        while pages_fetched < 5:   # fetch up to 5 pages (500 markets)
            params = {"limit": 100, "status": "open"}
            if cursor:
                params["cursor"] = cursor

            resp = requests.get(
                f"{KALSHI_BASE}/markets",
                headers=headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data   = resp.json()
            batch  = data.get("markets", [])
            if not batch:
                break

            for m in batch:
                try:
                    # Kalshi yes_bid / yes_ask mid-price as probability
                    yes_bid = float(m.get("yes_bid", 0) or 0)
                    yes_ask = float(m.get("yes_ask", 0) or 0)
                    if yes_bid == 0 and yes_ask == 0:
                        continue
                    prob = round(((yes_bid + yes_ask) / 2) * 100, 1)

                    # Volume: Kalshi gives volume in cents, convert to dollars
                    volume_cents = float(m.get("volume", 0) or 0)
                    volume_usd   = volume_cents / 100
                    if volume_usd < MIN_VOLUME_USD:
                        continue

                    # 24h change: Kalshi doesn't expose this directly in list endpoint.
                    # We'll approximate from previous_yes_bid if available,
                    # otherwise mark as 0 (no change shown).
                    prev_bid   = float(m.get("previous_yes_bid", yes_bid) or yes_bid)
                    prev_ask   = float(m.get("previous_yes_ask", yes_ask) or yes_ask)
                    prev_prob  = ((prev_bid + prev_ask) / 2) * 100
                    change_pts = round(prob - prev_prob, 1)

                    close_time = m.get("close_time", "") or ""

                    markets.append({
                        "source":      "Kalshi",
                        "question":    m.get("title", ""),
                        "slug":        m.get("ticker", ""),
                        "url":         f"https://kalshi.com/markets/{m.get('ticker', '')}",
                        "prob":        prob,
                        "change_pts":  change_pts,
                        "direction":   change_direction(change_pts),
                        "volume":      volume_usd,
                        "volume_fmt":  fmt_volume(volume_usd),
                        "volume_24h":  0,
                        "end_date":    fmt_date(close_time) if close_time else "",
                        "liquidity":   volume_usd * 0.1,  # rough estimate
                    })
                except (ValueError, KeyError):
                    continue

            cursor = data.get("cursor")
            if not cursor:
                break
            pages_fetched += 1

    except requests.RequestException as e:
        print(f"[WARN] Kalshi fetch failed: {e}")

    return markets


# ── SCORING & SELECTION ──────────────────────────────────────────────────────

def score_market(m: dict) -> float:
    """
    Score a market for "interestingness" as a mover.
    Weights: absolute change size > volume > raw probability interest.
    """
    abs_change = abs(m["change_pts"])
    vol_score  = math.log10(max(m["volume"], 1)) / 10  # normalize log volume
    # markets near 50% are most uncertain and interesting
    prob_interest = 1 - abs(m["prob"] - 50) / 50
    return (abs_change * 2.5) + (vol_score * 1.0) + (prob_interest * 0.5)


def pick_hero(markets: list[dict]) -> dict | None:
    """Pick the single most interesting market for the hero card."""
    candidates = [m for m in markets if m["volume"] >= HERO_MIN_VOLUME and abs(m["change_pts"]) >= 3]
    if not candidates:
        candidates = [m for m in markets if m["volume"] >= HERO_MIN_VOLUME]
    if not candidates:
        return None
    return max(candidates, key=score_market)


def pick_movers(markets: list[dict], exclude_slug: str = "") -> list[dict]:
    """Pick the top N movers, excluding the hero market."""
    candidates = [m for m in markets if m["slug"] != exclude_slug and abs(m["change_pts"]) > 0]
    candidates.sort(key=score_market, reverse=True)
    return candidates[:TOP_MOVERS_COUNT]


def pick_ticker(markets: list[dict]) -> list[dict]:
    """Pick ~10 markets for the scrolling ticker — mix of movers and high-volume."""
    by_change = sorted(markets, key=lambda m: abs(m["change_pts"]), reverse=True)[:6]
    by_volume = sorted(markets, key=lambda m: m["volume"], reverse=True)[:6]
    seen = set()
    ticker = []
    for m in by_change + by_volume:
        if m["slug"] not in seen:
            ticker.append(m)
            seen.add(m["slug"])
        if len(ticker) >= 10:
            break
    return ticker


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    now_utc = datetime.now(timezone.utc)
    # Display time in ET (UTC-5 standard / UTC-4 daylight — approximate)
    et_offset = timedelta(hours=-5)
    now_et = now_utc + et_offset
    updated_str = now_et.strftime("%b %-d, %Y · %-I:%M %p ET")

    print("Fetching Polymarket…")
    poly_markets   = fetch_polymarket()
    print(f"  Got {len(poly_markets)} markets")

    print("Fetching Kalshi…")
    kalshi_markets = fetch_kalshi()
    print(f"  Got {len(kalshi_markets)} markets")

    all_markets = poly_markets + kalshi_markets
    print(f"  Total: {len(all_markets)} markets above volume threshold")

    if not all_markets:
        print("ERROR: No markets fetched. Aborting to preserve existing data.")
        return

    hero   = pick_hero(all_markets)
    hero_slug = hero["slug"] if hero else ""
    movers = pick_movers(all_markets, exclude_slug=hero_slug)
    ticker = pick_ticker(all_markets)

    # Build output
    output = {
        "updated":    updated_str,
        "updated_iso": now_utc.isoformat(),
        "hero":       hero,
        "movers":     movers,
        "ticker":     ticker,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/markets.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Wrote data/markets.json")
    print(f"  Hero:   {hero['question'][:60] if hero else 'none'}…")
    print(f"  Movers: {len(movers)}")
    print(f"  Ticker: {len(ticker)}")
    print(f"  Updated: {updated_str}")


if __name__ == "__main__":
    main()
