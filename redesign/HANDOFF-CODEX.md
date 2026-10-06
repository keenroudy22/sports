# HANDOFF-CODEX.md: Kook'n redesign, everything Codex needs to implement it

Owner approved on 2026-10-06 in a Claude session. This file is a plan, not a permission slip: **AGENTS.md stays the
authority.** Phase C0 adds the owner's dated decisions to AGENTS.md; until then, follow AGENTS.md as written.

## 0. Ground rules for this work

- **Location.** Work happens in `~/Projects/sports-dev` on branch `dev`, deployed with the exact lock-holding script
  in AGENTS.md. Never edit `~/Projects/sports` by hand.
- **`redesign/` stays local and is never committed.** The repo is public, and this folder holds strategy docs and
  X analytics. It hides itself (`redesign/.gitignore` contains `*`).
  - **Port** its code into `site/`, `scripts/` and `tests/`, and its decisions into `docs/` and AGENTS.md.
  - **Never** `git add -f redesign/`. Never run `git clean -x` in sports-dev (it would delete `redesign/` and `work/`).
- **Preview locally.**
  - Start `python3 -m http.server 8790 --bind 127.0.0.1 --directory ~/Projects/sports-dev`.
  - Open `http://localhost:8790/redesign/site/`.
  - The prototype reads live JSON from `https://keenroudy.com/sports/data/` first, then `../../site/data/`.
  - Port 8765 belongs to `browser-audit.mjs`, so don't use it.
- **Baseline before any change** (2026-10-06, commit 3dde7bd6):
  - 880 Python tests OK (2 skipped) and 130/130 node tests.
  - Live assets: app v116, core v68, css v77.
- **Prototype tests:** `node --test redesign/tests/*.test.js` (19 tests, all passing). They resolve the shared
  `site/core.js` whether they sit in `redesign/tests/` or `tests/`.

## 1. What the owner decided (quote these into AGENTS.md at C0)

1. **Site direction: Hybrid A + B.**
   - Today is plain English and beginner-first, built around best-bet "tickets": price + book, "We think this hits
     54%. At +101 you only need 50%", a chance-vs-needed meter, fair price, edge, why, and one visible "what could
     go wrong".
   - Research is one sortable board (Edge default), replacing Board / Best lines / Prop lines / Game lines /
     Trends / Charts.
   - Story-style share cards make the site and X look the same.
2. **Navigation:** Today · Research · Games · Record · More. Every old hash link keeps working (§4).
3. **Name and words.**
   - The brand is "Kook'n". "Best bets" is the public name for the official plays: the same append-only set, gates,
     caps, grading and record. It adds no play, post, market or rule.
   - The research label "Best lines" is retired so the two can't be confused.
   - Public copy drops "official card", "plate", "Served at", "desk" and "priced reads".
   - Internal names (`KEENROUDY_*`, `com.keenroudy.sports.*`, `~/.config/keenroudy`) do not change.
4. **Palette: "casino felt".** This replaces navy/mint/cyan for the website and new card art.
   - Felt night `#07120D`, felt `#0E2219`, raised `#15301F`, line `#21412F` / `#3D7356`.
   - Chalk `#F2F7F4`, dim `#A9C0B3`.
   - Kook'n green `#20C774` (brand + hit). Chip red `#F2414E` for fills only, with `#FF6B75` for red text.
   - Dark ink on green and red fills.
   - Green = hit or support, red = miss, gray = unknown, always with ✓ / ✗ / – and a word. Brand green must never
     suggest a result on an open play.
   - Brown/tan/amber stay banned.
5. **Results show as tickets:** a green ✓ ticket for a hit, a red ✗ ticket for a miss, a gray ticket for a push.
   "Kook'd" / "Burnt" are optional caption flavor.
6. **Team logos and player photos stay** (owner, 2026-10-06): ESPN logos and headshots on the site and cards, as today, with the team-color badge as the fallback when an image fails. The rights question (`docs/SOURCE-RIGHTS.md`, P08) is revisited only before any paid launch.
7. **Logo:** the winning-ticket mark (a chalk ticket, felt "K", tilted chef hat, green ✓ stub) plus the KOOK'N wordmark
   with a green flame apostrophe over SPORTS. Files are in `redesign/brand/`. Whether the X avatar changes is the
   owner's call. The 3D chef stays as a personality character.
