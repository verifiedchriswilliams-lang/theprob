#!/usr/bin/env python3
"""
send_newsletter.py
Builds and sends The Prob daily newsletter via Beehiiv API.
Reads data/markets.json and data/news.json.
Runs once daily at 7AM ET via GitHub Actions.

Structure:
  1. Subject line (Claude-generated)
  2. Hero market + The Prob's Take
  3. Top 5 movers
  4. Top 3 news stories
  5. The Prob's Daily Take (editorial)
  6. CTA to site
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ── CONFIG ────────────────────────────────────────────────────────────────────

BEEHIIV_API_KEY    = os.environ.get("BEEHIIV_API_KEY", "")
BEEHIIV_PUB_ID     = os.environ.get("BEEHIIV_PUB_ID", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL       = "claude-haiku-4-5-20251001"
SITE_URL           = "https://theprobnewsletter.com"

HOUSE_STYLE_SYSTEM = (
    "You write for The Prob, a prediction markets newsletter. "
    "Voice: sharp, confident, dry wit, slightly irreverent. Like The Hustle. "
    "Intelligent but not academic. Opinionated but not arrogant. "
    "NEVER use em dashes. Use a comma or start a new sentence instead. "
    "Short sentences. Active voice. Numbers as numerals ($2M, 47%). "
    "No hedging. No fluff. No filler. "
    "Undetectable as AI. Write like a smart human who finds this genuinely interesting."
)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

# ── CLAUDE HELPERS ────────────────────────────────────────────────────────────

def claude(prompt: str, max_tokens: int = 200) -> str:
    """Call Claude API and return text response."""
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

def generate_subject(hero: dict, daily_take: dict) -> str:
    """Generate a punchy email subject line from the hero market."""
    q      = hero.get("question", "")
    prob   = hero.get("prob", 50)
    change = hero.get("change_pts", 0)
    take_headline = daily_take.get("headline", "") if daily_take else ""

    prompt = (
        f"Today's top prediction market: {q}\n"
        f"Current odds: {prob}%\n"
        f"24h change: {'+' if change > 0 else ''}{change} points\n"
        f"Editorial headline: {take_headline}\n\n"
        "Write ONE email subject line for The Prob newsletter. "
        "Max 60 characters. Make it feel urgent and specific. "
        "Include the odds or the move if it fits naturally. "
        "No em dashes. No quotes. No 'The Prob:' prefix. Just the subject line."
    )
    subject = claude(prompt, max_tokens=60)
    if not subject:
        direction = "up" if change > 0 else "down"
        subject = f"The crowd moved {abs(change)} pts {direction} on this one"
    return subject


# ── HTML BUILDERS ─────────────────────────────────────────────────────────────

def color_prob(prob: float) -> str:
    """Return color hex for a probability value."""
    if prob >= 65:   return "#00e5a0"   # green
    if prob <= 35:   return "#ff4757"   # red
    return "#f5a623"                    # amber

def arrow(change: float) -> str:
    if change > 0:  return "▲"
    if change < 0:  return "▼"
    return "–"

def change_color(change: float) -> str:
    if change > 0:  return "#00e5a0"
    if change < 0:  return "#ff4757"
    return "#8ba3bc"

def build_html(markets: dict, news: dict, subject: str) -> str:
    hero       = markets.get("hero", {})
    movers     = markets.get("movers", [])[:5]
    daily_take = markets.get("daily_take", {})
    articles   = news.get("articles", [])[:3]
    updated    = markets.get("updated", "")

    now_et     = datetime.now(timezone.utc) + timedelta(hours=-5)
    date_str   = now_et.strftime("%B %-d, %Y")

    # ── STYLES (inline for email client compatibility) ──
    S = {
        "body":        "margin:0;padding:0;background:#080b0f;font-family:'DM Sans',Arial,sans-serif;",
        "wrap":        "max-width:600px;margin:0 auto;background:#080b0f;",
        "header":      "background:#080b0f;padding:28px 32px 20px;border-bottom:1px solid #1e2a38;",
        "logo":        "font-family:'Courier New',monospace;font-size:22px;font-weight:700;color:#00e5a0;letter-spacing:-0.5px;text-decoration:none;",
        "date_line":   "font-family:'Courier New',monospace;font-size:10px;color:#546e85;letter-spacing:0.15em;text-transform:uppercase;margin-top:6px;",
        "section":     "padding:28px 32px;border-bottom:1px solid #1e2a38;",
        "eyebrow":     "font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#00e5a0;margin-bottom:12px;",
        "h1":          "font-family:Georgia,serif;font-size:26px;font-weight:700;line-height:1.2;color:#edf2f7;margin:0 0 14px;",
        "h2":          "font-family:Georgia,serif;font-size:20px;font-weight:700;line-height:1.25;color:#edf2f7;margin:0 0 10px;",
        "h3":          "font-family:Georgia,serif;font-size:16px;font-weight:700;color:#edf2f7;margin:0 0 6px;",
        "body_text":   "font-size:15px;color:#8ba3bc;line-height:1.65;margin:0 0 16px;",
        "small_text":  "font-family:'Courier New',monospace;font-size:10px;color:#546e85;letter-spacing:0.08em;",
        "cta_btn":     "display:inline-block;background:#00e5a0;color:#080b0f;font-family:'Courier New',monospace;font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;padding:12px 28px;text-decoration:none;",
        "divider":     "height:1px;background:#1e2a38;margin:0;border:none;",
        "footer":      "padding:24px 32px;text-align:center;",
        "footer_text": "font-family:'Courier New',monospace;font-size:10px;color:#546e85;line-height:1.8;",
    }

    # ── HERO SECTION ──
    hero_prob    = hero.get("prob", 50)
    hero_change  = hero.get("change_pts", 0)
    hero_q       = hero.get("question", "")
    hero_vol     = hero.get("volume_fmt", "")
    hero_source  = hero.get("source", "")
    hero_url     = hero.get("url", SITE_URL)
    hero_take    = hero.get("prob_take", "")
    hero_end     = hero.get("end_date", "")
    prob_color   = color_prob(hero_prob)

    hero_html = f"""
    <tr><td style="{S['section']}">
      <div style="{S['eyebrow']}">Market of the Day &middot; {hero_source}</div>
      <h1 style="{S['h1']}"><a href="{hero_url}" style="color:#edf2f7;text-decoration:none;">{hero_q}</a></h1>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">
        <tr>
          <td style="width:40%;vertical-align:top;">
            <div style="font-family:'Courier New',monospace;font-size:48px;font-weight:700;color:{prob_color};line-height:1;">{hero_prob}<span style="font-size:24px;">%</span></div>
            <div style="font-family:'Courier New',monospace;font-size:12px;color:{change_color(hero_change)};margin-top:4px;">{arrow(hero_change)} {'+' if hero_change > 0 else ''}{hero_change} pts today</div>
          </td>
          <td style="width:60%;vertical-align:top;padding-left:20px;">
            <div style="{S['small_text']}">VOLUME</div>
            <div style="font-family:'Courier New',monospace;font-size:14px;color:#edf2f7;margin-bottom:8px;">${hero_vol}</div>
            <div style="{S['small_text']}">RESOLVES</div>
            <div style="font-family:'Courier New',monospace;font-size:14px;color:#edf2f7;">{hero_end or 'TBD'}</div>
          </td>
        </tr>
      </table>
      {f'<p style="{S["body_text"]};font-style:italic;border-left:3px solid #00e5a0;padding-left:14px;color:#8ba3bc;">{hero_take}</p>' if hero_take else ''}
      <a href="{hero_url}" style="{S['cta_btn']}">View Market &rarr;</a>
    </td></tr>"""

    # ── MOVERS SECTION ──
    movers_rows = ""
    for i, m in enumerate(movers):
        bg = "#0d1117" if i % 2 == 0 else "#080b0f"
        p  = m.get("prob", 50)
        c  = m.get("change_pts", 0)
        movers_rows += f"""
        <tr style="background:{bg};">
          <td style="padding:12px 16px;font-size:13px;color:#edf2f7;font-family:'Courier New',monospace;width:24px;color:#546e85;">{str(i+1).zfill(2)}</td>
          <td style="padding:12px 8px;">
            <a href="{m.get('url', SITE_URL)}" style="font-size:13px;color:#edf2f7;text-decoration:none;line-height:1.4;">{m.get('question','')}</a>
            <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85;margin-top:3px;">{m.get('display_category','').upper()} &middot; {m.get('source','')}</div>
          </td>
          <td style="padding:12px 16px;text-align:right;white-space:nowrap;vertical-align:top;">
            <div style="font-family:'Courier New',monospace;font-size:16px;font-weight:700;color:{color_prob(p)};">{p}%</div>
            <div style="font-family:'Courier New',monospace;font-size:11px;color:{change_color(c)};">{arrow(c)} {abs(c)} pts</div>
          </td>
        </tr>"""

    movers_html = f"""
    <tr><td style="{S['section']}">
      <div style="{S['eyebrow']}">Today's Movers</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2a38;">
        {movers_rows}
      </table>
    </td></tr>"""

    # ── NEWS SECTION ──
    news_items = ""
    for i, a in enumerate(articles):
        num      = str(i + 1).zfill(2)
        title    = a.get("title", "")
        summary  = a.get("summary", "")
        source   = a.get("source", "")
        pub_date = a.get("pub_display", "")
        url      = a.get("url", SITE_URL)
        news_items += f"""
        <tr><td style="padding:16px 0;border-bottom:1px solid #1e2a38;">
          <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85;margin-bottom:6px;">{num} &nbsp; {source.upper()} &middot; {pub_date}</div>
          <h3 style="{S['h3']}"><a href="{url}" style="color:#edf2f7;text-decoration:none;">{title}</a></h3>
          {f'<p style="font-size:13px;color:#8ba3bc;line-height:1.6;margin:6px 0 0;">{summary}</p>' if summary else ''}
        </td></tr>"""

    news_html = f"""
    <tr><td style="{S['section']}">
      <div style="{S['eyebrow']}">What People Are Writing About</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        {news_items}
      </table>
      <div style="margin-top:16px;">
        <a href="{SITE_URL}/news.html" style="font-family:'Courier New',monospace;font-size:11px;color:#00e5a0;text-decoration:none;letter-spacing:0.1em;text-transform:uppercase;">All Prediction Market News &rarr;</a>
      </div>
    </td></tr>"""

    # ── DAILY TAKE SECTION ──
    take_html = ""
    if daily_take:
        take_headline = daily_take.get("headline", "")
        take_deck     = daily_take.get("deck", "")
        take_cat      = daily_take.get("category_label", "")
        take_url      = daily_take.get("hero_url", SITE_URL)
        sidebar       = daily_take.get("sidebar", [])

        sidebar_rows = ""
        for i, item in enumerate(sidebar[:3]):
            sidebar_rows += f"""
            <tr><td style="padding:12px 0;border-bottom:1px solid #1e2a38;">
              <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85;margin-bottom:4px;">0{i+1}</div>
              <div style="font-size:13px;color:#edf2f7;line-height:1.4;">{item.get('headline','')}</div>
              {f'<div style="font-family:\'Courier New\',monospace;font-size:11px;color:#00e5a0;margin-top:4px;">{item.get("label","")}</div>' if item.get('label') else ''}
            </td></tr>"""

        take_html = f"""
    <tr><td style="{S['section']}">
      <div style="{S['eyebrow']}">The Prob's Daily Take &middot; {take_cat}</div>
      <h2 style="{S['h2']}"><a href="{take_url}" style="color:#edf2f7;text-decoration:none;">{take_headline}</a></h2>
      <p style="{S['body_text']}">{take_deck}</p>
      {f'<table width="100%" cellpadding="0" cellspacing="0">{sidebar_rows}</table>' if sidebar_rows else ''}
    </td></tr>"""

    # ── CTA SECTION ──
    cta_html = f"""
    <tr><td style="padding:32px;text-align:center;background:#0d1117;">
      <div style="font-family:'Courier New',monospace;font-size:11px;color:#546e85;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:12px;">The full board is live</div>
      <a href="{SITE_URL}" style="{S['cta_btn']}">See All Markets &rarr;</a>
      <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85;margin-top:16px;">Updated {updated}</div>
    </td></tr>"""

    # ── FOOTER ──
    footer_html = f"""
    <tr><td style="{S['footer']}">
      <p style="{S['footer_text']}">
        The Prob &middot; Prediction Markets Intelligence<br>
        <a href="{SITE_URL}" style="color:#546e85;">{SITE_URL}</a><br><br>
        Not financial advice. For informational purposes only.<br>
        <a href="{{{{unsubscribe_url}}}}" style="color:#546e85;">Unsubscribe</a>
      </p>
    </td></tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
