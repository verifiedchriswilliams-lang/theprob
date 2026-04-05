#!/usr/bin/env python3
"""
run_bot.py
──────────
The Prob live trading bot — single execution loop.

What it does each run:
  1. Connect to Kalshi, fetch live balance
  2. Calculate dynamic trade size (10% of balance, scales with account)
  3. Check open positions (max 4 simultaneous)
  4. Run trade selector to find best available trades
  5. Place orders for each open slot (up to 4 - current positions)
  6. Log every decision with full audit trail

Safe-first design:
  - If balance < $5, stop (too small to trade)
  - If already at 4 open positions, stop (fully deployed)
  - If API errors at any step, log and exit cleanly — never retry blindly
  - Daily loss limit: if down $20+ today, stop trading for the day

Run manually:
    python3 scripts/run_bot.py

Run as dry-run (no real orders):
    python3 scripts/run_bot.py --dry-run

Designed to be called by GitHub Actions on a schedule.
"""

import json
import os
import sys
import logging
import argparse
from datetime import datetime, timezone, date
from pathlib import Path

# ── allow running from repo root ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from kalshi_orders import KalshiOrderClient, calculate_trade_budget
from trade_selector import select_trades

# ── Config ────────────────────────────────────────────────────────────────────
MAX_POSITIONS      = 4
DAILY_LOSS_LIMIT   = 20.00      # stop trading today if down more than this
LEDGER_PATH        = Path("data/live_trade_ledger.json")
MARKETS_JSON       = Path("data/markets.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("run_bot")


# ── Ledger helpers ────────────────────────────────────────────────────────────

def load_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    with LEDGER_PATH.open() as f:
        return json.load(f)


def save_ledger(ledger: list[dict]) -> None:
    LEDGER_PATH.parent.mkdir(exist_ok=True)
    with LEDGER_PATH.open("w") as f:
        json.dump(ledger, f, indent=2)


def todays_pnl(ledger: list[dict]) -> float:
    """Sum of realised P&L on trades that closed today."""
    today = date.today().isoformat()
    return sum(
        e.get("pnl", 0) or 0
        for e in ledger
        if e.get("event") == "trade_closed" and str(e.get("close_date", "")).startswith(today)
    )


def already_open_tickers(ledger: list[dict]) -> list[str]:
    """Tickers currently open (placed but not yet closed)."""
    open_set = set()
    for e in ledger:
        if e.get("event") == "order_placed":
            open_set.add(e.get("ticker", ""))
        elif e.get("event") in ("trade_closed", "order_cancelled"):
            open_set.discard(e.get("ticker", ""))
    return [t for t in open_set if t]


# ── Main ──────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> None:
    log.info("=" * 55)
    log.info("The Prob bot starting  dry_run=%s", dry_run)
    log.info("=" * 55)

    ledger = load_ledger()

    # ── Step 1: Safety — daily loss limit ────────────────────────────────
    pnl_today = todays_pnl(ledger)
    if pnl_today <= -DAILY_LOSS_LIMIT:
        log.warning("Daily loss limit hit ($%.2f). No more trades today.", pnl_today)
        return

    # ── Step 2: Connect + live balance ───────────────────────────────────
    try:
        client  = KalshiOrderClient(ledger_path=LEDGER_PATH)
        balance_data = client.get_balance()
        balance = balance_data.get("balance", 0) / 100
    except Exception as exc:
        log.error("Failed to connect to Kalshi: %s", exc)
        return

    if balance < 5.0:
        log.warning("Balance $%.2f is too low to trade (minimum $5).", balance)
        return

    # ── Step 3: Dynamic trade budget ─────────────────────────────────────
    budget = calculate_trade_budget(balance)
    log.info("Balance: $%.2f  |  Trade budget: $%.2f per position", balance, budget)

    # ── Step 4: Open position count ───────────────────────────────────────
    open_tickers = already_open_tickers(ledger)

    # Cross-check with live Kalshi positions
    try:
        live_positions = client.get_open_positions()
        live_tickers   = [p.get("ticker", "") for p in live_positions if p.get("position", 0) > 0]
        # Merge: use live as source of truth, supplement with ledger
        all_open = list(set(open_tickers) | set(live_tickers))
    except Exception as exc:
        log.warning("Could not fetch live positions (%s), using ledger only.", exc)
        all_open = open_tickers

    slots_available = MAX_POSITIONS - len(all_open)
    log.info("Open positions: %d / %d  |  Slots free: %d",
             len(all_open), MAX_POSITIONS, slots_available)

    if slots_available <= 0:
        log.info("All %d position slots filled. Nothing to do this run.", MAX_POSITIONS)
        return

    # ── Step 5: Trade selection ────────────────────────────────────────────
    selection = select_trades(
        markets_path=MARKETS_JSON,
        max_slots=slots_available,
        open_tickers=all_open,
    )
    trades = selection.get("trades", [])
    log.info("Selector found %d candidate(s) for %d slot(s). Data: %s",
             len(trades), slots_available, selection.get("data_updated", "?"))

    if not trades:
        log.info("No qualifying trades this run. Reasons:")
        for r in selection.get("no_trade_reasons", [])[:10]:
            log.info("  %s", r)
        return

    # ── Step 6: Place orders ───────────────────────────────────────────────
    placed = 0
    for trade in trades:
        ticker   = trade["ticker"]
        side     = trade["side"]
        prob     = trade["prob"]
        signal   = trade["signal"]
        reason   = trade["reason"]
        days     = trade.get("days_left")

        log.info("-" * 45)
        log.info("Trade %d: %s  %s  prob=%.1f%%  days=%s",
                 placed + 1, ticker, side.upper(), prob,
                 f"{days:.0f}" if days else "?")
        log.info("Signal : %s", signal)
        log.info("Reason : %s", reason)

        try:
            result = client.place_order(
                ticker=ticker,
                side=side,
                prob=prob,
                budget=budget,
                reason=f"[{signal}] {reason}",
                dry_run=dry_run,
            )
            placed += 1
            log.info("Order %s  status=%s  cost=$%.2f  order_id=%s",
                     "DRY-RUN" if dry_run else "PLACED",
                     result.get("status"),
                     result.get("cost_dollars", 0),
                     result.get("order_id") or "n/a")

        except Exception as exc:
            log.error("Failed to place order for %s: %s", ticker, exc)
            # Safe-first: log and continue to next trade rather than crashing
            ledger.append({
                "event":     "order_failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker":    ticker,
                "side":      side,
                "signal":    signal,
                "error":     str(exc),
            })
            save_ledger(ledger)

    log.info("=" * 55)
    log.info("Run complete. Orders placed: %d / %d candidates.", placed, len(trades))
    log.info("Balance: $%.2f  |  Budget used: $%.2f",
             balance, placed * budget)
    log.info("=" * 55)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="The Prob trading bot")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Select trades and log them but do not place real orders"
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)
