# Public website boundary

The Pages upload is the complete `site/` folder. Hiding a field or tab is not access control.
`scripts/publication_guard.py` now checks that exact folder after generation and before upload; it performs no
network calls and changes nothing. New file families require a reviewed allowlist update and fixtures.

## Reviewed public families

| Family | Public purpose |
|---|---|
| Site HTML, CSS, JavaScript and approved brand assets | The application itself, including the lazily loaded `app-more.js` and `app-games.js` (the Games list, live scores, game and team pages; same on-demand mechanism, fingerprinted by content); contains no authenticated premium boundary. |
| `kookn-mark.png` | 512-pixel ticket-mark avatar for the existing Discord publisher; `kookn.jpg` remains the legacy card asset. |
| `kookn-chef.png` | Owner-supplied clay-chef publisher avatar as of October 7; the server retains the ticket mark and immutable legacy attachments stay unchanged. |
| Dated NFL/CFB trend `-part-N.json` files | Complete player/stat groups split at one megabyte and loaded through the existing trend index. No threshold rows are omitted. |
| `data/research.json`, `forecasts.json`, scoreboards | Published selections, original forecasts, corrections and honest performance evidence. Preserve them. |
| Schedule, sports, line catalog, histories, identities, depth and research context | Existing public factual research and provenance; commercial permissions remain in SOURCE-RIGHTS.md. |
| `data/desk-notes.json` | Already-validated, bounded homepage research notes. Not the private operating desk. |
| `data/app/today-hero.json` | Today's first paint, under 4 KB (`payload_budget.py` limit; the builder trims to 3.5 KB): today's unsettled best bets, plus the next on-the-card game day for a league with none today, copied from the published rows (title, price, book, kickoff, posted chance and break-even, the card's `data/cards/` path), the Climb's status from the rung ledger and the last graded game day's W-L. No new fact, price or pick; the full `today.json` replaces it on arrival. |
| `data/app/` reviewed routes | Derived page data with projections, histories, quotes, sample and freshness information. This includes the full `record.json` (including the current Climb route's ledger-backed steps and clearly labeled future plan), the small `lines.json` manifest with `lines-NFL.json` and `lines-CFB.json`, dated NFL/CFB trend shards plus their index, and the separate CFB defense table. |
| `data/feed.xml`, `data/cards/`, `img/` | Approved public feed and artwork, including the current `data/cards/climb-route.png` rebuilt from the ledger and slate each publish. Do not rewrite posted attachments merely for a new look. |
| `kookn-chef-clip.png` | The 128-pixel copy of `kookn-chef.png` for the Kitchen Ticket chef clip on the rail (owner, Oct 7, decision 22). Exactly this one root file. |
| Kitchen Ticket fields in `today.json` / `today-hero.json` | `prep` (Prep List rows chosen by `build_site.prep_list` from the trend shards), `lastSlate`, `season` (the current-season best-bet W-L), and on straight plays `side`, `ticketWhy`, `ticketBut` (saved reasons, verbatim or a named template, guarded), `hitStrip` (stored box-score values), `held` (the A-22/A-23 hold kind on the play's market, with its real `recentFull` volumes) and `quote` (the latest fresh same-book board quote, never from a held row); the hero also carries each game's two teams' names and colours. `deskRuns` stays only in ignored `work/desk-status.json`, never these public files. No new public file family, price or pick. |
| Held line fields in `lines-<L>.json` | `roleHold` ('workload' or 'qb'), `recentFull` (three real full-game volumes) and `recentVolume` on rows already under a role hold; never the held projection. |
| Game context in `today.json` and `games/<id>.json` | `gap`, `tier`, `window`, `conference` (from the game or the dated `data/team-conferences-cfb.json` table, the public ESPN standings feed), `ranked` when stored, numeric `bettable` and checked `bettableParts`, the strip's `look` line, `plainGap`, `garbageTime`, and `whyDiffer` (the larger difference's lead and drivers plus `markets.spread`/`markets.total`, each driver with its template `text`, `direction`, `weight` and the `numbers` it used) from existing forecasts, box scores, stored NWS weather and captured prices. These are research display fields, never play admission or a result. Player line rows also carry the descriptive 21+-point `garbageTime` flag. No new feed, price or file family. |
| `card` on `record.json` picks | The `data/cards/<id>.png` path of a play that went out (X or Discord delivery evidence), so the results calendar can link the card; `null` otherwise. The path, not a new image, fact or count. |
| `dossier` on new published play rows | The already-admitted play's bounded reasons, counterpoints, verified status reports, stored weather, DraftKings/FanDuel captured line history, original model-versus-line figure, existing history and public source links. The first captured price is labeled `firstCaptured`, not a sportsbook opener; `open` stays null without true opening evidence. Missing evidence remains absent or explicitly partial. It consumes no extra research or odds requests and changes no grade or record. |
| `data/app/vegas.json` | Vegas vs reality (owner approved Oct 7): closing-line accuracy by league, computed at build time by `scripts/vegas.py` from the committed football, basketball and soccer stores. Counts, rates, average misses, seasons, sources and computed facts only; no picks, live prices or private fields. Exactly this one path; 64 KB warning budget. |

The check rejects unknown paths, symlinks, known owner-only files, credential-bearing JSON fields and selected
recognizable token/webhook patterns. It reports only file paths and reason codes, never matched values. Private
health/reliability, live pilot state, raw posting logs, keys and unreviewed policy exports do not belong in `site/`.

This narrow guard is not a complete secret scanner, an image-content inspector, a license clearance, or a promise
that existing published research/model outputs are proprietary. It deliberately does not delete provenance or
change stored records. Future premium fields need a reviewed server-side entitlement boundary; do not add a hidden
public JSON file and call it paid access. No accounts, billing, feed expansion or data removal is authorized here.
