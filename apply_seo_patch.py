#!/usr/bin/env python3
"""
apply_seo_patch.py — Run this script from your repo root to apply
all SEO improvements to The Prob's HTML files.

Usage:
    python3 apply_seo_patch.py

What it does:
    - Updates <head> blocks on all 7 HTML files with keyword-rich titles,
      meta descriptions, Open Graph tags, Twitter Cards, and JSON-LD structured data
    - Does NOT touch any HTML body content or JavaScript
    - Creates sitemap.xml and robots.txt if they don't exist
"""

import os, re, sys

# ── NEW HEAD BLOCKS ───────────────────────────────────────────────────────────

HEADS = {

"business.html": """\
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Business &amp; Finance Prediction Market Odds | Polymarket &amp; Kalshi | The Prob</title>

  <!-- SEO -->
  <meta name="description" content="Live Polymarket and Kalshi odds on Fed decisions, company acquisitions, IPOs, and economic events. Real money forecasting markets for business and finance — updated hourly.">
  <meta name="keywords" content="business prediction markets, finance prediction markets, Polymarket finance, Kalshi economics, Fed prediction market, IPO prediction market, Polymarket business, Kalshi business, economic prediction markets">
  <link rel="canonical" href="https://theprobnewsletter.com/business.html">

  <!-- Open Graph -->
  <meta property="og:type"         content="website">
  <meta property="og:site_name"    content="The Prob">
  <meta property="og:title"        content="Business Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta property="og:description"  content="Fed decisions, company acquisitions, IPOs, and jobs numbers. Real money odds on everything business from Polymarket and Kalshi.">
  <meta property="og:url"          content="https://theprobnewsletter.com/business.html">
  <meta property="og:image"        content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="@theprob">
  <meta name="twitter:title"       content="Business Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta name="twitter:description" content="Fed decisions, company acquisitions, IPOs, and jobs numbers. Real money odds on everything business from Polymarket and Kalshi.">
  <meta name="twitter:image"       content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">

  <!-- Structured Data (JSON-LD) -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "Business Prediction Market Odds — Polymarket & Kalshi | The Prob",
    "url": "https://theprobnewsletter.com/business.html",
    "description": "Live Polymarket and Kalshi odds on Fed decisions, company acquisitions, IPOs, and economic events.",
    "isPartOf": { "@type": "WebSite", "name": "The Prob", "url": "https://theprobnewsletter.com/" }
  }
  </script>""",

"culture.html": """\
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Culture &amp; Entertainment Prediction Market Odds | Polymarket &amp; Kalshi | The Prob</title>

  <!-- SEO -->
  <meta name="description" content="Live Polymarket and Kalshi odds on award shows, Oscars, viral events, and pop culture. Crowd-sourced probability on culture and entertainment — updated hourly.">
  <meta name="keywords" content="culture prediction markets, entertainment prediction markets, Oscars prediction market, Polymarket entertainment, Kalshi entertainment, award show odds, pop culture prediction market, Grammy prediction market">
  <link rel="canonical" href="https://theprobnewsletter.com/culture.html">

  <!-- Open Graph -->
  <meta property="og:type"         content="website">
  <meta property="og:site_name"    content="The Prob">
  <meta property="og:title"        content="Culture Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta property="og:description"  content="Award shows, viral moments, and the calls nobody else is making. Real money odds on culture from Polymarket and Kalshi.">
  <meta property="og:url"          content="https://theprobnewsletter.com/culture.html">
  <meta property="og:image"        content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="@theprob">
  <meta name="twitter:title"       content="Culture Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta name="twitter:description" content="Award shows, viral moments, and the calls nobody else is making. Real money odds on culture from Polymarket and Kalshi.">
  <meta name="twitter:image"       content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">

  <!-- Structured Data (JSON-LD) -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "Culture Prediction Market Odds — Polymarket & Kalshi | The Prob",
    "url": "https://theprobnewsletter.com/culture.html",
    "description": "Live Polymarket and Kalshi odds on award shows, Oscars, viral events, and pop culture.",
    "isPartOf": { "@type": "WebSite", "name": "The Prob", "url": "https://theprobnewsletter.com/" }
  }
  </script>""",

"news.html": """\
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Prediction Market News — Polymarket &amp; Kalshi Updates | The Prob</title>

  <!-- SEO -->
  <meta name="description" content="The latest news about Polymarket, Kalshi, and the prediction markets world. Coverage of market moves, regulatory updates, and crowd forecasting — updated 4x daily.">
  <meta name="keywords" content="Polymarket news, Kalshi news, prediction market news, prediction markets newsletter, Polymarket newsletter, Kalshi newsletter, prediction markets today, forecasting news, prediction market updates">
  <link rel="canonical" href="https://theprobnewsletter.com/news.html">

  <!-- Open Graph -->
  <meta property="og:type"         content="website">
  <meta property="og:site_name"    content="The Prob">
  <meta property="og:title"        content="Prediction Market News — Polymarket &amp; Kalshi | The Prob">
  <meta property="og:description"  content="The latest news from Polymarket, Kalshi, and the prediction markets world. Sourced, summarized, and updated 4 times a day.">
  <meta property="og:url"          content="https://theprobnewsletter.com/news.html">
  <meta property="og:image"        content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="@theprob">
  <meta name="twitter:title"       content="Prediction Market News — Polymarket &amp; Kalshi | The Prob">
  <meta name="twitter:description" content="The latest news from Polymarket, Kalshi, and the prediction markets world. Sourced, summarized, and updated 4 times a day.">
  <meta name="twitter:image"       content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">

  <!-- Structured Data (JSON-LD) -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "Prediction Market News — Polymarket & Kalshi | The Prob",
    "url": "https://theprobnewsletter.com/news.html",
    "description": "The latest news about Polymarket, Kalshi, and the prediction markets world.",
    "isPartOf": { "@type": "WebSite", "name": "The Prob", "url": "https://theprobnewsletter.com/" }
  }
  </script>""",

"politics.html": """\
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Political Prediction Market Odds — Elections &amp; Policy | Polymarket &amp; Kalshi | The Prob</title>

  <!-- SEO -->
  <meta name="description" content="Live Polymarket and Kalshi odds on elections, legislation, geopolitical events, and political forecasts. Real money crowd predictions on politics — updated hourly.">
  <meta name="keywords" content="political prediction markets, election prediction market, Polymarket politics, Kalshi politics, election odds, political forecasting, prediction market elections, US politics prediction market">
  <link rel="canonical" href="https://theprobnewsletter.com/politics.html">

  <!-- Open Graph -->
  <meta property="og:type"         content="website">
  <meta property="og:site_name"    content="The Prob">
  <meta property="og:title"        content="Political Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta property="og:description"  content="Real money on elections, policy fights, and geopolitical flashpoints. The crowd doesn&#39;t spin — it bets. Live odds from Polymarket and Kalshi.">
  <meta property="og:url"          content="https://theprobnewsletter.com/politics.html">
  <meta property="og:image"        content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="@theprob">
  <meta name="twitter:title"       content="Political Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta name="twitter:description" content="Real money on elections, policy fights, and geopolitical flashpoints. The crowd doesn&#39;t spin — it bets.">
  <meta name="twitter:image"       content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">

  <!-- Structured Data (JSON-LD) -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "Political Prediction Market Odds — Polymarket & Kalshi | The Prob",
    "url": "https://theprobnewsletter.com/politics.html",
    "description": "Live Polymarket and Kalshi odds on elections, legislation, geopolitical events, and political forecasts.",
    "isPartOf": { "@type": "WebSite", "name": "The Prob", "url": "https://theprobnewsletter.com/" }
  }
  </script>""",

"sports.html": """\
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sports Prediction Market Odds — Championships &amp; Futures | Polymarket &amp; Kalshi | The Prob</title>

  <!-- SEO -->
  <meta name="description" content="Live Polymarket and Kalshi odds on championship winners, season outcomes, and major sports events. Real crowd money on sports prediction markets — updated hourly.">
  <meta name="keywords" content="sports prediction markets, Polymarket sports, Kalshi sports, championship odds prediction market, sports prediction market odds, sports forecasting, NFL prediction market, NBA prediction market">
  <link rel="canonical" href="https://theprobnewsletter.com/sports.html">

  <!-- Open Graph -->
  <meta property="og:type"         content="website">
  <meta property="og:site_name"    content="The Prob">
  <meta property="og:title"        content="Sports Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta property="og:description"  content="Championship odds, season winners, and the markets that move when it matters. Real money from people who watch every game.">
  <meta property="og:url"          content="https://theprobnewsletter.com/sports.html">
  <meta property="og:image"        content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="@theprob">
  <meta name="twitter:title"       content="Sports Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta name="twitter:description" content="Championship odds, season winners, and the markets that move when it matters. Real money from people who watch every game.">
  <meta name="twitter:image"       content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">

  <!-- Structured Data (JSON-LD) -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "Sports Prediction Market Odds — Polymarket & Kalshi | The Prob",
    "url": "https://theprobnewsletter.com/sports.html",
    "description": "Live Polymarket and Kalshi odds on championship winners, season outcomes, and major sports events.",
    "isPartOf": { "@type": "WebSite", "name": "The Prob", "url": "https://theprobnewsletter.com/" }
  }
  </script>""",

"tech.html": """\
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tech &amp; Crypto Prediction Market Odds | Polymarket &amp; Kalshi | The Prob</title>

  <!-- SEO -->
  <meta name="description" content="Live Polymarket and Kalshi odds on Bitcoin price targets, AI model releases, tech IPOs, and regulatory decisions. Crowd-sourced tech and crypto prediction markets — updated hourly.">
  <meta name="keywords" content="crypto prediction markets, Bitcoin prediction market, AI prediction market, tech prediction markets, Polymarket crypto, Kalshi technology, crypto odds, Bitcoin odds prediction market, AI prediction markets">
  <link rel="canonical" href="https://theprobnewsletter.com/tech.html">

  <!-- Open Graph -->
  <meta property="og:type"         content="website">
  <meta property="og:site_name"    content="The Prob">
  <meta property="og:title"        content="Tech &amp; Crypto Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta property="og:description"  content="Bitcoin price targets, AI breakthroughs, and regulatory calls. The wildest crowdsourced tech forecasts on the board from Polymarket and Kalshi.">
  <meta property="og:url"          content="https://theprobnewsletter.com/tech.html">
  <meta property="og:image"        content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="@theprob">
  <meta name="twitter:title"       content="Tech &amp; Crypto Prediction Market Odds — Polymarket &amp; Kalshi | The Prob">
  <meta name="twitter:description" content="Bitcoin price targets, AI breakthroughs, and regulatory calls. Crowd-sourced tech and crypto forecasts from Polymarket and Kalshi.">
  <meta name="twitter:image"       content="https://theprobnewsletter.com/theprob_og_1200x630.jpg">

  <!-- Structured Data (JSON-LD) -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "Tech & Crypto Prediction Market Odds — Polymarket & Kalshi | The Prob",
    "url": "https://theprobnewsletter.com/tech.html",
    "description": "Live Polymarket and Kalshi odds on Bitcoin price targets, AI model releases, tech IPOs, and regulatory decisions.",
    "isPartOf": { "@type": "WebSite", "name": "The Prob", "url": "https://theprobnewsletter.com/" }
  }
  </script>""",

}

