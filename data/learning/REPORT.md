# What the kitchen learned, 2026-10-13

2165 recorded candidate rows, 1305 distinct game/side/player observations, 2083 graded. Closing line value is how far the market moved toward our side by kickoff; it is the first thing learning trusts.

## Changes this week

- **CFB/prop** calibration: 0.23 to 0.15. Calibrated chances predicted the later record better than the raw ones.
- **NFL/prop** calibration: 0.13 to 0.11. Calibrated chances predicted the later record better than the raw ones.
- **researcher** domains: {'preferDomains': ['sports.yahoo.com', 'goaztecs.com', 'goheels.com', 'navysports.com', 'abqjournal.com', 'giants.com'], 'avoidDomains': []} to {'preferDomains': ['si.com', 'sports.yahoo.com', 'buffalobills.com', 'chicagobears.com', 'jaguars.com', 'goheels.com', 'goaztecs.com', 'navysports.com'], 'avoidDomains': []}. Which sites the researcher cites keep checking out.

## Direction changes

Owner-approved bounded moves (2026-10-07): they only tighten, pause, shift weight between approved categories, or restore what they tightened. Nothing loosens below the Oct 7 baseline, no market is added, and the record and published plays are untouched.

Applied:
- none

In force now:
- NFL totals: paused as a best bet since 2026-10-08 (research and shadow only)

## Segments (published since their last change)

