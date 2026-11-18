#!/usr/bin/env python3
"""
send_newsletter.py
Builds The Prob daily newsletter HTML via Beehiiv API.
Reads data/markets.json and data/news.json.
Runs once daily at 7AM ET via GitHub Actions.

Mobile-first design implementing 26 best practices:
  - Fluid layout (100% width, max 600px)
  - 16px+ body text, 1.8 line-height
  - @media queries for mobile typography/padding/layout
  - Responsive hero stats (stacked on mobile)
  - Dark mode locked via @media prefers-color-scheme
  - MSO/Outlook conditional comment fallbacks
  - WCAG AA contrast on all text
  - Category color chips on movers
  - Tap-friendly CTA buttons (44px+ touch targets)
  - Plain text friendly structure
  - Reply CTA for deliverability
  - Read time estimate in header
  - Section visual separators
  - Accessible alt text and title attributes
  - News summaries capped at 2 sentences
  - <div> not <h1/h2/h3> (prevents Beehiiv color overrides)
  - !important on all colors (beats Beehiiv stylesheet)
  - No double dollar signs
  - HTML arrow entities (Outlook safe)
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ── CONFIG ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL       = "claude-haiku-4-5-20251001"
SITE_URL           = "https://theprob.ai"
OUTPUT_PATH        = "newsletter/latest.html"

# Resend — set via GitHub secrets RESEND_API_KEY and RESEND_AUDIENCE_ID
RESEND_API_KEY    = os.environ.get("RESEND_API_KEY", "")
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")
FROM_ADDRESS      = "The Prob <newsletter@theprob.ai>"

HOUSE_STYLE_SYSTEM = (
    "You write for The Prob, a prediction markets newsletter. "
    "The north star: help readers make money in prediction markets. "
    "Every piece of copy should deliver alpha, not just news. "
    "Ask yourself: what does this price move signal, is the market right, and what would a sharp bettor do? "
    "Voice: sharp, confident, dry wit, slightly irreverent. Like The Hustle meets a trading desk. "
    "Intelligent but not academic. Opinionated but not arrogant. "
    "NEVER use em dashes. Use a comma or start a new sentence instead. "
    "Short sentences. Active voice. Numbers as numerals ($2M, 47%). "
    "No hedging. No fluff. No filler. "
    "Undetectable as AI. Write like a sharp human who has real skin in the game."
)

# Category color chips — used in movers table
CATEGORY_COLORS = {
    "Politics":   "#ff4757",
    "Finance":    "#00e5a0",
    "Technology": "#4ecdc4",
    "Crypto":     "#f5a623",
    "Sports":     "#a78bfa",
    "Culture":    "#f97316",
    "World":      "#60a5fa",
}

# ── FROM THE BUILDER ──────────────────────────────────────────────────────────
# Loaded from data/builder_notes.json — update that file each session.
# Fields: built_recently, coming_next, last_updated
# Keep it trader-facing — no implementation jargon.

def load_builder_notes() -> dict:
    """Load From Chris section from data/builder_notes.json."""
    try:
        with open("data/builder_notes.json") as f:
            notes = json.load(f)
        # Warn in pipeline output if notes are stale (> 7 days)
        last_updated = notes.get("last_updated", "")
        if last_updated:
            try:
                updated_date = datetime.fromisoformat(last_updated).date()
                days_stale   = (datetime.now(timezone.utc).date() - updated_date).days
                if days_stale > 7:
                    print(f"  [WARN] builder_notes.json is {days_stale} days old — update data/builder_notes.json")
            except (ValueError, AttributeError):
                pass
        return notes
    except FileNotFoundError:
        print("  [WARN] data/builder_notes.json not found — From Chris section will be empty")
        return {}
    except Exception as e:
        print(f"  [WARN] Could not load builder_notes.json: {e}")
        return {}

# ── LOAD DATA ─────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

# ── HELPERS ───────────────────────────────────────────────────────────────────

def claude(prompt: str, max_tokens: int = 200) -> str:
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      CLAUDE_MODEL,
                "max_tokens": max_tokens,
                "system":     HOUSE_STYLE_SYSTEM,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        return text.replace("\u2014", ",").replace(" -- ", ", ")
    except Exception as e:
        print(f"  [WARN] Claude call failed: {e}")
        return ""

def color_prob(prob: float) -> str:
    if prob >= 65:  return "#059669"
    if prob <= 35:  return "#E11D48"
    return "#4A5568"

def arrow(change: float) -> str:
    if change > 0:  return "&#9650;"
    if change < 0:  return "&#9660;"
    return "&ndash;"

def change_color(change: float) -> str:
    if change > 0:  return "#059669"
    if change < 0:  return "#E11D48"
    return "#718096"

def category_chip(cat: str) -> str:
    """Colored category pill for movers table."""
    color = CATEGORY_COLORS.get(cat, "#94A3B8")
    return (
        f'<span style="display:inline-block;background:{color}22;'
        f'color:{color} !important;border:1px solid {color}55;'
        f'font-family:\'Courier New\',monospace;font-size:9px;'
        f'font-weight:700;letter-spacing:0.08em;padding:2px 6px;'
        f'text-transform:uppercase;border-radius:2px;margin-right:6px;">'
        f'{cat}</span>'
    )

def build_builder_section() -> str:
    """Personal 'From Chris' section — loaded fresh from data/builder_notes.json each run."""
    notes   = load_builder_notes()
    built   = notes.get("built_recently", "")
    coming  = notes.get("coming_next", "")
    if not built and not coming:
        return ""
    # Collapse if stale (older than 7 days)
    last_updated_str = notes.get("last_updated", "")
    if last_updated_str:
        try:
            last_updated = datetime.strptime(last_updated_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            if (now_utc - last_updated).days > 7:
                return ""
        except ValueError:
            pass
    built_block = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#4A5568;'
        'line-height:1.7;margin-bottom:12px;">'
        '<span style="color:#0B0E14;font-weight:700;">Recently:</span> ' + built
        + '</div>'
    ) if built else ""
    coming_block = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#4A5568;'
        'line-height:1.7;margin-bottom:16px;">'
        '<span style="color:#0B0E14;font-weight:700;">Next:</span> ' + coming
        + '</div>'
    ) if coming else ""
    return (
        '  <tr><td style="padding:24px 24px 20px;background:#E6F4FB;border-bottom:1px solid #E8ECF0;">\n'
        "    <div style=\"font-family:'Courier New',monospace;font-size:9px;letter-spacing:0.14em;"
        'text-transform:uppercase;color:#0077B6;margin-bottom:14px;">% From Chris</div>\n'
        '    ' + built_block + '\n'
        '    ' + coming_block + '\n'
        "    <div style=\"font-family:'Courier New',monospace;font-size:12px;color:#4A5568;"
        'border-top:1px solid #E8ECF0;padding-top:14px;">Chris</div>\n'
        '  </td></tr>'
    )

def truncate_summary(text: str, max_sentences: int = 2) -> str:
    """Cap news summaries at 2 sentences for mobile readability."""
    if not text:
        return ""
    sentences = text.replace("! ", ". ").replace("? ", ". ").split(". ")
    truncated = ". ".join(sentences[:max_sentences])
    if not truncated.endswith("."):
        truncated += "."
    return truncated

def estimate_read_time(markets: dict, news: dict) -> str:
    """Estimate read time based on content volume."""
    # ~200 words per section, 200wpm average reader
    word_count = 300  # header + hero
    word_count += len(markets.get("movers", [])) * 20
    word_count += len(news.get("articles", [])) * 60
    if markets.get("daily_take"):
        word_count += 120
    minutes = max(2, round(word_count / 200))
    return f"{minutes} min read"

def generate_subtitle(hero: dict, movers: list, daily_take: dict) -> str:
    q      = hero.get("question", "")
    prob   = hero.get("prob", 50)
    change = hero.get("change_pts", 0)
    top_movers = ", ".join(m.get("question", "")[:50] for m in movers[:3])
    take_headline = daily_take.get("headline", "") if daily_take else ""
    now_et = datetime.now(timezone.utc) + timedelta(hours=-5)
    date_str = now_et.strftime("%B %-d")
    prompt = (
        f"Today's top market: {q} — currently at {prob}%, moved {'+' if change > 0 else ''}{change}pts today\n"
        f"Other movers: {top_movers}\n"
        f"Today's take: {take_headline}\n\n"
        f"Write ONE short email preview/subtitle for The Prob newsletter dated {date_str}. "
        "This is the preview text shown under the subject line in an inbox. "
        "Max 80 characters. Make it feel like something is actually happening today — "
        "specific, punchy, tied to the actual markets. "
        "No em dashes. No quotes. Don't repeat the subject line. "
        "Just the preview text, nothing else."
    )
    subtitle = claude(prompt, max_tokens=80)
    if not subtitle:
        subtitle = f"The crowd's read on {date_str}. Markets, movers, and what it means."
    return subtitle


def generate_subject(hero: dict, daily_take: dict, movers: list = None, articles: list = None) -> str:
    q      = hero.get("question", "")
    prob   = hero.get("prob", 50)
    change = hero.get("change_pts", 0)
    take_headline = daily_take.get("headline", "") if daily_take else ""

    # Gather extra signals to give Claude more hooks to work with
    top_mover_line = ""
    if movers:
        m = movers[0]
        mc = m.get("change_pts", 0)
        top_mover_line = f"Biggest mover today: {m.get('question','')} ({'+' if mc>0 else ''}{mc} pts)\n"

    news_line = ""
    if articles:
        news_line = f"Top news headline: {articles[0].get('title','')}\n"

    chg_str = f"{'+' if change > 0 else ''}{change} pts"

    prompt = (
        f"You write subject lines for The Prob, a prediction markets newsletter.\n\n"
        f"TODAY'S DATA:\n"
        f"- Top market: {q}\n"
        f"- Current probability: {prob}%\n"
        f"- 24h swing: {chg_str}\n"
        + (f"- Editorial take: {take_headline}\n" if take_headline else "")
        + top_mover_line
        + news_line
        + "\n"
        "GOAL: Write ONE subject line that gets opened. Max 55 characters.\n\n"
        "FORMATS THAT WORK (pick whichever fits the data best):\n"
        '- Specific odds + stakes: "The crowd says 73%. Here\'s why that matters."\n'
        '- Sharp move: "Down 18 pts overnight. The crowd just changed its mind."\n'
        '- Counterintuitive read: "Everyone thinks this is 90%. The smart money disagrees."\n'
        '- News hook: "After today\'s headlines, the odds shifted hard."\n'
        '- Low-probability tension: "Only 12%. But $2M says it happens."\n'
        '- Simple provocation: "The crowd is pricing this wrong."\n\n'
        "RULES:\n"
        "- No em dashes. No quotes around the subject. No 'The Prob:' prefix.\n"
        "- Do not start with 'I' or 'We'.\n"
        "- Sound like insider intel, not a headline writer.\n"
        "- Output ONLY the subject line. Nothing else."
    )
    subject = claude(prompt, max_tokens=80)
    if not subject:
        direction = "up" if change > 0 else "down"
        subject = f"The crowd moved {abs(change)} pts {direction} on this one"
    return subject

# ── GLOBAL STYLES (injected into <head>) ─────────────────────────────────────

def build_head_styles() -> str:
    """CSS for the full-HTML preview version (latest-email.html / iframe).
    NOT used in latest-copy.html — Beehiiv strips style blocks, so the paste
    version uses only inline styles and single-column layout.
    """
    return """
