# What the kitchen learned, 2026-10-20

2857 recorded candidate rows, 1830 distinct game/side/player observations, 2740 graded. Closing line value is how far the market moved toward our side by kickoff; it is the first thing learning trusts.

## Changes this week

- **researcher** domains: {'preferDomains': ['si.com', 'sports.yahoo.com', 'buffalobills.com', 'chicagobears.com', 'jaguars.com', 'goheels.com', 'goaztecs.com', 'navysports.com'], 'avoidDomains': []} to {'preferDomains': ['si.com', 'sports.yahoo.com', 'buffalobills.com', 'seahawks.com', 'underdogdynasty.com', 'chicagobears.com', 'denverbroncos.com', 'jaguars.com'], 'avoidDomains': []}. Which sites the researcher cites keep checking out.
- **CFB/prop:passYds** twoWay.trust: 1.0 to 0.95. CFB/prop:passYds trust 1.00 to 0.95.
- **CFB/prop:passYds** twoWay.gap: 0.0 to 2.0. CFB/prop:passYds gap floor +2 points.
- **CFB/prop:passYds** twoWay.pause: False to True. Pause CFB/prop:passYds; research and shadow continue.
- **CFB/prop:rec** twoWay.trust: 1.0 to 0.95. CFB/prop:rec trust 1.00 to 0.95.
- **CFB/prop:rec** twoWay.gap: 0.0 to 2.0. CFB/prop:rec gap floor +2 points.
- **CFB/prop:rec** twoWay.pause: False to True. Pause CFB/prop:rec; research and shadow continue.
- **CFB/prop:recYds** twoWay.trust: 1.0 to 0.985. CFB/prop:recYds trust 1.00 to 0.98.
- **CFB/prop:rushYds** twoWay.trust: 1.0 to 0.965. CFB/prop:rushYds trust 1.00 to 0.96.
- **CFB/total** twoWay.trust: 1.0 to 0.95. CFB/total trust 1.00 to 0.95.
- **NFL/prop:att** twoWay.trust: 1.0 to 1.045. NFL/prop:att trust 1.00 to 1.04.
- **NFL/prop:cmp** twoWay.trust: 1.0 to 1.05. NFL/prop:cmp trust 1.00 to 1.05.
- **NFL/prop:passYds** twoWay.trust: 1.0 to 0.95. NFL/prop:passYds trust 1.00 to 0.95.
- **NFL/prop:rec** twoWay.trust: 1.0 to 0.959. NFL/prop:rec trust 1.00 to 0.96.
- **NFL/prop:recYds** twoWay.trust: 1.0 to 1.05. NFL/prop:recYds trust 1.00 to 1.05.
- **NFL/prop:rushYds** twoWay.trust: 1.0 to 0.95. NFL/prop:rushYds trust 1.00 to 0.95.
- **NFL/total** twoWay.trust: 1.0 to 0.95. NFL/total trust 1.00 to 0.95.

## Direction changes

Owner-approved bounded moves (2026-10-07): they only tighten, pause, shift weight between approved categories, or restore what they tightened. Nothing loosens below the Oct 7 baseline, no market is added, and the record and published plays are untouched.

Applied:
- none

In force now:
- NFL totals: paused as a best bet since 2026-10-08 (research and shadow only)

## Segments (published since their last change)