8. **Results proposals:** each is shadow-tested and needs its own owner yes (§7). None is pre-approved.
9. **X banner and bio:** Both are already live. Claude updated them on 2026-10-06 with the owner's go, as a one-time attended exception to "no browser automation on X".
10. **Not approved by any of this:**
   - analytics or a metrics collector
   - buying a domain or editing the personal homepage
   - Cloudflare hosting, Whop, payments or referral links
   - new post types or higher post frequency

## 2. Map: redesign file → real destination

| Prototype | Destination | Notes |
|---|---|---|
| `redesign/site/index.html` | `site/index.html` | Drop the `kr-data` meta and `noindex`; script paths become `core.js?v=69` etc.; add og:image, twitter:card, theme-color `#07120D` |
| `redesign/site/app.css` | `site/app.css` | Tokens at the top mirror `redesign/design/tokens.css` |
| `redesign/site/app.js` | `site/app.js` | Same UMD shape: `{model, boot}`; data base becomes `data/`; remove the live-URL fallback |
| `site/core.js`, `live.js`, `personal.js` | unchanged | The prototype already loads the real files; their tests carry over |
| `redesign/tests/model.test.js` | `tests/redesign_model.test.js` | Its resolver already finds `../site/` |
| `redesign/brand/*.svg`, `png/` | `site/favicon.svg` (mark), `site/img/` (lockups, OG default) | `img/` images already pass the guard |
| `redesign/social/cards.py` | `scripts/pick_card.py` (`modern_svg`, `receipt_svg`, `ladder_svg`, `ladder_result_svg`, `ticket_svg`), `scripts/sheet.py` `svg`, `scripts/research_art.py` `svg` | §6 |
| `redesign/copy/glossary.md` | in-app Start here + `docs/POSTS.md` voice section | |
| `redesign/proposals/*.md` | `docs/RESULTS-PROPOSALS.md`, `docs/PUBLIC-PAYLOADS.md` | |

## 3. Phases and gates

Every phase:
- ships through AGENTS.md's deploy script;
- gets a `docs/product-status.json` item;
- passes gates G1–G6 before the next phase starts.

| Phase | Work | Done when |
|---|---|---|
| **C0 Rules** (P16) | Add the AGENTS.md entries in §8 at the top of "The owner's current rules". Update POSTS.md (palette, no portraits, voice), PRODUCT-IMPLEMENTATION.md, SUBSCRIPTION-PLAN.md ("no public rebrand" superseded) and PUBLIC-PAYLOADS.md. Add the status items in §9. | Released; the weekly review shows P16 as next ready |
| **C1 Preview** (P17) | Publish `site/next/{index.html,app.js,app.css}` using `../core.js` etc., reading `../data/`, `noindex`, canonical `/sports/` | Live at 320–1440 px with no console errors; `/sports/` unchanged; owner approves on a phone |
| **C2 Parity tests** (P18) | Port the old app contracts to new tests (§5); add record parity and route tables | Both suites green on Codex's Node and the launchd Node |
| **C3 Swap** (P19, owner-gated) | One commit replaces the front end, retires and replaces tests, removes `site/next/` and its guard entry, bumps `?v=` | Live checks pass; the next desk run and publish are green; the rollback SHA is recorded |
| **C4 Data** (P20, P22) | Build-time display fields, slimmer payloads, RSS fix (§10) | `record_audit` and the guard pass; Today avoids `trends.json` and `slate.json` |
| **C5 Cards** (P21) | Felt templates with a cutover date, embedded open font, card cache (§6) | Owner approves the renders; quiet-window cutover; same card on X and Discord |
| **C6 Shadows** (P23 → P24) | Results proposals logged silently (§7) | Four weeks of counts per proposal; the owner says yes or no |
| **C7 Later** (P25–P28) | Domain, SEO pages, pinned post, image-rights decision before any paid launch, Cloudflare/Whop only after the `SUBSCRIPTION-PLAN.md` gates | Owner decisions recorded |

**Gates:**
- **G1:** Both suites pass:
  - `python -m unittest discover -s tests`;
  - `node --test tests/*.test.js`, run with both Codex's `node` and `/Users/keen/.nvm/versions/node/v22.16.0/bin/node`
    (the launchd path, `run.sh:19`).
