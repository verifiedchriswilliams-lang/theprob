#!/usr/bin/env python3
from __future__ import annotations
"""
trade_selector.py
─────────────────
Reads markets.json and returns up to N best Kalshi trades available right now.

Core philosophy:
  Duration is everything. Fast-resolving markets = fast compounding.
  Probability is the signal. Volume is NOT a signal filter.
  We want to churn through as many winning positions as possible per day.

Selection logic:
  1. ONLY consider Kalshi markets resolving within MAX_TRADE_DAYS (7 days).
  2. Score by: duration (primary) + conviction (secondary) + spread bonus.
  3. Probability gate: 65%+ → bet YES, 35%- → bet NO. No coin flips.
  4. No volume floor — thin markets with clear consensus are valid trades.
     (Fill quality is managed at order time via bid/ask spread check.)

Run this directly to see today's picks:
    python3 scripts/trade_selector.py
    python3 scripts/trade_selector.py --slots 4 --verbose
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKETS_JSON = Path("data/markets.json")

# ── Core gates ────────────────────────────────────────────────────────────────
CROWD_YES_GATE   = 65.0   # bet YES when prob ≥ this
CROWD_NO_GATE    = 35.0   # bet NO when prob ≤ this
SPREAD_MIN_GAP   = 8.0    # minimum Poly vs Kalshi gap for spread signal
MAX_TRADE_DAYS   = 7      # hard cap — never hold longer than a week
MIN_VOL_ABSOLUTE = 0      # any non-zero volume accepted (fill quality handled at order time)


def days_until(end_date_raw: str) -> float | None:
    if not end_date_raw:
        return None
    try:
        end = datetime.fromisoformat(end_date_raw.replace("Z", "+00:00"))
        return (end - datetime.now(timezone.utc)).total_seconds() / 86400
    except Exception:
        return None


def duration_score(days: float | None) -> float:
    """
    Duration is the PRIMARY ranking factor. Shorter = higher score.
    Resolves today: 10 pts. Resolves in 7 days: 1 pt.
    Anything beyond MAX_TRADE_DAYS: disqualified (returns -999).
    """
    if days is None:
        return -999.0
    if days <= 0:
        return -999.0           # already expired
    if days > MAX_TRADE_DAYS:
        return -999.0           # hard cap — skip
    if days <= 0.5:
        return 10.0             # resolves within 12 hours
    if days <= 1:
        return 9.0              # resolves today
    if days <= 2:
        return 7.0              # resolves tomorrow
    if days <= 3:
        return 5.0              # resolves in 2-3 days
    if days <= 5:
        return 3.0              # resolves this week
    return 1.0                  # resolves within the week


def score_candidate(m: dict, signal: str, days: float | None) -> float:
    """
    Score = duration (primary) + conviction (secondary) + spread bonus.
    Duration completely dominates: a 70% market closing today beats
    an 85% market closing in 5 days.
    """
    dur   = duration_score(days)
    if dur < -100:
        return dur              # disqualified

    prob       = m.get("prob", 50)
    conviction = abs(prob - 50) / 50     # 0.0 at 50%, 1.0 at 0% or 100%
    spread_bonus = 2.0 if signal == "spread" else 0.0

    return dur + (conviction * 3) + spread_bonus


def select_trades(
    markets_path: Path = MARKETS_JSON,
    max_slots: int = 4,
    open_tickers: list[str] | None = None,
    live_markets: list[dict] | None = None,
) -> dict:
    """
    Return up to `max_slots` trade recommendations, ranked best first.

    Args:
        markets_path:  path to markets.json (for spread pairs + fallback market list)
        max_slots:     how many new positions we're allowed to open
        open_tickers:  list of Kalshi tickers already held (skip these)
        live_markets:  real-time market list from KalshiOrderClient.get_live_candidates()
                       If provided, these are used INSTEAD of all_markets from markets.json
                       for candidate scoring. Spread pairs still come from markets.json.

    Returns dict with:
        trades           — list of trade dicts, best first
        no_trade_reasons — why we skipped markets
        data_updated     — ISO timestamp of markets.json
    """
    open_tickers = set(open_tickers or [])

    if not markets_path.exists():
        return {"trades": [], "no_trade_reasons": [f"{markets_path} not found"], "data_updated": ""}

    with markets_path.open() as f:
        data = json.load(f)

    updated      = data.get("updated_iso", "unknown")
    # Use live_markets if provided (real-time); otherwise fall back to markets.json catalog
    all_markets  = live_markets if live_markets is not None else data.get("all_markets", [])
    spread_pairs = data.get("the_spread", [])

    if live_markets is not None:
        import sys
        print(f"  [selector] Using {len(live_markets)} live markets "
              f"(real-time) + {len(spread_pairs)} spread pairs from markets.json",
              file=sys.stderr)

    candidates   = []   # (score, trade_dict)
    rejections   = []

    # ── Build spread lookup ───────────────────────────────────────────────────
    spread_by_ticker = {}
    for pair in spread_pairs:
        ticker = pair.get("kalshi_ticker") or pair.get("kalshi_slug", "")
        if ticker and ticker not in ("", "MISSING"):
            spread_by_ticker[ticker] = pair

    spread_missing_count = sum(
        1 for p in spread_pairs
        if not (p.get("kalshi_ticker") or p.get("kalshi_slug"))
        or (p.get("kalshi_ticker") or p.get("kalshi_slug")) in ("", "MISSING")
    )
    if spread_missing_count:
        rejections.append(
            f"[SPREAD] {spread_missing_count} spread pair(s) have no Kalshi ticker yet "
            "(will populate next pipeline run)"
        )

    # ── Score every Kalshi market ─────────────────────────────────────────────
    for m in all_markets:
        if m.get("source") != "Kalshi":
            continue

        ticker   = m.get("slug", "")
        prob     = m.get("prob", 50)
        vol24    = m.get("volume_24h", 0) or 0
        question = m.get("question", "?")
        days     = days_until(m.get("end_date_raw", ""))

        # ── Hard filters ─────────────────────────────────────────────────────
        if ticker in open_tickers:
            rejections.append(f"[SKIP] '{question[:55]}' — already open")
            continue

        dur = duration_score(days)
        if dur < -100:
            d_str = f"{days:.1f}d" if days is not None else "unknown"
            if days is not None and days > MAX_TRADE_DAYS:
                # Don't spam rejections with hundreds of long-duration markets
                pass
            elif days is not None and days <= 0:
                rejections.append(f"[SKIP] '{question[:55]}' — already expired")
            continue

        # Probability gate — skip the coin-flip zone
        if CROWD_NO_GATE < prob < CROWD_YES_GATE:
            rejections.append(
                f"[SKIP] '{question[:55]}' — prob {prob}% in dead zone "
                f"({CROWD_NO_GATE}–{CROWD_YES_GATE}%)"
            )
            continue

        d_str = f"{days:.1f}d" if days is not None else "?"

        # ── Check spread signal first ─────────────────────────────────────────
        in_spread = spread_by_ticker.get(ticker)
        if in_spread:
            gap    = in_spread.get("gap_pts", 0)
            p_prob = in_spread.get("poly_prob", prob)
            if gap >= SPREAD_MIN_GAP:
                score = score_candidate(m, "spread", days)
                candidates.append((score, {
                    "signal":    "spread",
                    "ticker":    ticker,
                    "side":      "yes",
                    "prob":      prob,
                    "days_left": round(days, 2) if days else None,
                    "question":  question,
                    "reason":    (
                        f"Polymarket {p_prob}% vs Kalshi {prob}% — {gap:.1f}pt gap. "
                        f"Bet YES on Kalshi, expect convergence. Resolves {d_str}."
                    ),
                }))
                continue
            else:
                rejections.append(
                    f"[SPREAD] '{question[:55]}' — gap only {gap:.1f}pts (need ≥{SPREAD_MIN_GAP})"
                )

        # ── Crowd conviction ──────────────────────────────────────────────────
        if prob >= CROWD_YES_GATE:
            score = score_candidate(m, "crowd", days)
            candidates.append((score, {
                "signal":    "crowd",
                "ticker":    ticker,
                "side":      "yes",
                "prob":      prob,
                "days_left": round(days, 2) if days else None,
                "question":  question,
                "reason":    (
                    f"Crowd conviction {prob}% → bet YES. "
                    f"${vol24:,.0f} traded today. Resolves {d_str}."
                ),
            }))
            continue

        if prob <= CROWD_NO_GATE:
            score = score_candidate(m, "crowd", days)
            candidates.append((score, {
                "signal":    "crowd",
                "ticker":    ticker,
                "side":      "no",
                "prob":      prob,
                "days_left": round(days, 2) if days else None,
                "question":  question,
                "reason":    (
                    f"Crowd conviction {prob}% → bet NO. "
                    f"${vol24:,.0f} traded today. Resolves {d_str}."
                ),
            }))
            continue

    # ── Rank and return top N ─────────────────────────────────────────────────
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
    import argparse
    parser = argparse.ArgumentParser(description="Select today's best Kalshi trades")
    parser.add_argument("--slots",   type=int,  default=4,     help="Open slots available")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all rejections")
    args = parser.parse_args()

    result = select_trades(max_slots=args.slots)

    print()
    print(f"  Data as of : {result['data_updated']}")
    print(f"  Slots open : {args.slots}")
    print(f"  Candidates : {result['all_candidates']} qualifying markets within {MAX_TRADE_DAYS} days")
    print()

    trades = result["trades"]

    if not trades:
        print("━" * 55)
        print("  NO TRADES — no qualifying markets closing within 7 days")
        print("━" * 55)
    else:
        labels = {"spread": "SPREAD ⚡", "crowd": "CROWD", "knife_edge": "KNIFE-EDGE"}
        for i, t in enumerate(trades, 1):
            hours = round(t['days_left'] * 24, 1) if t.get('days_left') else None
            time_str = f"{hours}h" if hours and hours < 48 else (f"{t['days_left']}d" if t.get('days_left') else "?")
            print(f"━━━  Trade {i}  " + "━" * 42)
            print(f"  Signal  : {labels.get(t['signal'], t['signal'])}")
            print(f"  Ticker  : {t['ticker']}")
            print(f"  Side    : {t['side'].upper()}")
            print(f"  Prob    : {t['prob']}%")
            print(f"  Closes  : {time_str}")
            print(f"  Market  : {t['question'][:72]}")
            print(f"  Why     : {t['reason']}")
    print("━" * 55)

    if args.verbose or not trades:
        if result["no_trade_reasons"]:
            print()
            relevant = [r for r in result["no_trade_reasons"]
                       if "[SKIP]" not in r or args.verbose]
            if relevant:
                print(f"── Notable rejections ({len(relevant)}) ──")
                for r in relevant[:20]:
                    print(f"  {r}")
