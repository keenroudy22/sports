# Kook'n plan: what we're building and why

**Goal:** grow a following with free, honest best bets and the best free research board in the niche, then turn it
into a subscription (props.cash / OddsJam style) on a $0 stack. Codex implements and runs it day to day.

## 1. Product (Hybrid A + B, casino felt)

- **Today (plain English).**
  - Today's best bets as paper tickets: price + book, "We think this hits 54%. At +101 you only need 50%", a meter,
    fair price, edge, why, and one visible "what could go wrong".
  - When there's no play, an honest empty state plus the next release window.
  - Next best bets shown open, not hidden.
  - Climb status, fun tickets in their own lane, three "worth a look" research rows, Underdog watch, today's games.
- **Research (one pro board).**
  - Modes: Lines · Trends · Players · News.
  - KPI strip, sport/type chips, Fresh prices and Value only (both on by default), sort by edge / most likely /
    kickoff, search.
  - Columns: Line · Best price (book, books, age) · Our chance vs needed · Edge · Fair.
  - Rows expand to show the season hit chart against the line and the case for and against.
- **Games.** Sorted by how unusual our gap with the market is, with honest caveats ("gaps this size went 1739–1729
  against the close"). Live scores for every sport.
- **Game, player and team pages.** The existing depth, laid out in plain sections. No raw "our number" that
  contradicts the chance.
- **Record.**
  - Season W–L, units at posted prices, "beat the closing line X of Y", and graded count.
  - A cumulative units chart; receipts as green ✓ / red ✗ tickets.
  - Tabs: Fun tickets · Climb · Model vs market (honest: "the line has been the closer forecast") · Trials.
- **More.** Start here plus glossary, Saved, My ticket, Arb calculator, Release schedule, Data status, Discord, X,
  Feedback, Responsible gaming (1-800-MY-RESET).

The working prototype is in `site/`. Preview: `python3 -m http.server 8790 --directory ~/Projects/sports-dev`, then
open `/redesign/site/`.

## 2. Brand

- **Name:** "Kook'n". "Best bets" = the daily official plays.
- **Logo:** a winning-ticket K with a chef hat and a green ✓ stub, plus the KOOK'N wordmark with a green flame
  apostrophe over SPORTS (`brand/`).
- **Palette and results:** casino felt with green (hit / brand) and red (miss). Results are green / red tickets. See
  `design/brand.md`.

## 3. Results: same or better

Props are the only category beating the closing line. Game lines aren't. The plan, all shadow-tested first and each
needing its own owner yes (`proposals/RESULTS.md`):

| Step | Change |
|---|---|
| R0 | Count each game once in learning |
| R1 | Take CFB totals at the opener |
| R2 | Take NFL totals off the official card |
| R3 | Per-market prop calibration |
| R4 | Stale-price guard |
| R5 | Hide steep alternate trends |
| R6 | Better line shopping inside free quotas |
| R7 | Closing-line value as the headline proof |

## 4. Growth (X, search, Discord)

- **X:** the new card system, fewer and better posts (ceilings of 12 / 5 / 3 by day type), a tighter bio, a pinned
  "Start here" post, the new banner, and 25 minutes a day of the owner's own replies (`social/X-PLAYBOOK.md`).
- **Search:** static game, player and pick pages with real titles, OG images and a sitemap. Free calculators as
  search magnets (odds converter, no-vig fair price, parlay, EV, arb).
- **Discord:** stays the first-alert channel; best bets land there 10–15 minutes before X.

## 5. Money (later, only after the SUBSCRIPTION-PLAN.md gates)

1. **Separate from MGL.** keenroudy.com is the owner's personal homepage and mentions MyGolfLinks. Before charging,
   Kook'n gets its own domain (about $10/yr, the only paid item; `*.pages.dev` is free).
2. **Hosting.** Move to Cloudflare Pages / Workers (free). GitHub Pages bars primarily commercial sites.
3. **Real gating.** Signed session → D1 entitlements → premium data from a private R2 bucket. Premium data never sits
   in the public repo.
4. **Billing.** Whop first (allows betting picks and analysis, gates a Discord role). Stripe needs written approval.
5. **Pricing.** Against props.cash at $19.99/mo. Always free: best bets, the record, the scorecard, basic research.
   Pro: full board filters, alerts, saves across devices, deep trends.
6. **Rights first.** The free site keeps ESPN logos and photos (owner's call). Before any paid launch, settle image and data rights (license, owned art or removal) and move raw odds captures out of the public repo.

## 6. Handoff

`HANDOFF-CODEX.md` holds the phases (C0–C7), gates, AGENTS.md entries, status items, tests, QA checklist and
rollback.