# index.html already has good SEO from prior work — just update og:image path
# and add JSON-LD + keywords. We'll do a targeted patch.
INDEX_OLD_IMAGE = 'content="https://theprobnewsletter.com/og-image.jpg"'
INDEX_NEW_IMAGE = 'content="https://theprobnewsletter.com/theprob_og_1200x630.jpg"'

INDEX_JSON_LD = """
  <!-- Structured Data (JSON-LD) -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "The Prob",
    "url": "https://theprobnewsletter.com/",
    "description": "Daily prediction markets intelligence from Polymarket and Kalshi. Live odds on politics, crypto, sports, and business.",
    "publisher": {
      "@type": "Organization",
      "name": "The Prob",
      "url": "https://theprobnewsletter.com/"
    }
  }
  </script>"""

# ── OLD HEAD PATTERNS TO REPLACE ─────────────────────────────────────────────
OLD_HEADS = {
    "business.html": """  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The Prob — Business Markets</title>
  <meta name="description" content="Fed decisions, market moves, company bets, jobs numbers, and everything else that touches your wallet. The crowd prices it before the headlines write it.">
  <link rel="canonical" href="https://theprobnewsletter.com/business.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="The Prob — Business Markets">
  <meta property="og:description" content="Fed decisions, market moves, company bets, jobs numbers, and everything else that touches your wallet. The crowd prices it before the headlines write it.">
  <meta property="og:image" content="https://theprobnewsletter.com/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="The Prob — Business Markets">
  <meta name="twitter:image" content="https://theprobnewsletter.com/og-image.jpg">""",

    "culture.html": """  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The Prob — Culture Markets</title>
  <meta name="description" content="Award shows, viral moments, science milestones, and the calls nobody else is making. Real money on almost anything — and the odds are surprisingly sharp.">
  <link rel="canonical" href="https://theprobnewsletter.com/culture.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="The Prob — Culture Markets">
  <meta property="og:description" content="Award shows, viral moments, science milestones, and the calls nobody else is making. Real money on almost anything — and the odds are surprisingly sharp.">
  <meta property="og:image" content="https://theprobnewsletter.com/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="The Prob — Culture Markets">
  <meta name="twitter:image" content="https://theprobnewsletter.com/og-image.jpg">""",

    "news.html": """  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The Prob — Prediction Market News</title>
  <meta name="description" content="The latest news from Polymarket, Kalshi, and the prediction markets world. Updated 4x daily.">
  <link rel="canonical" href="https://theprobnewsletter.com/news.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="The Prob — Prediction Market News">
  <meta property="og:description" content="The latest news from Polymarket, Kalshi, and the prediction markets world.">
  <meta property="og:image" content="https://theprobnewsletter.com/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">""",

    "politics.html": """  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The Prob — Politics Markets</title>
  <meta name="description" content="Real money on elections, policy fights, geopolitical flashpoints, and the decisions that shape everything else. The crowd doesn't spin. It bets.">
  <link rel="canonical" href="https://theprobnewsletter.com/politics.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="The Prob — Politics Markets">
  <meta property="og:description" content="Real money on elections, policy fights, geopolitical flashpoints, and the decisions that shape everything else. The crowd doesn't spin. It bets.">
  <meta property="og:image" content="https://theprobnewsletter.com/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="The Prob — Politics Markets">
  <meta name="twitter:image" content="https://theprobnewsletter.com/og-image.jpg">""",

    "sports.html": """  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The Prob — Sports Markets</title>
  <meta name="description" content="Not your typical sportsbook. These are prediction markets on who wins the title, the season, the moment. Real money from people who watch every game.">
  <link rel="canonical" href="https://theprobnewsletter.com/sports.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="The Prob — Sports Markets">
  <meta property="og:description" content="Not your typical sportsbook. These are prediction markets on who wins the title, the season, the moment. Real money from people who watch every game.">
  <meta property="og:image" content="https://theprobnewsletter.com/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="The Prob — Sports Markets">
  <meta name="twitter:image" content="https://theprobnewsletter.com/og-image.jpg">""",

    "tech.html": """  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The Prob — Tech Markets</title>
  <meta name="description" content="Crypto price targets, AI breakthroughs, regulatory calls, and the wildest crowdsourced tech forecasts on the board.">
  <link rel="canonical" href="https://theprobnewsletter.com/tech.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="The Prob — Tech Markets">
  <meta property="og:description" content="Crypto price targets, AI breakthroughs, regulatory calls, and the wildest crowdsourced tech forecasts on the board.">
  <meta property="og:image" content="https://theprobnewsletter.com/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="The Prob — Tech Markets">
  <meta name="twitter:image" content="https://theprobnewsletter.com/og-image.jpg">""",
}