<style type="text/css">
  body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
  table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
  img { -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }
  a { -webkit-tap-highlight-color: transparent; }
  a[x-apple-data-detectors] { color: inherit !important; text-decoration: none !important; }
</style>"""

# ── GAME NIGHT PROPS SECTION ─────────────────────────────────────────────────

def build_game5_section(props: list) -> str:
    """Render a 'Tonight's Prop Desk' section from a list of game5_props dicts."""
    if not props:
        return ""

    rows = ""
    for p in props:
        prob    = p.get("prob", 50)
        chg     = p.get("change_pts", 0)
        chg_str = (("+" if chg > 0 else "") + str(chg) + " pts") if chg != 0 else "—"
        chg_col = "#059669" if chg > 0 else ("#E11D48" if chg < 0 else "#718096")
        prob_col = color_prob(prob)
        src_col  = "#a78bfa"  # sports purple
        note     = p.get("note", "")
        url      = p.get("url", "#")

        rows += (
            '<tr><td style="padding:12px 0;border-bottom:1px solid #E8ECF0;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
            # left: label + note
            '<td style="vertical-align:top;padding-right:12px;">'
            '<a href="' + url + '" style="text-decoration:none;">'
            "<div style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
            'font-size:15px;color:#0B0E14;line-height:1.3;margin-bottom:3px;">'
            + p.get("label", "") + '</div></a>'
            + ('<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;'
               'color:#718096;line-height:1.4;">' + note + '</div>' if note else '')
            + '<div style="margin-top:4px;"><span style="font-family:Arial,Helvetica,sans-serif;'
            'font-size:9px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;'
            'color:#FFFFFF;background:' + src_col + ';padding:2px 6px;border-radius:3px;">'
            + p.get("source", "") + '</span></div>'
            '</td>'
            # right: prob + change
            '<td style="text-align:right;vertical-align:top;white-space:nowrap;">'
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:22px;font-weight:700;'
            'color:' + prob_col + ';line-height:1;">' + str(prob) + '%</div>'
            "<div style=\"font-family:'Courier New',monospace;font-size:10px;color:" + chg_col
            + ';margin-top:3px;">' + chg_str + '</div>'
            '</td>'
            '</tr></table>'
            '</td></tr>'
        )

    return (
        '  <tr><td style="padding:20px 24px 16px;background:#FFFFFF;border-bottom:1px solid #E8ECF0;">\n'
        '    ' + _eyebrow("Tonight&#39;s Prop Desk &middot; NBA Finals Game 5") + '\n'
        '    <table width="100%" cellpadding="0" cellspacing="0">\n'
        + rows +
        '    </table>\n'
        '    <div style="margin-top:10px;">'
        '<a href="https://kalshi.com/category/sports/basketball" '
        'style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#0077B6;'
        'text-decoration:none;letter-spacing:0.05em;">View all game markets &#8594;</a></div>\n'
        '  </td></tr>'
    )