- **G2:** `build_site.py`, then `record_audit.py`, then `publication_guard.py`, all exit 0.
- **G3:** `rehearse.py --slot <current window>` returns `ok` with zero outside writes.
- **G4:** `AUDIT_URL=… node tests/browser-audit.mjs` at 320/375/390/430/768/1280/1440 px, plus a 1.3× text scale run.
- **G5:** Locked deploy, then `gh run watch --exit-status`, then live checks at 375 and 1440 px.
- **G6:** The next scheduled desk run is clean.

Pin Node 22 in `publish.yml` with `actions/setup-node`. CI currently uses whatever the runner ships.

## 4. Contracts the swap must keep

- **Every old link resolves.** The full table is `model.resolve` / `model.canonical` in `redesign/site/app.js`, tested
  in `model.test.js`.
  - Old hashes are rewritten with `history.replaceState`.
  - `#pick/<id>` (RSS and X), `#game/<id>`, `#player/<L>/<id>` and `#team/<L>/<id>` never change.
  - Shared research links that carry a query string (`#stats?…`, `#board…?market=&sort=`, `#trends?…`) must map to
    the new filters. Board sort `best` → edge, `confidence` → chance, `time` → kickoff. Extend `resolve` with
    `C.researchContext` for the remaining parameters.
- **`core.js` stays as it is.** Its `routePath`/`LEGACY` stay, and so do the record functions (`recordBreakdown`,
  `recordArchive`, `theRecord`, `theLadder`, `unitsFor`). The record counts exactly as today. The new Record view
  reads them unchanged, backed by a parity test.
- **The exact AGENTS.md copy stays where it applies:**
  - "being checked · not posted yet"
  - "Past steps"
  - "about 10–15 minutes before X"
  - expired-quote and delivery labels (`C.deliveryText`, `C.quoteStatus`)
  - "Covering does not mean winning outright" (where an underdog spread shows)
- **Browser storage:** existing `kr:` keys (`league`, `ticket`, `stake`, `arb`, `watchlist`, `research-preferences`,
  `usage`) are read and written in the same shapes. New keys: `kr:board`, `kr:onboarded`.
- **Page structure:** keep a `#view` container and exactly one `h1` per view, because `browser-audit.mjs` waits for
  `#view h1`.
- **Card filenames, sizes and Discord's 8 MB limit are a contract** with Buffer and Discord (`POSTS.md:135-140`).
- **Play states (`model.pickVM().mode`).** `open` gets the pitch ("We think this hits…"), the meter and the green
  stub. `expired` (quote past its limit, no entry note) says "Old price · graded at −110 (Book)", past tense, gray
  stub. `closed` (Line moved / Pulled / Withdrawn / In play) shows the desk's `entryNote`, no pitch, no meter, gray
  stub. Never the words "Price expired" in public copy (owner).
- **Best-bet matching (`model.officialKey`).** A board row is badged "Best bet" only for an open pick with the same
  game, athlete, stat (props) or market kind (game lines) and side; a posted but not-open pick shows "On the card".
  Anything already on the card stays out of Today's "Worth a look".
- **Today order:** Pick of the Day → the Climb strip (status, ledger, Past steps with exact legs) → the other best
  bets; then Last game day, Also on the card, Waiting on results, Pulled before kickoff, the Discord card, Fun
  tickets, Worth a look, Underdog watch (outright candidates fresh within 4 h; spread value kept separate), Today's
  games (live-merged, no strength ranks). Non-football sports get their own Today with scores and the trial tracker.
- **Refresh:** live views re-render every 60 s and on tab focus, never while an input/select/textarea is focused,
  never on Feedback/Arb; data keeps its 5-minute cache; a newer render always wins (`renderToken`). Calculators update
  only their result box.
- **Link filters apply once.** `#research?type=&sort=&q=&sport=` (and legacy `#board…`, `#trends…`, `#today?sport=`)
  set the filters when the link is opened; the reader's own choices win after that.
- **History after the C4 split:** the prototype's `allPicks()` merges the history file with `today.json`, and
  `#pick/<id>` falls back to it. It requests the file only when `today.json` names it (`"historyFile": "record.json"`),
  so there are no 404s before C4. C4 must add that field together with `data/app/record.json`.

## 5. Tests to retire and replace at the swap (44 → at least 44 new)

