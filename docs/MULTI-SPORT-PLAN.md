# Kook'n other sports on free data: build plan for Codex (written 2026-10-06)

> **Changed Oct 7 by the owner:** focus on football, basketball and soccer only. NBA is built first (by Oct 20) instead of NHL; NHL and MLB get no new work. The order and scope in **SPORTS-FOCUS.md** override the release order and NHL milestones below. Everything else here (free-only rules, matching, stores, guards, gates) still applies.

## The answer first

The owner wants the football desk's features, and its posting, extended to other sports to draw a bigger audience. The free plans support it if every other-sport number comes from ESPN's public endpoints and other sports get **zero** Odds API, SharpAPI or SportsGameOdds requests. Release order:

- **Now:** NHL. The regular season is under way, ESPN's DraftKings props for it are priced, and its box scores are rich.
- **By Tue Oct 20:** NBA, ready for opening night. It is the biggest prop audience.
- **November:** men's college basketball.
- **From Sat Oct 17:** Premier League weekends.
- **Opening Day 2027:** MLB.
- **Last:** MLS and WNBA.

Website research ships first. Posting comes next and needs the owner's yes to a dated AGENTS.md rule (text supplied separately). Best bets, the Climb and fun tickets run silently in shadow in each new sport until that sport has its own calibration, settlement rules and a P11 owner decision. Today's backtests say basketball and soccer score models do not beat the closing line, so forcing picks early would most likely lose.

## Non-negotiables for every phase

1. **Free only.**
   - No new or reallocated Odds API, SharpAPI or SportsGameOdds request for any non-football league.
   - Add `tests/test_free_only.py`. It greps every new module for `the-odds-api.com`, `sharpapi`, `sportsgameodds` and fails if it finds them. New modules may call only `site.api.espn.com`, `site.web.api.espn.com` and `sports.core.api.espn.com`.
2. **Polite ESPN use.**
   - Python urllib's default User-Agent (the feed rejects custom ones; see `hoops_store.py`).
   - At least 0.5 s between requests, with a cap per run and a time box per run.
   - Stop after 3 consecutive errors and keep the last good data.
   - Run only on scheduled runs, never on hosted runs triggered by a push.
3. **Never invent a price or a side.**
   - ESPN prop items carry no over/under label.
   - An over/under price is stored only when its side is proven by an exact match to the same player's labeled milestone price in the same read (rule in M1.2). Otherwise keep only the line.
   - Freshness uses the desk's own `retrievedAt`, never ESPN `lastUpdated`.
   - A board read at or after the start is dropped.
4. **Append-only stores with a ledger.** Reuse `boxscores.append / ledger / verify / read_store / content_hash / write_json`. `scripts/integrity.py verify_store_history` already protects every `data/**/*.jsonl`. Each store has one writer: the Mac for pregame captures, the hosted workflow for box scores.
5. **The record does not change.** `leagues.OFFICIAL` must equal `{'NFL','CFB'}` until a P11 decision, enforced by a test. Trial, shadow and research results never enter the official record or Today's best bets.
6. **Website-first. New public file families each get:**
   - an explicit entry in `publication_guard.py`, never a wildcard;
   - test fixtures;
   - a line in `docs/PUBLIC-PAYLOADS.md`;
   - a limit in `payload_budget.py`.
7. **Deploy exactly per AGENTS.md "Changing the code and deploying":**
   - rebase `dev`;
   - pass both test suites;
   - run `scripts/rehearse.py --slot <current window>` (exit 0, outcome `ok`; missing network evidence is expected);
   - run `publication_guard.py` and `payload_budget.py` after a site build;
   - commit as keenroudy22 with the attribution line;
   - deploy with the locked script;
   - `gh run watch --exit-status`;
   - check the live site at 375 px (no sideways scroll, no console errors).
8. **No social category goes live without the owner's yes** to the AGENTS.md text. M0 to M2 proceed now under the existing rules ("Website-first new sports", "Season Trends", "Redesign boundaries") and the owner's Oct 6 request.

## Verified current state (2026-10-06)

- **Worktrees.** `~/Projects/sports-dev` is clean and at `16655b08`, the same commit as `main`. The uncommitted felt-card work seen earlier has been committed, so there is no collision risk now. Still keep felt-card files (`felt_cards.py`, `render_felt_review.py`, `research_posts.py`, `sheet.py`) out of M1 commits.
- **Site shell is almost at its size limit.** index.html + app.css + app.js gzip to 92,818 bytes against a 94,208 limit, leaving 1,390 bytes. **app.js cannot grow.** All other-sport UI goes into a lazily loaded `site/sports.js`.
- **Football-only code.**
  - 34 `in ('NFL','CFB')` filters across the scripts.
  - `app.js`: 16 `FOOTBALL` uses.
  - Publication guard regex allows `(NFL|CFB)` only.
  - `validate_report` asserts NFL/CFB, caps scores at 100 and allows spread/total only.
  - Mislabel risks: `x_post.py:350` labels any non-college parlay "NFL", and `:552` labels any non-NFL league "College".
- **Multi-sport code that exists:**
  - `sports_refresh.py`: scores for 7 leagues.
  - `market_lab.py`: MLB/NHL DraftKings game lines plus finals. The site already reads `site/data/market-lab.json` on sport Today.
  - `paper.py` + `hoops_store`: NBA/CBB totals trial, 0 rows, starts with the seasons.
  - `soccer_store`/`soccer_model`, `futures_store`: not run.
  - `sports_posts.py`: slate card, paused (`KEENROUDY_SPORTS_SOCIAL` unset).
