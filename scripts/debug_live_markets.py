#!/usr/bin/env python3
"""
debug_live_markets.py v2
─────────────────────────
Try multiple strategies to find live/near-term Kalshi sports game markets.

Run:
    python3 scripts/debug_live_markets.py
"""
import sys, os, time, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kalshi_orders import KalshiOrderClient

client = KalshiOrderClient()
now = datetime.now(timezone.utc)

print(f"\n{'='*70}")
print(f"  Kalshi Live Market Debug v2 — {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
print(f"{'='*70}\n")

# ── Strategy 1: /markets endpoint with min/max close_ts ───────────────────────
print("STRATEGY 1: /markets with min_close_ts + max_close_ts (24h window)")
print("─"*70)
try:
    params = {
        "limit": 100,
        "min_close_ts": int(now.timestamp()),
        "max_close_ts": int((now + timedelta(hours=24)).timestamp()),
        "status": "open",
    }
    data = client._get("/markets", params=params)
    mkts = data.get("markets", [])
    print(f"  Markets returned: {len(mkts)}")
    for m in mkts[:10]:
        print(f"    {m.get('ticker','?'):40s}  prob={m.get('last_price_dollars','?')}  ct={m.get('close_time','?')[:16]}")
except Exception as e:
    print(f"  ERROR: {e}")

print()

# ── Strategy 2: /markets?status=open (no time filter) sample ─────────────────
print("STRATEGY 2: /markets?status=open — first page sample")
print("─"*70)
try:
    params = {"limit": 20, "status": "open"}
    data = client._get("/markets", params=params)
    mkts = data.get("markets", [])
    print(f"  Markets returned: {len(mkts)}")
    if mkts:
        m = mkts[0]
        print(f"  Sample ALL FIELDS:")
        for k, v in sorted(m.items()):
            print(f"    {k:35s}: {v!r}")
except Exception as e:
    print(f"  ERROR: {e}")

print()

# ── Strategy 3: /events?category=Sports ──────────────────────────────────────
print("STRATEGY 3: /events?category=Sports")
print("─"*70)
# Try various category strings Kalshi might use
for cat in ["Sports", "sports", "Baseball", "baseball", "MLB", "mlb"]:
    try:
        params = {"limit": 10, "category": cat, "with_nested_markets": "true"}
        data = client._get("/events", params=params)
        events = data.get("events", [])
        if events:
            print(f"  category={cat!r}: {len(events)} events found")
            for ev in events[:3]:
                mkts = ev.get("markets", [])
                print(f"    [{ev.get('series_ticker','?')}] {ev.get('title','?')[:50]}  ({len(mkts)} markets)")
                for m in mkts[:2]:
                    print(f"      {m.get('ticker','?'):40s}  close={m.get('close_time','?')[:16]}  can_close_early={m.get('can_close_early')}")
        else:
            print(f"  category={cat!r}: 0 events")
        time.sleep(0.2)
    except Exception as e:
        print(f"  category={cat!r}: ERROR {e}")

print()

# ── Strategy 4: fetch /series to find sports series tickers ──────────────────
print("STRATEGY 4: /series endpoint")
print("─"*70)
try:
    data = client._get("/series", params={"limit": 50})
    series_list = data.get("series", [])
    print(f"  Series returned: {len(series_list)}")
    for s in series_list[:20]:
        print(f"    {s.get('ticker','?'):20s}  {s.get('title','?')[:50]}  cat={s.get('category','?')}")
except Exception as e:
    print(f"  ERROR: {e}")

print()

# ── Strategy 5: fetch 10 pages of /events, look for any Sports ───────────────
print("STRATEGY 5: Scan first 10 pages of /events for Sports category")
print("─"*70)
sports_events = []
cursor = None
for page in range(10):
    params = {"limit": 100, "with_nested_markets": "false"}
    if cursor:
        params["cursor"] = cursor
    try:
        data = client._get("/events", params=params)
        events = data.get("events", [])
        if not events:
            break
        for ev in events:
            cat = ev.get("category", "")
            if cat and cat.lower() in ("sports", "baseball", "mlb", "nba", "nfl", "hockey", "soccer"):
                sports_events.append(ev)
        cursor = data.get("cursor")
        if not cursor:
            break
        time.sleep(0.2)
    except Exception as e:
        print(f"  Page {page} error: {e}")
        break

print(f"  Sports events found in first 10 pages: {len(sports_events)}")
for ev in sports_events[:5]:
    print(f"    [{ev.get('series_ticker','?')}] {ev.get('title','?')[:50]}  cat={ev.get('category','?')}")

print()

# ── Strategy 6: Try known MLB/sports series tickers directly ─────────────────
print("STRATEGY 6: Fetch events by known sports series tickers")
print("─"*70)
known_sports_tickers = [
    "KXMLB", "KXNBA", "KXNFL", "KXNHL", "KXSOCCER",
    "MLB", "NBA", "NFL", "NHL",
    "KXSPORTS", "SPORTS",
]
for ticker in known_sports_tickers:
    try:
        params = {
            "limit": 5,
            "series_ticker": ticker,
            "with_nested_markets": "true",
        }
        data = client._get("/events", params=params)
        events = data.get("events", [])
        if events:
            print(f"  series_ticker={ticker!r}: {len(events)} events")
            for ev in events[:2]:
                mkts = ev.get("markets", [])
                print(f"    {ev.get('title','?')[:55]}")
                for m in mkts[:2]:
                    print(f"      {m.get('ticker','?'):40s}  ct={m.get('close_time','?')[:16]}  can_early={m.get('can_close_early')}")
        time.sleep(0.15)
    except Exception as e:
        if "404" not in str(e) and "400" not in str(e):
            print(f"  series_ticker={ticker!r}: {e}")

print(f"\n{'='*70}\n")