- CFB/prop:passYds (min edge 5): published 1-0, +1.00u; near misses 3-9, -6.37u
- CFB/prop:rec (min edge 5): published 2-0, +2.20u; near misses 5-11, -6.56u
- CFB/prop:recYds (min edge 5): published 1-1, -0.17u; near misses 12-10, +0.63u
- CFB/prop:rushYds (min edge 5): published 0-1, -1.00u; near misses 13-11, +0.39u
- CFB/spread (min edge 1): published 1-1, -0.05u, closing line value -0.25 points (90% -0.50 to +0.00, n 2); near misses 0-0, +0.00u
- CFB/total (min edge 1): published 7-10, -3.34u, closing line value -0.06 points (90% -0.59 to +0.47, n 17); near misses 0-0, +0.00u
- NFL/prop:att (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:car (min edge 5): published 1-1, -0.10u, closing line value +0.00 points (90% +0.00 to +0.00, n 2); near misses 0-0, +0.00u
- NFL/prop:cmp (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:passYds (min edge 5): published 0-0, +0.00u; near misses 0-1, -1.00u, closing line value -8.00 points (90% -8.00 to -8.00, n 1)
- NFL/prop:rec (min edge 5): published 3-2, +1.06u, closing line value +0.00 points (90% +0.00 to +0.00, n 4); near misses 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1)
- NFL/prop:recYds (min edge 5): published 6-3, +2.51u, closing line value +1.00 points (90% +0.00 to +2.12, n 8); near misses 3-1, +1.76u, closing line value +0.75 points (90% -1.50 to +3.00, n 4)
- NFL/prop:rushYds (min edge 5): published 0-3, -3.00u, closing line value -1.33 points (90% -3.33 to +1.00, n 3); near misses 0-0, +0.00u
- NFL/spread (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/total (higher-bar caution): published 0-4, -4.00u, closing line value -0.50 points (90% -1.00 to +0.12, n 4); near misses 1-0, +0.91u, closing line value +0.50 points (90% +0.50 to +0.50, n 1)

## Two-way Autopilot learning

- Waiting for a second Tuesday: gap:CFB/prop:passYds (CFB/prop:passYds gap floor +2 points).
- Waiting for a second Tuesday: gap:CFB/prop:rec (CFB/prop:rec gap floor +2 points).
- Waiting for a second Tuesday: gap:CFB/total (CFB/total gap floor +2 points).
- Waiting for a second Tuesday: pause:CFB/prop:passYds (Pause CFB/prop:passYds; research and shadow continue).
- Waiting for a second Tuesday: pause:CFB/prop:rec (Pause CFB/prop:rec; research and shadow continue).
- Waiting for a second Tuesday: pause:CFB/total (Pause CFB/total; research and shadow continue).
- Waiting for a second Tuesday: trust:CFB/prop:passYds (CFB/prop:passYds trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:CFB/prop:rec (CFB/prop:rec trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:CFB/prop:recYds (CFB/prop:recYds trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:CFB/prop:rushYds (CFB/prop:rushYds trust 1.00 to 0.98).
- Waiting for a second Tuesday: trust:CFB/spread (CFB/spread trust 1.00 to 1.04).
- Waiting for a second Tuesday: trust:CFB/total (CFB/total trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:NFL/prop:att (NFL/prop:att trust 1.00 to 1.05).
- Waiting for a second Tuesday: trust:NFL/prop:car (NFL/prop:car trust 1.00 to 1.03).
- Waiting for a second Tuesday: trust:NFL/prop:cmp (NFL/prop:cmp trust 1.00 to 1.05).
- Waiting for a second Tuesday: trust:NFL/prop:passYds (NFL/prop:passYds trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:NFL/prop:rec (NFL/prop:rec trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:NFL/prop:recYds (NFL/prop:recYds trust 1.00 to 1.05).
- Waiting for a second Tuesday: trust:NFL/prop:rushYds (NFL/prop:rushYds trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:NFL/total (NFL/total trust 1.00 to 0.95).

## Player chances

- CFB/prop: 1312 graded projections; our favoured side came in 51.0% against a raw 60.8%; tested shrink k 0.15 (previous: 0.23).
- NFL/prop: 2285 graded projections; our favoured side came in 51.3% against a raw 61.5%; tested shrink k 0.11 (previous: 0.13).

## What each rule refused

- bar-4: 109 graded, 52-57, -12.39u, closing line value -0.01 points (90% -0.46 to +0.39, n 35)
- best_quote_by_ev: 7 graded, 3-4, -1.64u, closing line value -0.43 points (90% -1.00 to +0.14, n 7)
- card_cap: 1049 graded, 536-513, -45.45u, closing line value +0.21 points (90% +0.12 to +0.30, n 673)
- cfb_jurisdiction: 46 graded, 25-21, +2.20u, closing line value -0.28 points (90% -0.72 to +0.10, n 30)
- fresh_quote: 29 graded, 13-16, -4.60u
- held: 71 graded, 31-39-1, -10.34u, closing line value -0.32 points (90% -0.59 to -0.01, n 44)
- lean_daily_cap: 26 graded, 11-15, -4.67u, closing line value -0.50 points (90% -0.86 to -0.14, n 26)
- lean_edge: 8 graded, 3-5, -2.26u, closing line value -1.25 points (90% -2.62 to -0.12, n 8)
- lean_nothing_against: 234 graded, 116-118, -15.23u, closing line value +0.19 points (90% -0.00 to +0.39, n 234)
- learned_pause: 58 graded, 11-47, -36.73u, closing line value -0.46 points (90% -0.93 to -0.04, n 58)
- longshot_one_per_day: 0 graded, 0-0, +0.00u
- not_duplicate: 48 graded, 15-33, -18.24u, closing line value +0.11 points (90% -0.15 to +0.36, n 42)
- one_book: 867 graded, 432-435, -56.06u, closing line value +0.26 points (90% +0.14 to +0.39, n 524)
- plan_selection: 122 graded, 61-60-1, -7.16u, closing line value -0.03 points (90% -0.35 to +0.25, n 120)
- player_overlap: 15 graded, 6-9, -3.73u, closing line value +0.18 points (90% -0.09 to +0.55, n 11)
- prop_calibrated_value: 1091 graded, 556-535, -66.78u, closing line value +0.47 points (90% +0.37 to +0.56, n 805)
- prop_injury_clear: 3 graded, 2-1, +0.60u, closing line value -0.33 points (90% -1.00 to +0.00, n 3)
- prop_market_not_trailing: 723 graded, 371-352, +6.72u, closing line value +0.47 points (90% +0.37 to +0.58, n 719)
- prop_not_in_longshot: 56 graded, 23-33, -12.11u, closing line value +0.02 points (90% -0.27 to +0.29, n 41)
- prop_one_per_player: 16 graded, 9-7, +1.09u, closing line value +0.00 points (90% -0.64 to +0.64, n 11)
- prop_price_floor: 5 graded, 2-3, -2.15u, closing line value +0.67 points (90% +0.00 to +1.00, n 3)
- prop_raw_edge: 127 graded, 62-65, -20.21u, closing line value +0.00 points (90% -0.06 to +0.06, n 84)
- prop_settled_role: 4 graded, 1-3, -2.08u, closing line value -1.00 points (90% -4.00 to +1.00, n 4)
- prop_window_cap: 160 graded, 78-82, -16.01u, closing line value +0.31 points (90% +0.12 to +0.50, n 160)
- qb-change-recent: 1 graded, 0-1, -1.00u
- qb_available: 14 graded, 2-12, -10.11u, closing line value +0.21 points (90% -0.11 to +0.57, n 14)
- totals_policy: 25 graded, 10-15, -5.62u, closing line value +0.28 points (90% -0.12 to +0.64, n 25)
- two_sided_straight: 22 graded, 9-13, -4.47u, closing line value +0.36 points (90% -0.04 to +0.73, n 22)
- x_window: 13 graded, 8-5, +1.71u, closing line value -0.14 points (90% -0.43 to +0.00, n 7)

## The judge

- published: 53 graded, 24-29, -6.05u, closing line value +0.02 points (90% -0.32 to +0.39, n 45)
- argues against: 11 graded, 3-8, -5.16u, closing line value -0.25 points (90% -0.60 to +0.10, n 10)
- rule of thumb: 44 graded, 22-21-1, -0.79u, closing line value -0.03 points (90% -0.53 to +0.56, n 18)
- unsure: 10 graded, 4-6, -2.32u, closing line value -1.10 points (90% -1.70 to -0.50, n 10)

## Sources the researcher cited

- 146.freechallenge.14.racing.cbssports.com: 0 of 2 checked out
- abqjournal.com: 4 of 5 checked out
- ajc.com: 2 of 2 checked out
- amp.nfl.com: 2 of 3 checked out
- arizonawildcats.com: 2 of 3 checked out
- atlantafalcons.com: 2 of 2 checked out
- attheroost.com: 3 of 3 checked out
- azcardinals.com: 3 of 3 checked out
- azdesertswarm.com: 2 of 2 checked out
- bceagles.com: 1 of 1 checked out
- boston.com: 3 of 3 checked out
- buffalobills.com: 11 of 11 checked out
- bythebelt.com: 1 of 1 checked out
- chicagobears.com: 8 of 8 checked out
- chiefs.com: 2 of 2 checked out
- clevelandbrowns.com: 3 of 4 checked out
- cuse.com: 1 of 1 checked out
- dailylobo.com: 1 of 1 checked out
- dallascowboys.com: 4 of 4 checked out
- db5y6jlvyeaqj.cloudfront.net: 5 of 5 checked out
- espn.com: 2 of 2 checked out
- fightingillini.com: 1 of 1 checked out
- fiusports.com: 4 of 4 checked out
- floridagators.com: 2 of 3 checked out
- fox11online.com: 1 of 1 checked out
- gamedaynd.com: 1 of 1 checked out
- giants.com: 4 of 5 checked out
- goairforcefalcons.com: 1 of 1 checked out
- goaztecs.com: 5 of 6 checked out
- goheels.com: 7 of 7 checked out
- gohuskies.com: 2 of 2 checked out
- golobos.com: 2 of 2 checked out
- gophersports.com: 2 of 2 checked out
- hawkeyesports.com: 2 of 3 checked out
- hoosierhuddle.com: 4 of 5 checked out
- houstontexans.com: 3 of 4 checked out
- huskers.com: 1 of 1 checked out
- iuhoosiers.com: 3 of 3 checked out
- jaguars.com: 7 of 8 checked out
- jaxstatesports.com: 1 of 1 checked out
- kolotv.com: 3 of 3 checked out
- mgoblue.com: 4 of 4 checked out
- miamihurricanes.com: 3 of 3 checked out
- miamistudent.net: 3 of 3 checked out
- nationalfootballpost.com: 3 of 4 checked out
- navysports.com: 6 of 6 checked out
- nbcmiami.com: 0 of 2 checked out
- nevadawolfpack.com: 1 of 1 checked out
- neworleanssaints.com: 2 of 3 checked out
- newson6.com: 1 of 1 checked out
- nfl.com: 5 of 6 checked out
- nmstatesports.com: 6 of 6 checked out
- odusports.com: 2 of 2 checked out
- osubeavers.com: 1 of 2 checked out
- packers.com: 2 of 2 checked out
- panthers.com: 2 of 2 checked out
- patriots.com: 2 of 4 checked out
- philadelphiaeagles.com: 5 of 5 checked out
- raiders.com: 3 of 4 checked out
- riceowls.com: 1 of 1 checked out
- si.com: 24 of 29 checked out
- smumustangs.com: 1 of 1 checked out
- soflobulls.com: 2 of 4 checked out
- sports.yahoo.com: 13 of 15 checked out
- steelers.com: 3 of 5 checked out
- theacc.com: 4 of 4 checked out
- thedailyhoosier.com: 3 of 4 checked out
- therams.com: 18 of 24 checked out
- thescore.com: 4 of 4 checked out
- uconnhuskies.com: 2 of 2 checked out
- underdogdynasty.com: 3 of 4 checked out
- usforacle.com: 1 of 2 checked out
- utepminers.com: 3 of 4 checked out
- wjr.com: 2 of 2 checked out
- wsbtv.com: 1 of 1 checked out
- wvmetronews.com: 3 of 3 checked out
- wvusports.com: 1 of 1 checked out

## Posts

- reason kind injury: 4 posts, 8.25 engagements per thousand views
- reason kind none: 27 posts, 6.15 engagements per thousand views
- reason kind other: 2 posts, 12.0 engagements per thousand views
- reason kind stats: 1 posts, 29.41 engagements per thousand views

## Which posts and which hours

- announcement: 1 posts, 0.0 engagements per thousand views
- book: 1 posts, 32.26 engagements per thousand views
- cashed: 11 posts, 12.7 engagements per thousand views
- community: 2 posts, 13.51 engagements per thousand views
- conversation: 4 posts, 22.6 engagements per thousand views
- menu: 4 posts, 0.0 engagements per thousand views
- play: 34 posts, 7.42 engagements per thousand views
- receipt: 16 posts, 5.57 engagements per thousand views
- research: 9 posts, 4.46 engagements per thousand views
- sheet: 3 posts, 7.09 engagements per thousand views
- before 9 AM: 4 posts, 1.1 engagements per thousand views
- 9 to 11 AM: 31 posts, 8.35 engagements per thousand views
- 11 AM to 2 PM: 34 posts, 6.97 engagements per thousand views
- 2 to 6 PM: 6 posts, 10.42 engagements per thousand views
- after 6 PM: 10 posts, 12.96 engagements per thousand views

## Card themes by the same post category

- book / legacy: 1 posts, 32.26 engagements per thousand views (small sample)
- cashed / legacy: 2 posts, 20.55 engagements per thousand views (small sample)
- community / legacy: 2 posts, 13.51 engagements per thousand views (small sample)
- menu / legacy: 4 posts, 0.0 engagements per thousand views (small sample)
- play / legacy: 34 posts, 7.42 engagements per thousand views
- receipt / legacy: 15 posts, 5.94 engagements per thousand views
- research / legacy: 9 posts, 4.46 engagements per thousand views
- sheet / legacy: 3 posts, 7.09 engagements per thousand views (small sample)

## Engagement scorecard

- 85 measured posts; 70 human interactions across 11175 impressions; 6.26 per thousand.
- announcement: 1 posts, 0.0 per thousand (small sample)
- book: 1 posts, 32.26 per thousand (small sample)
- cashed: 11 posts, 11.84 per thousand
- community: 2 posts, 13.45 per thousand (small sample)
- conversation: 4 posts, 21.05 per thousand (small sample)
- menu: 4 posts, 0.0 per thousand (small sample)
- play: 34 posts, 5.75 per thousand
- receipt: 16 posts, 5.93 per thousand
- research: 9 posts, 3.61 per thousand
- sheet: 3 posts, 8.77 per thousand (small sample)

## The number against the close (season to date)

- CFB v1: 263 games, total miss 12.75 vs the close's 12.22
- CFB v2.0: 259 games, total miss 12.72 vs the close's 12.3
- NFL v1: 64 games, total miss 11.28 vs the close's 10.05
- NFL v2.0: 60 games, total miss 11.34 vs the close's 10.0
- NFL v2.1: 2 games, total miss 13.2 vs the close's 12.0

## Prop formula review

Earlier 60% of kickoff dates train; later dates test. Both error scores must improve. Repeated retrospective evaluation; future shadow results required before promotion. Counts are prop observations, not independent games; no ROI claim without captured prices.

p = 0.5 + k * (raw - 0.5); k = w*k_market + (1-w)*k_league; w = n_train/(n_train+300)

- CFB/prop:passYds: 140 earlier / 71 later observations; later-game squared probability error 0.2506 league / 0.2503 pooled; shadow candidate.
- CFB/prop:rec: 137 earlier / 121 later observations; later-game squared probability error 0.2491 league / 0.2493 pooled; keep league formula.
- CFB/prop:recYds: 302 earlier / 170 later observations; later-game squared probability error 0.2497 league / 0.2497 pooled; shadow candidate.
- CFB/prop:rushYds: 241 earlier / 130 later observations; later-game squared probability error 0.2508 league / 0.2520 pooled; keep league formula.
- NFL/prop:att: 85 earlier / 33 later observations; later-game squared probability error 0.2510 league / 0.2507 pooled; insufficient history.
- NFL/prop:car: 156 earlier / 60 later observations; later-game squared probability error 0.2514 league / 0.2519 pooled; keep league formula.
- NFL/prop:cmp: 85 earlier / 33 later observations; later-game squared probability error 0.2503 league / 0.2508 pooled; insufficient history.
- NFL/prop:passYds: 83 earlier / 32 later observations; later-game squared probability error 0.2518 league / 0.2514 pooled; insufficient history.
- NFL/prop:rec: 494 earlier / 194 later observations; later-game squared probability error 0.2491 league / 0.2490 pooled; shadow candidate.
- NFL/prop:recYds: 493 earlier / 194 later observations; later-game squared probability error 0.2502 league / 0.2503 pooled; keep league formula.
- NFL/prop:rushYds: 249 earlier / 94 later observations; later-game squared probability error 0.2500 league / 0.2499 pooled; shadow candidate.


## Silent results shadows

- These observations changed no play, card, post, record, gate or request budget.
- R0: 2156 raw rows, 1301 distinct
- R1: observation active; public behavior unchanged
- R2: observation active; public behavior unchanged
- R3: 11 prop markets observed
- R4: observation active; public behavior unchanged
- R5: 69 heavy alternates observed; default unchanged
- R6: observation active; public behavior unchanged
- R7: observation active; public behavior unchanged