- **ESPN prop boards (saved probe boards, measured offline).** Exact milestone matching verified 57 NHL pairs on one game, 51 on another, 34 NBA Finals, 15 MLB and 11 WNBA. In all 168 exact matches the over was the first item, with 0 contradictions.
- **Run writers and staging.**
  - `run.py` `WHITELIST`/`LEFTOVER` (lines 57-58, 139-140) list the directories the Mac may commit.
  - The workflow `git add` list (publish.yml line ~150) lists the directories the hosted runs commit.
  - `merge_store.STORES` lists the stores rebase conflicts are resolved for.
  - New directories must be added to the right list.

## Free-data matrix (ESPN public endpoints; DK = DraftKings, provider 100)

| League | Season now | Game lines (DK) | Player props (DK, priced) | Side label | Box score | Player gamelog | Injuries | Lineup/role | Stored history | Site research | First social (if approved) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NHL | Regular season since Oct 6 | Yes (market_lab; 51 games, 202 snapshots) | Yes: SOG, points, assists, blocked shots, saves, anytime goal (labeled yes). Player boards appear on game day | Exact milestone match | Yes. Groups `forwards`, `defenses`, `goalies`. Shots = `shotsTotal` ("S"); "SOG" is **shootout goals** | Yes | Yes (115 entries) | Starting goalie not verified, so saves excluded | Lines only, no player rows | ~Oct 12 (players reach 3 games) | Slate now; trend board ~Oct 16-20 (5 games) |
| NBA | Preseason; opener Oct 20 | Yes (scoreboard + core odds) | Preseason 404. Regular-season board confirmed on 2026 Finals game 401859967 (619 priced) | Exact milestone match | Yes (keys to verify on one final summary fixture) | Yes | Yes (93 entries) | Depth charts yes (next man up) | hoops team-level 3 seasons; no players | Oct 18-20 (lines, injuries, last-season-labeled charts); trends ~Oct 24-25 | Trend board ~Oct 28-Nov 1; totals-trial receipt Tue Oct 27 |
| CBB | Starts ~Nov 3 | Not posted yet | Unknown; thin | n/a | Yes | Yes | Incomplete (disclose) | n/a | hoops team-level 3 seasons | Nov: team pages + trial | Trial receipt ~Tue Nov 10 |
| MLB | Postseason | Yes (market_lab; 17 games) | Yes, batter markets (698 priced). No pitcher props seen ~16 h out | Exact milestone match | Batting box lacks 2B/3B (gamelog has them) | Yes | Yes (283 entries) | Probables yes; lineups empty 17 h out | Lines only | Optional World Series pages; full build for Opening Day 2027 | Optional WS; else Apr 2027 |
| EPL | Break; next Oct 17 | DK 1X2 + total 2.5 in scoreboard | Not probed | n/a | Shots, SOT, starters (after match) | Yes | n/a | Lineups ~60-75 min pre-kickoff | soccer_store 3,850 matches (football-data.co.uk, not in the rights register) | Weekends from Oct 17 (lines + team shots) | Slate only until props verified |
| MLS | In season / playoffs | DK pickcenter. Live odds on in-progress games must be filtered | Not probed | n/a | Yes | Yes | Empty | n/a | soccer_store 4,832 | Low priority | Slate only |
| WNBA | Finals Oct 7-8 | Yes | Yes (686 priced) | Exact milestone match | Yes | Yes | Yes | n/a | none | Off until May 2027 | Slate only |

## Credit and request budget (detail in the budget field)

- **Other sports:** 0 Odds API credits, 0 SharpAPI requests, 0 SportsGameOdds objects.
- **Football:** 186 Odds API credits by Oct 7 00:39Z, about 31 a day. On that pace the 476-credit stop arrives around Oct 16, the night before the Oct 17-18 football weekend. That is a separate owner decision (M0).
- **ESPN new requests:**
  - Steady state about 250 a day.
  - About 800 a day during a one-week backfill.
- **Buffer:** about 270 more requests a month at most, against an estimated 1,500-2,000 of 3,000 already used. A counter gets added first.

## Rollout calendar

| Date (2026) | Milestone |
|---|---|
| Tonight to Oct 8 | M0 budget hygiene; M1 capture foundation (shadow). Product queue items P29-P34 added |
| Oct 7-8 (owner yes) | Resume the existing Around the leagues slate card |
| ~Oct 12 | M2a NHL website research live |
| Oct 16-20 | First NHL trend board on X/Discord (owner yes + card review) |
| Oct 17 | EPL weekend lines/team-shots pages (M7) |
| Oct 18-19 | M2b NBA website research live before the Oct 20 opener |
| Oct 27 (Tue) | First NBA totals paper-trial weekly receipt (if approved) |
| Oct 28-Nov 1 | First NBA trend board |
| Late Oct to mid-Nov | M4 projections pass backtests; M5 grading and calibration accumulate |
| Nov 3 | CBB totals trial auto-starts; CBB team pages |
| Dec at earliest | M6: first P11 packet per sport/market (owner decides) |

---

## M0: Budget hygiene (tonight, no public change)

**Goal.** Stop the Odds API month-rollover deadlock, make the pace visible, and start counting the unmeasured free plans. No behavior change to what football captures.

**Changes**

1. **Month-rollover fix.** These three readers treat stored usage as unknown when its `at` falls in an earlier UTC month than `now`:
   - `scripts/odds_api.py due()` (line ~178)
   - `scripts/prop_odds.py wanted()` (line ~70)
   - `scripts/easy_parlay.py credits_left()` (line ~62)
   
   With usage unknown, the call proceeds to `quota.guarded_json`, which verifies through its free probe. Today, once the guard stops a month at about 24 remaining, `due()` keeps returning "keeping the reserve" after the reset, because nothing refreshes the stored number.
