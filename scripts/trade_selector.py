#!/usr/bin/env python3
"""
trade_selector.py
─────────────────
Reads markets.json and returns up to N best Kalshi trades available right now.

Key design decisions:
  - Kalshi only (CFTC-regulated, no crypto required)
  - Up to 4 simultaneous open positions (caller passes how many slots are free)
  - NO hard duration cap — Kalshi markets are mostly long-duration by nature.
    Instead, duration is scored: shorter resolving markets ranked higher.
  - Returns a RANKED LIST so the execution loop can place as many as slots allow

Priority order (first matching signal wins for each candidate):
  1. Spread signal  — Kalshi prob is 8+ pts BELOW Polymarket for same event.
                      Bet YES on Kalshi — expecting convergence to Poly price.
                      Requires: kalshi_ticker present, Kalshi vol_24h ≥ $500
  2. Crowd model    — prob ≥ 65% (bet YES) or ≤ 35% (bet NO).
                      Requires: vol_24h ≥ $500, signal != stale
  3. Knife-edge     — trading_signal = knife_edge, clear directional move today,
                      vol_24h ≥ $500, resolves ≤ 90 days

Hard filters (every candidate must pass):
  - Kalshi source only
  - vol_24h ≥ $200 (de-facto dead market filter)
  - trading_signal != stale
  - Probability NOT between 40–60% (unless spread signal)
  - Market not already in open_tickers list

Run this directly to see today's picks:
    python3 scripts/trade_selector.py
    python3 scripts/trade_selector.py --slots 4 --verbose
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKETS_JSON = Path("data/markets.json")

# Probability gates
CROWD_YES_GATE  = 65.0
CROWD_NO_GATE   = 35.0
SPREAD_MIN_GAP  = 8.0

# Volume floors
MIN_VOL_24H     = 200     # absolute dead-market floor
MIN_VOL_CROWD   = 500     # crowd model minimum
MIN_VOL_SPREAD  = 500     # spread signal minimum
MIN_VOL_KNIFE   = 500     # knife-edge minimum

# Duration scoring: shorter = better, but nothing is hard-blocked
# Markets resolving sooner get a bonus in ranking
DURATION_TIERS = [
    (7,   4.0),   # ≤ 7 days  → +4 score bonus
    (30,  2.0),   # ≤ 30 days → +2
    (90,  1.0),   # ≤ 90 days → +1
    (365, 0.0),   # ≤ 365 days → no bonus
    (9999, -1.0), # > 365 days → small penalty (long capital lockup)
]

# Knife-edge: only worth it if resolves soon enough to matter
KNIFE_MAX_DAYS  = 90


def days_until(end_date_raw: str) -> float | None:
    if not end_date_raw:
        return None
    try:
        end = datetime.fromisoformat(end_date_raw.replace("Z", "+00:00"))
        return (end - datetime.now(timezone.utc)).total_seconds() / 86400
    except Exception:
        return None


def duration_bonus(days: float | None) -> float:
    if days is None:
        return -2.0
    for threshold, bonus in DURATION_TIERS:
        if days <= threshold:
            return bonus
    return -1.0


def score_candidate(m: dict, signal: str, days: float | None) -> float:
    """
    Higher score = better trade. Used to rank candidates when multiple qualify.
    Components:
      - Conviction: how far prob is from 50% (more extreme = more conviction)
      - Volume: log of 24h volume (more liquid = better fill)
      - Duration bonus: shorter resolving markets are preferred
    """
    prob   = m.get("prob", 50)
    vol24  = max(m.get("volume_24h", 1), 1)
    import math
    conviction = abs(prob - 50) / 50     # 0 at prob=50, 1.0 at prob=0 or 100
    vol_score  = math.log10(vol24) / 5   # normalised, ~0.5 at $10K
    dur_bonus  = duration_bonus(days)
    spread_bonus = 1.5 if signal == "spread" else 0.0
    return conviction * 3 + vol_score + dur_bonus + spread_bonus


def select_trades(
    markets_path: Path = MARKETS_JSON,
    max_slots: int = 4,
    open_tickers: list[str] | None = None,
) -> dict:
    """
    Return up to `max_slots` trade recommendations as a ranked list.

    Args:
        markets_path:  path to markets.json
        max_slots:     how many new positions we're allowed to open
        open_tickers:  list of Kalshi tickers already held (skip these)

    Returns dict with:
        trades        — list of trade dicts, best first
        no_trade_reasons — why we couldn't fill all slots
        data_updated  — ISO timestamp of markets.json
    """
    open_tickers = set(open_tickers or [])

    if not markets_path.exists():
        return {"trades": [], "no_trade_reasons": [f"{markets_path} not found"], "data_updated": ""}

    with markets_path.open() as f:
        data = json.load(f)

    updated      = data.get("updated_iso", "unknown")
    all_markets  = data.get("all_markets", [])
    spread_pairs = data.get("the_spread", [])

    candidates   = []   # (score, trade_dict)
    rejections   = []

    # ── Build spread lookup: kalshi_ticker → pair ─────────────────────────
    spread_by_ticker = {}
    spread_by_question = {}
    for pair in spread_pairs:
        ticker = pair.get("kalshi_ticker") or pair.get("kalshi_slug")
        if ticker and ticker not in ("", "MISSING"):
            spread_by_ticker[ticker] = pair
        spread_by_question[pair.get("poly_question", "")[:60]] = pair

    spread_missing = [
        p.get("poly_question", "?")[:55]
        for p in spread_pairs
        if not (p.get("kalshi_ticker") or p.get("kalshi_slug"))
        or (p.get("kalshi_ticker") or p.get("kalshi_slug")) in ("", "MISSING")
    ]
    if spread_missing:
        for q in spread_missing:
            rejections.append(f"[SPREAD] '{q}' — Kalshi ticker not stored in markets.json yet")

    # ── Score every Kalshi market ─────────────────────────────────────────
    for m in all_markets:
        if m.get("source") != "Kalshi":
            continue

        ticker  = m.get("slug", "")
        prob    = m.get("prob", 50)
        vol24   = m.get("volume_24h", 0)
        signal  = m.get("trading_signal", "")
        days    = days_until(m.get("end_date_raw", ""))
        question = m.get("question", "?")

        # ── Hard filters ─────────────────────────────────────────────────
        if ticker in open_tickers:
            rejections.append(f"[SKIP] '{question[:55]}' — already in open positions")
            continue
        if signal == "stale":
            rejections.append(f"[SKIP] '{question[:55]}' — signal=stale")
            continue
        if vol24 < MIN_VOL_24H:
            rejections.append(f"[SKIP] '{question[:55]}' — vol24h ${vol24:,.0f} < ${MIN_VOL_24H:,} floor")
            continue
        if days is not None and days <= 0:
            rejections.append(f"[SKIP] '{question[:55]}' — already expired")
            continue

        # ── Check for spread signal first ────────────────────────────────
        in_spread = spread_by_ticker.get(ticker)
        if in_spread:
            gap   = in_spread.get("gap_pts", 0)
            p_prob = in_spread.get("poly_prob", prob)
            if gap >= SPREAD_MIN_GAP and vol24 >= MIN_VOL_SPREAD:
                score = score_candidate(m, "spread", days)
                d_str = f"{days:.0f}d" if days else "?"
                candidates.append((score, {
                    "signal":    "spread",
                    "ticker":    ticker,
                    "side":      "yes",
                    "prob":      prob,
                    "days_left": round(days, 1) if days else None,
                    "question":  question,
                    "reason":    f"Polymarket {p_prob}% vs Kalshi {prob}% — {gap:.1f}pt gap. "
                                 f"Bet YES, expect convergence. Resolves {d_str}.",
                }))
                continue
            else:
                rejections.append(f"[SPREAD] '{question[:55]}' — gap {gap}pts or vol24h ${vol24:,.0f} too low")

        # ── Crowd model ───────────────────────────────────────────────────
        if prob >= CROWD_YES_GATE and vol24 >= MIN_VOL_CROWD:
            side  = "yes"
            score = score_candidate(m, "crowd", days)
            d_str = f"{days:.0f}d" if days else "?"
            candidates.append((score, {
                "signal":    "crowd",
                "ticker":    ticker,
                "side":      side,
                "prob":      prob,
                "days_left": round(days, 1) if days else None,
                "question":  question,
                "reason":    f"Crowd conviction {prob}% → bet YES. "
                             f"${vol24:,.0f} traded today. Resolves {d_str}.",
            }))
            continue

        if prob <= CROWD_NO_GATE and vol24 >= MIN_VOL_CROWD:
            side  = "no"
            score = score_candidate(m, "crowd", days)
            d_str = f"{days:.0f}d" if days else "?"
            candidates.append((score, {
                "signal":    "crowd",
                "ticker":    ticker,
                "side":      side,
                "prob":      prob,
                "days_left": round(days, 1) if days else None,
                "question":  question,
                "reason":    f"Crowd conviction {prob}% → bet NO. "
                             f"${vol24:,.0f} traded today. Resolves {d_str}.",
            }))
            continue

        # ── Knife-edge ────────────────────────────────────────────────────
        if signal == "knife_edge":
            change = m.get("change_pts", 0)
            if abs(change) >= 1.0 and vol24 >= MIN_VOL_KNIFE:
                if days is None or days > KNIFE_MAX_DAYS:
                    rejections.append(f"[KNIFE] '{question[:55]}' — resolves {days:.0f}d out, need ≤{KNIFE_MAX_DAYS}d")
                    continue
                side  = "yes" if change > 0 else "no"
                score = score_candidate(m, "knife_edge", days)
                d_str = f"{days:.0f}d" if days else "?"
                candidates.append((score, {
                    "signal":    "knife_edge",
                    "ticker":    ticker,
                    "side":      side,
                    "prob":      prob,
                    "days_left": round(days, 1) if days else None,
                    "question":  question,
                    "reason":    f"Knife-edge: moved {change:+.1f}pts today at {prob}% → bet {side.upper()}. "
                                 f"Resolves {d_str}.",
                }))
                continue

        # Didn't qualify for any signal
        if 40 < prob < 60:
            rejections.append(f"[SKIP] '{question[:55]}' — prob {prob}% in dead zone (40-60%)")
        elif vol24 < MIN_VOL_CROWD:
            rejections.append(f"[SKIP] '{question[:55]}' — vol24h ${vol24:,.0f} below crowd floor")

    # ── Rank and return top N ─────────────────────────────────────────────
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = [trade for _, trade in candidates[:max_slots]]

    return {
        "trades":           top,
        "all_candidates":   len(candidates),
        "no_trade_reasons": rejections,
        "data_updated":     updated,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, math
    parser = argparse.ArgumentParser(description="Select today's best Kalshi trades")
    parser.add_argument("--slots",   type=int, default=4, help="Open position slots available (default 4)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all rejection reasons")
    args = parser.parse_args()

    result = select_trades(max_slots=args.slots)

    print()
    print(f"  Data as of : {result['data_updated']}")
    print(f"  Slots open : {args.slots}")
    print(f"  Candidates : {result['all_candidates']} qualified markets found")
    print()

    trades = result["trades"]

    if not trades:
        print("━" * 55)
        print("  NO TRADES TODAY — no qualifying signals found")
        print("━" * 55)
    else:
        labels = {"spread": "SPREAD", "crowd": "CROWD", "knife_edge": "KNIFE-EDGE"}
        for i, t in enumerate(trades, 1):
            print(f"━━━  Trade {i} of {len(trades)}  " + "━" * 35)
            print(f"  Signal  : {labels.get(t['signal'], t['signal'])}")
            print(f"  Ticker  : {t['ticker']}")
            print(f"  Side    : {t['side'].upper()}")
            print(f"  Prob    : {t['prob']}%")
            print(f"  Expires : {t['days_left']} days" if t['days_left'] else "  Expires : unknown")
            print(f"  Market  : {t['question'][:72]}")
            print(f"  Why     : {t['reason']}")
        print("━" * 55)

    if args.verbose:
        print()
        print(f"── Rejections ({len(result['no_trade_reasons'])}) ──")
        for r in result["no_trade_reasons"]:
            print(f"  {r}")