# ── THE SPREAD SECTION ────────────────────────────────────────────────────────

def build_spread_section(spread_markets: list, max_items: int = 4) -> str:
    """
    Generate the 'The Spread' newsletter HTML block.
    Surfaces where Polymarket and Kalshi price the same event differently.
    Beehiiv-safe: no h1/h2, all colors !important, HTML entities, no double dollar signs.
    Returns empty string if no divergence pairs available.
    """
    if not spread_markets:
        return ""

    items = spread_markets[:max_items]

    def fv(n):
        """Format volume — single dollar sign only (Beehiiv strips doubles)."""
        if not n:
            return "\u2014"
        if n >= 1_000_000:
            return f"${n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"${n/1_000:.0f}K"
        return f"${int(n)}"

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    rows = ""
    for m in items:
        poly_p   = m["poly_prob"]
        kal_p    = m["kalshi_prob"]
        gap      = m["gap_pts"]
        title    = esc(m["display_title"])
        vol      = fv(m.get("combined_volume", 0))

        p_url    = m.get("poly_url", "")
        k_url    = m.get("kalshi_url", "")
        p_open   = f'<a href="{p_url}" style="color:#a78bfa !important;text-decoration:none !important;" target="_blank">' if p_url else "<span>"
        p_close  = "</a>" if p_url else "</span>"
        k_open   = f'<a href="{k_url}" style="color:#93c5fd !important;text-decoration:none !important;" target="_blank">' if k_url else "<span>"
        k_close  = "</a>" if k_url else "</span>"

        oi_str   = f' &bull; Kalshi OI: {fv(m.get("kalshi_oi", 0))}' if m.get("kalshi_oi", 0) > 0 else ""

        rows += f"""
    <tr><td style="padding:0 0 8px 0 !important;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#07090E !important;border:1px solid #141B2D !important;border-radius:8px !important;">
      <tr><td style="padding:12px 14px 10px !important;">
        <div style="font-size:13px !important;font-weight:600 !important;color:#F8F9FA !important;line-height:1.35 !important;margin-bottom:8px !important;">{title}</div>
        <div style="display:flex !important;align-items:center !important;gap:8px !important;flex-wrap:wrap !important;margin-bottom:6px !important;">
          {p_open}<span style="display:inline-block !important;background:rgba(139,92,246,.2) !important;color:#a78bfa !important;border:1px solid rgba(139,92,246,.3) !important;border-radius:999px !important;padding:3px 10px !important;font-size:12px !important;font-weight:700 !important;">Poly&nbsp;{poly_p}%</span>{p_close}
          <span style="color:#64748B !important;font-size:11px !important;">&#8596;</span>
          {k_open}<span style="display:inline-block !important;background:rgba(59,130,246,.2) !important;color:#93c5fd !important;border:1px solid rgba(59,130,246,.3) !important;border-radius:999px !important;padding:3px 10px !important;font-size:12px !important;font-weight:700 !important;">Kalshi&nbsp;{kal_p}%</span>{k_close}
          <span style="display:inline-block !important;background:rgba(245,166,35,.15) !important;color:#f5a623 !important;border:1px solid rgba(245,166,35,.3) !important;border-radius:999px !important;padding:3px 8px !important;font-size:11px !important;font-weight:700 !important;">&#9889; {gap} pts</span>
        </div>
        <div style="font-size:11px !important;color:#64748B !important;">Vol: {vol}{oi_str}</div>
      </td></tr>
      </table>
    </td></tr>"""

    return f"""
  <!-- THE SPREAD -->
  <tr><td style="padding:20px 0 0 !important;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#07090E !important;border:2px solid #141B2D !important;border-radius:10px !important;padding:0 !important;">
  <tr><td style="padding:18px 20px 6px !important;">
    <div style="font-family:'Space Mono',monospace !important;font-size:10px !important;letter-spacing:0.2em !important;text-transform:uppercase !important;color:#94A3B8 !important;margin-bottom:4px !important;">&#9889; The Spread</div>
    <div style="font-size:16px !important;font-weight:700 !important;color:#F8F9FA !important;margin-bottom:4px !important;">The crowd disagrees with itself</div>
    <div style="font-size:12px !important;color:#64748B !important;margin-bottom:14px !important;">Polymarket vs Kalshi &bull; 8pt+ gap &bull; one of them is wrong</div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {rows}
    </table>
    <div style="font-size:11px !important;color:#64748B !important;padding-bottom:14px !important;">
      <a href="https://theprob.ai" style="color:#94A3B8 !important;">See all divergences on The Prob &#8594;</a>
    </div>
  </td></tr>
  </table>
  </td></tr>"""


# ── HTML BUILDER ──────────────────────────────────────────────────────────────

def _eyebrow(label):
    return (
        '<div style="margin-bottom:14px;">'
        '<span style="display:inline-block;background:#E6F4FB;color:#0077B6;'
        "font-family:'Courier New',monospace;font-size:9px;font-weight:600;"
        'letter-spacing:0.12em;text-transform:uppercase;padding:4px 10px;border-radius:999px;">'
        '% ' + label + '</span></div>'
    )