</head>
<body style="{S['body']}">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#080b0f;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="{S['wrap']}">

  <!-- HEADER -->
  <tr><td style="{S['header']}">
    <a href="{SITE_URL}" style="{S['logo']}">THE PROB</a>
    <div style="{S['date_line']}">{date_str} &middot; Prediction Markets Intelligence</div>
  </td></tr>

  {hero_html}
  {movers_html}
  {news_html}
  {take_html}
  {cta_html}
  {footer_html}

</table>
</td></tr>
</table>
</body>
</html>"""

    return html


# ── BEEHIIV API ───────────────────────────────────────────────────────────────

def send_to_beehiiv(subject: str, html: str) -> bool:
    """Create and send a Beehiiv post via API."""
    if not BEEHIIV_API_KEY or not BEEHIIV_PUB_ID:
        print("  [ERROR] BEEHIIV_API_KEY or BEEHIIV_PUB_ID not set")
        return False

    now_et   = datetime.now(timezone.utc) + timedelta(hours=-5)
    subtitle = f"The crowd's read on {now_et.strftime('%B %-d')} — markets, movers, and what it means."

    payload = {
        "publication_id": BEEHIIV_PUB_ID,
        "subject_line":   subject,
        "subtitle":       subtitle,
        "status":         "confirmed",   # send immediately
        "send_at":        None,          # send now
        "content_blocks": [
            {
                "type":    "raw_html",
                "content": html,
            }
        ],
        "audience":       "free",        # send to all free + paid subscribers
        "email_enabled":  True,
        "web_enabled":    True,
    }

    try:
        r = requests.post(
            f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/posts",
            headers={
                "Authorization": f"Bearer {BEEHIIV_API_KEY}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=30,
        )
        if r.ok:
            data    = r.json()
            post_id = data.get("data", {}).get("id", "unknown")
            print(f"  Post created: {post_id}")
            return True
        else:
            print(f"  [ERROR] Beehiiv API {r.status_code}: {r.text[:300]}")
            return False
    except Exception as e:
        print(f"  [ERROR] Beehiiv request failed: {e}")
        return False


# ── MAIN ──────────────────────────────────────────────────────────────────────

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

    print(f"  Hero: {hero.get('question','')[:60]}")
    print(f"  Movers: {len(markets.get('movers', []))}")
    print(f"  News articles: {len(news.get('articles', []))}")

    print("\nGenerating subject line...")
    subject = generate_subject(hero, daily_take)
    print(f"  Subject: {subject}")

    print("\nBuilding newsletter HTML...")
    html = build_html(markets, news, subject)
    print(f"  HTML length: {len(html):,} chars")

    print("\nSending to Beehiiv...")
    success = send_to_beehiiv(subject, html)

    if success:
        print("\n✓ Newsletter sent successfully")
    else:
        print("\n✗ Newsletter send failed")

if __name__ == "__main__":
    main()
