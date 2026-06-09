#!/usr/bin/env python3
"""
send_sunday5.py
Builds The Prob's Sunday 5 newsletter — a weekly editorial on the biggest
stories IN the prediction markets space (not the markets themselves).

Format per story:
  - Headline
  - 2-sentence summary in The Prob voice
  - 3 bullets: what you need to know
  - The Prob's Take

Reads: data/sunday5_stories.json  (manually curated each Sunday)
Writes: newsletter/latest.html, latest-email.html, latest-copy.html,
        newsletter/YYYY-MM-DD.html, newsletter/index.json

Run manually each Sunday morning:
  python scripts/send_sunday5.py
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ── CONFIG ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-haiku-4-5-20251001"
SITE_URL          = "https://theprob.ai"

# Chris's headshot — commit this file to the repo, then update this URL.
# File should be committed to: images/chris-williams.jpg (square, min 200x200)
CHRIS_PHOTO_URL = f"{SITE_URL}/images/chris-williams.jpg"

HOUSE_STYLE_SYSTEM = (
    "You write for The Prob, a prediction markets newsletter. "
    "Voice: sharp, confident, dry wit, slightly irreverent. Like The Hustle meets a trading desk. "
    "Intelligent but not academic. Opinionated but not arrogant. "
    "NEVER use em dashes. Use a comma or start a new sentence instead. "
    "Short sentences. Active voice. Numbers as numerals ($2M, 47%). "
    "No hedging. No fluff. No filler. "
    "Undetectable as AI. Write like a sharp human who finds this genuinely interesting."
)

# ── CLAUDE API ────────────────────────────────────────────────────────────────

def claude(prompt: str, max_tokens: int = 300) -> str:
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
            timeout=30,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        # Hard-strip em dashes just in case
        return text.replace("\u2014", ",").replace(" -- ", ", ")
    except Exception as e:
        print(f"  [WARN] Claude call failed: {e}")
        return ""

# ── COPY GENERATION ───────────────────────────────────────────────────────────

def generate_story_copy(story: dict) -> dict:
    """
    For a given story dict, call Claude to produce:
      - summary: 2-sentence Prob-voice summary
      - bullets: list of 3 sharp bullet strings
      - take: The Prob's Take (2 sentences max)
    Falls back to raw_summary if Claude unavailable.
    """
    headline    = story.get("headline", "")
    raw         = story.get("raw_summary", "")
    source      = story.get("source", "")

    # Summary
    summary_prompt = (
        f"Source: {source}\n"
        f"Headline: {headline}\n"
        f"Background: {raw}\n\n"
        "Write a 2-sentence summary for The Prob newsletter. "
        "Sentence 1: what happened. Sentence 2: why it matters for prediction market readers. "
        "No em dashes. No hedging. Under 50 words total. Just the two sentences, nothing else."
    )
    summary = claude(summary_prompt, max_tokens=120) or raw

    # Bullets
    bullets_prompt = (
        f"Headline: {headline}\n"
        f"Background: {raw}\n\n"
        "Write exactly 3 bullet points for a prediction markets newsletter. "
        "Each bullet: one sharp sentence, max 18 words. Start each with a strong verb or number. "
        "No em dashes. No bullet symbols, just the text. "
        "Return them as 3 lines, one per line, nothing else."
    )
    bullets_raw = claude(bullets_prompt, max_tokens=150) or ""
    bullets = [b.strip().lstrip("-•*").strip() for b in bullets_raw.strip().split("\n") if b.strip()][:3]
    if len(bullets) < 3:
        bullets += ["Watch regulatory responses closely over the next 30 days."] * (3 - len(bullets))

    # The Prob's Take
    take_prompt = (
        f"Headline: {headline}\n"
        f"Background: {raw}\n\n"
        "Write The Prob's Take: 1-2 sentences, max 40 words. "
        "This is the editorial opinion for prediction market traders. "
        "What does a sharp bettor need to know or do with this information? "
        "No em dashes. No hedging. Be direct. Just the take, nothing else."
    )
    take = claude(take_prompt, max_tokens=100) or "Watch this space. The crowd will price it before the press does."

    return {
        "summary": summary,
        "bullets": bullets,
        "take":    take,
    }


def generate_subject(stories: list) -> str:
    headlines = "\n".join(f"- {s.get('headline', '')}" for s in stories)
    prompt = (
        f"This week's 5 prediction markets stories:\n{headlines}\n\n"
        "Write ONE punchy email subject line for The Prob's Sunday 5 newsletter. "
        "Angle: what's the most provocative or surprising thing in this list? "
        "Lead with the tension or the stakes. Max 55 characters. "
        "No em dashes. No 'The Prob:' or 'Sunday 5:' prefix. No quotes. "
        "Just the subject line, nothing else."
    )
    subj = claude(prompt, max_tokens=70)
    if not subj:
        subj = "The Sunday 5: This Week in Prediction Markets"
    return subj


def generate_subtitle(stories: list) -> str:
    headlines = " | ".join(s.get("headline", "")[:45] for s in stories[:3])
    prompt = (
        f"This week's top prediction markets stories: {headlines}\n\n"
        "Write ONE short inbox preview line for The Prob's Sunday 5 newsletter. "
        "This appears under the subject line in Gmail/Apple Mail. Max 85 characters. "
        "Make it feel urgent and specific to this week's actual stories. "
        "No em dashes. No quotes. No generic filler. Just the preview text, nothing else."
    )
    sub = claude(prompt, max_tokens=90)
    if not sub:
        sub = "Five stories shaping the prediction markets conversation this week."
    return sub

# ── HTML HELPERS ──────────────────────────────────────────────────────────────

def build_head_styles() -> str:
    return """