2. **Pace warning.** `scripts/desk_health.py` warns when `used > 476 * elapsed_fraction_of_UTC_month + 30`. Keep the existing `remaining <= 48` alarm.
3. **Request counters (counts only, never keys):**
   - `work/quota/sharp.jsonl`: one row per SharpAPI request, appended by `sharp_odds.fetch`.
   - `work/quota/buffer.jsonl`: one row per GraphQL request, appended by buffer_post's request helper.
   - The weekly review packet shows monthly totals.

**Tests.** In `tests/test_odds_api.py`, `test_prop_odds.py` and `test_easy_parlay.py`:
- stale-month usage → not blocked;
- same-month low usage → blocked;
- missing usage → guarded path.

In `test_desk_health.py`: a pace fixture. Counter tests confirm no key text in a row.

**Gate.** Both suites, rehearsal, locked deploy.

**Public:** nothing. **Owner decision (separate):** the football trim plan; see the budget field.

## M1: Free multi-sport capture foundation, NHL + NBA first (tonight to Oct 8, shadow)

**Goal.** Start collecting, today and for free, the evidence every later feature needs: priced DraftKings props with proven sides, per-player box scores, injuries, and game lines for the new leagues.

### M1.1 `scripts/leagues.py` (new registry)

```python
LEAGUES = {
 'NFL': {'sport':'football','slug':'nfl','name':'NFL','tag':'#NFL','official':True},
 'CFB': {'sport':'football','slug':'college-football','name':'College football','tag':'#CFB','official':True},
 'NHL': {'sport':'hockey','slug':'nhl','name':'NHL','tag':'#NHL','official':False,'seasonEndYear':True},
 'NBA': {'sport':'basketball','slug':'nba','name':'NBA','tag':'#NBA','official':False,'seasonEndYear':True},
 'WNBA':{'sport':'basketball','slug':'wnba','name':'WNBA','tag':'#WNBA','official':False},
 'CBB': {'sport':'basketball','slug':'mens-college-basketball','name':"Men's college basketball",'tag':'#CBB','official':False,'seasonEndYear':True},
 'MLB': {'sport':'baseball','slug':'mlb','name':'MLB','tag':'#MLB','official':False},
 'EPL': {'sport':'soccer','slug':'eng.1','name':'Premier League','tag':'#EPL','official':False},
 'MLS': {'sport':'soccer','slug':'usa.1','name':'MLS','tag':'#MLS','official':False},
}
OFFICIAL = frozenset(k for k, v in LEAGUES.items() if v['official'])
RESEARCH = ('NFL', 'CFB')   # grows to add 'NHL' in M2a and 'NBA' in M2b
```

- Fail closed on mislabels: `x_post.py` parlay head (line ~350) and the scoreboard post name (~552) raise `ValueError` for any league not in `OFFICIAL`.
- `tests/test_leagues.py`:
  - `OFFICIAL == {'NFL','CFB'}`;
  - `sports_refresh.LEAGUES` keys and slugs match;
  - the guard's explicit tuple equals `leagues.RESEARCH`;
  - x_post raises for NHL.

### M1.2 `scripts/espn_props.py` (new; priced leagues; leave the NFL `prop_lines.py` untouched)

**Constants**
- `STORE = data/sport-props`
- `LEAGUES = ('NHL','NBA','WNBA','MLB')`. EPL/MLS are added only after a saved fixture shows a priced board.
- `WINDOW = 10 h`, same Eastern date.
- `MAX_BOARDS = 30` per run, across leagues; priority NBA > NHL > MLB > WNBA.
- `MAX_PAGES = 3`, following `pageCount`.
- `GAP = 0.5 s`.
- URL: `https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{slug}/events/{id}/competitions/{id}/odds/100/propBets?limit=1000` plus the page parameter. Confirm the parameter name with one GET when saving the fixture.

**Main markets** (exact `type.name` strings from the saved boards; ignore anything else and count it in `status.unknownMarkets`):
- NHL: `Total Shots on Goal`→sog, `Total Points`→pts, `Total Assists`→ast, `Total Blocked Shots`→blk, `Total Saves`→saves (stored but never public until a confirmed-starter source exists).
- NBA/WNBA: `Total Points`→pts, `Total Rebounds`→reb, `Total Assists`→ast, `Total 3-Point Field Goals`→fg3m, `Total Steals`→stl, `Total Blocks`→blk, `Total Points, Rebounds, and Assists`→pra, `Total Points and Rebounds`→pr, `Total Points and Assists`→pa, `Total Assists and Rebounds`→ra, `Total Steals and Blocks`→sb.
- MLB: `Total Hits`→h, `Total Bases`→tb, `Total Runs Scored`→r, `Total RBIs`→rbi, `Total Hits + Runs + RBIs`→hrr, `Total Singles Hit`→1b, `Total Doubles Hit`→2b.

**Milestones** (single-sided, labeled):
- NHL: `Shots on Goal Milestones`, `Points Milestones`, `Assists Milestones`, `Blocked Shots Milestones`, `Goals Milestones`, `Powerplay Points Milestones`, `Goalkeeper Saves Milestones`.
- NBA: `Points Milestones`, `Rebounds Milestones`, `Assists Milestones`, `3-Point Field Goals Milestones`, `Steals Milestones`, `Blocks Milestones`, `Points + Assists + Rebounds Milestones`, `Points + Rebounds Milestones`, `Points + Assists Milestones`.
- MLB: `Hits Milestones`, `Total Bases Milestones`, `Runs Milestones`, `RBIs Milestones`, `Hits + Runs + RBIs Milestones`, `Singles Milestones`, `Doubles Milestones`, `Home Runs Milestones`, `Strikeouts (Batter) Milestones`.