These tests regex-extract function bodies from the old `app.js` / `app.css` and will break:
- `tests/app.test.js`: all 25.
- `core.test.js`: "game pages show next-up depth…" and "app.js parses".
- `desk-notes.test.js`: test 2.
- `player_history.test.js`: the 11 view-level tests (from line 85).
- `research_workspace.test.js`: tests 2–6.

The swap PR lists each retired test next to its replacement. The other 86 stay as they are.

Replacements build on `redesign/tests/model.test.js` and add:
- `ui-playcard`: order is POTD → Climb → rest; expired quotes are never "Open"; closed, pulled and withdrawn plays
  never show the pitch or meter; the raw projection appears only in "How we got this". (`model.test.js` already
  covers the view-model half: 23 tests.)
- `ui-board`: fresh-only filter, same-line best price, official match.
- `ui-record`: the headline equals `recordBreakdown`; the chart ends at captured units.
- `ui-render`: `vm.Script` parse check plus the AGENTS wording above.
- `ui-contrast`: token pairs ≥ 4.5:1 for text.

## 6. Social cards: port the felt templates safely

- **Templates:** `redesign/social/cards.py`. Samples: `redesign/social/samples/*.png`. Render with
  `render_samples.py`.
- **The hosted build redraws every live card on every run.** `site/data/cards/` is gitignored, there's no cache, and
  `feed.render_cards` only skips files that already exist.
  - Add a `FELT_FROM` cutover timestamp.
  - Each builder uses the old template when the item's date (`publishedAt`, receipt day, rung `settledAt`, sheet or
    research day) is before the cutover. Already-posted art never changes.
  - Also add an `actions/cache` restore/save around the `feed.py` step.
- **Fonts.** CI renders on Ubuntu, which has no Helvetica Neue.
  - Embed an open-licensed font (Barlow Condensed and DM Sans are both SIL OFL) as base64 `@font-face` in the SVG,
    with `OFL.txt` committed beside it.
  - The prototype samples load Google Fonts at render time; production must not depend on the network.
- **Layout and rules:**
  - Keep `sha256(id)[0] % 3` ticket-style rotation.
  - Fit 1080×1350 for up to 5 legs; grow only beyond that.
  - Research cards move from 1200×675 to 1080×1350.
  - Type floors: hero ≥ 96, hook ≥ 64, numbers ≥ 56, rows ≥ 40, labels ≥ 30, footer ≥ 26 px.