def build_html(markets, news, subject, with_footer=True):
    hero       = markets.get("hero", {})
    trade      = markets.get("trade") or {}
    movers     = [m for m in markets.get("movers", []) if abs(m.get("change_pts", 0)) >= 5][:5]
    daily_take = markets.get("daily_take", {})
    articles   = news.get("articles", [])[:3]

    now_et   = datetime.now(timezone.utc) + timedelta(hours=-5)
    date_str = now_et.strftime("%B %-d, %Y")

    hero_prob   = hero.get("prob", 50)
    hero_change = hero.get("change_pts", 0)
    hero_q      = hero.get("question", "")
    hero_vol    = hero.get("volume_fmt", "")
    hero_source = hero.get("source", "")
    hero_url    = hero.get("url", SITE_URL)
    hero_take   = hero.get("prob_take", "")
    hero_end    = hero.get("end_date", "")
    prob_col    = color_prob(hero_prob)
    chg_col     = change_color(hero_change)
    chg_sign    = "+" if hero_change > 0 else ""

    portfolio = markets.get("portfolio", {})
    variants  = portfolio.get("variants", {})
    def _v(k): return variants.get(k, {})
    def _ret(k):
        ytd = _v(k).get("ytd_return_pct", 0.0)
        col = "#059669" if ytd >= 0 else "#E11D48"
        sgn = "+" if ytd >= 0 else ""
        return '<span style="color:' + col + ';font-weight:700;">' + sgn + f"{ytd:.1f}%" + '</span>'
    any_trades = any((_v(k).get("win_count",0)+_v(k).get("loss_count",0))>0 for k in "abc")
    if any_trades:
        port_line = (
            "A:" + _ret("a") + " &nbsp; B:" + _ret("b") + " &nbsp; C:" + _ret("c")
            + " &nbsp;&middot;&nbsp; <a href='" + SITE_URL + "/portfolio.html'"
            + " style='color:#0077B6;text-decoration:none;'>portfolio &#8599;</a>"
        )
    else:
        port_line = (
            "<a href='" + SITE_URL + "/portfolio.html'"
            + " style='color:#0077B6;text-decoration:none;'>3 models running &#8599;</a>"
        )

    # ── HEADER ──
    header = (
        '  <tr><td style="background:#FFFFFF;padding:24px 24px 20px;border-bottom:3px solid #0077B6;">\n'
        '    <table width="100%" cellpadding="0" cellspacing="0"><tr>\n'
        '      <td style="vertical-align:middle;">\n'
        '        <a href="' + SITE_URL + '" style="text-decoration:none;">\n'
        '          <table cellpadding="0" cellspacing="0"><tr>\n'
        '            <td style="vertical-align:middle;">\n'
        '              <div style="width:32px;height:32px;background:#0077B6;border-radius:8px;'
        'text-align:center;line-height:32px;display:inline-block;">\n'
        '                <span style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#fff;">%</span>\n'
        '              </div>\n'
        '            </td>\n'
        '            <td style="vertical-align:middle;padding-left:8px;">\n'
        "              <span style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
        'font-size:26px;font-weight:400;color:#0B0E14;letter-spacing:-0.5px;line-height:1;">The Prob</span>\n'
        '            </td>\n'
        '          </tr></table>\n'
        '        </a>\n'
        '      </td>\n'
        '      <td style="text-align:right;vertical-align:middle;">\n'
        "        <div style=\"font-family:'Courier New',monospace;font-size:9px;color:#718096;"
        'letter-spacing:0.12em;text-transform:uppercase;">' + date_str + '</div>\n'
        '        <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#4A5568;margin-top:4px;">'
        + port_line + '</div>\n'
        '      </td>\n'
        '    </tr></table>\n'
        '  </td></tr>'
    )

    # ── HERO ──
    hero_chg_str = f"{chg_sign}{hero_change} pts today"
    # Prob bar width (capped 2–98%)
    bar_pct = max(2, min(98, hero_prob))

    # Take as card footer (brand-soft bg, matches .hero-card-insight on the website)
    hero_take_footer = ""
    if hero_take:
        hero_take_footer = (
            '  <tr><td style="padding:16px 24px;background:rgba(0,119,182,.08);'
            'border-top:1px solid rgba(11,14,20,.08);">\n'
            "    <p style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
            'font-size:13px;font-style:italic;color:#4A5568;line-height:1.6;margin:0;">'
            "<strong style=\"color:#0077B6;font-style:normal;font-family:'Courier New',monospace;"
            "font-size:10px;letter-spacing:0.1em;text-transform:uppercase;\">% The Prob's Take</strong>"
            '<br>' + hero_take + '</p>\n'
            '  </td></tr>'
        )

    hero_section = (
        # Card wrapper — matches .hero-card: white bg, border, 16px radius, shadow
        '  <tr><td style="padding:20px 24px;background:#F8F9FA;">\n'
        '  <table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;'
        'border:1px solid rgba(11,14,20,.08);border-radius:16px;overflow:hidden;'
        'box-shadow:0 12px 32px -4px rgba(11,14,20,.08),0 4px 12px -2px rgba(11,14,20,.04);">\n'
        # Card header — "Trending" label with live dot + source
        '  <tr><td style="padding:16px 24px;border-bottom:1px solid rgba(11,14,20,.08);">\n'
        '    <table width="100%" cellpadding="0" cellspacing="0"><tr>\n'
        '      <td>\n'
        "        <span style=\"font-family:'Courier New',monospace;font-size:10px;"
        'letter-spacing:0.15em;text-transform:uppercase;color:#718096;'
        'display:inline-flex;align-items:center;gap:8px;">'
        '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;'
        'background:#059669;"></span> Trending</span>\n'
        '      </td>\n'
        "      <td style=\"text-align:right;font-family:'Courier New',monospace;"
        'font-size:10px;color:#718096;">' + hero_source + '</td>\n'
        '    </tr></table>\n'
        '  </td></tr>\n'
        # Card body
        '  <tr><td style="padding:24px;">\n'
        # Question
        "    <div style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
        'font-size:18px;line-height:1.4;color:#0B0E14;margin-bottom:20px;">'
        '<a href="' + hero_url + '" style="color:#0B0E14;text-decoration:none;">'
        + hero_q + '</a></div>\n'
        # Prob display: big number + % + YES/change stacked to its right
        '    <div style="margin-bottom:20px;">\n'
        '    <table cellpadding="0" cellspacing="0"><tr>\n'
        '      <td style="vertical-align:bottom;padding-right:16px;">\n'
        '        <div style="font-family:Arial,Helvetica,sans-serif;font-size:64px;'
        'font-weight:800;color:' + prob_col + ';line-height:1;letter-spacing:-2px;'
        'font-feature-settings:\'tnum\';">' + str(hero_prob) + '</div>\n'
        '      </td>\n'
        '      <td style="vertical-align:bottom;padding-bottom:6px;">\n'
        '        <div style="font-family:Arial,Helvetica,sans-serif;font-size:24px;'
        'font-weight:700;color:' + prob_col + ';line-height:1;margin-bottom:6px;">%</div>\n'
        "        <div style=\"font-family:'Courier New',monospace;font-size:13px;color:"
        + chg_col + ';margin-bottom:4px;">' + arrow(hero_change) + ' ' + hero_chg_str + '</div>\n'
        '      </td>\n'
        '    </tr></table>\n'
        '    </div>\n'
        # Prob bar
        '    <div style="height:6px;background:#F1F3F5;border-radius:9999px;margin-bottom:20px;overflow:hidden;">\n'
        '      <div style="height:100%;width:' + str(bar_pct) + '%;'
        'background:linear-gradient(to right,rgba(5,150,105,.3),' + prob_col + ');'
        'border-radius:9999px;"></div>\n'
        '    </div>\n'
        # Meta 2x2 tiles
        '    <table width="100%" cellpadding="0" cellspacing="0"><tr>\n'
        '      <td style="width:50%;padding-right:4px;">\n'
        '        <div style="background:#F1F3F5;padding:12px 14px;border-radius:8px;">\n'
        "          <div style=\"font-family:'Courier New',monospace;font-size:9px;"
        'letter-spacing:0.15em;text-transform:uppercase;color:#718096;margin-bottom:4px;">Volume</div>\n'
        "          <div style=\"font-family:'Courier New',monospace;font-size:14px;"
        'color:#0B0E14;font-weight:600;font-feature-settings:\'tnum\';">' + hero_vol + '</div>\n'
        '        </div>\n'
        '      </td>\n'
        '      <td style="width:50%;padding-left:4px;">\n'
        '        <div style="background:#F1F3F5;padding:12px 14px;border-radius:8px;">\n'
        "          <div style=\"font-family:'Courier New',monospace;font-size:9px;"
        'letter-spacing:0.15em;text-transform:uppercase;color:#718096;margin-bottom:4px;">Resolves</div>\n'
        "          <div style=\"font-family:'Courier New',monospace;font-size:14px;"
        'color:#0B0E14;font-weight:600;font-feature-settings:\'tnum\';">' + (hero_end or "TBD") + '</div>\n'
        '        </div>\n'
        '      </td>\n'
        '    </tr></table>\n'
        '  </td></tr>\n'
        + hero_take_footer
        + '  </table>\n'
        '  </td></tr>'
    )

    # ── TODAY'S TRADE ──
    trade_section = ""
    if trade:
        t_prob = trade.get("prob", 50)
        t_dir  = "YES" if t_prob >= 65 else "NO"
        t_q    = trade.get("question", "")
        t_end  = trade.get("end_date", "")
        t_url  = trade.get("url", SITE_URL)
        t_src  = trade.get("source", "")
        t_chg  = trade.get("change_pts", 0)
        t_col  = color_prob(t_prob)
        d_col  = "#059669" if t_dir == "YES" else "#E11D48"
        cc     = change_color(t_chg)
        ca     = arrow(t_chg)
        trade_eyebrow = _eyebrow("Today's Trade")
        trade_section = (
            '  <tr><td style="padding:20px 24px;background:#F8F9FA;border-bottom:1px solid rgba(11,14,20,.08);">\n'
            '    ' + trade_eyebrow + '\n'
            '    <div style="background:#FFFFFF;border:1px solid #E8ECF0;border-top:3px solid #0077B6;'
            'border-radius:0 0 8px 8px;padding:16px 20px;">\n'
            "      <div style=\"font-family:'Courier New',monospace;font-size:9px;color:#718096;"
            'letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;">'
            + t_src + ' &middot; Closes ' + t_end + '</div>\n'
            '      <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:600;'
            'color:#0B0E14;line-height:1.4;margin-bottom:14px;">'
            '<a href="' + t_url + '" style="color:#0B0E14;text-decoration:none;">' + t_q + '</a></div>\n'
            '      <table cellpadding="0" cellspacing="0"><tr>\n'
            '        <td style="padding-right:24px;">\n'
            "          <div style=\"font-family:'Courier New',monospace;font-size:9px;color:#718096;"
            'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">Probability</div>\n'
            '          <div style="font-family:Arial,Helvetica,sans-serif;font-size:26px;font-weight:700;'
            'color:' + t_col + ';">' + str(t_prob) + '%</div>\n'
            '        </td>\n'
            '        <td style="padding-right:24px;">\n'
            "          <div style=\"font-family:'Courier New',monospace;font-size:9px;color:#718096;"
            'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">24h Move</div>\n'
            '          <div style="font-family:Arial,Helvetica,sans-serif;font-size:18px;font-weight:700;'
            'color:' + cc + ';">' + ca + ' ' + f"{abs(t_chg):.1f}" + 'pts</div>\n'
            '        </td>\n'
            '        <td>\n'
            "          <div style=\"font-family:'Courier New',monospace;font-size:9px;color:#718096;"
            'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">The Prob plays</div>\n'
            '          <div style="font-family:Arial,Helvetica,sans-serif;font-size:26px;font-weight:700;'
            'color:' + d_col + ';">' + t_dir + '</div>\n'
            '        </td>\n'
            '      </tr></table>\n'
            '      <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#718096;'
            'margin-top:12px;">$100 paper trade &middot; '
            '<a href="' + SITE_URL + '/portfolio.html" style="color:#0077B6;text-decoration:none;">'
            'tracked at theprob.ai/portfolio</a></div>\n'
            '    </div>\n'
            '  </td></tr>'
        )

    # ── MOVERS ──
    mover_cards = ""
    for m in movers:
        p      = m.get("prob", 50)
        c      = m.get("change_pts", 0)
        p_col  = color_prob(p)
        c_col  = change_color(c)
        # 3px top-accent color: green for up, red for down
        accent = "#059669" if c > 0 else "#E11D48"
        bar_w  = max(2, min(98, p))
        mover_cards += (
            '    <table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;'
            'border:1px solid rgba(11,14,20,.08);border-radius:12px;overflow:hidden;'
            'box-shadow:0 4px 20px -2px rgba(11,14,20,.05),0 2px 6px -1px rgba(11,14,20,.03);'
            'margin-bottom:8px;">\n'
            # 3px accent bar at top
            '      <tr><td style="height:3px;background:' + accent + ';padding:0;line-height:0;">&nbsp;</td></tr>\n'
            '      <tr><td style="padding:16px 20px;">\n'
            # Source
            "        <div style=\"font-family:'Courier New',monospace;font-size:9px;"
            'letter-spacing:0.15em;text-transform:uppercase;color:#718096;margin-bottom:8px;">'
            + m.get("source", "").upper() + '</div>\n'
            # Question
            "        <div style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
            'font-size:15px;line-height:1.4;color:#0B0E14;margin-bottom:14px;">'
            '<a href="' + m.get("url", SITE_URL) + '" style="color:#0B0E14;text-decoration:none;">'
            + m.get("question", "") + '</a></div>\n'
            # Stats row: big prob left, change right
            '        <table width="100%" cellpadding="0" cellspacing="0"><tr>\n'
            '          <td>\n'
            '            <div style="font-family:Arial,Helvetica,sans-serif;font-size:28px;'
            'font-weight:800;color:' + p_col + ';line-height:1;font-feature-settings:\'tnum\';">'
            + str(p) + '%</div>\n'
            '          </td>\n'
            '          <td style="text-align:right;">\n'
            "            <div style=\"font-family:'Courier New',monospace;font-size:12px;color:"
            + c_col + ';margin-bottom:4px;">' + arrow(c) + ' ' + f"{abs(c):.1f}" + ' pts</div>\n'
            "            <div style=\"font-family:'Courier New',monospace;font-size:10px;color:#718096;\">"
            + m.get("volume_fmt", "") + '</div>\n'
            '          </td>\n'
            '        </tr></table>\n'
            # Prob bar
            '        <div style="height:3px;background:#F1F3F5;border-radius:9999px;margin-top:14px;overflow:hidden;">\n'
            '          <div style="height:100%;width:' + str(bar_w) + '%;background:' + p_col
            + ';border-radius:9999px;"></div>\n'
            '        </div>\n'
            '      </td></tr>\n'
            '    </table>\n'
        )

    movers_eyebrow = _eyebrow("Today's Biggest Movers")
    movers_section = ""
    if movers:
        movers_section = (
            '  <tr><td style="padding:20px 24px;background:#F8F9FA;border-bottom:1px solid rgba(11,14,20,.08);">\n'
            '    ' + movers_eyebrow + '\n'
            + mover_cards
            + '    <div style="margin-top:4px;">'
            '<a href="' + SITE_URL + '" style="font-family:\'Courier New\',monospace;'
            'font-size:10px;color:#0077B6;text-decoration:none;letter-spacing:0.1em;'
            'text-transform:uppercase;">See all markets &#8594;</a></div>\n'
            '  </td></tr>'
        )

    # ── NEWS ──
    news_rows = ""
    for i, a in enumerate(articles):
        border  = "border-bottom:1px solid #E8ECF0;" if i < len(articles)-1 else ""
        summary = truncate_summary(a.get("summary", ""))
        summary_html = (
            '      <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;'
            'color:#4A5568;line-height:1.65;">' + summary + '</div>\n'
        ) if summary else ""
        news_rows += (
            '    <tr><td style="padding:16px 20px;' + border + '">\n'
            "      <div style=\"font-family:'Courier New',monospace;font-size:9px;"
            'letter-spacing:0.12em;text-transform:uppercase;color:#718096;margin-bottom:6px;">'
            + a.get("source", "").upper() + ' &middot; ' + a.get("pub_display", "") + '</div>\n'
            "      <div style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
            'font-size:16px;color:#0B0E14;line-height:1.35;margin-bottom:6px;">'
            '<a href="' + a.get("url", SITE_URL) + '" style="color:#0B0E14;text-decoration:none;">'
            + a.get("title", "") + '</a></div>\n'
            + summary_html
            + '    </td></tr>\n'
        )

    news_eyebrow = _eyebrow("What People Are Writing About")
    news_section = (
        '  <tr><td style="padding:20px 24px;background:#F8F9FA;border-bottom:1px solid rgba(11,14,20,.08);">\n'
        '    ' + news_eyebrow + '\n'
        '    <table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;'
        'border:1px solid rgba(11,14,20,.08);border-radius:12px;overflow:hidden;padding:0;">\n'
        + news_rows
        + '    </table>\n'
        '  </td></tr>'
    )

    # ── DAILY TAKE ──
    take_section = ""
    if daily_take:
        t_headline = daily_take.get("headline", "")
        t_deck     = daily_take.get("deck", "")
        t_cat      = daily_take.get("category_label", "")
        t_url      = daily_take.get("hero_url", SITE_URL)
        take_eyebrow = _eyebrow("The Prob's Take &middot; " + t_cat)
        take_section = (
            '  <tr><td style="padding:20px 24px;background:#F8F9FA;border-bottom:1px solid rgba(11,14,20,.08);">\n'
            '    ' + take_eyebrow + '\n'
            "    <div style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
            'font-size:22px;font-weight:400;line-height:1.3;color:#0B0E14;margin-bottom:12px;">'
            '<a href="' + t_url + '" style="color:#0B0E14;text-decoration:none;">'
            + t_headline + '</a></div>\n'
            '    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
            'color:#4A5568;line-height:1.75;">' + t_deck + '</div>\n'
            '  </td></tr>'
        )

    # ── CTA ──
    cta_section = (
        '  <tr><td style="padding:28px 24px;background:#0077B6;text-align:center;">\n'
        "    <div style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
        'font-size:18px;font-style:italic;color:#ffffff;margin-bottom:16px;">'
        '"The crowd doesn\'t spin. <em>It bets.</em>"</div>\n'
        '    <a href="' + SITE_URL + '" style="display:inline-block;background:#ffffff;'
        "color:#0077B6;font-family:'Courier New',monospace;font-size:10px;font-weight:600;"
        'letter-spacing:0.12em;text-transform:uppercase;padding:12px 28px;'
        "text-decoration:none;border-radius:4px;\">See Today's Full Board &#8594;</a>\n"
        '  </td></tr>'
    )

    # ── FOOTER (full-HTML version only) ──
    footer_section = (
        '  <tr><td style="padding:20px 24px;background:#FFFFFF;border-top:1px solid #E8ECF0;text-align:center;">\n'
        '    <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="text-align:center;">\n'
        '      <table cellpadding="0" cellspacing="0" align="center" style="margin-bottom:8px;"><tr>\n'
        '        <td style="vertical-align:middle;">\n'
        '          <div style="width:20px;height:20px;background:#0077B6;border-radius:5px;'
        'text-align:center;line-height:20px;">\n'
        '            <span style="font-family:Georgia,serif;font-size:13px;font-weight:700;color:#fff;">%</span>\n'
        '          </div>\n'
        '        </td>\n'
        '        <td style="vertical-align:middle;padding-left:6px;">\n'
        "          <span style=\"font-family:'Instrument Serif',Georgia,'Times New Roman',serif;"
        'font-size:16px;color:#0B0E14;">The Prob</span>\n'
        '        </td>\n'
        '      </tr></table>\n'
        '      <div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;'
        'color:#718096;margin-bottom:8px;">Prediction market intelligence, daily.</div>\n'
        '      <div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;'
        'color:#718096;margin-bottom:10px;">Not financial advice. For informational purposes only.</div>\n'
        '      <div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;">\n'
        '        <a href="' + SITE_URL + '" style="color:#0077B6;text-decoration:none;">theprob.ai</a>\n'
        '        &nbsp;&middot;&nbsp;\n'
        '        <a href="' + SITE_URL + '/portfolio.html" style="color:#718096;text-decoration:none;">Portfolio</a>\n'
        '        &nbsp;&middot;&nbsp;\n'
        '        <a href="' + SITE_URL + '/prediction-markets-101.html" style="color:#718096;text-decoration:none;">Markets 101</a>\n'
        '      </div>\n'
        '      <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;'
        'color:#718096;margin-top:12px;">\n'
        '        <a href="mailto:newsletter@theprob.ai?subject=Unsubscribe" style="color:#718096;">Unsubscribe</a>\n'
        '        &nbsp;&middot;&nbsp;\n'
        '        <a href="' + SITE_URL + '" style="color:#718096;">View online</a>\n'
        '      </div>\n'
        '    </td></tr></table>\n'
        '  </td></tr>'
    )

    # ── ASSEMBLE ──
    builder_html = build_builder_section()
    spread_html   = build_spread_section(markets.get("the_spread", []), max_items=4)
    game5_html    = build_game5_section(markets.get("game5_props", []))

    # Re-skin spread section to Clean Book palette
    spread_html = (spread_html
        .replace("background:#07090E", "background:#FFFFFF")
        .replace("background:#07090E", "background:#F1F3F5")
        .replace("#141B2D", "#E8ECF0")
        .replace("color:#F8F9FA", "color:#0B0E14")
        .replace("color:#d0dde8", "color:#4A5568")
        .replace("color:#94A3B8", "color:#718096")
        .replace("color:#00e5a0", "color:#059669")
        .replace("color:#ff4757", "color:#E11D48")
        .replace("color:#f59e0b", "color:#F5A524")
    )

    sections = [
        header, hero_section, game5_html, trade_section, movers_section,
        spread_html, news_section, take_section,
        builder_html, cta_section,
    ]
    if with_footer:
        sections.append(footer_section)

    inner = "\n".join(s for s in sections if s)

    preheader = (
        '<!-- PREHEADER (hidden preview text) -->\n'
        '<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;'
        'color:#FBFCFD;line-height:1px;">' + subject
        + ('&nbsp;&#847;' * 30)
        + '</div>\n'
    )

    body_html = (
        preheader
        + '\n<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8F9FA;">\n'
        + '<tr><td align="center" style="padding:0;">\n'
        + '<table width="100%" cellpadding="0" cellspacing="0"'
        + ' style="max-width:600px;margin:0 auto;background:#F8F9FA;">\n\n'
        + inner
        + '\n\n</table>\n</td></tr>\n</table>'
    )

    if with_footer:
        # Full document for latest-email.html / iframe preview
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '<meta name="x-apple-disable-message-reformatting">\n'
            "<title>" + subject + "</title>\n"
            + build_head_styles()
            + "\n</head>\n"
            '<body style="margin:0;padding:0;background:#FBFCFD;">\n'
            + body_html
            + "\n</body>\n</html>"
        )
    else:
        # Body-only — paste directly into Beehiiv custom HTML block
        return body_html


