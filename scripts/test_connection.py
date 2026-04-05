#!/usr/bin/env python3
"""
test_connection.py
──────────────────
Step 1 health check: can we talk to Kalshi with your real credentials?

This script does ONE read-only thing: fetches your account balance.
No orders. No risk. Just confirms your keys work.

Run it like this from inside the theprob/ folder:

    KALSHI_KEY_ID="your-key-id" \
    KALSHI_PRIVATE_KEY="$(cat your_private_key.pem)" \
    python scripts/test_connection.py
"""

import os
import sys

# ── Check for credentials before importing anything ──────────────────────────
key_id      = os.environ.get("KALSHI_KEY_ID", "")
private_key = os.environ.get("KALSHI_PRIVATE_KEY", "")

if not key_id or not private_key:
    print()
    print("ERROR: Missing credentials.")
    print()
    print("You need to set two environment variables before running this:")
    print()
    print('  export KALSHI_KEY_ID="paste-your-key-id-here"')
    print('  export KALSHI_PRIVATE_KEY="$(cat path/to/your_private_key.pem)"')
    print()
    print("Then run this script again.")
    sys.exit(1)

# ── Connect ───────────────────────────────────────────────────────────────────
sys.path.insert(0, "scripts")   # allow running from repo root
from kalshi_orders import KalshiOrderClient

print()
print("Connecting to Kalshi...")
print()

try:
    client = KalshiOrderClient()
    data   = client.get_balance()

    balance_cents = data.get("balance", 0)
    balance_dollars = balance_cents / 100

    print("=" * 40)
    print("  CONNECTION SUCCESSFUL")
    print(f"  Account balance: ${balance_dollars:.2f}")
    print("=" * 40)
    print()
    print("You're ready for the next step.")

except Exception as e:
    print()
    print(f"ERROR: Could not connect — {e}")
    print()
    print("Common causes:")
    print("  - Wrong KALSHI_KEY_ID (should be a UUID like xxxxxxxx-xxxx-...)")
    print("  - Private key not in PEM format (should start with -----BEGIN)")
    print("  - Key was created on demo account, not production")
    sys.exit(1)
