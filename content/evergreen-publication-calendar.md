# Evergreen SEO Publication Calendar

10 articles. 5-week rollout. Tuesday/Thursday cadence.

All articles are built and in the repo. The site is static (GitHub Pages) with no scheduling system. Release each article by merging/pushing and manually submitting the URL to Google Search Console.

---

## Schedule

| Week | Date | Article | URL | Status |
|------|------|---------|-----|--------|
| 1 | Tue 2026-11-25 | How to Read Prediction Market Odds | `/how-to-read-prediction-market-odds.html` | ✅ Built |
| 1 | Thu 2026-11-27 | Prediction Market Liquidity | `/prediction-market-liquidity.html` | ✅ Built |
| 2 | Tue 2026-12-01 | Are Prediction Markets Accurate? | `/are-prediction-markets-accurate.html` | ✅ Built |
| 2 | Thu 2026-12-04 | Polymarket vs. Kalshi Prices | `/polymarket-vs-kalshi-prices.html` | ✅ Built |
| 3 | Tue 2026-12-08 | Prediction Markets vs. Sports Betting | `/prediction-markets-vs-sports-betting.html` | ✅ Built |
| 3 | Thu 2026-12-11 | How Prediction Markets Resolve | `/how-prediction-markets-resolve.html` | ✅ Built |
| 4 | Tue 2026-12-15 | Prediction Markets vs. Polls | `/prediction-markets-vs-polls.html` | ✅ Built |
| 4 | Thu 2026-12-18 | Prediction Market Arbitrage | `/prediction-market-arbitrage.html` | ✅ Built |
| 5 | Tue 2026-12-22 | How Businesses Use Prediction Markets | `/prediction-markets-business-forecasting.html` | ✅ Built |
| 5 | Thu 2026-12-25 | History of Prediction Markets | `/history-of-prediction-markets.html` | ✅ Built |

---

## Release checklist (per article, on publish date)

- [ ] Page returns HTTP 200
- [ ] `<link rel="canonical">` matches the live URL
- [ ] `robots.txt` allows indexing (check no `Disallow: /` present)
- [ ] Page appears in `sitemap.xml` (already added for all 10)
- [ ] Mobile layout renders correctly (test at 375px)
- [ ] Internal links resolve (no 404s)
- [ ] Structured data validates (use Google Rich Results Test)
- [ ] Submit URL to Google Search Console manually (Search Console > URL Inspection > Request Indexing)
- [ ] Check for console JS errors

---

## Notes

- All 10 articles pre-built. Keep them indexed from day 1 since the site is static (no draft/publish toggle). The publish dates are editorial, not technical.
- `sitemap.xml` is updated with all 10 URLs and their scheduled `lastmod` dates.
- Articles are **not** linked from the homepage or nav yet. Add links as each article goes "live" per the schedule above.
- After Week 1, link Articles 1 and 3 from `prediction-markets-101.html` to begin building the internal link graph.
- SVGs live in `images/articles/` (30 files, 3 per article, labeled by article number).