# ── SAVE ─────────────────────────────────────────────────────────────────────

def build_preview_page(subject: str) -> str:
    """
    Wrapper HTML page for newsletter/latest.html.
    Shows the email in an iframe + a floating 'Copy Email HTML' button.
    Clicking Copy fetches latest-copy.html (no-footer version) and puts it
    on the clipboard, ready to paste directly into Beehiiv.
    Morning workflow: open URL → click Copy → paste into Beehiiv → Send.
    """
    subj_escaped = (subject
        .replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The Prob &mdash; Newsletter Preview</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #07090E; font-family: 'Courier New', monospace; }}
    #preview-bar {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
      background: #07090E; border-bottom: 2px solid #141B2D;
      padding: 10px 20px; display: flex; align-items: center;
      justify-content: space-between; gap: 12px;
    }}
    #subject-line {{
      font-size: 12px; color: #94A3B8; flex: 1; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap;
    }}
    #subject-label {{
      color: #64748B; margin-right: 8px; font-size: 10px;
      text-transform: uppercase; letter-spacing: 0.15em;
    }}
    #copy-btn {{
      background: #00e5a0; color: #07090E; border: none; padding: 9px 18px;
      font-family: 'Courier New', monospace; font-size: 12px; font-weight: 700;
      letter-spacing: 0.08em; text-transform: uppercase; cursor: pointer;
      white-space: nowrap; flex-shrink: 0; transition: opacity 0.15s;
    }}
    #copy-btn:hover {{ opacity: 0.85; }}
    #copy-btn:disabled {{ opacity: 0.6; cursor: default; }}
    #copy-feedback {{
      font-size: 11px; color: #00e5a0; white-space: nowrap;
      opacity: 0; transition: opacity 0.3s;
    }}
    #note {{
      font-size: 10px; color: #64748B; white-space: nowrap; flex-shrink: 0;
    }}
    #email-frame {{
      display: block; width: 100%; border: none;
      margin-top: 46px; height: calc(100vh - 46px);
    }}
  </style>