`target.displayValue 'N+'` becomes `{kind:'milestone', line:N-0.5, direction:'over', odds}`. NHL `Anytime Goalscorer` is a labeled yes price, stored as `{kind:'yes', stat:'g', line:0.5}`.

**Excluded:** quarter, period and 1st-inning markets, first/last scorer, double-double, triple-double.

**Side rule (load-bearing)**

Group main items by (athlete, stat, current line). Keep a group only if it has exactly 2 items, a half-point line, and two different American prices with |p| ≥ 100.

Let `m` be the same athlete's same-stat milestone price at `N = floor(line) + 1`, from the same read:
- If exactly one item's price equals `m`, that item is the over and the other is the under. Store `{over, under, sideVerified: true, sideMethod: 'milestone-exact'}`.
- If no item matches, or both do, store only `{line, openLine, sideVerified: false}` with **no prices**.

Record `orderAgrees` (the over was the first item) for monitoring only, and count `orderContradictions`. Order is never used to label a side.

**Capture**
- Games come from `site/data/sports.json` with status `scheduled` and a confirmed time.
- Stamp `retrievedAt` from the clock *after* the fetch, and drop the board if `retrievedAt >= kickoff`.
- If any page fails, drop the whole board (a pair split across pages breaks the side check).
- Append only rows that changed for a given key (eventId, athleteId, stat, kind, line).
- Store ESPN `lastUpdated` as `providerUpdatedAt`, diagnostics only.
- Names are joined later from `sport-box` by athlete ID. The capture makes no per-athlete name requests.

**Outputs:** `data/sport-props/<league>-<season>.jsonl` + `ledger.json`; `data/sport-props/status.json` (counts only); `data/sport-props/REPORT.md` (verification rate by league and stat, late boards, unknown markets).

**Tests** (`tests/test_espn_props.py`; fixtures in `tests/fixtures/espn/`):
1. NHL board: verified pairs > 0, and every verified over equals its milestone price.
2. No milestone → no prices stored.
3. Both items equal the milestone → unverified.
4. 3 items at one line → dropped.
5. Board fetched at kickoff → dropped.
6. Page 2 fails → whole board dropped.
7. Unknown market counted, not stored.
8. `lastUpdated` never drives freshness.
9. Ledger refuses a tampered store.
10. NFL refused.
11. Saves rows carry `public: false`.

### M1.3 `scripts/sport_box.py` (new; NHL + NBA in M1)

- `SUMMARY = https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/summary?event={id}`.
- **Record:** `{league, season, seasonType (1 pre, 2 regular, 3 post), eventId:'NHL-<id>', kickoff, teams:{id:{abbr, score, home, opp}}, players:[{id, name, team, pos, group, starter, dnp, stats}], retrievedAt, extractor:1, source}`.
- **NHL:**
  - Read groups `forwards`, `defenses` and `goalies` only. Ignore the `skaters` group so nothing is counted twice (test it).
  - Keys: `goals`→g, `assists`→a, pts = g + a, **`shotsTotal`→sog (never `shootoutGoals`)**, `blockedShots`→blk, `hits`→hit, `timeOnIce`/`powerPlayTimeOnIce`/`evenStrengthTimeOnIce` → minutes.
  - Goalies: `saves`, `shotsAgainst`, `goalsAgainst`, `timeOnIce`.
  - Groups: C/LW/RW→F, D→D, G→G. Scratched players → `dnp`.
- **NBA:**
  - Map keys from one saved final-summary fixture. Fetch event 401859967 with 1 polite GET.
  - Expected keys: minutes, points, FG/3PT/FT made-attempted, offensive/defensive/total rebounds, assists, steals, blocks, turnovers, fouls, plusMinus, starter, didNotPlay.
  - Groups: PG/SG→G, SF/PF→F, C→C.
- **`step(limit=60)`:** finals not yet stored, plus one recheck at least 24 h later (a changed content hash appends a revision).
- **`backfill(league, season, limit=60)`:**
  - NHL 2027 (current) first.
  - Then NBA 2026, using the event IDs already in `data/hoops/nba-2026.jsonl` (no enumeration requests).
  - Then NHL 2026. Enumerate by scoreboard date, or by the team schedule endpoint after a one-GET check.
- **Wiring:** hosted `publish.yml` step after `sports_refresh.py`, `if: github.event_name == 'schedule'`: `python scripts/sport_box.py step --limit 60 && python scripts/sport_box.py backfill --limit 60`, 1 s gap. Add `data/sport-box` to the workflow `git add` list and to `merge_store.STORES`.
- **Tests:**
  - NHL fixture: summed `sog` equals the team's shotsTotal (CAR 34, MTL 20);
  - "SOG" is never read;
  - goalies kept separate;
  - `skaters` not double-counted;
  - NBA key map, DNP, preseason stored but flagged;
  - limit honored;
  - stops after 3 errors;
  - append-only/ledger.

### M1.4 `scripts/market_lab.py` (extend)

- `LEAGUES = ('MLB','NHL','NBA','WNBA','EPL','MLS','CBB')`.
- Soccer: a three-way moneyline (`home/draw/away`) plus total; no spread unless one is supplied.
- CBB: use the DraftKings odds embedded in the scoreboard (zero extra requests). Games within 12 h only; at most 25 per-event calls per league per run, and only when the embedded block lacks a price.
- Keep the existing live-provider exclusion and pregame-only rule.
- Tests extend `test_market_lab.py`: draw schema, CBB cap, preseason seasonType kept, MLB/NHL rows unchanged.

### M1.5 `scripts/sport_injuries.py` (new)

- One GET per league per slot (NHL, NBA, MLB, WNBA).
- Append changed `(athleteId, team, position, status, date, type)` rows to `data/sport-injuries/<league>-<season>.jsonl`. **Never store comment text.**
- `HARD = {'Out','Suspension','Injured Reserve','IR','10-Day IL','15-Day IL','60-Day IL'}`. Day-To-Day is soft.
- Tests: status mapping, unchanged rows not appended, no comment field.

