# Data, speed, search and guard changes

All additive. Tracked schemas, `record_audit.py` and integrity hashing stay as they are. Every new public file
family gets a narrow `publication_guard.py` entry, a fixture in `tests/test_publication_guard.py` and a line in
`docs/PUBLIC-PAYLOADS.md`. Never a wildcard.

## 1. Display fields the new site wants (build_site.py)

The prototype computes these in the browser today (`model.lineVM`, `model.pickVM`). Moving them to build time keeps
the math in one tested place and makes the payloads self-explanatory.

| Where | Field | Rule |
|---|---|---|
| `grade_line` (L1045) | `fairOdds` | American odds of the calibrated `chance`; null unless `calibrated` |
| | `ev` | `chance × decimal(odds) − 1` |
| | `chanceDisplay` | `chance` only when calibrated, not thin, not limited |
| | `range80` | from `forecast.players` or `v2.range` |
| line rows | `ageMinutes`, `freshness` | fresh ≤ 60 min, aging ≤ 4 h, stale beyond (the same 4-hour limit as `C.quoteStatus`) |
| line rows | `bestSameLine` | best odds among books quoting the same line, excluding comparison-only books |
| `board_picks` (L961) | `fairOddsAtPublication`, `quoteAgeMinutes`, `recordAsOfPublication` | Frozen at publication |
| books | provider + display names | Keep `book: "ESPN BET"` for selection, jurisdiction gates and stable ids; add `displayBook: "theScore Bet"` for the site (rebranded 2025-12-01). Drop "Book unavailable" rows from public lines. |

Also fix at the source:
- Game totals reach the site with no market type, so the old UI called them "Team prop".
- `reasoning` is null on all picks. Publish structured `reasons[]` / `cautions[]` so the UI doesn't have to parse
  sentences.

## 2. Slimmer payloads (phones first)

| File | Today | Plan |
|---|---|---|
| `trends.json` | 4.1–4.7 MB, 4,575 rows; 95% unpriced milestones; per-row histories are 35% of the bytes | Split into `data/app/trends/<LEAGUE>-<date>.json` plus `-milestones` files and `trends/index.json`; store each player-stat history once; update `core.trendWindow` to look them up |
| `today.json` | 455 KB; 91 picks of which 5 are open | Keep open picks plus the last 72 h; move the full list to `data/app/record.json` (Record loads it) |
| `teams/CFB.json` | 457 KB | Split the defense table from team metadata |
| `app.js` | 239 KB (70 KB gzipped) | The prototype is 278 KB (80 KB gzipped) after the full parity port. app.css shrinks from 78 KB to 33 KB, so the total is about even. |
| `kookn-chef.png` | 128 KB favicon | `favicon.svg` from `redesign/brand/kookn-mark.svg` (under 2 KB) |

Budgets for the new site: HTML + CSS + JS no larger than today, about 90 KB gzipped (the old site is 87 KB, the prototype 89 KB). Any minification must stay build-step-free. Today's first paint loads only `today.json` and
`desk-notes.json`; lines load right after. `trends.json` and player charts load only on their own screens.

## 3. RSS feed (currently empty most of the day)

`feed.build` (L195) appends only `pick_items`, which emits a play only inside `feed.in_window` (game day, 9:00 AM ET
until 45 minutes before kickoff) at the moment the hosted build runs. `recap_items` and `scoreboard_item` are never
appended.

Fix:
- A rolling 30-day feed: one item per official first publication (guid = pick id, unchanged) and one per daily
  receipt.
- `TITLE` becomes "Kook'n".
- Buffer, featured and receipts use `feed.postable`, not the feed file, so posting is unaffected.

## 4. Search pages (C7, after the separate domain)

Hash routes can't be indexed. Add `scripts/static_pages.py` as a hosted step after `feed.py`. Not in
`build_site.build`: the desk calls that every run, and untracked output would fail the deploy's clean check. Add its
output folders to `.gitignore`.

- **`/sports/game/<gameId>/`:**
  - Title: "{Away} vs {Home} prediction, odds and total ({date}) | Kook'n".
  - Description built from the projected score, line, book and capture time.
  - og:image is the open best-bet card, else `img/og-default.png`.
  - JSON-LD `SportsEvent`.
  - Links to `#game/<id>`.
- **`/sports/player/<LEAGUE>/<id>/`:** only for players with fresh priced main lines.
- **`/sports/pick/<id>/`:** a permanent page per best bet. og:image is `data/cards/<id>.png` while open, else the
  default.
- **Also:** `site/sitemap.xml`. The homepage repo controls `robots.txt`, so the owner submits the sitemap in Search
  Console.
- **`index.html`:** add og:image (felt lockup), `twitter:card=summary_large_image`, theme-color `#07120D`, and a
  per-view `document.title` (the prototype already sets it).

## 5. Exact guard changes

```python
ROOT_FILES |= {'sitemap.xml'}                       # robots.txt only once on our own domain
APP_FILES  |= {'record.json'}
# data/app/trends/(?:index|(?:NFL|CFB)-\d{4}-\d{2}-\d{2}(?:-milestones)?)\.json
# pages: (?:game/(?:NFL|CFB)-\d+|player/(?:NFL|CFB)/\d+|pick/(?:NFL|CFB)-[A-Za-z0-9-]+)/index\.html
# C1 preview only: next/(?:index\.html|app\.js|app\.css)   (removed at the swap)
# fonts/(?:[A-Za-z0-9-]+\.woff2|OFL\.txt)           only if fonts are self-hosted
PRIVATE_DIRS |= {'premium', 'shadow'}
```

## 6. Rights before money

- **ESPN.** Undocumented feeds, headshots and logos are tolerable for a free hobby site and unresolved for a paid one
  (`docs/SOURCE-RIGHTS.md`).
  - The owner keeps ESPN logos and photos on the free site and cards (2026-10-06). Team-color badges are the
    built-in fallback.
  - Before any paid launch, decide under P08: license the images, switch to owned art, or remove them.
- **Raw odds in the public repo.** It commits raw Odds API and SharpAPI captures (`git add data/odds data/prop-odds`
  in `publish.yml`), which conflicts with the raw-redistribution limits in SOURCE-RIGHTS.md. Before charging, move raw
  stores to private storage.
  - Making the repo private would likely exceed free Actions minutes; measure first. Each run takes 3–7 min and
    there are about 30 a day.
- **Paid tier (later, only after the SUBSCRIPTION-PLAN.md gates):**
  - Host on Cloudflare Pages / Workers (free tier). GitHub Pages disallows primarily commercial sites.
  - A Pages Function at `/api/pro/*` checks a signed HttpOnly session against a D1 `entitlements` table.
  - Premium data streams from a private R2 bucket uploaded by Actions; it is never written to `site/` or committed.
  - Use Whop first. It explicitly allows sports-betting picks and analysis, and can gate a Discord role. Stripe
    restricts gambling-adjacent businesses, so it needs written approval first.
