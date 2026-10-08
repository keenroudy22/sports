# Kook'n direction rules: when the results say change course, the desk changes on its own (owner, 2026-10-07)

The owner: "My end goal is for this to be streamlined so I can get on the site and get what I want and get off. With expectations of it being autonomous and improving. If ... trends / bets aren't hitting at the rate we want we change directions after x."

That is the owner's **standing approval** for the bounded, automatic course corrections below. Record it as a dated owner rule.

It changes the earlier "each results proposal needs its own owner yes" only for these listed moves. These rules can only:
- tighten;
- pause;
- shift weight between already-approved categories;
- restore what they tightened once results recover.

They never:
- loosen a gate below its Oct 7 baseline;
- add a market, sport, category, post slot or paid service;
- change how the record counts;
- touch a published play.

Every change is logged with its numbers and reported in the Monday review and the weekly owner ping ("what changed direction and why"). The owner can veto any of them by telling Codex to undo its named key.

The engine is the weekly learning run (learn.weekly) plus the Monday improvement task. Windows count graded plays at captured prices. Closing line value (CLV) means how far the market moved toward our side by kickoff.

## 1. Best bets (official plays), per segment (league × market, e.g. NFL rec yds, CFB totals)

| Trigger (after N graded in the segment) | Automatic move | Undo when |
|---|---|---|
| N ≥ 20, hit rate at least 5 pts under the segment's average break-even, and CLV ≤ 0 | Raise that segment's edge bar by +2 pts, up to +6 over baseline | The next 20 are at or above break-even with CLV ≥ 0: step back 2 pts |
| N ≥ 30, units ≤ −5u and CLV < 0 | **Pause the segment as a best bet.** It stays on the board and the Prep List as research and keeps running in shadow. This is the existing learned_pause, made explicit. | Shadow: 30 more at or above break-even with CLV > 0, then restore at the raised bar |
| N ≥ 30, units ≥ +3u and CLV ≥ 0 | That segment ranks first when the card is filled, within the existing caps. Caps never rise. | It falls below either mark |
| All straight plays, last 60: ≤ −8u | Weekend card cap 5 → 3 for two weeks; weekday unchanged | The next 30 at or above break-even: restore 5 |
| The model's calibration drifts: said-vs-hit gap over 5 pts in any 10-pt band, n ≥ 50 | Re-fit that league/market shrink this week (already automatic) and flag it on the calibration page | Automatic |

Today's evidence these rules would act on (Oct 6 report):
- NFL totals are 0-3 with negative CLV, and its near misses went 1-5. It's already under the higher bar.
- NFL rush yds are 0-3.
- Props overall are the bright spot.

## 2. Fun tickets and the 80/20 Climb

| Trigger | Move | Undo |
|---|---|---|
| Fun tickets: 0 wins in the last 12, or units ≤ −3u (0.25u each) over the last 20 | For two weeks, prefer shorter tickets: +300 to +800, 3-4 legs, every leg in a segment that isn't paused | Two wins in the next 10 |
| Climb: two climbs in a row lose at step 1 or 2 | The next climb excludes legs from paused or raised segments, retaining 0.83 minimum leg chance and the existing −180 to −130 ticket band | The climb reaches step 3 |
| Climb: no qualifying rung for 5 straight days with 2+ games | Report it in the Monday review (no auto-loosening) | n/a |

The Climb still runs whenever there are 2+ games in a league, any day, and is never forced (OWNER-DECISIONS item 6).

## 3. Trends and the Prep List

- Grade every Prep List row against the final box score. The rows are research, not the record, but keep a public "Prep List: X of Y hit this week" line.

| Trigger (rolling 40 rows) | Move | Undo |
|---|---|---|
| Hit rate < 60% | Raise the hit thresholds +5 pts (5-9 games: 85%; 10+: 9 of 10 and 75% season) and raise line floors one step | ≥ 70% over the next 40 |
| One stat type < 50% over 20 rows (e.g. receptions) | Drop that stat from the Prep List for 4 weeks | It hits ≥ 65% in shadow |
| Rows where "My price check: clears" beat "History only" by ≥ 10 pts over 40 | Show only "clears" rows | Gap < 5 pts |

## 4. Social posts

These are already in AUTOPILOT section 3: variants retire after 8 posts below the series median, and a research series pauses after 4 weeks under the floor. Add one move:

- **Any series with zero real replies and below-median likes per view for 4 weeks:** swap its card layout variant and caption family, then re-judge after 8 posts.

## 5. The site: "get on, get what I want, get off"

**The owner's 10-second Today: above the fold at 375 px, with no taps**

Kitchen Ticket update (owner, 2026-10-07; OWNER-DECISIONS item 22): the first best bet hangs on
the rail with its price, book and kickoff, the Climb stub sits directly under it, and the last game
day's W-L rides in the date line above it. The two compact status rows are retired. The 0.86/two-book
Climb variant is retired: it built no rung in 26 stored opportunities.
- today's best bets: the whole first ticket (pick, price, book, kickoff) with no scroll at 375 x 812;
- Climb status: "80/20 Climb #N", the step and its state line, with no scroll;
- last slate's result: W-L in the date line, then the slips with margins on the spike;
- the top 3 Prep List lines: one short scroll down.

Owner update (2026-10-07, after the Kitchen Ticket release): nothing else is behind a tap either. Below
the unchanged first screen come the season line, every other open best bet, Leftovers, the Prep List,
Underdog watch, Research worth a look, today's games, Fun / Pulled / Off the card, the Discord card and
More sports, with no "More for today" fold. On a long card the Prep List follows the best bets and
Leftovers rather than sitting one scroll down. The Codex weekly improvement task gets two jobs:
- **It ships one small site tweak a week aimed at this,** verified at 375 and 1440 px.
- **It keeps a speed budget:** Today's best bets visible in ≤ 2 s on a cold phone load. Measure it in the live check; a regression of over 20% blocks the release.

**Usage signal (free sources only):**
- Discord joins, from the invite with_counts API (once a day);
- X link clicks, from Buffer metrics;
- page-view trends, only if the owner later adds a free read-only Cloudflare token, never otherwise.

**Bigger site changes** (a new page, navigation or category) go into the one weekly owner ask.

## 6. Reporting

- **The Monday review gets a "Direction changes" box:** each move, its trigger numbers, what it does, and when it would undo.
- **The weekly owner ping is one line per change, plus a single link:** "Paused NFL totals as a best bet (0-3, −3u, CLV −0.33). Still on the board as research. To undo, tell Codex: undo KEY."
- **Tests:** each trigger and undo is pure, testable logic over the graded store. It never edits the published record.