### M1.6 Mac wiring (`scripts/run.py`)

- In `paper_trials()` (line ~1029; slots 11, 17, 21, 23 = 11:45 AM, 5:30, 9:00 and 11:30 PM), after `market_lab.step`, call `espn_props.step(now)` then `sport_injuries.step(now)`:
  - each inside its own try/except;
  - a shared 150-second time budget;
  - kill switch `KEENROUDY_SPORTS_CAPTURE` (default `1`; `0` disables);
  - one log line each.
- Add `data/sport-props/` and `data/sport-injuries/` to `WHITELIST` and `LEFTOVER`.
- Under `rehearse.py` the network is blocked, so these must return `{'captured': 0, 'reason': 'offline'}` and never fail the run.

### M1.7 Product queue

Add to `docs/product-status.json`, each with a specific next action and completion condition:
- P29 capture foundation;
- P30 NHL website research;
- P31 NBA website research;
- P32 other-sport social research (owner-gated);
- P33 other-sport projections, calibration and shadow plays;
- P34 Odds API pace and rollover.

P11 keeps "other-sport official releases".

**M1 gate.** Suites, `test_free_only`, rehearsal, a guard run (no new public files), locked deploy, watched publish run.

**M1 done when:**
- two desk days show captures at all four slots;
- NHL averages at least 30 verified pairs per game night;
- 0 boards stored after their start, and `orderContradictions = 0`;
- the NHL current-season box store is complete and the NBA 2026 backfill is complete (at most 4 days).

**Public:** nothing new on the site. The data is visible in the public repo, like market-lab today. **Shadow:** everything.

## M2: Website research for NHL (~Oct 12) and NBA (Oct 18-19)

**Goal.** "Same features" on the site for each league as its data allows: per-sport Today, Research (lines with hit rates, trends, player charts), Games (game pages, defense versus position, injuries, next man up for the NBA), honest capability flags, and no football data substituted.

### Python

1. **`scripts/sport_features.py` (new; do not refactor football `features.py`):**
   - `player_logs(records)`, `team_logs(records)`;
   - `defense_logs(records, groups)`;
   - `defense_table(logs, stat, last, season)`, which ranks 1..N per game (NBA also per 100 possessions, with possessions ≈ FGA + 0.44·FTA − OREB + TOV, weighted by minutes);
   - `with_without(records, player, teammate)` for the NBA.
   - Groups: NHL F/D, NBA G/F/C.
   - Windows: NHL last 10 + season; NBA last 15 + season.
2. **`scripts/season_trends.py`:**
   - Add `STATS_BY_LEAGUE`:
     - NHL `sog` (shots on goal, step 1), `pts`, `ast`, `blk`;
     - NBA `pts` (5), `reb` (1), `ast` (1), `fg3m` (1), `pra` (5), `pr`, `pa`, `ra`, `stl`, `blk`;
     - MLB later.
   - `build()` picks maps by league, so football output must stay byte-identical on the existing fixtures (add that test).
   - Offers come from `sport-props` rows with `sideVerified` and age ≤ 4 h.
   - `history()` stays as is: current season, seasonType 2, at least 3 games, any unknown stat suppresses the row.
   - Goalie saves are excluded.
3. **`scripts/build_site.py`:** a new `build_sport(league, now)`, called for `leagues.RESEARCH` minus NFL/CFB. It writes:
   - `data/app/sports/<L>.json` (Today):
     - tonight's and tomorrow's games;
     - DK game lines from market-lab with `retrievedAt`, hidden at the start or after 4 h;
     - injuries (status only);
     - up to 10 trend rows;
     - trial summary;
     - freshness times;
     - a one-line honest status ("Best bets cover NFL and college football. NHL is research only.").
   - `data/app/player-charts/<L>.json`: game-by-game bars, current DK line (unpriced allowed, as with the NFL charts), L5/L10/season hit counts, position and opponent rank.
   - `data/app/trends/<L>-YYYY-MM-DD.json` plus an index entry.
   - `data/app/games/<L>-<eventId>.json`:
     - lines, injuries, last-5 form, defense ranks, top trend rows for the game;
     - the NBA totals trial projection when present (already approved as a labeled trial);
     - an NBA blowout caution when |spread| ≥ 12 (a caution, never a direction).
   - `data/app/teams/<L>-defense.json`.
   - `capabilities` per league inside the existing `data/app/sport-research.json`, for example `{NHL:{today:true, research:true, trends:true, charts:true, games:true, injuries:true, lines:true, projections:false, bestBets:false, climb:false}}`, computed from which payloads were written and are fresh.
   - **NBA only:** next man up. When a rotation player is Out (HARD status), name the depth-chart next player (`/teams/{id}/depthcharts`, at most 1 request per team playing today, cached for the day) with his minutes and with/without splits from the box store. Label it research.
   - **Early season (owner decision 6):** last season appears only as a separately labeled chart window, never in a hit-rate row or a post.
4. **`scripts/publication_guard.py`:**
   - `RESEARCH_LEAGUES = ('NFL','CFB','NHL')`, adding `'NBA'` in M2b;
   - `DEFENSE_LEAGUES = ('CFB','NHL','NBA')`;
   - `SPORT_PAGES = ('NHL','NBA')`;
   - build the existing regex from these explicit tuples;
   - add `sports/(?:NHL|NBA)\.json`;
   - add `sports.js` to `ROOT_FILES`.
   
   Fixtures:
   - allow `games/NHL-401891815.json`, `trends/NHL-2026-10-12.json`, `sports/NHL.json`;
   - reject `games/ALL-1.json`, `sports/NFL.json`, `sports/../x.json`.
