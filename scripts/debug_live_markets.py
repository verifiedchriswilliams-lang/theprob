#!/usr/bin/env python3
"""
debug_live_markets.py v3
─────────────────────────
Find Kalshi game-winner series tickers by scanning /series for sports.
Then fetch today's game events from those series.

Run:
    python3 scripts/debug_live_markets.py
"""
import sys, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kalshi_orders import KalshiOrderClient

client = KalshiOrderClient()
now = datetime.now(timezone.utc)
today_str = now.strftime("%y%b%d").upper()   # e.g. "26APR12"
yesterday = now - timedelta(days=1)

print(f"\n{'='*70}")
print(f"  Kalshi Game Finder v3 — {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
print(f"  Today string: {today_str}")
print(f"{'='*70}\n")

# ── Strategy A: Scan /series for sports game series ───────────────────────────
print("A) Scan /series for sports game-winner series")
print("─"*70)
sports_keywords = [
    "game", "winner", "win", "mlb", "nba", "nhl", "nfl",
    "baseball", "basketball", "hockey", "football",
    "score", "match",
]
sports_series = []
cursor = None
pages = 0
while pages < 100:
    params = {"limit": 100}
    if cursor:
        params["cursor"] = cursor
    try:
        data = client._get("/series", params=params)
        series_list = data.get("series", [])
        if not series_list:
            break
        for s in series_list:
            title = (s.get("title") or "").lower()
            ticker = (s.get("ticker") or "")
            cat = (s.get("category") or "").lower()
            if any(k in title or k in ticker.lower() for k in sports_keywords):
                sports_series.append(s)
        cursor = data.get("cursor")
        if not cursor:
            break
        pages += 1
        time.sleep(0.1)
    except Exception as e:
        print(f"  Error page {pages}: {e}")
        break

print(f"  Sports game series found: {len(sports_series)} (scanned {pages+1} pages)")
for s in sports_series[:30]:
    print(f"  {s.get('ticker','?'):30s}  cat={s.get('category','?'):12s}  {s.get('title','?')[:45]}")

print()

# ── Strategy B: Fetch today's events from promising series ───────────────────
print(f"B) Fetch events from top sports series containing today's date ({today_str})")
print("─"*70)

# Focus on series with game/winner patterns
game_series = [s for s in sports_series if any(
    k in (s.get("ticker","")).lower() or k in (s.get("title","")).lower()
    for k in ["game", "winner", "win", "score", "mlb", "nba", "nhl", "nfl"]
)]
print(f"  Narrowed to {len(game_series)} game-related series\n")

found_today = []
for s in game_series[:50]:  # check first 50 game series
    ticker = s.get("ticker","")
    try:
        params = {
            "limit": 20,
            "series_ticker": ticker,
            "with_nested_markets": "true",
        }
        data = client._get("/events", params=params)
        events = data.get("events", [])
        for ev in events:
            ev_ticker = ev.get("event_ticker","") or ev.get("series_ticker","")
            title = ev.get("title","")
            # Look for today's date in ticker or title
            if today_str in ev_ticker.upper() or today_str in title.upper():
                mkts = ev.get("markets",[])
                found_today.append({
                    "series": ticker,
                    "event": ev_ticker,
                    "title": title,
                    "markets": mkts,
                })
        time.sleep(0.1)
    except Exception:
        continue

print(f"  Events containing today's date ({today_str}): {len(found_today)}")
for ev in found_today:
    print(f"\n  [{ev['series']}] {ev['event']}")
    print(f"  Title: {ev['title']}")
    for m in ev["markets"][:4]:
        bid = m.get("yes_bid_dollars",0) or 0
        ask = m.get("yes_ask_dollars",0) or 0
        last = m.get("last_price_dollars",0) or 0
        prob = round((float(bid)+float(ask))/2*100,1) if (bid or ask) else round(float(last)*100,1)
        print(f"    {m.get('ticker','?'):45s}  prob={prob}%  ct={m.get('close_time','?')[:16]}")

print()

# ── Strategy C: Check events with recent created_time ─────────────────────────
print("C) Markets endpoint filtered by status=active, look at non-MVE, non-range sample")
print("─"*70)
try:
    params = {"limit": 100, "status": "active"}
    data = client._get("/markets", params=params)
    mkts = data.get("markets", [])
    non_mve = [m for m in mkts if not m.get("mve_collection_ticker") and "::" not in m.get("ticker","")]
    import re
    non_range = [m for m in non_mve if not re.search(r"-T\d+(\.\d+)?$", m.get("ticker",""))]
    print(f"  Total active: {len(mkts)}  Non-MVE: {len(non_mve)}  Non-range non-MVE: {len(non_range)}")
    print(f"\n  First 10 non-MVE non-range active markets:")
    for m in non_range[:10]:
        bid = float(m.get("yes_bid_dollars",0) or 0)
        ask = float(m.get("yes_ask_dollars",0) or 0)
        last = float(m.get("last_price_dollars",0) or 0)
        prob = round((bid+ask)/2*100,1) if (bid or ask) else round(last*100,1)
        ct = m.get("close_time","")[:16]
        exp = m.get("expected_expiration_time","")[:16]
        vol24 = float(m.get("volume_24h_fp",0) or 0)/100
        print(f"  {m.get('ticker','?'):42s}  prob={prob}%  ct={ct}  exp={exp}  24h=${vol24:.0f}")
except Exception as e:
    print(f"  ERROR: {e}")

print(f"\n{'='*70}\n")
