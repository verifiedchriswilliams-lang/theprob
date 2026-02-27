#!/usr/bin/env python3
"""
Run this once from your repo root:
  python3 patch_generate_email.py

Patches scripts/generate_email.py to:
1. Replace all <h1>/<h2>/<h3> with <div> so Beehiiv can't override colors
2. Fix double-dollar-sign bug ($$350K -> $350K)  
3. Add !important to critical color styles
"""
import re, sys, shutil
from pathlib import Path

target = Path("scripts/generate_email.py")
if not target.exists():
    print(f"ERROR: {target} not found. Run from repo root.")
    sys.exit(1)

# Backup
shutil.copy(target, target.with_suffix(".py.bak"))
print(f"Backed up to {target.with_suffix('.py.bak')}")

src = target.read_text()
original = src

# ── Fix 1: h1/h2/h3 → div in all f-string / string literals ─────────────────
# Match opening tags like <h1 style="..."> or <h1>
src = re.sub(r'<h1\b', '<div', src)
src = re.sub(r'</h1>', '</div>', src)
src = re.sub(r'<h2\b', '<div', src)
src = re.sub(r'</h2>', '</div>', src)
src = re.sub(r'<h3\b', '<div', src)
src = re.sub(r'</h3>', '</div>', src)

# ── Fix 2: Double dollar sign from f-string interpolation ────────────────────
# Pattern: fmt_volume returns "$350K", then template wraps it in another $
# Common patterns: f"$${volume}" or "$${vol_fmt}" 
src = re.sub(r'\$\$\{', '${', src)           # $${variable} -> ${variable}
src = re.sub(r'"\$\$', '"$', src)             # "$$350K" -> "$350K"  
src = re.sub(r"'\$\$", "'$", src)             # '$$350K' -> '$350K'

# ── Fix 3: Force !important on text colors Beehiiv overrides most ─────────────
# Target the key color properties in the hero title and section headers
FORCE_COLORS = [
    # (old, new)
    ('color:#edf2f7;', 'color:#edf2f7 !important;'),
    ('color:#00e5a0;', 'color:#00e5a0 !important;'),
    ('color:#ff4757;', 'color:#ff4757 !important;'),
    ('color:#8ba3bc;', 'color:#8ba3bc !important;'),
    ('color:#546e85;', 'color:#546e85 !important;'),
    ('color:#f5a623;', 'color:#f5a623 !important;'),
    ('color:#080b0f;', 'color:#080b0f !important;'),
]
for old, new in FORCE_COLORS:
    src = src.replace(old, new)

if src == original:
    print("WARNING: No changes made — check that script/generate_email.py contains h1/h2/h3 tags")
else:
    target.write_text(src)
    changed = sum(1 for a, b in zip(original.splitlines(), src.splitlines()) if a != b)
    print(f"Patched {target} ({changed} lines changed)")
    print("Changes:")
    print("  ✓ h1/h2/h3 → div (prevents Beehiiv color overrides)")
    print("  ✓ Double dollar sign fixed")
    print("  ✓ !important added to critical color styles")