5. **`scripts/payload_budget.py`:**
   - `sports-module-gzip` 40 KB;
   - `sport-today` 192 KB per league;
   - `sport-charts` 768 KB;
   - `sport-game` 96 KB (largest file);
   - `sport-defense` 128 KB;
   - `market-lab` 256 KB;
   - trend shards reuse the 2 MB limit;
   - the shell limit is unchanged.
6. **`docs/PUBLIC-PAYLOADS.md`:** one line per new family. **`docs/SOURCE-RIGHTS.md`:** add the exact ESPN fields used (DK prices, box stats, injury status, logos/portraits) under the existing unresolved row. Add a football-data.co.uk row (currently missing).

### Site

- **`site/sports.js` (new, lazy).**
  - Same UMD pattern as `core.js`, so Node can test it.
  - Exports pure helpers: `capable`, `lineState` (fresh / stale / started → hidden), `trendRows`, `defenseRank`, `labels` (per-sport stat words: "shots on goal", "points", "3-pointers made").
  - In the browser it registers `window.KookSports = {today, research, charts, trends, games, game, player, notYet}`.
- **`site/app.js`, net size change ≤ 0 bytes gzipped.**
  - Add one loader: inject `sports.js?v=1` once, on first non-football selection.
  - Replace `NOT_YET`/`notYet`/`sportToday`/`trialCard`, the Games "Football only for projections" branch (line ~1374) and the non-football game-page branch with `capable(league, view) ? KookSports.view(...) : KookSports.notYet(...)`.
  - Move those long strings into sports.js to pay for the hook.
  - Keep the Climb (line ~2019), official Record (~2029), best bets and `projectionScorecard` on `FOOTBALL`.
  - The selector optgroups become "Best bets and research" (NFL, CFB), "Research" (leagues where `capabilities.research` is true) and "Scores and trials" (the rest).
- **`site/core.js`:** let `parseRoute` accept research leagues for `#player/<L>/<id>` and `#game/<L>-<id>`. Existing hashes keep working. Record math is untouched.
- **Lazy loading:** a league's files are fetched only when that league's view opens. Today never downloads another league's payload.
- **Node tests (`tests/sports.test.js`):**
  - an NHL view never renders NFL data;
  - an unverified price is never rendered;
  - lines are hidden at the start and after 4 h;
  - capability off → honest empty state;
  - existing routes (`#today?sport=NHL`, `#games/live`, `#record/trials`) still resolve;
  - the payload budget passes.

### Verification and release

- Suites; rehearsal; `build_site` locally; `publication_guard.py`; `payload_budget.py`.
- Browser QA at 375 px and at desktop width: NHL Today, NHL trends, an NHL game page, an NHL player page, defense table, and the NBA Today preview. No sideways scroll, no console errors.
- Locked deploy, watched run, live check.

**M2a done when:** NHL views are live with at least one trend row from 3 or more games and verified prices, the guard and budget pass, and the status file updates P30 with run evidence. **M2b:** the same for the NBA by Oct 19 (schedule, lines, injuries; trends once players reach 3 games, about Oct 24-25).

**Public:** website research. **Shadow:** saves, unverified prices, anything model-based.

**Optional M2c (only if M2b ships by Oct 20): MLB postseason pages.** Use athlete gamelogs (they carry 2B/3B) for the players on that day's board, about 32 GETs per game. Batter markets only; pitcher lines only for ESPN's listed probable starter.

## M3: Posting for other sports (needs the owner's yes to the AGENTS.md text, plus a review of 2 rendered sample cards)

**Goal.** Up to 3 other-sport posts a day that draw attention without risking football or the record.

1. **Around the leagues slate card (existing).**
   - Set `KEENROUDY_SPORTS_SOCIAL=1` in `~/.config/keenroudy/env` (a non-secret flag) under the run lock.
   - Add a felt variant in `felt_cards.py` that switches with the other categories when `FELT_FROM` is set (P21). Legacy art stays until then.
   - Due 5:50 PM ET; already guarded.
2. **Other-sport trend board (new): `scripts/sports_research_posts.py`.**
   - Buffer key `sports-research:<LEAGUE>:<YYYY-MM-DD>`. Do **not** reuse the `research:` prefix: `research_posts.already_posted` (line 317) would treat it as football's slot.
   - Kind: `sports-research`.
   - Candidate rows, computed from the stores (not from the site JSON), must have:
     - kind main, `sideVerified`, book DraftKings;
     - captured before the start and no more than 4 h before the post;
     - at least 5 current-season regular-season games, every stat known;
     - hits at least 80%, shown as exact hits/games;
     - no ESPN injury status;
     - no goalie saves;
     - for pitchers, only ESPN's listed probable;
     - a price no shorter than −200 (owner decision 5).
   - Up to 3 rows, one per player.
   - Rotate the league by date among leagues that have a qualifying board.
   - Prepared at the 5:30 PM run, due 6:05 PM ET. Stale at min(capture + 4 h, first included start − 40 min). A late run is skipped, never forced.
   - Card: felt, 1080×1350. It carries the research label, 21+ and entertainment-only wording, the exact line, price and book, and the full-season count.
3. **Basketball totals paper-trial receipt (weekly): `scripts/sports_trial_receipt.py`.**
   - Kind `sports-trial`, Tuesday 1:00 PM ET.
   - Built from `sport_research`/`paper` graded rows for the prior Mon-Sun: every graded lean, W-L-P at the logged number.
   - Posted the same way in a losing week. Labeled "Paper trial, not part of the Kook'n record."
   - Pregame trial leans never post.
