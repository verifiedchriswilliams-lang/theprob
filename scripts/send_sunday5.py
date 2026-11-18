#!/usr/bin/env python3
"""
send_sunday5.py
Builds and sends The Prob's Sunday 5 newsletter.

Auto-selects the 5 most important prediction-market stories from
data/weekly_stories.json (accumulated Mon-Sat by fetch_news.py).
Sends via Resend Audiences API. Writes newsletter/latest*.html + archive.
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ── CONFIG ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")
CLAUDE_MODEL       = "claude-haiku-4-5-20251001"
FROM_ADDRESS       = "The Prob <newsletter@theprob.ai>"
SITE_URL           = "https://theprob.ai"

HOUSE_STYLE = (
    "You write for The Prob, a prediction markets newsletter. "
    "Voice: sharp, confident, dry wit, slightly irreverent. Like The Hustle meets a trading desk. "
    "Intelligent but not academic. Opinionated but not arrogant. "
    "NEVER use em dashes. Use a comma or start a new sentence instead. "
    "Short sentences. Active voice. Numbers as numerals ($2M, 47%). "
    "No hedging. No fluff. No filler. "
    "Undetectable as AI. Write like a sharp human who finds this genuinely interesting."
)

# ── CLAUDE ────────────────────────────────────────────────────────────────────

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
                "system":     HOUSE_STYLE,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        return text.replace("—", ",").replace(" -- ", ", ")
    except Exception as e:
        print(f"  [WARN] Claude call failed: {e}")
        return ""

# ── STORY SELECTION ───────────────────────────────────────────────────────────

def select_top_stories(weekly: list) -> list:
    """Ask Claude to rank the week's articles and return the top 5."""
    if len(weekly) <= 5:
        return weekly[:5]

    catalog = "\n".join(
        f"{i+1}. [{a['source']}] {a['title']} | {a.get('pub_display','')}"
        for i, a in enumerate(weekly)
    )
    prompt = (
        f"Here are this week's prediction markets news articles:\n{catalog}\n\n"
        "Pick the 5 most important for a weekly newsletter aimed at prediction market traders. "
        "Criteria: genuine news value, impact on prediction markets, reader interest. "
        "Avoid duplicates covering the same event. Favor variety across topics. "
        "Return ONLY 5 line numbers, one per line, like:\n3\n7\n12\n5\n9\nNothing else."
    )
    result = claude(prompt, max_tokens=30)
    indices = []
    for line in result.strip().split("\n"):
        try:
            idx = int(line.strip()) - 1
            if 0 <= idx < len(weekly) and idx not in indices:
                indices.append(idx)
        except ValueError:
            pass

    if len(indices) < 5:
        # Fill with remaining articles not already picked
        for i in range(len(weekly)):
            if i not in indices:
                indices.append(i)
            if len(indices) == 5:
                break

    return [weekly[i] for i in indices[:5]]


# ── COPY GENERATION ───────────────────────────────────────────────────────────

def generate_story_copy(story: dict) -> dict:
    title   = story.get("title", "")
    summary = story.get("summary", "")
    source  = story.get("source", "")

    summary_prompt = (
        f"Source: {source}\nHeadline: {title}\nBackground: {summary}\n\n"
        "Write a 2-sentence summary for The Prob newsletter. "
        "Sentence 1: what happened. Sentence 2: why it matters for prediction market readers. "
        "No em dashes. Under 50 words total. Just the two sentences, nothing else."
    )
    polished_summary = claude(summary_prompt, max_tokens=120) or summary

    bullets_prompt = (
        f"Headline: {title}\nBackground: {summary}\n\n"
        "Write exactly 3 bullet points for a prediction markets newsletter. "
        "Each bullet: one sharp sentence, max 18 words. Start each with a strong verb or number. "
        "No em dashes. No bullet symbols, just the text. "
        "Return them as 3 lines, one per line, nothing else."
    )
    bullets_raw = claude(bullets_prompt, max_tokens=150) or ""
    bullets = [b.strip().lstrip("-*").strip() for b in bullets_raw.strip().split("\n") if b.strip()][:3]
    if len(bullets) < 3:
        bullets += ["Watch how this develops over the next two weeks."] * (3 - len(bullets))

    take_prompt = (
        f"Headline: {title}\nBackground: {summary}\n\n"
        "Write The Prob's Take: 1-2 sentences, max 40 words. "
        "Editorial opinion for prediction market traders. What does a sharp bettor need to know? "
        "No em dashes. No hedging. Be direct. Just the take, nothing else."
    )
    take = claude(take_prompt, max_tokens=100) or "Watch this space. The crowd will price it before the press does."

    return {"summary": polished_summary, "bullets": bullets, "take": take}