</head>
<body>
  <div id="preview-bar">
    <div id="subject-line">
      <span id="subject-label">Subject</span>{subj_escaped}
    </div>
    <span id="copy-feedback">Copied to clipboard!</span>
    <span id="note">no-footer version &rarr; paste into Beehiiv</span>
    <button id="copy-btn" onclick="copyHTML()">Copy Email HTML</button>
  </div>
  <iframe id="email-frame" src="latest-email.html" title="Newsletter Preview"
          onload="resizeFrame(this)"></iframe>
  <script>
    function resizeFrame(f) {{
      try {{ f.style.height = f.contentDocument.body.scrollHeight + 'px'; }}
      catch(e) {{}}
    }}
    function copyHTML() {{
      var btn = document.getElementById('copy-btn');
      var fb  = document.getElementById('copy-feedback');
      btn.disabled = true;
      btn.textContent = 'Fetching...';
      fetch('latest-copy.html?t=' + Date.now())
        .then(function(r) {{
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.text();
        }})
        .then(function(text) {{
          return navigator.clipboard.writeText(text);
        }})
        .then(function() {{
          btn.textContent = 'Copied!';
          btn.disabled = false;
          fb.style.opacity = '1';
          setTimeout(function() {{
            btn.textContent = 'Copy Email HTML';
            fb.style.opacity = '0';
          }}, 3000);
        }})
        .catch(function(err) {{
          btn.textContent = 'Error — retry';
          btn.disabled = false;
          console.error('Copy failed:', err);
          setTimeout(function() {{ btn.textContent = 'Copy Email HTML'; }}, 3000);
        }});
    }}
  </script>