4. **`scripts/buffer_post.py`:**
   - Order: `'sports': 3, 'sports-research': 4, 'sports-trial': 4`.
   - Overflow drop order: `('sports-trial','sports-research','sports','research','conversation','news')`.
   - `fit_limit` optional set adds all three other-sport kinds.
   - New other-sport cap: at most 3 per Eastern date Mon-Fri and 2 on Sat/Sun, at most 1 per league (the slate counts once). Sat/Sun scheduling only from the 5:30 PM run. Never moves a football post. The 20/day ceiling and 10-minute spacing stay.
   - Record `league` and `kind` on new rows in `data/x-posted.json`.
5. **Captions.**
   - Shape: category, the exact line and price, one proof point, one league tag (from `leagues`).
   - Never: "!", dashes, promises, "lock", @Playbook, units, "save this", or "history does not predict".
   - Every digit in the caption must appear in the payload (port the receipts/x_post number guard).
   - Example template: `NHL TREND BOARD` / `{player} over 2.5 shots on goal (-120 DK)` / `9/10 this season` / `+2 more on the card` / `#NHL`.
6. **Discord.** Mirror after Buffer confirms X, in Plays & Results, league first; no pings, no early lead. This uses the existing mirror; confirm it accepts the new kinds.
7. **Docs.** `docs/POSTS.md`, `docs/SOCIAL-SCHEDULE.md`, `docs/GROWTH.md` (tags), `deployment/mac/env.example` comment, SOURCE-RIGHTS owner-accepted-risk row, product-status P32.

**Tests:**
- `tests/test_sports_research_posts.py`:
  - every candidate rule above;
  - the key prefix does not collide with football's research slot;
  - an unverified price is refused;
  - a stale row is refused;
  - an injured player is refused;
  - −200 floor;
  - every caption number exists in the payload;
  - caption style guard.
- `tests/test_buffer_post.py`: drop order; weekday/weekend caps; per-league cap; weekend only from 17:30; football untouched.
- `tests/test_sports_trial_receipt.py`: a losing week posts identically; preseason excluded.

**Verification:**
- `run.sh py scripts/buffer_post.py plan` (read-only);
- card previews via the felt review renderer, sent to the owner;
- the first live post watched through `buffer_post.py reconcile` and the Discord mirror.

**Done when:** 8 measured posts per category, then a review at 2 weeks of impressions by kind and league (docs/GROWTH.md) before any cap change.

## M4: Projections and model leans (late Oct to mid-Nov; website only after passing)

- **`scripts/sport_project.py`:**
  - **NHL SOG:** projected TOI (EWMA of the last 10, power-play share) × SOG/60 shrunk to the position mean × opponent shots-against factor (shrunk), as a negative binomial with dispersion fitted on 2026.
  - **NHL points/assists:** Poisson rates per 60.
  - **NBA:** minutes model (L10 EWMA, starter, back-to-back, blowout adjustment from the spread, injury redistribution from with/without) × shrunk per-minute rates × pace × opponent G/F/C factor. Negative binomial for reb/ast/fg3m.
- **Walk-forward backtest** on the backfilled 2026 season. A projection is displayed only when:
  - 80% interval coverage is 75-85%;
  - |bias| ≤ 5% of the mean;
  - MAE beats the naive season average by at least 2%.
  
  The results go to `docs/OTHER-SPORTS.md`.
- **Game projections:** the NBA uses the existing `hoops_model` projected score, labeled as a trial. An NHL shots-and-goalie model is paper-only until it passes its own backtest.
- **Model leans** (descriptive gap between line and projection, no confidence rank) appear only for players whose projection passed. A trial projected-winner record per league sits under Record → Trials, labeled separately from official model accuracy.
- Gate as M2. **Public:** passed projections and leans with a trial label. **Shadow:** everything else.

## M5: Settlement, calibration and shadow best bets (Nov onward, no public picks)

1. **`scripts/sport_settle.py`, tested per sport:**
   - NHL: props include OT and exclude shootouts; SOG = shotsTotal; void with no TOI. Check DK rules.
   - NBA: OT counts; DNP void.
   - MLB (2027): a batter needs a plate appearance; listed pitcher/action rules; shortened games.
   - Soccer: 90 minutes plus stoppage.
2. **Grading and calibration.** Grade every captured main line against its raw projected chance. `learn.py` segments: `NHL/prop:sog`, `NBA/prop:pts`, and so on. A segment ships a k only with at least 300 graded pairs (`CAL_MIN`), spanning at least 14 days, and beating the raw chance's held-out log-likelihood. Until then the board says "Grading first". Add the leagues to `gates.OWN_CALIBRATION` / `build_site.PROP_OWN_CALIBRATION`.
3. **`scripts/sport_shadow.py`:**
   - Football-equivalent gates per league: verified side, at least 2 adjusted points over the exact price after calibration, 4 h freshness, HARD injury stop, one per player.
   - Append would-be best bets to `data/sport-shadow/<league>-<season>.jsonl` with the exact price and time, graded by `sport_settle`.
   - Also run shadow Climb legs (same sport, different games) and fun tickets. No cross-sport tickets.
   - Shown only as a labeled paper trial under Record → Trials, never on Today and never posted.
4. **P11 packet per sport/market:**
   - n, W-L-P at the captured price, ROI at the captured price;
   - closing-line value against the last pregame capture;
   - k and held-out log-loss;
   - drawdown;
   - settlement edge cases seen;
   - the proposed cap;
   - the all-sport record before and after.

## M6: Official release per sport (owner decision; December at earliest)