def generate_subject(stories: list) -> str:
    headlines = "\n".join(f"- {s.get('title','')}" for s in stories)
    prompt = (
        f"This week's 5 prediction markets stories:\n{headlines}\n\n"
        "Write ONE punchy email subject line for The Prob's Sunday 5 newsletter. "
        "Lead with the most provocative or surprising story. Max 55 characters. "
        "No em dashes. No 'The Prob:' or 'Sunday 5:' prefix. No quotes. "
        "Just the subject line, nothing else."
    )
    return claude(prompt, max_tokens=70) or "The Sunday 5: This Week in Prediction Markets"


def generate_subtitle(stories: list) -> str:
    headlines = " | ".join(s.get("title", "")[:40] for s in stories[:3])
    prompt = (
        f"Top stories: {headlines}\n\n"
        "Write ONE short inbox preview line for The Prob's Sunday 5. "
        "Max 85 characters. Specific to this week. No em dashes. No quotes. Just the preview text."
    )
    return claude(prompt, max_tokens=90) or "Five stories shaping the prediction markets conversation this week."


# ── HTML ──────────────────────────────────────────────────────────────────────

def story_card_html(number: int, story: dict, copy: dict) -> str:
    title   = story.get("title", "")
    source  = story.get("source", "")
    url     = story.get("url", "#")
    pub     = story.get("pub_display", "")
    summary = copy["summary"]
    bullets = copy["bullets"]
    take    = copy["take"]

    bullet_items = "".join(
        f'<li style="margin-bottom:8px;font-family:\'Manrope\',\'Helvetica Neue\',Arial,sans-serif;'
        f'font-size:14px;color:#3D4551;line-height:1.7;">{b}</li>'
        for b in bullets
    )

    accent_colors = ["#0077B6", "#00B4D8", "#023E8A", "#48CAE4", "#90E0EF"]
    accent = accent_colors[(number - 1) % len(accent_colors)]

    return f"""
  <tr><td style="padding:0;border-bottom:1px solid rgba(11,14,20,.08);">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="height:3px;background:{accent};font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td style="padding:28px 32px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="vertical-align:top;width:48px;padding-right:16px;">
              <div style="font-family:'Courier New',monospace;font-size:36px;font-weight:700;
                          color:{accent};line-height:1;">{number:02d}</div>
            </td>
            <td style="vertical-align:top;">
              <div style="font-family:'Manrope','Helvetica Neue',Arial,sans-serif;font-size:10px;
                          letter-spacing:0.14em;text-transform:uppercase;color:#8A93A0;margin-bottom:6px;">
                {source}{(' &nbsp;·&nbsp; ' + pub) if pub else ''}
              </div>
              <div style="font-family:'Georgia','Times New Roman',serif;font-size:18px;font-weight:700;
                          color:#0B0E14;line-height:1.35;margin-bottom:12px;">
                <a href="{url}" style="color:#0B0E14;text-decoration:none;">{title}</a>
              </div>
              <p style="font-family:'Manrope','Helvetica Neue',Arial,sans-serif;font-size:14px;
                        color:#3D4551;line-height:1.8;margin:0 0 16px;">{summary}</p>
              <div style="margin-bottom:16px;">
                <div style="font-family:'Courier New',monospace;font-size:9px;letter-spacing:0.14em;
                            text-transform:uppercase;color:#8A93A0;margin-bottom:8px;">What You Need to Know</div>
                <ul style="margin:0;padding-left:18px;list-style:disc;">
                  {bullet_items}
                </ul>
              </div>
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr><td style="background:rgba(0,119,182,.08);padding:12px 16px;border-radius:6px;">
                  <div style="font-family:'Courier New',monospace;font-size:9px;letter-spacing:0.14em;
                              text-transform:uppercase;color:#0077B6;margin-bottom:6px;">% The Prob's Take</div>
                  <p style="font-family:'Georgia','Times New Roman',serif;font-size:14px;font-style:italic;
                            color:#0B0E14;line-height:1.6;margin:0;">{take}</p>
                </td></tr>
              </table>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </td></tr>"""


def build_email_html(stories: list, enriched: list, subject: str, subtitle: str, date_fmt: str, edition: int) -> str:
    story_cards = "".join(
        story_card_html(i + 1, story, copy) for i, (story, copy) in enumerate(enriched)
    )
    top_sources = ", ".join(dict.fromkeys(s.get("source","") for s in stories[:3]))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