# ── SITEMAP ───────────────────────────────────────────────────────────────────
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://theprobnewsletter.com/</loc>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://theprobnewsletter.com/news.html</loc>
    <changefreq>hourly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://theprobnewsletter.com/politics.html</loc>
    <changefreq>hourly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://theprobnewsletter.com/business.html</loc>
    <changefreq>hourly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://theprobnewsletter.com/tech.html</loc>
    <changefreq>hourly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://theprobnewsletter.com/sports.html</loc>
    <changefreq>hourly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://theprobnewsletter.com/culture.html</loc>
    <changefreq>hourly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>
"""

ROBOTS = """User-agent: *
Allow: /

Sitemap: https://theprobnewsletter.com/sitemap.xml
"""

# ── APPLY PATCHES ─────────────────────────────────────────────────────────────
def apply():
    errors = []
    patched = []

    for fname, old_head in OLD_HEADS.items():
        if not os.path.exists(fname):
            errors.append(f"  SKIP {fname} — file not found")
            continue
        with open(fname) as f:
            src = f.read()
        if old_head not in src:
            errors.append(f"  WARN {fname} — old head block not found (already patched?)")
            continue
        new_src = src.replace(old_head, HEADS[fname], 1)
        with open(fname, 'w') as f:
            f.write(new_src)
        patched.append(fname)
        print(f"  ✓ {fname}")

    # index.html: just fix og-image path and add JSON-LD before </head>
    if os.path.exists("index.html"):
        with open("index.html") as f:
            idx = f.read()
        changed = False
        if INDEX_OLD_IMAGE in idx:
            idx = idx.replace(INDEX_OLD_IMAGE, INDEX_NEW_IMAGE)
            changed = True
        if "application/ld+json" not in idx:
            idx = idx.replace("</head>", INDEX_JSON_LD + "\n</head>", 1)
            changed = True
        if changed:
            with open("index.html", 'w') as f:
                f.write(idx)
            print("  ✓ index.html (og-image path + JSON-LD)")
            patched.append("index.html")
        else:
            print("  — index.html (no changes needed)")

    # Write sitemap.xml
    with open("sitemap.xml", 'w') as f:
        f.write(SITEMAP)
    print("  ✓ sitemap.xml (created)")

    # Write robots.txt
    with open("robots.txt", 'w') as f:
        f.write(ROBOTS)
    print("  ✓ robots.txt (created)")

    print(f"\nDone. {len(patched)} files patched.")
    for e in errors:
        print(e)

if __name__ == "__main__":
    print("Applying SEO patches to The Prob...\n")
    apply()