Only on an explicit P11 yes for a named sport and market:
- `leagues` official=True for that league;
- `refresh.validate_report` reads the league set from `leagues.OFFICIAL`, with score caps by sport (NBA ≤ 200, NHL ≤ 20, MLB ≤ 40, soccer ≤ 15) and `moneyline` only if approved;
- per-sport hard-news gates (NBA injury report; NHL confirmed goalie);
- a separate card ceiling for the new sport that never displaces football's 5/1 (owner sets it);
- POTD/Climb eligibility per the owner;
- Record season/stage views (already supported).

## M7: Seasonal leagues

- **EPL (from Oct 17):**
  - market_lab 1X2/total plus a soccer box extractor (shots, SOT, starters, formation) feeding weekend website pages.
  - One polite propBets probe on Oct 16. Trends only if the board is priced and sides are verifiable.
  - Saturday kickoffs (7:30 AM-12:30 PM ET) need hour 6 added to the capture slots on Sat/Sun for EPL only.
  - Asian-handicap leans stay paper-only.
- **CBB (Nov 3):** the totals trial starts automatically; team tempo/efficiency pages; incomplete injury coverage disclosed; props only if ESPN lists DK boards; first trial receipt around Nov 10.
- **MLB:** optional World Series pages (M2c). Offseason backfill of 2024-26 box scores (about 2,430 a season at a polite pace) plus gamelogs for 2B/3B, then a pitcher-strikeout model, research live by Opening Day 2027, calibration around mid-April.
- **MLS / WNBA:** slate card and scores only; WNBA research for May 2027.

## Local-LLM uses (free; code supplies every number)

- **Row selection (M3):** `llm.draft_json` on qwen3.8:27b picks up to 3 row IDs from up to 12 code-qualified candidates. Output schema `{rows:[id], template:'t1'..'t5'}`. Fallback: the deterministic sort (rate, games, kickoff).
- **Caption wording (M3):** the model picks a template and may add one clause of up to 12 words, chosen from a code-supplied fact list (back-to-back, opponent shots-allowed rank, home/road). Any digit, name or team not present in the facts → reject and fall back to the template.
- **AI-tell check (deterministic, never a model):** extend `llm.check_style` with an `AI_TELLS` regex list:
  - dashes, "delve", "dive in", "buckle up", "game-changer", "unleash", "elevate", "in the world of", "look no further", "without further ado", "a testament";
  - more than one emoji, "!";
  - any hashtag other than the one league tag;
  - "not financial advice", "history does not predict", "save this".
  
  Then `x_post.tweet_length` and the number guard.
- **Limits:** one call per other-sport post (at most 3 a day), 120 s timeout, no retry, serialized with the existing sports calls. `--no-llm` and `KEENROUDY_SPORTS_LLM=0` disable it. Ollama down → template. qwen3.5:9b-mlx is not used for judgment.
- **Weekly review:** the packet adds other-sport capture, verification and posting counts deterministically. The existing 27B excerpt selection is unchanged.
- **Never:** side labels, injuries, projections, picks, numbers, or free-form facts.

## Posting caps per sport

| Category | NHL | NBA | CBB | MLB | EPL / MLS / WNBA |
|---|---|---|---|---|---|
| Around the leagues slate (multi-league) | shared: 1/day, 5:50 PM, counts once | shared | shared | shared | shared |
| Trend board | ≤1/day total across sports, rotating by date (from ~Oct 16-20) | same (from ~Oct 28) | only if DK props exist | WS optional; Apr 2027 | none until props verified |
| Trial receipt | none | weekly Tue (from Oct 27) | weekly Tue (from ~Nov 10) | none | none |

- Daily other-sport X total: ≤3 Mon-Fri, ≤2 Sat/Sun; ≤1 per league.
- Dropped first; inside the 20/day ceiling and 10-minute spacing.
- Discord after X only. No @Playbook, no units.

## Start tonight (Codex checklist)

1. `git -C ~/Projects/sports-dev fetch -q origin && git -C ~/Projects/sports-dev rebase origin/main`. Read `docs/PRODUCT-IMPLEMENTATION.md` and `docs/product-status.json`; add P29-P34.
2. **Commit C1 (M0):** rollover fix + tests, pace warning, request counters.
3. **Fixtures.** Copy trimmed boards (≤150 KB each) from `/private/tmp/claude-501/-Users-keen-Library-Application-Support-Claude-scratch-workspaces-da7a5138-6d58-4d8b-ab63-3dcdcdeb4506-a449a77c-0e2e-4708-ad0d-3efedc9a099f-scratch-2026-10-06-dc51b5/fe68a07d-7723-406c-8d60-7cebd5d9318d/scratchpad/espn/` into `tests/fixtures/espn/`:
   - `nhl_props_final.json`, `nhl_props_all.json`, `nba_props_finals.json`, `mlb_props_all.json`, `wnba_props.json`, `nhl_summary_final.json`.
   - If that folder is gone, re-fetch with at most 8 GETs, 1 s apart.
   - Fetch the NBA final summary 401859967 once.
   - Strip any `links` and DraftKings deep links (they carry ESPN referral parameters).
4. **Commit C2:** `leagues.py` + fail-closed labels + `test_leagues.py` + `test_free_only.py`.
5. **Commit C3:** `espn_props.py` + tests.
6. **Commit C4:** `sport_box.py` (NHL first) + tests.
7. **Commit C5:** market_lab extension, `sport_injuries.py`, run.py wiring (`paper_trials`, `WHITELIST`, `LEFTOVER`), workflow step (schedule only), `git add` list, `merge_store.STORES`.
8. Both suites; `rehearse.py --slot 2330` (or the current window); guard; locked deploy (C1-C2 can ship tonight, C3-C5 by Oct 8); `gh run watch`.
9. After the next 11:45 AM slot, read `data/sport-props/REPORT.md` (verified pairs, late boards, contradictions) and the run log. Report the numbers to the owner in plain words.