- **Keep ESPN art on cards** (owner's call): `pick_card.artwork()` already fetches the player photo or team logos as data URIs. Pass that `art` into the felt builders (`cards.play_card(..., art=...)` draws the photo in a ringed circle and logos in the team chips). `cards.team_chip` (team color + abbreviation) stays as the fallback.
- **Footer on every card:** `21+ · Entertainment only · Gambling problem? 1-800-MY-RESET` plus the site URL.
  1-800-MY-RESET is the National Council on Problem Gambling's national number since early 2026; 1-800-522-4700
  still works.
- **Captions keep the `x_post.draft` shapes.** Every variant passes `x_post.guard` and `llm.check_style`, with a test
  in `test_x_post.py`.
- **Tests to update:** `test_pick_card.py`, `test_modern_art.py` (it asserts portraits today), `test_research_art.py`,
  `test_sheet.py`, `test_receipts.py`.

## 7. Results proposals (shadow first; each needs its own owner yes)

Details and success bars are in `redesign/proposals/RESULTS.md`.

**R0 comes first:** `learn.joined()` double-counts games (up to 7 rows per game). Add `learn.distinct()`, use it in
every shadow report and in `learn_segments` sample counts, and show the owner the before and after numbers.

| ID | Proposal | Owner question |
|---|---|---|
| R1 | Take CFB totals at the opener: move the one daily early capture to Sunday evening; allow up to 2 of 3 Saturday slots to fill Sunday–Tuesday | Shift capture timing (no extra credits)? |
| R2 | Take NFL game totals off the official card; they keep grading as research | Override the Oct 4 "not a veto" rule for this one market? |
| R3 | Per-market prop calibration where 300+ graded lines beat the pooled number on held-out dates | Adopt per market when it wins? |
| R4 | Stale-price guard: props ≤ 3 h, game lines ≤ 6 h before publishing | Fewer plays in exchange for fresher prices? |
| R5 | Hide alternate-line trends priced shorter than −300 (131 of 208 alt rows) | Display-only change OK? |
| R6 | Better line shopping inside free quotas (pace Odds API credits; probe SharpAPI game totals) | After a terms check |
| R7 | Closing-line value as a Record headline, with price-aware CLV | Public headline change |

Shadow verdicts go to `data/learning/shadow-<season>.jsonl` and are graded by the existing `learn.grade_pending`. The
market supplies prices, gates and grades only; it is never blended into the model (MIGRATION.md §4d).

## 8. AGENTS.md entries to add at C0 (newest first, matching the file's style)

- **Casino-felt palette (2026-10-06, owner approved):**
  - Kook'n site and new card art use felt night #07120D, felt #0E2219, chalk #F2F7F4, dim #A9C0B3, Kook'n green
    #20C774 and chip red #F2414E (fills only; #FF6B75 for red text). This replaces the navy/mint/cyan foundation of
    Oct 1/2/5.
  - Green = hit or support, red = miss, gray = unknown, always with a symbol or word. Brand green never implies a
    result on an open play.
  - Text stays at WCAG AA. Dark ink goes on green and red fills.
  - Brown/tan/amber stay banned.
  - Cards choose their theme by publication time; posted attachments never change.
- **Kook'n best bets (2026-10-06, owner approved):**
  - "Best bets" is the public name for official plays, with the same set, gates, caps, grading and record. It is
    never advice.
  - The research "Best lines" label is retired. Public copy drops "official card", "plate", "Served at" and "desk".
  - Internal names are unchanged.
  - Entertainment-only and 21+ wording stays on every page and card. This supersedes "no public rebrand" in
    SUBSCRIPTION-PLAN.md.
- **Website redesign (2026-10-06, owner approved; supersedes the Oct 5 navigation once swapped):**
  - Today · Research · Games · Record · More.
  - Today shows beginner-first best-bet tickets (published price and book, stored calibrated chance vs break-even,
    fair price, edge, why, one visible counterpoint, hit chart). One sortable Research board replaces the line and
    trend tabs.
  - It ships first as a noindex preview at `/sports/next/` and swaps only after owner sign-off.
  - Every existing hash, `#pick/<id>` and shared research link keeps opening its equivalent view.
  - Confidence badges are removed; value rank (edge) is the default sort.
  - Thin, stale, unpriced and uncalibrated rows get no rank. Main lines stay the default, with the 4-hour freshness
    limit and the 3-game minimum.
  - Record math reuses core.js unchanged.
- **Share cards and X (2026-10-06, owner approved):**
  - Existing categories are restyled only. Filenames, dimensions and Discord's 8 MB limit are unchanged.
  - Captions keep the Sept 26 shape; chance and break-even live on the card.
  - No new post type, slot, frequency, Playbook use or automation. The owner sets the bio, pinned post and banner and
    writes replies by hand.
  - Claude may upload the new banner once, attended.
  - ESPN player photos and team logos stay on site and card art (team-color badges are the fallback).
- **Results proposals stay in shadow (2026-10-06, owner approved process):**
  - R0–R7 run as silent, logged shadows. They make no new metered requests and change no play, card or record.
  - Each needs its own owner yes, with before/after counts.
  - The NFL-totals pause would override the Oct 4 "not a veto" rule only on that yes.
- **Redesign boundaries (2026-10-06):**
  - Each new public file type gets a narrow guard entry, test fixtures and a PUBLIC-PAYLOADS.md line; never a
    wildcard.
  - New built data only adds files under `site/data/app/`. Tracked schemas, `record_audit.py` and integrity checks
    don't change.
  - The RSS feed is renamed "Kook'n" and keeps its item IDs.
  - Not approved: analytics, domain purchase, homepage edits, Cloudflare, Whop, payments, referral links.
- **Logos and photos stay (2026-10-06, owner approved):** keep ESPN team logos and player headshots on the website and cards, with team-color badges as the fallback. SOURCE-RIGHTS.md stays open; revisit before any paid launch (P08).

## 9. `docs/product-status.json` items to add

Constraints:
- Statuses and owners must be ones the validator accepts (`product_followthrough.py:13-18`).
- Fields are 240 characters at most (500 for evidence), with no newlines; 40 items maximum.
- Start each evidence field with "Owner approved 2026-10-06; plan in owner's local redesign/ folder".
- Bump `updatedAt`. Update P09's next action to name Whop and Cloudflare as candidates.

| ID | Title | Status / owner | Next action | Done when |
|---|---|---|---|---|
| P16 | Redesign rules and docs | ready / agent | Add the §8 entries; update POSTS, PRODUCT-IMPLEMENTATION, SUBSCRIPTION-PLAN, PUBLIC-PAYLOADS | Released; `read_status()` lists it |
| P17 | Felt preview at /sports/next/ | ready / agent | Port the prototype with relative data and the shared core.js; noindex; narrow guard rule + tests | Live preview passes G4; /sports/ unchanged |
| P18 | Route and record parity tests | ready / agent | Table-test every legacy hash and shared link; record parity; port the app.test.js contracts | Green on both Node binaries |
| P19 | Front-end swap | gated / owner | Owner reviews /sports/next/ on a phone | Swapped, versions bumped, live checks, next desk run green, rollback SHA recorded |
| P20 | Additive display data | ready / agent | Fair price, quote age, safe projection and slim files under data/app with size-budget tests | record_audit and guard pass |
| P21 | Felt share cards | ready / agent | Shared tokens; theme by publication time; embedded OFL font; render every category | Owner approved renders; quiet-window cutover |
| P22 | RSS fix and rename | ready / agent | Rolling 30-day feed of first publications and daily receipts; keep GUIDs | Released; feed shows items on a no-play day |
| P23 | Results shadows | ready / desk | R0 then R1–R7 behind default-off flags; weekly review section | Four weeks of counts per proposal |
| P24 | Results decisions | gated / owner | Review before/after counts | Each proposal approved or declined with its own dated rule |
| P25 | Separate domain | owner-needed / owner | Choose and buy a domain (the one paid item) | Redirects keep query and hash; Buffer and Discord verified |
| P26 | SEO pages, sitemap, OG images | gated / agent | Start after P25 | Guard passes; owner submits the sitemap |
| P27 | X profile refresh | owner-needed / owner | Banner and bio done (updated by Claude with the owner's go, 2026-10-06). Remaining: pinned "Start here" post | Owner confirms |
| P28 | Image rights before paid launch | gated / owner | Owner keeps ESPN logos and photos for the free site (2026-10-06); before any paid launch, decide under P08 (license, owned art, or remove) | Decision recorded |

## 10. Data and guard changes (C4, C7)

Full spec: `redesign/proposals/DATA.md`.

- **RSS:**
  - `feed.build` (L195) only appends `pick_items`, which emits a play only inside `feed.in_window` (game day, 9 AM
    until 45 minutes before kickoff) at build time. Most builds therefore publish an empty channel.
  - Make it a rolling 30-day feed with one item per official first publication (guid = pick id) and one per daily
    receipt.
  - Retitle it "Kook'n". Posting is unaffected: Buffer and receipts use `feed.postable`, not the file.
- **Display fields:**
  - In `build_site.grade_line` (L1045): `fairOdds`, `ev`, `chanceDisplay` (null unless calibrated), `range80`.
  - On line rows: `ageMinutes`, `freshness`.
- **Payloads:**
  - Split `trends.json` (4.7 MB; 95% unpriced milestones) per league and day, storing each history once.
  - Keep open picks plus 72 hours in `today.json`; move history to `record.json`.
- **SEO pages:** done by a separate hosted step (`scripts/static_pages.py`, not `build_site.build`, which the desk
  calls every run):
  - `/sports/game/<id>/`, `/sports/player/<L>/<id>/` and `/sports/pick/<id>/`, with real titles, descriptions,
    og:image and JSON-LD;
  - plus `sitemap.xml`.
- **Guard (narrow regex entries only):**
  - `ROOT_FILES += sitemap.xml`.
  - Page regex `(?:game/(?:NFL|CFB)-\d+|player/(?:NFL|CFB)/\d+|pick/(?:NFL|CFB)-[A-Za-z0-9-]+)/index\.html`.
  - `APP_FILES += record.json`, plus the trends split regex.
  - `next/` during C1 only.
  - Fixtures go in `test_publication_guard.py`, with a row in PUBLIC-PAYLOADS.md.

## 11. QA checklist

- [ ] No sideways overflow and zero console errors at 320/375/390/430/768/1024/1280/1440 px
- [ ] 200% zoom; keyboard focus visible; Escape and Back behave; one `h1` per view; focus moves to it on navigation
- [ ] Text contrast ≥ 4.5:1; color is never the only signal; meters have text labels
- [ ] Every state renders: no plays today, open, settled, pulled, line moved, price expired, stale quote, missing
      quote, POTD present and absent, Climb open and unposted, unsupported sport, FCS game
- [ ] Copy passes `llm.MARKETING` / `llm.ADVICE`: no "lock", no "guaranteed", no advice wording
- [ ] Record headline equals the current site's numbers for the same season and stage
- [ ] Old `kr:` storage from the current site is read correctly by the new one
- [ ] Card filenames and sizes are unchanged; cards stay under 8 MB; posted cards are byte-identical after a rebuild

## 12. Rollback

- `git revert <swap sha>` on dev, then the normal locked deploy. Never force-push or reset main, because the desk and
  CI push to it all the time.
- HTML caches for about 10 minutes. Any follow-up uses a new `?v=` number.
- Card theme rollback is a new dated cutover entry; it never redraws published cards.
- Results policies roll back with their flags.

## 13. Open questions for the owner (Claude asked; answers pending)

1. Where is `kookn-product-plan-2026-10-05.html`? Is anything in it still pending?
2. Why is `reasoning` null on all picks? Could `build_site.py` publish structured reasons again? The prototype parses
   the `why`/`risk` text instead.
3. Where do the "Book unavailable" rows and the "ESPN BET" name come from? Fix them at the source. The prototype
   relabels "ESPN BET" as theScore Bet (rebranded Dec 1, 2025) and hides unavailable books.
4. When is a quiet window for the card cutover?
5. Does the Buffer free queue limit (about 10 per channel) ever bind today?
6. What is the current state of P06, P08 and P09?

**Owner decisions the prototype leaves switched off** (`OWNER_FLAGS` in `redesign/site/app.js`; flip only with a
dated owner yes in AGENTS.md):

7. **R7, closing-line value as a headline.** `clvHeadline: false`. Until then the KPI strip shows Pick of the Day
   W–L, and CLV appears only on Record › Model vs market (with its definition) and on each receipt
   ("beat the close by 2").
8. **A public ROI number.** `roi: false`. The old site never showed ROI; showing it changes how the record is
   presented. If approved: units at captured prices over units staked, from 10 priced plays.
9. **R5, heavy favorites in Trends.** Shown by default, tagged "Heavy favorite" with "price needs N%", and a
   "Hide heavy favorites" chip. R5 proposes hiding only alternates shorter than −300 by default.

## 14. Parity review results (2026-10-06, before handoff)

Two independent multi-agent reviews compared every feature of the old site (`site/app.js`, `core.js`) with the
prototype, and a skeptic agent re-checked each finding:
- **Review 1:** 183 findings, 150 confirmed. All high and medium items were fixed.
- **Review 2:** checked against the fixed code. 135 of the earlier gaps are confirmed closed, and its 69 new or
  remaining items are fixed.
- **Then:**
  - 39 routes rendered at 1280 px and 26 at 375 px: one `h1` each, no console errors, no sideways scroll, and no
    "undefined", "NaN" or "Price expired" text.
  - `redesign/tests/model.test.js` 23/23 passing. The repo suites are unchanged at 130 Node / 880 Python.

**Deliberately not ported, or waiting on data or a decision (put these in `docs/product-status.json`):**
- `#lab` shows Record › Trials instead of the old "In the kitchen" roadmap. `#digest` folds into Today.
- Expanded prop rows still lack the old role line (`C.roleOf`) and the last-5 / prior-season defense ranks.
  The board has no market chips; search covers it.
- Neutral-site games: team pages print "–" for the closing spread, because the pipeline does not store which side was
  listed at home. Store it (for example `listedHome`), then sign the spread and include those games in ATS.
- `reasoning` is null on every pick, so the prototype parses `why`/`risk` text (§13 Q2). Context lines show with a
  neutral bullet, and a hit count shows only as History, never as a ✓ reason.
- Owner flags R7, ROI and R5 (§13 items 7–9).
- The X analytics figures in `AUDIT.md` become public when C0 commits `redesign/`. Confirm with the owner, or move
  them to a private note first.
