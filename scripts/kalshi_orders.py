from __future__ import annotations
"""
kalshi_orders.py
────────────────
Kalshi order placement module for the $100→$1M live trading bot.

Authentication: RSA-PSS/SHA-256 using KALSHI_KEY_ID + KALSHI_PRIVATE_KEY
API: Kalshi Trade API v2  (https://trading.kalshi.com/trade-api/v2)

Public surface:
    KalshiOrderClient          – authenticated HTTP client
    KalshiOrderClient.place_order()  – place a limit YES or NO order
    KalshiOrderClient.get_order()    – fetch single order status
    KalshiOrderClient.get_balance()  – current account balance

Helper:
    calculate_contracts()      – how many contracts $N buys at a given price
    load_ledger() / append_ledger()  – JSON audit-log helpers
"""

import base64
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from math import floor
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# ─────────────────────────────────────────────
# Config / constants
# ─────────────────────────────────────────────

PROD_BASE_URL  = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE_URL  = "https://demo-api.kalshi.co/trade-api/v2"
LEDGER_PATH    = Path("trade_ledger.json")
REQUEST_TIMEOUT = 15          # seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("kalshi_orders")


# ─────────────────────────────────────────────
# Utility – dynamic trade sizing
# ─────────────────────────────────────────────

def calculate_trade_budget(balance: float) -> float:
    """
    Dynamic trade size: scales with account balance to maximise compounding.

    Tiers (% of balance per trade):
        $0   – $1,000   →  10%   e.g. $100 account → $10/trade
        $1K  – $10,000  →   8%   e.g. $5,000       → $400/trade
        $10K – $50,000  →   5%   e.g. $20,000      → $1,000/trade
        $50K+           →   2%   e.g. $100,000      → $2,000/trade

    Minimum $5 so we can always place at least one contract.
    Maximum $5,000 per trade regardless of balance (risk cap).
    """
    if balance <= 1_000:
        pct = 0.10
    elif balance <= 10_000:
        pct = 0.08
    elif balance <= 50_000:
        pct = 0.05
    else:
        pct = 0.02
    return round(min(max(balance * pct, 5.0), 5_000.0), 2)


# ─────────────────────────────────────────────
# Utility – contract sizing
# ─────────────────────────────────────────────

def calculate_contracts(
    budget_dollars: float,
    price_cents: int,
) -> int:
    """
    How many whole contracts can we buy for `budget_dollars` at `price_cents`
    per contract?

    Kalshi contracts cost `price_cents / 100` dollars each and pay $1 on win.

    Example:
        calculate_contracts(10.00, 65)  →  15  (costs $9.75)
        calculate_contracts(10.00, 30)  →  33  (costs $9.90)
    """
    if not (1 <= price_cents <= 99):
        raise ValueError(f"price_cents must be 1–99, got {price_cents}")
    budget_cents = budget_dollars * 100
    return floor(budget_cents / price_cents)


# ─────────────────────────────────────────────
# Utility – audit ledger
# ─────────────────────────────────────────────

def load_ledger(path: Path = LEDGER_PATH) -> list[dict]:
    """Return the current ledger as a list; creates file if absent."""
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


def append_ledger(entry: dict, path: Path = LEDGER_PATH) -> None:
    """Append one trade/event record to the JSON ledger."""
    ledger = load_ledger(path)
    ledger.append(entry)
    with path.open("w") as f:
        json.dump(ledger, f, indent=2)
    log.info("Ledger updated → %s (%d entries)", path, len(ledger))


# ─────────────────────────────────────────────
# Core client
# ─────────────────────────────────────────────

