#!/usr/bin/env python3
"""
fetch_news.py
Fetches prediction market news from Google News RSS.
Generates 2-sentence Hustle-style summaries via Claude API.
Writes data/news.json — runs 4x daily via GitHub Actions.

HOUSE STYLE (see fetch_markets.py):
  - No em dashes. Ever.
  - Short sentences. Active voice.
  - Numbers as numerals.
  - Confident, not hedging.
"""

import os
import json
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import requests

# ── CONFIG ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-20250514"

MAX_ARTICLES      = 12   # Total articles in news.json (news.html shows all)
HOMEPAGE_COUNT    = 3    # Articles surfaced on the homepage Daily Brief
CACHE_HOURS       = 5    # Minimum hours before re-fetching existing article

# Search queries — ordered by priority
# Each pulls up to ~10 results; we merge, dedup by URL, keep best MAX_ARTICLES
SEARCH_QUERIES = [
    "Polymarket prediction market",
    "Kalshi prediction market",
    "prediction markets news",
]

GNEWS_BASE = "https://news.google.com/rss/search"

HOUSE_STYLE_SYSTEM = (
    "You write for The Prob, a prediction markets newsletter. "
    "Voice: sharp, confident, dry wit, slightly irreverent. Like The Hustle. "
    "Intelligent but not academic. Opinionated but not arrogant. "
    "NEVER use em dashes. Use a comma or start a new sentence instead. "
    "Short sentences. Active voice. Numbers as numerals ($2M, 47%). "
    "No hedging ('perhaps', 'might', 'could potentially'). No fluff. No filler. "
    "Undetectable as AI. Write like a smart human who finds this genuinely interesting."
)

# ── FETCH RSS ─────────────────────────────────────────────────────────────────

def fetch_gnews(query: str, max_results: int = 15) -> list[dict]:
    """Fetch Google News RSS for a query, return list of raw article dicts."""
    url    = f"{GNEWS_BASE}?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    articles = []
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item")[:max_results]:
            title  = item.findtext("title", "").strip()
            link   = item.findtext("link", "").strip()
            pub    = item.findtext("pubDate", "").strip()
            source_el = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
            desc   = item.findtext("description", "").strip()
            # Clean HTML tags from description
            desc   = re.sub(r"<[^>]+>", " ", desc).strip()
            desc   = re.sub(r"\s+", " ", desc)

            if not title or not link:
                continue

            # Parse publication date
            pub_iso = ""
            try:
                dt     = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z")
                pub_iso = dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pub_iso = datetime.now(timezone.utc).isoformat()

            # Extract source name from title (Google News appends " - Source Name")
            source_name = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source_name = parts[1].strip()

            articles.append({
                "title":       title,
                "url":         link,
                "source":      source_name,
                "pub_iso":     pub_iso,
                "description": desc,
                "summary":     "",   # filled by Claude
            })
    except Exception as e:
        print(f"  [WARN] RSS fetch failed for '{query}': {e}")
    return articles


def merge_and_dedup(all_articles: list[list[dict]]) -> list[dict]:
    """Merge results from multiple queries, dedup by URL, sort by date."""
    seen_urls = set()
    merged    = []
    for batch in all_articles:
        for a in batch:
            url = a["url"]
            # Normalize Google redirect URLs (they wrap with /url?...)
            if "news.google.com/rss/articles" in url:
                url = a["url"]  # keep as-is; redirect resolves on click
            if url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(a)
    # Sort by publication date, newest first
    merged.sort(key=lambda x: x.get("pub_iso", ""), reverse=True)
    return merged


# ── CLAUDE SUMMARIZER ─────────────────────────────────────────────────────────

def summarize_article(title: str, description: str) -> str:
    """
    Call Claude API to generate a 2-sentence Hustle-style summary.
    Returns the summary string, or a fallback if API fails.
    """
    if not ANTHROPIC_API_KEY:
        return f"{description[:180]}..." if len(description) > 180 else description

    prompt = (
        f"Article title: {title}\n\n"
        f"Article snippet: {description}\n\n"
        "Write exactly 2 sentences summarizing this article for The Prob newsletter. "
        "Sentence 1: what happened. Sentence 2: why it matters for prediction markets or bettors. "
        "No em dashes. No quotes. No intro phrases like 'This article' or 'The piece'. Just the two sentences."
    )

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
                "max_tokens": 120,
                "system":     HOUSE_STYLE_SYSTEM,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        r.raise_for_status()
        data    = r.json()
        summary = data["content"][0]["text"].strip()
        # Hard enforce: strip any em dashes that slipped through
        summary = summary.replace("\u2014", ",").replace(" -- ", ", ")
        return summary
    except Exception as e:
        print(f"  [WARN] Claude summary failed: {e}")
        return f"{description[:180]}..." if len(description) > 180 else description


def format_pub_date(pub_iso: str) -> str:
    """Format ISO date as 'Feb 22' or 'Feb 22, 2026' if not current year."""
    try:
        dt      = datetime.fromisoformat(pub_iso)
        now     = datetime.now(timezone.utc)
        if dt.year == now.year:
            return dt.strftime("%b %-d")
        return dt.strftime("%b %-d, %Y")
    except Exception:
        return ""


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    now_utc     = datetime.now(timezone.utc)
    now_et      = now_utc + timedelta(hours=-5)
    updated_str = now_et.strftime("%b %-d, %Y · %-I:%M %p ET")

    # Load existing news.json to avoid re-summarizing articles we already have
    existing_summaries = {}
    try:
        with open("data/news.json") as f:
            existing = json.load(f)
            for a in existing.get("articles", []):
                if a.get("summary") and a.get("url"):
                    existing_summaries[a["url"]] = a["summary"]
        print(f"  Loaded {len(existing_summaries)} cached summaries")
    except FileNotFoundError:
        print("  No existing news.json — starting fresh")

    # Fetch from all queries
    print("Fetching news from Google News RSS...")
    all_batches = []
    for query in SEARCH_QUERIES:
        print(f"  Querying: '{query}'")
        batch = fetch_gnews(query, max_results=15)
        print(f"    Got {len(batch)} articles")
        all_batches.append(batch)
        time.sleep(0.5)  # be polite

    articles = merge_and_dedup(all_batches)
    print(f"  {len(articles)} unique articles after dedup")

    # Keep top MAX_ARTICLES by recency
    articles = articles[:MAX_ARTICLES]

    # Generate summaries — use cached if available, else call Claude
    print(f"Generating summaries (Claude API)...")
    for i, a in enumerate(articles):
        url = a["url"]
        if url in existing_summaries:
            a["summary"] = existing_summaries[url]
            print(f"  [{i+1}/{len(articles)}] cached  — {a['title'][:60]}")
        else:
            print(f"  [{i+1}/{len(articles)}] summarizing — {a['title'][:60]}")
            a["summary"] = summarize_article(a["title"], a["description"])
            time.sleep(0.3)  # gentle rate limiting

        a["pub_display"] = format_pub_date(a["pub_iso"])

    output = {
        "updated":        updated_str,
        "updated_iso":    now_utc.isoformat(),
        "homepage_count": HOMEPAGE_COUNT,
        "articles":       articles,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/news.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Wrote data/news.json ({len(articles)} articles)")
    print(f"  Updated: {updated_str}")

if __name__ == "__main__":
    main()
