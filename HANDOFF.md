# The Prob — Design Handoff

Everything a developer (or Claude Code) needs to rebuild **theprobnewsletter.com** on the new design system.

## TL;DR
- **Direction:** "The Clean Book" — editorial fintech. Friendly, scannable, opinionated.
- **Brand mark:** the `%` glyph = **"What's the Probability."** It's the logo, the favicon, and a recurring editorial sign-off.
- **Brand color:** Ultramarine `#3A2BD4` (a deep blue-violet). In dark mode it lightens to periwinkle `#8B7CFF`.
- **Type:** Instrument Serif (headlines) · Instrument Sans (UI/body/numbers) · Geist Mono (labels/data).
- **One hard rule:** the brand accent is **never** green or red. Green = YES/up, red = NO/down are reserved market signals.

## Files in this package
| File | What it is |
|---|---|
| `design-tokens.css` | **The source of truth.** All colors, type, spacing, radius, shadow as CSS variables. Light + dark. Import this first. |
| `design-system.html` | Visual reference — the rendered spec. Open it to see every token, component, and voice rule in context. |
| `02-clean.html` | The reference homepage build. Working light/dark toggle, real component markup to copy from. |
| `index.html` | Cover page showing all three explored directions (Clean Book is the chosen one). |
| `01-broadsheet.html`, `03-terminal.html` | The two directions **not** chosen. Keep for reference; do not build from these. |

## How to use the tokens
1. Drop `design-tokens.css` into the site and load it before any other stylesheet.
2. Reference variables everywhere — never hardcode a hex. `color: var(--ink)`, `background: var(--brand)`, etc.
3. Dark mode is automatic: set `<html data-theme="dark">`. Default to the user's OS preference, then let them toggle (see the toggle script in `02-clean.html`). Persist the choice in `localStorage` under `prob_theme`.

## Fonts
Load from Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```
- **Headlines** use Instrument Serif at weight 400. The accent phrase in a headline is set in *italic* and colored `var(--brand)` (see "The crowd already *placed its bets.*").
- **Numbers/odds** use Instrument Sans, weight 700–800, with `font-feature-settings:"tnum"` for tabular alignment.
- **Labels, timestamps, tickers, platform names** use Geist Mono, uppercase, letterspaced `.08em`.

## Color rules (non-negotiable)
- `--brand` (Ultramarine/periwinkle): logo chip, primary buttons, links, focus rings, the eyebrow pill, the italic headline phrase, the `%` sign-off.
- `--yes` / `--no`: **only** for market direction — odds numbers, up/down chips, YES/NO bars, probability fills. Never decorative.
- `--amber`: watch states, flags, "resolves soon."
- Feature panels (The Prob's Take, the "Why" band) use `--feature-bg`, which is intentionally dark in light mode and an elevated dark surface in dark mode. Text on them stays light in both modes.

## The favicon / app icon
Square brand chip, radius ~`--r-xl`, `--brand` fill, white `%`. Inline SVG version (swap fill for dark contexts):
```html
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='15' fill='%233A2BD4'/%3E%3Ctext x='32' y='46' font-family='Georgia,serif' font-weight='700' font-size='42' text-anchor='middle' fill='%23ffffff'%3E%25%3C/text%3E%3C/svg%3E">
```

## Components to carry across the site
All markup exists in `02-clean.html` — copy from there. Key ones:
- **Nav** — sticky, blurred `--nav-bg`, `%` chip + "The Prob", category links, theme toggle, primary CTA.
- **Market card** (hero / Market of the Day) — big odds number in `--yes`/`--no`, YES/NO bar, platform pill, 3-stat footer, a Take blurb.
- **Mover tile** — platform label, up/down chip, question, big probability, mini progress bar. Used in a 3-up grid.
- **The Spread panel** — two platforms' odds on the same question, with a gap badge.
- **The Prob's Take** — feature panel, serif headline with italic brand accent, signed with `%`.
- **Buttons** — `.btn-pri` (brand fill) and `.btn-ghost` (outline).
- **Eyebrow pill** — mono label with the `%` chip, on `--brand-soft`.

## Voice & copy
- Confident, witty, numerate. The Hustle meets Bloomberg.
- Short active sentences. Lead with numbers. Have a point of view.
- **No em dashes, ever.** Use a colon, a comma, or split the sentence.
- Recurring segments: **Market of the Day**, **Biggest Movers**, **The Spread**, **The Prob's Take**.
- Voice the *change*, not just the level: "Down 9 points" is the story; "41%" is context.

## Pages still to design (not in this package)
These were out of scope for the exploration. Build them in this same system:
- Market detail page (one market, full history chart, YES/NO depth, the Take).
- Category pages (Politics, Business, Tech, Sports, Culture, News).
- The newsletter email template.
- Archive / past briefs.

## Brand facts
- Domain: theprobnewsletter.com. `predictionmarketnewsletter.com` and `predictionmarketsnewsletter.com` both redirect here.
- Data sources: **Polymarket** and **Kalshi**.
- Always include: "Not financial advice. Market data for informational purposes only."