- CFB/parlay/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/prop:passYds (min edge 5): published 1-0, +1.00u; near misses 3-9, -6.37u
- CFB/prop:rec (min edge 5): published 2-0, +2.20u; near misses 5-11, -6.56u
- CFB/prop:rec/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/prop:recYds (min edge 5): published 1-1, -0.17u; near misses 12-10, +0.63u
- CFB/prop:rushYds (min edge 5): published 0-1, -1.00u; near misses 13-11, +0.39u
- CFB/spread (min edge 1): published 1-1, -0.05u, closing line value -0.25 points (90% -0.50 to +0.00, n 2); near misses 0-0, +0.00u
- CFB/total (min edge 1): published 8-11, -3.42u, closing line value +0.00 points (90% -0.47 to +0.55, n 19); near misses 0-0, +0.00u
- NFL/moneyline (min edge 1): published 1-0, +0.93u; near misses 0-0, +0.00u
- NFL/moneyline/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:att (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:car (min edge 5): published 1-2, -1.10u, closing line value +0.00 points (90% +0.00 to +0.00, n 3); near misses 0-0, +0.00u
- NFL/prop:car/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:cmp (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:cmp/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:passYds (min edge 5): published 0-0, +0.00u; near misses 0-1, -1.00u, closing line value -8.00 points (90% -8.00 to -8.00, n 1)
- NFL/prop:rec (min edge 5): published 3-2, +1.06u, closing line value +0.00 points (90% +0.00 to +0.00, n 4); near misses 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1)
- NFL/prop:rec/plus_money (min edge 5): published 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1); near misses 0-0, +0.00u
- NFL/prop:recYds (min edge 5): published 6-3, +2.51u, closing line value +1.00 points (90% +0.00 to +2.12, n 8); near misses 3-1, +1.76u, closing line value +0.75 points (90% -1.50 to +3.00, n 4)
- NFL/prop:recYds/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:rushYds (min edge 5): published 0-3, -3.00u, closing line value -1.33 points (90% -3.33 to +1.00, n 3); near misses 0-0, +0.00u
- NFL/prop:rushYds/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/spread (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/total (higher-bar caution): published 0-4, -4.00u, closing line value -0.50 points (90% -1.00 to +0.12, n 4); near misses 1-0, +0.91u, closing line value +0.50 points (90% +0.50 to +0.50, n 1)

## Two-way Autopilot learning

- Applied trust:CFB/prop:passYds: CFB/prop:passYds trust 1.00 to 0.95.
- Applied gap:CFB/prop:passYds: CFB/prop:passYds gap floor +2 points.
- Applied pause:CFB/prop:passYds: Pause CFB/prop:passYds; research and shadow continue.
- Applied trust:CFB/prop:rec: CFB/prop:rec trust 1.00 to 0.95.
- Applied gap:CFB/prop:rec: CFB/prop:rec gap floor +2 points.
- Applied pause:CFB/prop:rec: Pause CFB/prop:rec; research and shadow continue.
- Applied trust:CFB/prop:recYds: CFB/prop:recYds trust 1.00 to 0.98.
- Applied trust:CFB/prop:rushYds: CFB/prop:rushYds trust 1.00 to 0.96.
- Applied trust:CFB/total: CFB/total trust 1.00 to 0.95.
- Applied trust:NFL/prop:att: NFL/prop:att trust 1.00 to 1.04.
- Applied trust:NFL/prop:cmp: NFL/prop:cmp trust 1.00 to 1.05.
- Applied trust:NFL/prop:passYds: NFL/prop:passYds trust 1.00 to 0.95.
- Applied trust:NFL/prop:rec: NFL/prop:rec trust 1.00 to 0.96.
- Applied trust:NFL/prop:recYds: NFL/prop:recYds trust 1.00 to 1.05.
- Applied trust:NFL/prop:rushYds: NFL/prop:rushYds trust 1.00 to 0.95.
- Applied trust:NFL/total: NFL/total trust 1.00 to 0.95.
- Waiting for a second Tuesday: trust:CFB/spread (CFB/spread trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:NFL/prop:rec/plus_money (NFL/prop:rec/plus_money trust 1.00 to 1.01).
- Waiting for a second Tuesday: trust:NFL/spread (NFL/spread trust 1.00 to 0.96).

## Player chances

- CFB/prop: 1811 graded projections; our favoured side came in 51.4% against a raw 60.6%; tested shrink k 0.13 (previous: 0.15).
- NFL/prop: 2841 graded projections; our favoured side came in 51.4% against a raw 61.4%; tested shrink k 0.14 (previous: 0.11).

## What each rule refused

- bar-4: 109 graded, 52-57, -12.39u, closing line value -0.01 points (90% -0.46 to +0.39, n 35)
- best_quote_by_ev: 94 graded, 40-52-2, -17.96u, closing line value +0.11 points (90% -0.11 to +0.33, n 92)
- card_cap: 1100 graded, 565-535, -41.95u, closing line value +0.23 points (90% +0.15 to +0.31, n 722)
- cfb_jurisdiction: 47 graded, 25-22, +1.20u, closing line value -0.37 points (90% -0.77 to +0.05, n 31)
- fresh_quote: 45 graded, 21-24, -5.31u
- held: 239 graded, 120-118-1, -10.35u, closing line value -0.01 points (90% -0.22 to +0.19, n 87)
- lean_daily_cap: 26 graded, 11-15, -4.67u, closing line value -0.50 points (90% -0.86 to -0.14, n 26)
- lean_edge: 8 graded, 3-5, -2.26u, closing line value -1.25 points (90% -2.62 to -0.12, n 8)
- lean_nothing_against: 286 graded, 147-138-1, -7.72u, closing line value +0.23 points (90% +0.07 to +0.40, n 286)
- learned_pause: 68 graded, 14-53-1, -39.98u, closing line value -0.39 points (90% -0.78 to -0.01, n 68)
- longshot_one_per_day: 0 graded, 0-0, +0.00u
- not_duplicate: 48 graded, 15-33, -18.24u, closing line value +0.11 points (90% -0.15 to +0.36, n 42)
- one_book: 1080 graded, 534-542-4, -72.64u, closing line value +0.25 points (90% +0.15 to +0.36, n 635)
- plan_selection: 407 graded, 221-185-1, +7.37u, closing line value +0.10 points (90% -0.04 to +0.25, n 383)
- player_overlap: 20 graded, 10-10, -1.38u, closing line value +0.38 points (90% +0.00 to +0.81, n 16)
- prop_calibrated_value: 1091 graded, 556-535, -66.78u, closing line value +0.47 points (90% +0.37 to +0.56, n 805)
- prop_injury_clear: 15 graded, 10-5, +3.63u, closing line value +0.53 points (90% -0.13 to +1.33, n 15)
- prop_market_not_trailing: 723 graded, 371-352, +6.72u, closing line value +0.47 points (90% +0.37 to +0.58, n 719)
- prop_not_in_longshot: 61 graded, 27-34, -9.76u, closing line value +0.11 points (90% -0.15 to +0.39, n 46)
- prop_one_per_player: 16 graded, 9-7, +1.09u, closing line value +0.00 points (90% -0.64 to +0.64, n 11)
- prop_price_floor: 5 graded, 2-3, -2.15u, closing line value +0.67 points (90% +0.00 to +1.00, n 3)
- prop_raw_edge: 127 graded, 62-65, -20.21u, closing line value +0.00 points (90% -0.06 to +0.06, n 84)
- prop_settled_role: 31 graded, 15-16, -2.83u, closing line value -0.19 points (90% -0.77 to +0.35, n 31)
- prop_window_cap: 160 graded, 78-82, -16.01u, closing line value +0.31 points (90% +0.12 to +0.50, n 160)
- qb-change-recent: 1 graded, 0-1, -1.00u
- qb_available: 16 graded, 2-13-1, -11.11u, closing line value +0.28 points (90% -0.03 to +0.59, n 16)
- ticket_research: 0 graded, 0-0, +0.00u
- totals_policy: 64 graded, 29-35, -8.34u, closing line value +0.36 points (90% +0.12 to +0.59, n 64)
- two_sided_straight: 22 graded, 9-13, -4.47u, closing line value +0.36 points (90% -0.04 to +0.73, n 22)
- x_window: 172 graded, 92-77-3, +3.58u, closing line value +0.38 points (90% +0.21 to +0.56, n 110)

## The judge

- published: 58 graded, 26-32, -7.19u, closing line value +0.04 points (90% -0.30 to +0.38, n 49)
- argues against: 16 graded, 5-11, -6.43u, closing line value +0.03 points (90% -0.37 to +0.50, n 15)
- rule of thumb: 99 graded, 49-49-1, -5.03u, closing line value -0.09 points (90% -0.46 to +0.26, n 33)
- unsure: 10 graded, 4-6, -2.32u, closing line value -1.10 points (90% -1.70 to -0.50, n 10)

## Sources the researcher cited

- 146.freechallenge.14.racing.cbssports.com: 0 of 2 checked out
- 49ers.com: 6 of 7 checked out
- abqjournal.com: 4 of 5 checked out
- ajc.com: 2 of 2 checked out
- amp.nfl.com: 5 of 7 checked out
- appstatesports.com: 4 of 4 checked out
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
- commanders.com: 6 of 7 checked out
- cuse.com: 1 of 1 checked out
- dailylobo.com: 1 of 1 checked out
- dallascowboys.com: 5 of 6 checked out
- db5y6jlvyeaqj.cloudfront.net: 5 of 5 checked out
- denverbroncos.com: 7 of 8 checked out
- denvergazette.com: 1 of 1 checked out
- espn.com: 2 of 2 checked out
- fightingillini.com: 1 of 1 checked out
- fiusports.com: 4 of 4 checked out
- floridagators.com: 2 of 3 checked out
- fox11online.com: 1 of 1 checked out
- gamedaynd.com: 1 of 1 checked out
- giants.com: 4 of 5 checked out
- goairforcefalcons.com: 1 of 1 checked out
- goaztecs.com: 5 of 6 checked out
- goccusports.com: 3 of 3 checked out
- goheels.com: 7 of 7 checked out
- gohuskies.com: 2 of 2 checked out
- golobos.com: 2 of 2 checked out
- gophersports.com: 2 of 2 checked out
- gotigersgo.com: 7 of 7 checked out
- gousfbulls.com: 2 of 2 checked out
- hawkeyesports.com: 2 of 3 checked out
- hoosierhuddle.com: 4 of 5 checked out
- houstontexans.com: 3 of 4 checked out
- huskers.com: 1 of 1 checked out
- iuhoosiers.com: 3 of 3 checked out
- jaguars.com: 7 of 8 checked out
- jaxstatesports.com: 1 of 1 checked out
- kentstatesports.com: 3 of 3 checked out
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
- packers.com: 4 of 5 checked out
- panthers.com: 2 of 2 checked out
- patriots.com: 2 of 4 checked out
- philadelphiaeagles.com: 5 of 5 checked out
- purduesports.com: 2 of 2 checked out
- raiders.com: 3 of 4 checked out
- riceowls.com: 1 of 1 checked out
- seahawks.com: 8 of 10 checked out
- si.com: 30 of 35 checked out
- smumustangs.com: 1 of 1 checked out
- soflobulls.com: 2 of 4 checked out
- southernmiss.com: 3 of 3 checked out
- sports.yahoo.com: 13 of 15 checked out
- steelers.com: 3 of 5 checked out
- theacc.com: 4 of 4 checked out
- thedailyhoosier.com: 3 of 4 checked out
- therams.com: 18 of 24 checked out
- thescore.com: 4 of 4 checked out
- txst.com: 2 of 2 checked out
- uconnhuskies.com: 2 of 2 checked out
- underdogdynasty.com: 8 of 9 checked out
- usforacle.com: 1 of 2 checked out
- utepminers.com: 3 of 4 checked out
- wjr.com: 2 of 2 checked out
- wsbtv.com: 1 of 1 checked out
- wvmetronews.com: 3 of 3 checked out
- wvusports.com: 1 of 1 checked out

## Posts

- reason kind injury: 5 posts, 6.6 engagements per thousand views
- reason kind none: 27 posts, 6.15 engagements per thousand views
- reason kind other: 5 posts, 4.8 engagements per thousand views
- reason kind stats: 3 posts, 14.43 engagements per thousand views

## Which posts and which hours

- announcement: 1 posts, 0.0 engagements per thousand views
- book: 1 posts, 32.26 engagements per thousand views
- cashed: 15 posts, 12.35 engagements per thousand views
- community: 4 posts, 8.2 engagements per thousand views
- conversation: 4 posts, 22.6 engagements per thousand views
- menu: 4 posts, 0.0 engagements per thousand views
- news: 1 posts, 0.0 engagements per thousand views
- play: 40 posts, 6.66 engagements per thousand views
- receipt: 20 posts, 7.16 engagements per thousand views
- research: 15 posts, 4.77 engagements per thousand views
- sheet: 5 posts, 4.26 engagements per thousand views
- before 9 AM: 6 posts, 8.31 engagements per thousand views
- 9 to 11 AM: 46 posts, 7.91 engagements per thousand views
- 11 AM to 2 PM: 38 posts, 6.24 engagements per thousand views
- 2 to 6 PM: 6 posts, 10.42 engagements per thousand views
- after 6 PM: 14 posts, 9.26 engagements per thousand views

## Card themes by the same post category

- book / legacy: 1 posts, 32.26 engagements per thousand views (small sample)
- cashed / legacy: 6 posts, 14.43 engagements per thousand views (small sample)
- community / legacy: 3 posts, 10.94 engagements per thousand views (small sample)
- menu / legacy: 4 posts, 0.0 engagements per thousand views (small sample)
- play / legacy: 40 posts, 6.66 engagements per thousand views
- receipt / legacy: 19 posts, 7.54 engagements per thousand views
- research / legacy: 15 posts, 4.77 engagements per thousand views
- sheet / legacy: 5 posts, 4.26 engagements per thousand views (small sample)

## Matchup-supported leans

- 52 graded, distinct matchup-supported observations. Reporting only; this changes no gate.
- NFL/CFB: player defense-vs-position and opponent-quality splits are active.
- NBA/CBB: team projections are active; player defense-vs-position is not live yet.
- EPL/MLS: team-level score and market shadows only.
- MLB: scores and market collection only; no batter-vs-pitcher lean yet.
- NHL: scores and market collection only; no skater/goalie lean yet.
- NFL WR over recYds vs bottom-half defense: 5-1, +3.54u (n 6).
- NFL TE over rec vs bottom-half defense: 3-3, -0.39u (n 6).
- NFL WR over rec vs bottom-half defense: 3-1, +1.51u (n 4).
- NFL WR under rec vs top 10 defense: 3-1, +1.24u (n 4).
- NFL TE over recYds vs bottom-half defense: 2-2, -0.23u (n 4).
- NFL RB over recYds vs bottom-half defense: 2-1, +0.89u (n 3).
- NFL QB over rushYds vs bottom-half defense: 2-1, +0.74u (n 3).
- NFL QB over cmp vs bottom-half defense: 2-1, +0.67u (n 3).
- NFL RB over rec vs bottom-half defense: 0-3, -3.00u (n 3).
- NFL QB over att vs bottom-half defense: 2-0, +1.78u (n 2).
- NFL TE under rec vs top 10 defense: 2-0, +1.40u (n 2).
- NFL WR under recYds vs top 10 defense: 1-1, -0.11u (n 2).
- NFL RB under car vs top 10 defense: 1-1, -0.23u (n 2).
- CFB WR over rec vs bottom-half defense: 1-0, +1.12u (n 1).
- NFL RB over rushYds vs bottom-half defense: 1-0, +0.91u (n 1).
- NFL QB over passYds vs bottom-half defense: 1-0, +0.88u (n 1).
- NFL WR over rushYds vs bottom-half defense: 1-0, +0.88u (n 1).
- NFL RB over car vs bottom-half defense: 1-0, +0.79u (n 1).
- CFB WR under recYds vs top-half defense: 0-1, -1.00u (n 1).
- NFL QB under cmp vs top 10 defense: 0-1, -1.00u (n 1).
- NFL RB under rushYds vs top 10 defense: 0-1, -1.00u (n 1).

## Released multi-leg tickets

- 9 released and graded tickets. Unreleased ideas are excluded.
- Climb / 2-leg / all alternates: 2-2-0-0, -0.24u on 4 with stored units (n 4).
- Climb / 2-leg / main lines: 1-0-0-0, +0.18u on 1 with stored units (n 1).
- Fun ticket / 3-leg / main lines: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 5-leg / main lines: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 5-leg / mixed alternates: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 3-leg / unclassified: 0-1-0-0, units unavailable (n 1).

## Engagement scorecard

- 110 measured posts; 79 human interactions across 13623 impressions; 5.8 per thousand.
- announcement: 1 posts, 0.0 per thousand (small sample)
- book: 1 posts, 32.26 per thousand (small sample)
- cashed: 15 posts, 11.19 per thousand
- community: 4 posts, 9.64 per thousand (small sample)
- conversation: 4 posts, 21.05 per thousand (small sample)
- menu: 4 posts, 0.0 per thousand (small sample)
- news: 1 posts, 0.0 per thousand (small sample)
- play: 40 posts, 5.36 per thousand
- receipt: 20 posts, 6.46 per thousand
- research: 15 posts, 3.94 per thousand
- sheet: 5 posts, 6.45 per thousand (small sample)

## The number against the close (season to date)

- CFB v1: 325 games, total miss 12.83 vs the close's 12.33
- CFB v2.0: 259 games, total miss 12.72 vs the close's 12.3
- CFB v2.1: 62 games, total miss 13.44 vs the close's 12.79
- NFL v1: 78 games, total miss 11.38 vs the close's 10.24
- NFL v2.0: 60 games, total miss 11.34 vs the close's 10.1
- NFL v2.1: 16 games, total miss 11.4 vs the close's 10.88

## Prop formula review

Earlier 60% of kickoff dates train; later dates test. Both error scores must improve. Repeated retrospective evaluation; future shadow results required before promotion. Counts are prop observations, not independent games; no ROI claim without captured prices.

p = 0.5 + k * (raw - 0.5); k = w*k_market + (1-w)*k_league; w = n_train/(n_train+300)

- CFB/prop:passYds: 155 earlier / 123 later observations; later-game squared probability error 0.2531 league / 0.2525 pooled; shadow candidate.
- CFB/prop:rec: 162 earlier / 214 later observations; later-game squared probability error 0.2475 league / 0.2483 pooled; keep league formula.
- CFB/prop:recYds: 341 earlier / 314 later observations; later-game squared probability error 0.2487 league / 0.2487 pooled; shadow candidate.
- CFB/prop:rushYds: 271 earlier / 231 later observations; later-game squared probability error 0.2502 league / 0.2510 pooled; keep league formula.
- NFL/prop:att: 89 earlier / 55 later observations; later-game squared probability error 0.2526 league / 0.2520 pooled; insufficient history.
- NFL/prop:car: 163 earlier / 104 later observations; later-game squared probability error 0.2501 league / 0.2502 pooled; keep league formula.
- NFL/prop:cmp: 89 earlier / 55 later observations; later-game squared probability error 0.2509 league / 0.2524 pooled; insufficient history.
- NFL/prop:passYds: 87 earlier / 52 later observations; later-game squared probability error 0.2530 league / 0.2523 pooled; insufficient history.
- NFL/prop:rec: 519 earlier / 343 later observations; later-game squared probability error 0.2485 league / 0.2483 pooled; shadow candidate.
- NFL/prop:recYds: 518 earlier / 341 later observations; later-game squared probability error 0.2498 league / 0.2498 pooled; keep league formula.
- NFL/prop:rushYds: 260 earlier / 166 later observations; later-game squared probability error 0.2526 league / 0.2513 pooled; shadow candidate.


## Silent results shadows

- These observations changed no play, card, post, record, gate or request budget.
- R0: 2848 raw rows, 1826 distinct
- R1: observation active; public behavior unchanged
- R2: observation active; public behavior unchanged
- R3: 11 prop markets observed
- R4: observation active; public behavior unchanged
- R5: 81 heavy alternates observed; default unchanged
- R6: observation active; public behavior unchanged
- R7: observation active; public behavior unchanged