class KalshiOrderClient:
    """
    Thin authenticated wrapper around the Kalshi Trade API v2.

    Reads credentials from environment variables by default:
        KALSHI_KEY_ID         – your API key ID (UUID string)
        KALSHI_PRIVATE_KEY    – PEM-encoded RSA private key
                                (newlines as \\n are accepted)

    Pass demo=True to route requests to the sandbox environment.
    """

    def __init__(
        self,
        key_id:      str | None = None,
        private_key_pem: str | None = None,
        *,
        demo: bool = False,
        budget_per_trade: float | None = None,  # None = use dynamic sizing
        ledger_path: Path = LEDGER_PATH,
    ) -> None:
        self.key_id          = key_id or os.environ["KALSHI_KEY_ID"]
        self.base_url        = DEMO_BASE_URL if demo else PROD_BASE_URL
        self._fixed_budget   = budget_per_trade   # None means dynamic
        self.budget          = budget_per_trade or 10.00  # fallback until balance fetched
        self.ledger_path     = ledger_path
        self._session        = requests.Session()
        self._private_key    = self._load_private_key(
            private_key_pem or os.environ["KALSHI_PRIVATE_KEY"]
        )
        log.info(
            "KalshiOrderClient ready  key=%s  env=%s  budget=$%.2f",
            self.key_id[:8] + "…",
            "DEMO" if demo else "LIVE",
            self.budget,
        )

    # ── auth ──────────────────────────────────

    @staticmethod
    def _load_private_key(pem_string: str):
        """
        Load an RSA private key from a PEM string.
        Handles both literal newlines and escaped \\n (common in env vars).
        """
        pem_string = pem_string.replace("\\n", "\n").strip()
        if not pem_string.startswith("-----"):
            # Assume raw base64-encoded DER; wrap it.
            pem_string = (
                "-----BEGIN RSA PRIVATE KEY-----\n"
                + pem_string
                + "\n-----END RSA PRIVATE KEY-----"
            )
        return serialization.load_pem_private_key(pem_string.encode(), password=None)

    def _sign(self, method: str, path: str) -> tuple[str, str]:
        """
        Produce (timestamp_ms_str, base64_signature) for a request.

        Kalshi signature message = timestamp_ms + METHOD + /path
        Algorithm: RSA-PSS with SHA-256, salt length = digest length (32 bytes).
        """
        ts_ms = str(int(time.time() * 1000))
        # Kalshi requires the full path including the /trade-api/v2 prefix in the signature
        full_path = "/trade-api/v2" + path
        message = (ts_ms + method.upper() + full_path).encode("utf-8")
        raw_sig = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return ts_ms, base64.b64encode(raw_sig).decode("utf-8")

    def _auth_headers(self, method: str, path: str) -> dict[str, str]:
        """Return the three Kalshi authentication headers for a request."""
        ts, sig = self._sign(method, path)
        return {
            "KALSHI-ACCESS-KEY":       self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "Content-Type":            "application/json",
        }

    # ── low-level HTTP ─────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict:
        """Authenticated GET. Raises on non-2xx."""
        url     = self.base_url + path
        headers = self._auth_headers("GET", path)   # sign path only, not query
        resp    = self._session.get(
            url, headers=headers, params=params, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        """Authenticated POST with JSON body. Raises on non-2xx."""
        url     = self.base_url + path
        headers = self._auth_headers("POST", path)
        resp    = self._session.post(
            url, headers=headers, json=body, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()

    # ── account info ──────────────────────────

    def get_trade_budget(self) -> float:
        """
        Fetch live balance and return the dynamic trade size for this run.
        If a fixed budget was set at init, use that instead.
        """
        if self._fixed_budget is not None:
            return self._fixed_budget
        data    = self.get_balance()
        balance = data.get("balance", 0) / 100
        budget  = calculate_trade_budget(balance)
        self.budget = budget   # cache for logging
        log.info("Dynamic budget: $%.2f  (balance $%.2f)", budget, balance)
        return budget

    def get_balance(self) -> dict:
        """
        Return account balance info.
        Response includes: balance (cents), payout (cents).

        Example:
            {"balance": 10000, "payout": 0}   # $100.00 available
        """
        data = self._get("/portfolio/balance")
        dollars = data.get("balance", 0) / 100
        log.info("Account balance: $%.2f", dollars)
        return data

    # ── orders ────────────────────────────────

    def place_order(
        self,
        ticker:       str,
        side:         str,          # "yes" or "no"
        prob:         float,        # current market probability (0–1 or 0–100)
        *,
        budget:       float | None = None,
        limit_buffer: int = 2,      # extra cents added to limit price for fill confidence
        reason:       str = "",     # human-readable signal description for ledger
        dry_run:      bool = False,
    ) -> dict:
        """
        Place a Kalshi limit order and log the result.

        Parameters
        ----------
        ticker        Kalshi market ticker, e.g. "KXINFL-25JAN-B3.5"
        side          "yes" or "no"
        prob          Market probability (0.0–1.0  OR  0–100 accepted)
        budget        Dollar amount to spend. Defaults to self.budget ($10).
        limit_buffer  Cents added to limit price to improve fill probability.
                      e.g. buffer=2 on a YES@65 sets limit to 67¢.
        reason        Free-text reason for the trade (logged for audit).
        dry_run       If True, build the payload but don't send it.

        Returns
        -------
        dict with keys: order_id, status, ticker, side, count,
                        yes_price, cost_dollars, ledger_entry
        """
        side = side.lower()
        if side not in ("yes", "no"):
            raise ValueError(f"side must be 'yes' or 'no', got {side!r}")

        # Normalise prob to 0–100 range
        if 0.0 < prob <= 1.0:
            prob = prob * 100
        prob_pct = round(prob)          # integer cents representation of YES price

        # Determine limit price for the chosen side
        if side == "yes":
            raw_price  = prob_pct
            limit_price = min(99, raw_price + limit_buffer)
        else:
            raw_price  = 100 - prob_pct
            limit_price = min(99, raw_price + limit_buffer)

        trade_budget = budget if budget is not None else self.budget
        count = calculate_contracts(trade_budget, limit_price)

        if count < 1:
            raise ValueError(
                f"Budget ${trade_budget:.2f} too small for 1 contract at {limit_price}¢"
            )

        cost_dollars = round(count * limit_price / 100, 2)

        # Build order payload
        payload: dict[str, Any] = {
            "ticker":           ticker,
            "action":           "buy",
            "type":             "limit",
            "side":             side,
            "count":            count,
            "client_order_id":  str(uuid.uuid4()),   # idempotency key
        }
        if side == "yes":
            payload["yes_price"] = limit_price
        else:
            payload["no_price"] = limit_price

        log.info(
            "ORDER  %s  BUY-%s  count=%d  limit=%d¢  cost≈$%.2f%s",
            ticker, side.upper(), count, limit_price, cost_dollars,
            "  [DRY RUN]" if dry_run else "",
        )

        if dry_run:
            log.info("Dry run — skipping API call.")
            return {
                "order_id":     None,
                "status":       "dry_run",
                "ticker":       ticker,
                "side":         side,
                "count":        count,
                "yes_price":    limit_price if side == "yes" else None,
                "no_price":     limit_price if side == "no"  else None,
                "cost_dollars": cost_dollars,
                "payload":      payload,
            }

        # ── Send the order ──
        try:
            response = self._post("/portfolio/orders", payload)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "?"
            body        = exc.response.text       if exc.response is not None else ""
            log.error("Order rejected  HTTP %s: %s", status_code, body)
            self._log_failure(ticker, side, count, limit_price, reason, str(exc))
            raise

        order = response.get("order", response)   # API wraps in "order" key
        order_id = order.get("order_id") or order.get("id", "unknown")
        status   = order.get("status", "unknown")

        log.info("Order accepted  order_id=%s  status=%s", order_id, status)

        # ── Audit ledger entry ──
        entry = {
            "event":        "order_placed",
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "order_id":     order_id,
            "ticker":       ticker,
            "side":         side,
            "count":        count,
            "limit_price":  limit_price,
            "market_prob":  prob_pct,
            "cost_dollars": cost_dollars,
            "budget":       trade_budget,
            "status":       status,
            "reason":       reason,
            "client_order_id": payload["client_order_id"],
            "raw_response": order,
        }
        append_ledger(entry, self.ledger_path)

        return {
            "order_id":     order_id,
            "status":       status,
            "ticker":       ticker,
            "side":         side,
            "count":        count,
            "yes_price":    limit_price if side == "yes" else None,
            "no_price":     limit_price if side == "no"  else None,
            "cost_dollars": cost_dollars,
            "ledger_entry": entry,
        }

    def get_order(self, order_id: str) -> dict:
        """
        Fetch the current state of an order by ID.

        Response fields include: order_id, status, ticker, side,
        count, remaining_count, yes_price, no_price, created_time.
        """
        data = self._get(f"/portfolio/orders/{order_id}")
        order = data.get("order", data)
        log.info(
            "Order %s  status=%s  filled=%d/%d",
            order_id,
            order.get("status"),
            order.get("count", 0) - order.get("remaining_count", 0),
            order.get("count", 0),
        )
        return order

    def get_open_positions(self) -> list[dict]:
        """
        Return all current open positions.

        Each position dict includes: ticker, side, position (contract count),
        market_exposure, realized_pnl, unrealized_pnl.
        """
        data = self._get("/portfolio/positions")
        positions = data.get("market_positions", [])
        log.info("Open positions: %d", len(positions))
        return positions

    def cancel_order(self, order_id: str) -> dict:
        """Cancel a resting limit order."""
        path = f"/portfolio/orders/{order_id}"
        url  = self.base_url + path
        headers = self._auth_headers("DELETE", path)
        resp = self._session.delete(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        log.info("Order %s cancelled.", order_id)
        return resp.json()

    # ── internal helpers ──────────────────────

    def _log_failure(
        self,
        ticker: str,
        side: str,
        count: int,
        limit_price: int,
        reason: str,
        error: str,
    ) -> None:
        entry = {
            "event":      "order_failed",
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "ticker":     ticker,
            "side":       side,
            "count":      count,
            "limit_price": limit_price,
            "reason":     reason,
            "error":      error,
        }
        append_ledger(entry, self.ledger_path)