<style>
@media only screen and (max-width:600px){{
  .outer{{width:100%!important;}}
  .pad{{padding:20px 16px!important;}}
}}
</style>
</head>
<body style="margin:0;padding:16px 0;background:#F8F9FA;font-family:'Manrope','Helvetica Neue',Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;">{subtitle}</div>
<!--[if mso]><center><table width="600"><tr><td><![endif]-->
<table class="outer" align="center" width="600" cellpadding="0" cellspacing="0" border="0"
       style="max-width:600px;width:100%;background:#FFFFFF;border-radius:8px;
              border:1px solid rgba(11,14,20,.08);overflow:hidden;">

  <!-- HEADER -->
  <tr><td class="pad" style="padding:28px 32px 24px;border-bottom:1px solid rgba(11,14,20,.08);">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td>
          <a href="{SITE_URL}" style="text-decoration:none;">
            <span style="font-family:'Courier New',monospace;font-size:13px;font-weight:700;
                         letter-spacing:0.18em;text-transform:uppercase;color:#0B0E14;">THEPROB.AI</span>
          </a>
        </td>
        <td style="text-align:right;">
          <span style="font-family:'Manrope','Helvetica Neue',Arial,sans-serif;font-size:11px;
                       color:#8A93A0;">{date_fmt} &nbsp;·&nbsp; Edition #{edition:02d}</span>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- SUNDAY 5 HERO -->
  <tr><td class="pad" style="padding:32px 32px 24px;background:#FFFFFF;border-bottom:1px solid rgba(11,14,20,.08);text-align:center;">
    <div style="font-family:'Courier New',monospace;font-size:9px;letter-spacing:0.2em;
                text-transform:uppercase;color:#0077B6;margin-bottom:10px;">
      <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#0077B6;
                   vertical-align:middle;margin-right:5px;"></span>Sunday Edition
    </div>
    <div style="font-family:'Georgia','Times New Roman',serif;font-size:36px;font-weight:700;
                color:#0B0E14;line-height:1.1;margin-bottom:8px;">The Sunday 5</div>
    <div style="font-family:'Manrope','Helvetica Neue',Arial,sans-serif;font-size:13px;
                color:#8A93A0;margin-bottom:20px;">The 5 biggest prediction markets stories of the week</div>
    <div style="font-family:'Manrope','Helvetica Neue',Arial,sans-serif;font-size:14px;
                color:#3D4551;line-height:1.75;max-width:440px;margin:0 auto;">
      {subtitle}
    </div>
  </td></tr>

  <!-- STORY CARDS -->
  {story_cards}

  <!-- FOOTER -->
  <tr><td class="pad" style="padding:24px 32px;background:#F8F9FA;text-align:center;
                              border-top:1px solid rgba(11,14,20,.08);">
    <div style="font-family:'Manrope','Helvetica Neue',Arial,sans-serif;font-size:12px;
                color:#8A93A0;line-height:1.8;margin-bottom:12px;">
      <a href="{SITE_URL}" style="color:#8A93A0;text-decoration:none;">theprob.ai</a>
      &nbsp;·&nbsp;
      <a href="{SITE_URL}/prediction-markets-101.html" style="color:#8A93A0;text-decoration:none;">PM 101</a>
      &nbsp;·&nbsp;
      <a href="{SITE_URL}/archive.html" style="color:#8A93A0;text-decoration:none;">Archive</a>
    </div>
    <div style="font-family:'Manrope','Helvetica Neue',Arial,sans-serif;font-size:11px;
                color:#C4C9D1;line-height:1.7;">
      Prediction markets data from Polymarket and Kalshi. Not financial advice.<br>
      <a href="mailto:newsletter@theprob.ai?subject=Unsubscribe" style="color:#C4C9D1;">Unsubscribe</a>
    </div>
  </td></tr>

</table>
<!--[if mso]></td></tr></table></center><![endif]-->
</body>
</html>"""


def build_preview_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sunday 5 Preview</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#07090E;font-family:'Courier New',monospace;}}
  #preview-bar{{position:fixed;top:0;left:0;right:0;z-index:9999;background:#07090E;
    border-bottom:2px solid #141B2D;padding:10px 20px;display:flex;align-items:center;
    justify-content:space-between;gap:12px;}}
  #subject-label{{color:#64748B;margin-right:8px;font-size:10px;text-transform:uppercase;letter-spacing:0.15em;}}
  #subject-line{{font-size:12px;color:#94A3B8;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
  #copy-btn{{background:#00e5a0;color:#07090E;border:none;padding:9px 18px;font-family:'Courier New',monospace;
    font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;cursor:pointer;
    white-space:nowrap;flex-shrink:0;}}
  #copy-btn:hover{{opacity:0.85;}}
  #email-frame{{display:block;width:100%;border:none;margin-top:46px;height:calc(100vh - 46px);}}
</style>
</head>
<body>
<div id="preview-bar">
  <div id="subject-line">
    <span id="subject-label">Subject</span>
    <span id="subj-text">Loading...</span>
  </div>
  <button id="copy-btn" onclick="copyHTML()">Copy Email HTML</button>
</div>
<iframe id="email-frame" src="latest-email.html" title="Sunday 5 Preview"></iframe>
<script>
fetch('latest-subject.txt').then(r=>r.text()).then(t=>{document.getElementById('subj-text').textContent=t.trim();});
function copyHTML(){
  var btn=document.getElementById('copy-btn');
  btn.disabled=true; btn.textContent='Fetching...';
  fetch('latest-copy.html?t='+Date.now())
    .then(r=>r.text()).then(t=>navigator.clipboard.writeText(t))
    .then(()=>{btn.textContent='Copied!'; setTimeout(()=>{btn.textContent='Copy Email HTML';btn.disabled=false;},3000);})
    .catch(()=>{btn.textContent='Error'; btn.disabled=false;});
}
</script>
</body>
</html>"""


