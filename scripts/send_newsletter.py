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
SITE_URL           = "https://theprobnewsletter.com"
OUTPUT_PATH        = "newsletter/latest.html"

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
    if prob >= 65:  return "#00e5a0"
    if prob <= 35:  return "#ff4757"
    return "#f5a623"

def arrow(change: float) -> str:
    if change > 0:  return "&#9650;"
    if change < 0:  return "&#9660;"
    return "&ndash;"

def change_color(change: float) -> str:
    if change > 0:  return "#00e5a0"
    if change < 0:  return "#ff4757"
    return "#8ba3bc"

def category_chip(cat: str) -> str:
    """Colored category pill for movers table."""
    color = CATEGORY_COLORS.get(cat, "#8ba3bc")
    return (
        f'<span style="display:inline-block;background:{color}22;'
        f'color:{color} !important;border:1px solid {color}55;'
        f'font-family:\'Courier New\',monospace;font-size:9px;'
        f'font-weight:700;letter-spacing:0.08em;padding:2px 6px;'
        f'text-transform:uppercase;border-radius:2px;margin-right:6px;">'
        f'{cat}</span>'
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

def generate_subject(hero: dict, daily_take: dict) -> str:
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

# ── GLOBAL STYLES (injected into <head>) ─────────────────────────────────────

def build_head_styles() -> str:
    """
    Media queries and resets that email clients respect.
    - Mobile: fluid width, larger text, reduced padding, stacked layouts
    - Dark mode: lock our palette so Apple Mail doesn't invert weirdly
    - Outlook: handled via MSO conditionals in the body
    """
    return """
<style type="text/css">
  /* ── Reset ── */
  body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
  table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
  img { -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }

  /* ── Dark mode: lock our palette ── */
  @media (prefers-color-scheme: dark) {
    body, .email-body { background-color: #080b0f !important; }
    .email-wrap { background-color: #080b0f !important; }
    .section-bg { background-color: #080b0f !important; }
    .alt-bg { background-color: #0d1117 !important; }
    /* Prevent Apple Mail from inverting our intentional dark design */
    [data-ogsc] .email-body { background-color: #080b0f !important; }
  }

  /* ── Mobile: max 600px screens ── */
  @media only screen and (max-width: 620px) {
    .email-wrap    { width: 100% !important; max-width: 100% !important; }
    .section-pad   { padding: 20px 16px !important; }
    .header-pad    { padding: 20px 16px 16px !important; }
    .footer-pad    { padding: 20px 16px !important; }

    /* Typography scale-up */
    .hero-title    { font-size: 22px !important; line-height: 1.35 !important; }
    .hero-prob     { font-size: 56px !important; }
    .hero-change   { font-size: 14px !important; }
    .body-text     { font-size: 16px !important; line-height: 1.8 !important; }
    .news-title    { font-size: 18px !important; }
    .take-headline { font-size: 20px !important; line-height: 1.3 !important; }
    .mover-q       { font-size: 15px !important; }
    .mover-prob    { font-size: 18px !important; }
    .eyebrow       { font-size: 11px !important; }
    .logo-text     { font-size: 24px !important; }
    .footer-text   { font-size: 12px !important; line-height: 2 !important; }
    .read-time     { font-size: 11px !important; }

    /* Stack hero stats vertically on mobile */
    .hero-stats-left  { display: block !important; width: 100% !important; padding-bottom: 12px !important; }
    .hero-stats-right { display: block !important; width: 100% !important; padding-left: 0 !important; }
    .hero-stats-table { display: block !important; width: 100% !important; }
    .hero-stats-row   { display: block !important; width: 100% !important; }

    /* Bigger tap targets */
    .cta-btn {
      display: block !important;
      text-align: center !important;
      padding: 16px 24px !important;
      font-size: 14px !important;
    }
    .cta-small {
      font-size: 13px !important;
      padding: 10px 0 !important;
      display: inline-block !important;
    }

    /* Movers: more row padding */
    .mover-row td  { padding-top: 14px !important; padding-bottom: 14px !important; }
    .mover-num     { display: none !important; }

    /* Hide movers 4 and 5 on mobile — show 3 + "see all" link */
    .mover-hide-mobile { display: none !important; }

    /* Section divider accent */
    .section-accent { height: 3px !important; }
  }

  /* ── Tap highlight remove ── */
  a { -webkit-tap-highlight-color: transparent; }

  /* ── Link color lock ── */
  a[x-apple-data-detectors] {
    color: inherit !important;
    text-decoration: none !important;
  }
</style>"""

# ── HTML BUILDER ──────────────────────────────────────────────────────────────

def build_html(markets: dict, news: dict, subject: str) -> str:
    hero       = markets.get("hero", {})
    movers     = markets.get("movers", [])[:5]
    daily_take = markets.get("daily_take", {})
    articles   = news.get("articles", [])[:3]
    updated    = markets.get("updated", "")

    now_et    = datetime.now(timezone.utc) + timedelta(hours=-5)
    date_str  = now_et.strftime("%B %-d, %Y")
    read_time = estimate_read_time(markets, news)

    # ── Hero data ──
    hero_prob   = hero.get("prob", 50)
    hero_change = hero.get("change_pts", 0)
    hero_q      = hero.get("question", "")
    hero_vol    = hero.get("volume_fmt", "")
    hero_source = hero.get("source", "")
    hero_url    = hero.get("url", SITE_URL)
    hero_take   = hero.get("prob_take", "")
    hero_end    = hero.get("end_date", "")
    prob_color  = color_prob(hero_prob)

    # ── HEADER ──
    header_html = f"""
  <tr><td class="header-pad" style="background:#080b0f !important;padding:28px 32px 20px;border-bottom:2px solid #1e2a38;">
    <!--[if mso]><table width="100%"><tr><td><![endif]-->
    <a href="{SITE_URL}" class="logo-text" title="The Prob — Prediction Markets Intelligence"
       style="font-family:'Courier New',monospace;font-size:22px;font-weight:700;color:#00e5a0 !important;letter-spacing:-0.5px;text-decoration:none;display:block;margin-bottom:8px;">THE PROB</a>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="vertical-align:middle;">
          <div class="read-time" style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;letter-spacing:0.15em;text-transform:uppercase;">{date_str} &middot; Prediction Markets Intelligence</div>
        </td>
        <td style="vertical-align:middle;text-align:right;">
          <div class="read-time" style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;letter-spacing:0.1em;text-transform:uppercase;">{read_time}</div>
        </td>
      </tr>
    </table>
    <!--[if mso]></td></tr></table><![endif]-->
  </td></tr>"""

    # ── HERO SECTION ──
    # Mobile: stats stack vertically via @media classes
    hero_html = f"""
  <tr><td class="section-pad" style="padding:28px 32px;border-bottom:1px solid #1e2a38;">
    <div class="eyebrow" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#00e5a0 !important;margin-bottom:14px;">
      Market of the Day &middot; {hero_source}
    </div>
    <div class="hero-title" style="font-family:Georgia,serif;font-size:26px;font-weight:700;line-height:1.3;color:#edf2f7 !important;margin:0 0 20px;">
      <a href="{hero_url}" title="{hero_q}" style="color:#edf2f7 !important;text-decoration:none;">{hero_q}</a>
    </div>

    <!--[if mso]><table width="100%"><tr><td width="40%" valign="top"><![endif]-->
    <table class="hero-stats-table" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
      <tr class="hero-stats-row">
        <td class="hero-stats-left" width="40%" style="vertical-align:top;padding-bottom:0;">
          <div class="hero-prob" style="font-family:'Courier New',monospace;font-size:56px;font-weight:700;color:{prob_color} !important;line-height:1;">{hero_prob}<span style="font-size:26px;color:{prob_color} !important;">%</span></div>
          <div class="hero-change" style="font-family:'Courier New',monospace;font-size:13px;color:{change_color(hero_change)} !important;margin-top:6px;font-weight:700;">{arrow(hero_change)} {'+' if hero_change > 0 else ''}{hero_change} pts today</div>
        </td>
        <!--[if mso]></td><td width="60%" valign="top" style="padding-left:20px;"><![endif]-->
        <td class="hero-stats-right" width="60%" style="vertical-align:top;padding-left:20px;">
          <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:3px;">VOLUME</div>
          <div style="font-family:'Courier New',monospace;font-size:16px;color:#edf2f7 !important;font-weight:700;margin-bottom:12px;">{hero_vol}</div>
          <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:3px;">RESOLVES</div>
          <div style="font-family:'Courier New',monospace;font-size:16px;color:#edf2f7 !important;font-weight:700;">{hero_end or 'TBD'}</div>
        </td>
      </tr>
    </table>
    <!--[if mso]></td></tr></table><![endif]-->

    {f'''<p class="body-text" style="font-size:15px;color:#d0dde8 !important;line-height:1.75;margin:0 0 20px;font-style:italic;border-left:3px solid #00e5a0;padding-left:16px;">{hero_take}</p>''' if hero_take else ''}

    <!--[if mso]><table><tr><td><![endif]-->
    <a href="{hero_url}" class="cta-btn" title="View this market on {hero_source}"
       style="display:inline-block;background:#00e5a0;color:#080b0f !important;font-family:'Courier New',monospace;font-size:13px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;padding:14px 32px;text-decoration:none;min-height:44px;line-height:1.2;">
      View Market &#8594;
    </a>
    <!--[if mso]></td></tr></table><![endif]-->
  </td></tr>"""

    # ── MOVERS SECTION ──
    movers_rows = ""
    for i, m in enumerate(movers):
        bg       = "#0d1117" if i % 2 == 0 else "#080b0f"
        p        = m.get("prob", 50)
        c        = m.get("change_pts", 0)
        cat      = m.get("display_category", "")
        chip     = category_chip(cat)
        # Hide rows 4+5 on mobile (shown via "see all" link)
        hide_cls = ' class="mover-hide-mobile"' if i >= 3 else ' class="mover-row"'

        movers_rows += f"""
        <tr{hide_cls} style="background:{bg};">
          <td class="mover-num" style="padding:12px 14px;font-family:'Courier New',monospace;font-size:11px;width:28px;color:#546e85 !important;vertical-align:top;">{str(i+1).zfill(2)}</td>
          <td style="padding:12px 10px 12px 14px;vertical-align:top;">
            <a href="{m.get('url', SITE_URL)}" class="mover-q" title="{m.get('question','')}"
               style="font-size:14px;color:#edf2f7 !important;text-decoration:none;line-height:1.45;display:block;margin-bottom:6px;">{m.get('question','')}</a>
            <div>{chip}<span style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;">{m.get('source','')}</span></div>
          </td>
          <td style="padding:12px 14px 12px 8px;text-align:right;white-space:nowrap;vertical-align:top;min-width:72px;">
            <div class="mover-prob" style="font-family:'Courier New',monospace;font-size:17px;font-weight:700;color:{color_prob(p)} !important;">{p}%</div>
            <div style="font-family:'Courier New',monospace;font-size:11px;color:{change_color(c)} !important;margin-top:3px;">{arrow(c)} {abs(c)} pts</div>
          </td>
        </tr>"""

    # "See all movers" row — visible on mobile when rows 4+5 are hidden
    movers_html = f"""
  <tr><td class="section-pad" style="padding:28px 32px;border-bottom:1px solid #1e2a38;">
    <div class="eyebrow" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#00e5a0 !important;margin-bottom:14px;">Today's Movers</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2a38;border-radius:2px;">
      {movers_rows}
    </table>
    <div style="margin-top:14px;">
      <a href="{SITE_URL}" class="cta-small" title="See all markets on The Prob"
         style="font-family:'Courier New',monospace;font-size:11px;color:#00e5a0 !important;text-decoration:none;letter-spacing:0.1em;text-transform:uppercase;">
        See all {len(movers)} movers &#8594;
      </a>
    </div>
  </td></tr>"""

    # ── NEWS SECTION ──
    news_items = ""
    for i, a in enumerate(articles):
        num      = str(i + 1).zfill(2)
        title    = a.get("title", "")
        summary  = truncate_summary(a.get("summary", ""))  # capped at 2 sentences
        source   = a.get("source", "")
        pub_date = a.get("pub_display", "")
        url      = a.get("url", SITE_URL)
        border   = "border-bottom:1px solid #1e2a38;" if i < len(articles) - 1 else ""

        news_items += f"""
        <tr><td style="padding:16px 0;{border}">
          <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;margin-bottom:8px;letter-spacing:0.08em;">{num} &nbsp; {source.upper()} &middot; {pub_date}</div>
          <div class="news-title" style="font-family:Georgia,serif;font-size:17px;font-weight:700;color:#edf2f7 !important;margin:0 0 8px;line-height:1.35;">
            <a href="{url}" title="{title}" style="color:#edf2f7 !important;text-decoration:none;">{title}</a>
          </div>
          {f'<p class="body-text" style="font-size:14px;color:#d0dde8 !important;line-height:1.7;margin:0;">{summary}</p>' if summary else ''}
        </td></tr>"""

    news_html = f"""
  <tr><td class="section-pad" style="padding:28px 32px;border-bottom:1px solid #1e2a38;">
    <div class="eyebrow" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#00e5a0 !important;margin-bottom:14px;">What People Are Writing About</div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {news_items}
    </table>
    <div style="margin-top:16px;">
      <a href="{SITE_URL}/news.html" class="cta-small" title="All prediction market news"
         style="font-family:'Courier New',monospace;font-size:11px;color:#00e5a0 !important;text-decoration:none;letter-spacing:0.1em;text-transform:uppercase;">
        All Prediction Market News &#8594;
      </a>
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
            label_html = (
                f'<div style="font-family:\'Courier New\',monospace;font-size:12px;'
                f'color:#00e5a0 !important;margin-top:5px;font-weight:700;">'
                f'{item.get("label","")}</div>'
            ) if item.get("label") else ""
            item_url  = item.get("url", SITE_URL)
            border    = "border-bottom:1px solid #1e2a38;" if i < 2 else ""
            sidebar_rows += f"""
            <tr><td style="padding:14px 0;{border}">
              <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;margin-bottom:5px;letter-spacing:0.08em;">0{i+1}</div>
              <div style="font-size:14px;color:#edf2f7 !important;line-height:1.5;">
                <a href="{item_url}" style="color:#edf2f7 !important;text-decoration:none;">{item.get('headline','')}</a>
              </div>
              {label_html}
            </td></tr>"""

        # Inline share link for the take
        share_text = f"Today on The Prob: {take_headline}"
        share_url  = f"https://twitter.com/intent/tweet?text={requests.utils.quote(share_text)}&url={SITE_URL}"

        take_html = f"""
  <tr><td class="section-pad" style="padding:28px 32px;border-bottom:1px solid #1e2a38;background:#0a0e14 !important;">
    <div class="eyebrow" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#00e5a0 !important;margin-bottom:14px;">The Prob's Daily Take &middot; {take_cat}</div>
    <div class="take-headline" style="font-family:Georgia,serif;font-size:22px;font-weight:700;line-height:1.3;color:#edf2f7 !important;margin:0 0 14px;">
      <a href="{take_url}" style="color:#edf2f7 !important;text-decoration:none;">{take_headline}</a>
    </div>
    <p class="body-text" style="font-size:15px;color:#d0dde8 !important;line-height:1.8;margin:0 0 20px;">{take_deck}</p>
    {f'<table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1e2a38;margin-bottom:20px;">{sidebar_rows}</table>' if sidebar_rows else ''}
    <a href="{share_url}" title="Share this take on Twitter/X"
       style="font-family:'Courier New',monospace;font-size:11px;color:#00e5a0 !important;text-decoration:none;letter-spacing:0.1em;text-transform:uppercase;">
      Share This Take &#8594;
    </a>
  </td></tr>"""

    # ── CTA ──
    cta_html = f"""
  <tr><td style="padding:36px 32px;text-align:center;background:#0d1117 !important;">
    <div style="font-family:'Courier New',monospace;font-size:11px;color:#546e85 !important;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:16px;">The full board is live</div>
    <!--[if mso]><table align="center"><tr><td><![endif]-->
    <a href="{SITE_URL}" class="cta-btn" title="See all markets on The Prob"
       style="display:inline-block;background:#00e5a0;color:#080b0f !important;font-family:'Courier New',monospace;font-size:13px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;padding:16px 40px;text-decoration:none;min-height:44px;line-height:1.2;">
      See All Markets &#8594;
    </a>
    <!--[if mso]></td></tr></table><![endif]-->
    <div style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;margin-top:16px;">Updated {updated}</div>
  </td></tr>"""

    # ── FOOTER ──
    # Includes: reply CTA, unsubscribe in body, plain text friendly
    footer_html = f"""
  <tr><td class="footer-pad" style="padding:28px 32px;text-align:center;border-top:1px solid #1e2a38;">
    <p class="footer-text" style="font-family:'Courier New',monospace;font-size:11px;color:#8ba3bc !important;line-height:2;margin:0 0 16px;">
      Got a take? Hit reply. We read every one.
    </p>
    <p class="footer-text" style="font-family:'Courier New',monospace;font-size:10px;color:#546e85 !important;line-height:2;margin:0;">
      The Prob &middot; Prediction Markets Intelligence<br>
      <a href="{SITE_URL}" title="The Prob Newsletter" style="color:#546e85 !important;text-decoration:none;">{SITE_URL}</a><br><br>
      Not financial advice. For informational purposes only.<br>
      <a href="{{{{unsubscribe_url}}}}" title="Unsubscribe from The Prob" style="color:#8ba3bc !important;">Unsubscribe</a>
      &nbsp;&middot;&nbsp;
      <a href="{SITE_URL}" title="View online" style="color:#8ba3bc !important;">View online</a>
    </p>
  </td></tr>"""

    # ── ASSEMBLE ──
    html = f"""<!DOCTYPE html>
<html lang="en" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="dark">
<meta name="supported-color-schemes" content="dark">
<!--[if !mso]><!-->
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<!--<![endif]-->
<!--[if mso]>
<xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
<![endif]-->
<title>{subject}</title>
{build_head_styles()}
</head>
<body class="email-body" style="margin:0;padding:0;background:#080b0f !important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">

<!-- Outlook wrapper -->
<!--[if mso]>
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#080b0f"><tr><td align="center">
<![endif]-->

<table width="100%" cellpadding="0" cellspacing="0" style="background:#080b0f !important;min-width:320px;">
<tr><td align="center" style="padding:0;">

  <!-- Main container: fluid on mobile, max 600px on desktop -->
  <table class="email-wrap" width="600" cellpadding="0" cellspacing="0"
         style="max-width:600px;width:100%;margin:0 auto;background:#080b0f !important;">

    {header_html}
    {hero_html}
    {movers_html}
    {news_html}
    {take_html}
    {cta_html}
    {footer_html}

  </table>

</td></tr>
</table>

<!--[if mso]>
</td></tr></table>
<![endif]-->

</body>
</html>"""

    return html

# ── SAVE ─────────────────────────────────────────────────────────────────────

def save_newsletter(subject: str, html: str) -> bool:
    try:
        os.makedirs("newsletter", exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            f.write(html)

        now_et    = datetime.now(timezone.utc) + timedelta(hours=-5)
        date_slug = now_et.strftime("%Y-%m-%d")
        archive   = f"newsletter/{date_slug}.html"
        with open(archive, "w") as f:
            f.write(html)

        subtitle = f"The crowd's read on {now_et.strftime('%B %-d')} — markets, movers, and what it means."
        with open("newsletter/latest-subject.txt", "w") as f:
            f.write(f"SUBJECT: {subject}\n")
            f.write(f"SUBTITLE: {subtitle}\n")

        print(f"  Saved:   {OUTPUT_PATH}")
        print(f"  Archive: {archive}")
        print(f"  Subject: newsletter/latest-subject.txt")
        return True
    except Exception as e:
        print(f"  [ERROR] Could not save newsletter: {e}")
        return False

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

    print("\nGenerating subject line...")
    subject = generate_subject(hero, daily_take)
    print(f"  Subject: {subject}")

    print("\nBuilding newsletter HTML...")
    html = build_html(markets, news, subject)
    print(f"  HTML:    {len(html):,} chars")

    print("\nSaving newsletter...")
    success = save_newsletter(subject, html)

    if success:
        print("\n✓ Newsletter ready — open newsletter/latest.html")
        print("  Paste into Beehiiv and send!")
    else:
        print("\n✗ Save failed")

if __name__ == "__main__":
    main()