</body>
</html>"""


def save_newsletter(subject: str, html_full: str, html_no_ftr: str, subtitle: str = "") -> bool:
    """
    Saves three newsletter files:
      latest.html       — preview wrapper page with Copy HTML button
      latest-email.html — full email HTML (with footer), shown in iframe preview
      latest-copy.html  — email HTML WITHOUT footer (paste this into Beehiiv)
      YYYY-MM-DD.html   — date-stamped archive (full)
      latest-subject.txt — subject + subtitle for reference
    """
    try:
        os.makedirs("newsletter", exist_ok=True)

        # Preview wrapper page (what you open in the browser)
        with open("newsletter/latest.html", "w") as f:
            f.write(build_preview_page(subject))

        # Full email (with footer) — shown in the iframe preview
        with open("newsletter/latest-email.html", "w") as f:
            f.write(html_full)

        # No-footer email — this is what Copy HTML puts on your clipboard
        with open("newsletter/latest-copy.html", "w") as f:
            f.write(html_no_ftr)

        # Date archive
        now_et    = datetime.now(timezone.utc) + timedelta(hours=-5)
        date_slug = now_et.strftime("%Y-%m-%d")
        archive   = f"newsletter/{date_slug}.html"
        with open(archive, "w") as f:
            f.write(html_full)

        # Subject file
        with open("newsletter/latest-subject.txt", "w") as f:
            f.write(f"SUBJECT: {subject}\n")
            f.write(f"SUBTITLE: {subtitle}\n")

        # Archive index — prepend today's entry so archive.html stays current
        index_path = "newsletter/index.json"
        try:
            with open(index_path) as f:
                index = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            index = []
        display_date = now_et.strftime("%b %-d, %Y")
        # Remove any existing entry for today (avoid duplicates on re-runs)
        index = [e for e in index if e.get("date") != date_slug]
        index.insert(0, {"date": date_slug, "display_date": display_date, "subject": subject})
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)

        print(f"  Preview: newsletter/latest.html")
        print(f"  Email:   newsletter/latest-email.html")
        print(f"  Copy:    newsletter/latest-copy.html  (no-footer — paste into Beehiiv)")
        print(f"  Archive: {archive}")
        print(f"  Index:   newsletter/index.json  ({len(index)} editions)")
        print(f"  Subject: newsletter/latest-subject.txt")
        return True
    except Exception as e:
        print(f"  [ERROR] Could not save newsletter: {e}")
        return False

# ── RESEND API ───────────────────────────────────────────────────────────────

def fetch_audience_contacts() -> list:
    """Fetch all subscribed contacts from the Resend audience."""
    if not RESEND_API_KEY or not RESEND_AUDIENCE_ID:
        return []
    contacts = []
    cursor = None
    while True:
        url = f"https://api.resend.com/audiences/{RESEND_AUDIENCE_ID}/contacts"
        if cursor:
            url += f"?cursor={cursor}"
        try:
            r = requests.get(url, headers={"Authorization": f"Bearer {RESEND_API_KEY}"}, timeout=15)
            r.raise_for_status()
            data = r.json()
            for c in data.get("data", []):
                if not c.get("unsubscribed", False):
                    contacts.append(c["email"])
            if data.get("has_more") and data.get("next"):
                cursor = data["next"]
            else:
                break
        except Exception as e:
            print(f"  [WARN] Could not fetch contacts: {e}")
            break
    return contacts


def send_via_resend(subject: str, html: str) -> bool:
    """Send the newsletter to all subscribed contacts in the Resend audience."""
    if not RESEND_API_KEY:
        print("  [INFO] RESEND_API_KEY not set — skipping send")
        return False
    if not RESEND_AUDIENCE_ID:
        print("  [INFO] RESEND_AUDIENCE_ID not set — skipping send")
        return False

    subscribers = fetch_audience_contacts()
    if not subscribers:
        print("  [INFO] No subscribers in audience — skipping send")
        return False

    print(f"  Sending to {len(subscribers)} subscribers via Resend...")
    sent = 0
    failed = 0
    for email in subscribers:
        try:
            r = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "from":    FROM_ADDRESS,
                    "to":      [email],
                    "subject": subject,
                    "html":    html,
                    "headers": {
                        "List-Unsubscribe": "<mailto:newsletter@theprob.ai?subject=Unsubscribe>",
                    },
                },
                timeout=30,
            )
            r.raise_for_status()
            sent += 1
        except Exception as e:
            print(f"  [WARN] Failed to send to {email}: {e}")
            failed += 1

    print(f"  ✓ Resend: {sent} sent, {failed} failed")
    return sent > 0


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    try:
        markets = load_json("data/markets.json")
        news    = load_json("data/news.json")
    except FileNotFoundError as e:
        print(f"  [ERROR] {e} — run fetch_markets.py and fetch_news.py first")
        return

    hero       = markets.get("hero", {})
    daily_take = markets.get("daily_take", {})

    if not hero:
        print("  [ERROR] No hero market in markets.json")
        return

    print(f"  Hero:    {hero.get('question','')[:60]}")
    print(f"  Movers:  {len(markets.get('movers', []))}")
    print(f"  News:    {len(news.get('articles', []))}")

    print("\nGenerating subject line and subtitle...")
    filtered_movers = [m for m in markets.get("movers", []) if abs(m.get("change_pts", 0)) >= 5][:5]
    subject  = generate_subject(hero, daily_take, movers=filtered_movers, articles=news.get("articles", [])[:3])
    subtitle = generate_subtitle(hero, markets.get("movers", []), daily_take)
    print(f"  Subject:  {subject}")
    print(f"  Subtitle: {subtitle}")

    print("\nBuilding newsletter HTML...")
    html_full   = build_html(markets, news, subject, with_footer=True)
    html_no_ftr = build_html(markets, news, subject, with_footer=False)
    print(f"  HTML:    {len(html_full):,} chars")

    print("\nSaving newsletter...")
    success = save_newsletter(subject, html_full, html_no_ftr, subtitle)

    print("\nSending via Resend...")
    sent = send_via_resend(subject, html_full)

    if success and sent:
        print("\n✓ Newsletter sent via Resend and saved to newsletter/latest.html")
    elif success:
        print("\n✓ Newsletter saved to newsletter/latest.html")
        print("  Resend not configured — email not sent")
    else:
        print("\n✗ Save failed")

if __name__ == "__main__":
    main()