<style type="text/css">
  /* ── Mobile ── */
  @media only screen and (max-width:600px){
    .outer-table{width:100%!important;}
    .section-pad{padding:20px 16px!important;}
    /* Story numbers stay bold on mobile */
    .story-num{font-size:30px!important;}
    /* Headlines readable on phone */
    .story-headline{font-size:17px!important;line-height:1.4!important;}
    /* Body copy comfortable on small screen */
    .body-text{font-size:16px!important;line-height:1.85!important;}
    /* Take text */
    .take-text{font-size:15px!important;line-height:1.75!important;}
    /* Labels — minimum 12px, never smaller */
    .label-text{font-size:12px!important;letter-spacing:0.1em!important;}
    /* Intro paragraph */
    .intro-text{font-size:16px!important;line-height:1.85!important;}
    /* Subtitle / preview row */
    .subtitle-text{font-size:16px!important;}
    /* Bullet list items */
    .bullet-item{font-size:15px!important;line-height:1.75!important;}
    /* Brand bar */
    .brand-name{font-size:20px!important;}
    .brand-tag{font-size:11px!important;}
  }
  /* ── Dark mode lock ── */
  @media (prefers-color-scheme:dark){
    body,div,td{background-color:#0a0e14!important;color:#d0dde8!important;}
  }
</style>"""


def story_card_html(number: str, story: dict, copy: dict) -> str:
    headline = story.get("headline", "")
    source   = story.get("source", "")
    url      = story.get("url", "#")
    summary  = copy.get("summary", "")
    bullets  = copy.get("bullets", [])
    take     = copy.get("take", "")
    signal   = story.get("market_signal", None)

    bullet_items = "".join(
        f'<li class="bullet-item" style="margin-bottom:8px;color:#d0dde8 !important;font-size:14px;line-height:1.7;">{b}</li>'
        for b in bullets
    )

    signal_block = ""
    if signal:
        signal_block = f"""
      <div style="background:#1a2535 !important;border-left:3px solid #f5a623;padding:10px 14px;margin:14px 0 0;border-radius:0 4px 4px 0;">
        <span style="font-family:'Courier New',monospace;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:#f5a623 !important;display:block;margin-bottom:4px;">The Prob Notes</span>
        <span style="font-size:13px;color:#d0dde8 !important;line-height:1.6;">{signal}</span>
      </div>"""

    return f"""
  <tr><td class="section-pad" style="padding:28px 32px;border-bottom:1px solid #1e2a38;">
    <div class="story-num" style="font-family:'Courier New',monospace;font-size:38px;font-weight:700;color:#00e5a0 !important;line-height:1;margin-bottom:6px;">{number}</div>
    <div class="label-text" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:#a8bfce !important;margin:0 0 10px;">via {source}</div>
    <div class="story-headline" style="font-size:18px;font-weight:700;color:#edf2f7 !important;line-height:1.35;margin-bottom:12px;">
      <a href="{url}" style="color:#edf2f7 !important;text-decoration:none;">{headline}</a>
    </div>
    <p class="body-text" style="font-size:15px;color:#d0dde8 !important;line-height:1.8;margin:0 0 16px;">{summary}</p>
    <div style="margin-bottom:16px;">
      <div class="label-text" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:#a8bfce !important;margin-bottom:8px;">What You Need to Know</div>
      <ul style="margin:0;padding-left:18px;list-style:disc;">
        {bullet_items}
      </ul>
    </div>
    <div style="background:#0f1825 !important;border:1px solid #1e2a38;border-left:3px solid #00e5a0;padding:12px 16px;border-radius:0 4px 4px 0;">
      <div style="font-family:'Courier New',monospace;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:#00e5a0 !important;margin-bottom:6px;">The Prob's Take</div>
      <p class="take-text" style="font-size:14px;color:#d0dde8 !important;line-height:1.7;margin:0;">{take}</p>
    </div>
    {signal_block}
  </td></tr>"""


def build_header_html(date_str: str, edition: int, subtitle: str) -> str:
    return f"""
  <tr><td style="padding:24px 32px 20px;text-align:center;background:#0a0e14 !important;border-bottom:2px solid #1e2a38;">
    <!-- Brand bar matching theprob.ai -->
    <div style="margin-bottom:24px;">
      <a href="{SITE_URL}" style="text-decoration:none;">
        <span class="brand-name" style="font-family:'Courier New',monospace;font-size:22px;font-weight:700;color:#00e5a0 !important;letter-spacing:-0.5px;">THE PROB</span>
        <span style="font-family:'Courier New',monospace;font-size:16px;color:#4a6880 !important;margin:0 8px;">|</span>
        <span class="brand-tag" style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#a8bfce !important;">What's the Probability?</span>
      </a>
    </div>

    <!-- Photo bubble -->
    <div style="width:80px;height:80px;border-radius:50%;overflow:hidden;margin:0 auto 10px;border:2px solid #00e5a0;background:#1e2a38;">
      <img src="{CHRIS_PHOTO_URL}" alt="-usernamedchris" width="80" height="80"
           style="width:80px;height:80px;border-radius:50%;object-fit:cover;display:block;"
           onerror="this.style.display='none'">
    </div>
    <div style="font-family:'Courier New',monospace;font-size:11px;color:#00e5a0 !important;margin-bottom:20px;letter-spacing:0.05em;">-usernamedchris</div>

    <!-- Sunday 5 title -->
    <div style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:0.25em;text-transform:uppercase;color:#f5a623 !important;margin-bottom:8px;">Sunday Edition</div>
    <div style="font-size:30px;font-weight:700;color:#edf2f7 !important;line-height:1.15;margin-bottom:8px;">The Sunday 5</div>
    <div style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:#8ba3bc !important;margin-bottom:18px;">{date_str} &nbsp;&#183;&nbsp; Edition #{edition:02d}</div>

    <!-- Two-sentence intro -->
    <div class="intro-text" style="font-size:15px;color:#c8dae6 !important;line-height:1.8;max-width:420px;margin:0 auto 6px;">
      Every Sunday, I hand-pick the 5 most important stories from the prediction markets world and tell you why they matter. These are the headlines shaping where smart money is moving next.
    </div>
  </td></tr>
  <tr><td style="padding:14px 32px 18px;background:#0d1117 !important;text-align:center;border-bottom:1px solid #1e2a38;">
    <div class="subtitle-text" style="font-size:15px;color:#edf2f7 !important;font-style:italic;">{subtitle}</div>
  </td></tr>"""


def build_footer_html() -> str:
    return f"""
  <tr><td class="section-pad" style="padding:28px 32px;background:#0a0e14 !important;text-align:center;border-top:1px solid #1e2a38;">
    <div style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:#8ba3bc !important;margin-bottom:16px;">The Prob</div>
    <div style="font-size:12px;color:#8ba3bc !important;line-height:1.8;">
      <a href="{SITE_URL}" style="color:#a8bfce !important;text-decoration:none;">theprob.ai</a>
      &nbsp;&#183;&nbsp;
      <a href="{SITE_URL}/prediction-markets-101.html" style="color:#a8bfce !important;text-decoration:none;">Prediction Markets 101</a>
      &nbsp;&#183;&nbsp;
      <a href="{SITE_URL}/archive.html" style="color:#a8bfce !important;text-decoration:none;">Archive</a>
      &nbsp;&#183;&nbsp;
      <a href="{SITE_URL}/contact.html" style="color:#a8bfce !important;text-decoration:none;">Contact</a>
    </div>
    <div style="font-size:11px;color:#8ba3bc !important;margin-top:14px;line-height:1.7;">
      Prediction markets data from Polymarket and Kalshi.<br>
      Not financial advice. Trade at your own risk.
    </div>
  </td></tr>"""


def build_full_html(header: str, story_cards: str, footer: str, subject: str, subtitle: str) -> str:
    styles = build_head_styles()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{subject}</title>
{styles}
</head>
<body style="margin:0;padding:0;background:#0a0e14 !important;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;">{subtitle}</div>
<!--[if mso]><center><table width="600"><tr><td><![endif]-->
<table class="outer-table" align="center" width="600" cellpadding="0" cellspacing="0" border="0"
       style="max-width:600px;width:100%;background:#0a0e14 !important;border-radius:8px;overflow:hidden;">
  {header}
  {story_cards}
  {footer}
</table>
<!--[if mso]></td></tr></table></center><![endif]-->
</body>
</html>"""


# ── PREVIEW WRAPPER ───────────────────────────────────────────────────────────

def build_preview_html(email_html: str) -> str:
    """Wraps the email HTML in a browser preview page with a Copy button."""
    escaped = email_html.replace("`", "\\`").replace("${", "\\${")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sunday 5 Preview</title>
<style>
  body{{margin:0;background:#111;font-family:system-ui,sans-serif;}}
  .controls{{position:fixed;top:16px;right:16px;z-index:999;display:flex;gap:8px;}}
  .btn{{background:#00e5a0;color:#0a0e14;border:none;padding:10px 20px;border-radius:6px;
        font-weight:700;font-size:13px;cursor:pointer;letter-spacing:0.05em;}}
  .btn:hover{{background:#00c98a;}}
  .btn.copied{{background:#f5a623;}}
  iframe{{display:block;width:640px;max-width:100%;margin:0 auto;border:none;height:100vh;}}
</style>
</head>
<body>
<div class="controls">
  <button class="btn" onclick="copyEmail()" id="copyBtn">Copy Email HTML</button>
</div>
<iframe src="latest-email.html" id="preview"></iframe>
<script>
async function copyEmail(){{
  try{{
    const r=await fetch('latest-copy.html');
    const t=await r.text();
    await navigator.clipboard.writeText(t);
    const b=document.getElementById('copyBtn');
    b.textContent='Copied!';b.classList.add('copied');
    setTimeout(()=>{{b.textContent='Copy Email HTML';b.classList.remove('copied');}},2500);
  }}catch(e){{alert('Copy failed: '+e);}}
}}
</script>
</body>
</html>"""


# ── INDEX JSON ────────────────────────────────────────────────────────────────

def update_index(date_str: str, subject: str, subtitle: str, archive_path: str):
    index_path = "newsletter/index.json"
    try:
        with open(index_path) as f:
            index = json.load(f)
    except Exception:
        index = []

    entry = {
        "date":     date_str,
        "subject":  subject,
        "subtitle": subtitle,
        "url":      f"{SITE_URL}/{archive_path}",
        "type":     "sunday5",
    }

    # Deduplicate by date
    index = [e for e in index if e.get("date") != date_str]
    index.insert(0, entry)

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"  Index:   {index_path}  ({len(index)} editions)")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading Sunday 5 stories...")

    with open("data/sunday5_stories.json") as f:
        data = json.load(f)

    stories = data.get("stories", [])
    edition = data.get("edition", 1)
    date_str = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    now_et   = datetime.now(timezone.utc) + timedelta(hours=-4)  # EDT
    date_fmt = datetime.fromisoformat(date_str).strftime("%B %-d, %Y")

    print(f"  Stories: {len(stories)}")
    print(f"  Edition: #{edition:02d} | {date_str}")

    print("\nGenerating copy via Claude API...")
    enriched = []
    for s in stories:
        print(f"  {s['number']} {s['source']}: {s['headline'][:55]}...")
        copy = generate_story_copy(s)
        enriched.append((s, copy))

    subject  = generate_subject(stories)
    subtitle = generate_subtitle(stories)
    print(f"  Subject:  {subject}")
    print(f"  Subtitle: {subtitle}")

    print("\nBuilding HTML...")
    header = build_header_html(date_fmt, edition, subtitle)
    story_cards = "".join(story_card_html(s["number"], s, copy) for s, copy in enriched)
    footer = build_footer_html()

    email_html   = build_full_html(header, story_cards, footer, subject, subtitle)
    preview_html = build_preview_html(email_html)

    # Strip footer for the copy-to-Beehiiv version
    copy_html = email_html

    archive_path = f"newsletter/{date_str}-sunday5.html"

    os.makedirs("newsletter", exist_ok=True)
    with open("newsletter/latest-email.html", "w") as f:
        f.write(email_html)
    with open("newsletter/latest-copy.html", "w") as f:
        f.write(copy_html)
    with open("newsletter/latest.html", "w") as f:
        f.write(preview_html)
    with open(archive_path, "w") as f:
        f.write(email_html)
    with open("newsletter/latest-subject.txt", "w") as f:
        f.write(subject)

    update_index(date_str, subject, subtitle, archive_path)

    print(f"\nSaving newsletter...")
    print(f"  Preview: newsletter/latest.html")
    print(f"  Email:   newsletter/latest-email.html")
    print(f"  Copy:    newsletter/latest-copy.html  (paste into Beehiiv)")
    print(f"  Archive: {archive_path}")
    print(f"  Subject: newsletter/latest-subject.txt")
    print(f"\nTo send: open {SITE_URL}/newsletter/latest.html -> Copy Email HTML -> paste into Beehiiv")
    print(f"NOTE: Commit images/chris-williams.jpg to the repo for the photo bubble to appear.")


if __name__ == "__main__":
    main()