# ── RESEND ────────────────────────────────────────────────────────────────────

def fetch_audience_contacts() -> list:
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

    print(f"  Sending Sunday 5 to {len(subscribers)} subscribers via Resend...")
    sent = failed = 0
    for email in subscribers:
        try:
            r = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={
                    "from":    FROM_ADDRESS,
                    "to":      [email],
                    "subject": subject,
                    "html":    html,
                    "headers": {"List-Unsubscribe": "<mailto:newsletter@theprob.ai?subject=Unsubscribe>"},
                },
                timeout=30,
            )
            r.raise_for_status()
            sent += 1
        except Exception as e:
            print(f"  [WARN] Failed to send to {email}: {e}")
            failed += 1
    print(f"  Sunday 5 Resend: {sent} sent, {failed} failed")
    return sent > 0


# ── INDEX ─────────────────────────────────────────────────────────────────────

def update_index(date_str: str, subject: str, subtitle: str, archive_path: str):
    index_path = "newsletter/index.json"
    try:
        with open(index_path) as f:
            index = json.load(f)
    except Exception:
        index = []
    entry = {"date": date_str, "subject": subject, "subtitle": subtitle,
             "url": f"{SITE_URL}/{archive_path}", "type": "sunday5"}
    index = [e for e in index if e.get("date") != date_str]
    index.insert(0, entry)
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"  Index: {len(index)} editions")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    now_utc  = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    date_fmt = now_utc.strftime("%B %-d, %Y")

    print("Loading weekly story accumulator...")
    try:
        with open("data/weekly_stories.json") as f:
            weekly = json.load(f)
    except FileNotFoundError:
        print("  [WARN] data/weekly_stories.json not found — falling back to data/news.json")
        with open("data/news.json") as f:
            d = json.load(f)
        weekly = [{"url": a["url"], "title": a["title"], "source": a["source"],
                   "summary": a.get("summary",""), "pub_iso": a.get("pub_iso",""),
                   "pub_display": a.get("pub_display","")} for a in d.get("articles",[])]

    print(f"  {len(weekly)} articles in accumulator")

    # Determine edition number from index
    try:
        with open("newsletter/index.json") as f:
            idx = json.load(f)
        edition = sum(1 for e in idx if e.get("type") == "sunday5") + 1
    except Exception:
        edition = 1

    print("\nSelecting top 5 stories via Claude...")
    stories = select_top_stories(weekly)
    for i, s in enumerate(stories, 1):
        print(f"  {i}. [{s['source']}] {s['title'][:60]}...")

    print("\nGenerating copy via Claude...")
    enriched = []
    for s in stories:
        copy = generate_story_copy(s)
        enriched.append((s, copy))

    subject  = generate_subject(stories)
    subtitle = generate_subtitle(stories)
    print(f"  Subject:  {subject}")
    print(f"  Subtitle: {subtitle}")

    print("\nBuilding HTML...")
    email_html   = build_email_html(stories, enriched, subject, subtitle, date_fmt, edition)
    preview_html = build_preview_html()

    archive_path = f"newsletter/{date_str}-sunday5.html"
    os.makedirs("newsletter", exist_ok=True)
    with open("newsletter/latest-email.html", "w") as f:
        f.write(email_html)
    with open("newsletter/latest-copy.html", "w") as f:
        f.write(email_html)
    with open("newsletter/latest.html", "w") as f:
        f.write(preview_html)
    with open(archive_path, "w") as f:
        f.write(email_html)
    with open("newsletter/latest-subject.txt", "w") as f:
        f.write(subject)

    update_index(date_str, subject, subtitle, archive_path)
    print(f"  Archive: {archive_path}")

    print("\nSending via Resend...")
    send_via_resend(subject, email_html)

    # Clear the weekly accumulator after Sunday send
    with open("data/weekly_stories.json", "w") as f:
        json.dump([], f, indent=2)
    print("  Weekly accumulator cleared for next week.")

    print(f"\nDone. Subject: {subject}")


if __name__ == "__main__":
    main()
