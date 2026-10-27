# What the kitchen learned, 2026-10-27

4201 recorded candidate rows, 2876 distinct game/side/player observations, 4076 graded. Closing line value is how far the market moved toward our side by kickoff; it is the first thing learning trusts.

## Changes this week

- **Climb/alternate-offers** ladderSegments: 0 to 0. Weekly stored pregame alternate offers versus official final boxes.
- **NFL/prop** calibration: 0.11 to 0.09. Calibrated chances predicted the later record better than the raw ones.
- **researcher** domains: {'avoidDomains': [], 'preferDomains': ['si.com', 'sports.yahoo.com', 'buffalobills.com', 'seahawks.com', 'underdogdynasty.com', 'chicagobears.com', 'denverbroncos.com', 'jaguars.com']} to {'avoidDomains': [], 'preferDomains': ['si.com', 'sports.yahoo.com', 'philadelphiaeagles.com', 'abqjournal.com', 'chicagobears.com', 'buffalobills.com', 'denverbroncos.com', 'seahawks.com']}. Which sites the researcher cites keep checking out.
- **CFB/prop:passYds** twoWay.trust: 0.95 to 0.9. CFB/prop:passYds trust 0.95 to 0.90.
- **CFB/prop:rec** twoWay.trust: 0.95 to 0.9. CFB/prop:rec trust 0.95 to 0.90.
- **CFB/spread** twoWay.trust: 1.0 to 0.95. CFB/spread trust 1.00 to 0.95.
- **CFB/total** twoWay.trust: 0.95 to 0.9. CFB/total trust 0.95 to 0.90.
- **NFL/prop:cmp** twoWay.trust: 1.05 to 1.1. NFL/prop:cmp trust 1.05 to 1.10.
- **NFL/prop:passYds** twoWay.trust: 0.95 to 0.923. NFL/prop:passYds trust 0.95 to 0.92.
- **NFL/prop:rec/plus_money** twoWay.trust: 1.0 to 1.048. NFL/prop:rec/plus_money trust 1.00 to 1.05.
- **NFL/prop:recYds** twoWay.trust: 1.05 to 1.06. NFL/prop:recYds trust 1.05 to 1.06.
- **NFL/prop:rushYds** twoWay.trust: 0.95 to 0.9. NFL/prop:rushYds trust 0.95 to 0.90.
- **NFL/spread** twoWay.trust: 1.0 to 0.95. NFL/spread trust 1.00 to 0.95.
- **NFL/total** twoWay.trust: 0.95 to 0.9. NFL/total trust 0.95 to 0.90.
- **Climb/alternate-offers** ladderSegments: 0 to 0. Weekly stored pregame alternate offers versus official final boxes.
- **Climb/alternate-offers** ladderSegments: 0 to 0. Weekly stored pregame alternate offers versus official final boxes.

## Direction changes

Owner-approved bounded moves (2026-10-07): they only tighten, pause, shift weight between approved categories, or restore what they tightened. Nothing loosens below the Oct 7 baseline, no market is added, and the record and published plays are untouched.

Applied:
- none

In force now:
- NFL totals: paused as a best bet since 2026-10-08 (research and shadow only)

## Segments (published since their last change)

- CFB/moneyline (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/moneyline/plus_money (min edge 1): published 0-2, -2.00u; near misses 0-0, +0.00u
- CFB/parlay/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/prop:passYds (min edge 5): published 1-0, +1.00u; near misses 3-9, -6.37u
- CFB/prop:rec (min edge 5): published 2-0, +2.20u; near misses 5-11, -6.56u
- CFB/prop:rec/plus_money (min edge 5): published 1-2, -0.80u; near misses 0-0, +0.00u
- CFB/prop:recYds (min edge 5): published 1-1, -0.17u; near misses 12-10, +0.63u
- CFB/prop:rushYds (min edge 5): published 0-1, -1.00u; near misses 13-11, +0.39u
- CFB/spread (min edge 1): published 1-1, -0.05u, closing line value -0.25 points (90% -0.50 to +0.00, n 2); near misses 0-0, +0.00u
- CFB/spread/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/total (min edge 1): published 11-13, -2.67u, closing line value +0.08 points (90% -0.40 to +0.56, n 24); near misses 0-0, +0.00u
- CFB/total/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/moneyline (min edge 1): published 1-0, +0.93u; near misses 0-0, +0.00u
- NFL/moneyline/plus_money (min edge 1): published 0-1, -1.00u; near misses 0-0, +0.00u
- NFL/parlay/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:att (min edge 5): published 1-0, +0.98u; near misses 0-0, +0.00u
- NFL/prop:car (min edge 5): published 1-2, -1.10u, closing line value +0.00 points (90% +0.00 to +0.00, n 3); near misses 0-0, +0.00u
- NFL/prop:car/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:cmp (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:cmp/plus_money (min edge 5): published 0-2, -2.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 2); near misses 0-0, +0.00u
- NFL/prop:passYds (min edge 5): published 0-0, +0.00u; near misses 0-1, -1.00u, closing line value -8.00 points (90% -8.00 to -8.00, n 1)
- NFL/prop:rec (min edge 5): published 4-2, +2.04u, closing line value +0.00 points (90% +0.00 to +0.00, n 5); near misses 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1)
- NFL/prop:rec/plus_money (min edge 5): published 1-3, -1.52u, closing line value +0.00 points (90% +0.00 to +0.00, n 4); near misses 0-0, +0.00u
- NFL/prop:recYds (min edge 5): published 6-3, +2.51u, closing line value +1.00 points (90% +0.00 to +2.12, n 8); near misses 3-1, +1.76u, closing line value +0.75 points (90% -1.50 to +3.00, n 4)
- NFL/prop:recYds/plus_money (min edge 5): published 1-1, +0.05u, closing line value -2.00 points (90% -2.00 to -2.00, n 2); near misses 0-0, +0.00u
- NFL/prop:rushYds (min edge 5): published 0-3, -3.00u, closing line value -1.33 points (90% -3.33 to +1.00, n 3); near misses 0-0, +0.00u
- NFL/prop:rushYds/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/spread (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/spread/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/total (higher-bar caution): published 0-4, -4.00u, closing line value -0.50 points (90% -1.00 to +0.12, n 4); near misses 8-8, -0.57u, closing line value -0.06 points (90% -0.31 to +0.25, n 16)
- NFL/total/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u

## Two-way Autopilot learning

- Waiting for a second Tuesday: gap:NFL/total (NFL/total gap floor +2 points).
- Waiting for a second Tuesday: pause:CFB/total (Pause CFB/total; research and shadow continue).
- Waiting for a second Tuesday: trust:CFB/moneyline (CFB/moneyline trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:CFB/moneyline/plus_money (CFB/moneyline/plus_money trust 1.00 to 1.05).
- Waiting for a second Tuesday: trust:CFB/prop:passYds (CFB/prop:passYds trust 0.90 to 0.88).
- Waiting for a second Tuesday: trust:CFB/prop:rec (CFB/prop:rec trust 0.90 to 0.85).
- Waiting for a second Tuesday: trust:CFB/prop:recYds (CFB/prop:recYds trust 0.98 to 1.03).
- Waiting for a second Tuesday: trust:CFB/prop:rushYds (CFB/prop:rushYds trust 0.96 to 0.96).
- Waiting for a second Tuesday: trust:CFB/spread (CFB/spread trust 0.95 to 0.93).
- Waiting for a second Tuesday: trust:CFB/total (CFB/total trust 0.90 to 0.87).
- Waiting for a second Tuesday: trust:CFB/total/plus_money (CFB/total/plus_money trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:NFL/moneyline (NFL/moneyline trust 1.00 to 1.02).
- Waiting for a second Tuesday: trust:NFL/moneyline/plus_money (NFL/moneyline/plus_money trust 1.00 to 0.97).
- Waiting for a second Tuesday: trust:NFL/prop:att (NFL/prop:att trust 1.04 to 1.01).
- Waiting for a second Tuesday: trust:NFL/prop:car (NFL/prop:car trust 1.00 to 0.99).
- Waiting for a second Tuesday: trust:NFL/prop:cmp (NFL/prop:cmp trust 1.10 to 1.12).
- Waiting for a second Tuesday: trust:NFL/prop:rec (NFL/prop:rec trust 0.96 to 0.99).
- Waiting for a second Tuesday: trust:NFL/prop:recYds/plus_money (NFL/prop:recYds/plus_money trust 1.00 to 1.03).
- Waiting for a second Tuesday: trust:NFL/prop:rushYds (NFL/prop:rushYds trust 0.90 to 0.85).
- Waiting for a second Tuesday: trust:NFL/spread (NFL/spread trust 0.95 to 0.94).
- Waiting for a second Tuesday: trust:NFL/total (NFL/total trust 0.90 to 0.85).

## Player chances

- CFB/prop: 2347 graded projections; our favoured side came in 51.8% against a raw 60.6%; tested shrink k 0.14 (previous: 0.15).
- NFL/prop: 3361 graded projections; our favoured side came in 51.6% against a raw 61.3%; tested shrink k 0.09 (previous: 0.09).

## What each rule refused

- bar-4: 109 graded, 52-57, -12.39u, closing line value -0.01 points (90% -0.46 to +0.39, n 35)
- best_quote_by_ev: 119 graded, 52-65-2, -20.30u, closing line value +0.04 points (90% -0.16 to +0.25, n 115)
- card_cap: 1208 graded, 614-594, -55.05u, closing line value +0.20 points (90% +0.12 to +0.29, n 822)
- cfb_jurisdiction: 47 graded, 25-22, +1.20u, closing line value -0.37 points (90% -0.77 to +0.05, n 31)
- daily_exposure: 60 graded, 31-29, -2.01u, closing line value +0.24 points (90% +0.07 to +0.41, n 54)
- expiry_ok: 20 graded, 12-8, +2.51u
- fresh_quote: 69 graded, 37-32, +0.68u
- held: 846 graded, 418-425-3, -40.57u, closing line value -0.04 points (90% -0.13 to +0.06, n 368)
- lean_daily_cap: 26 graded, 11-15, -4.67u, closing line value -0.50 points (90% -0.86 to -0.14, n 26)
- lean_edge: 8 graded, 3-5, -2.26u, closing line value -1.25 points (90% -2.62 to -0.12, n 8)
- lean_nothing_against: 306 graded, 156-149-1, -9.81u, closing line value +0.22 points (90% +0.06 to +0.38, n 305)
- learned_pause: 100 graded, 29-70-1, -43.03u, closing line value -0.28 points (90% -0.56 to -0.01, n 100)
- longshot_one_per_day: 0 graded, 0-0, +0.00u
- not_duplicate: 51 graded, 17-34, -17.12u, closing line value +0.10 points (90% -0.12 to +0.34, n 45)
- one_book: 1342 graded, 657-681-4, -99.27u, closing line value +0.27 points (90% +0.17 to +0.37, n 692)
- plan_selection: 921 graded, 489-431-1, +1.00u, closing line value +0.21 points (90% +0.12 to +0.29, n 862)
- player_overlap: 49 graded, 28-21, +3.72u, closing line value +0.29 points (90% -0.10 to +0.73, n 41)
- prop_calibrated_value: 1091 graded, 556-535, -66.78u, closing line value +0.47 points (90% +0.37 to +0.56, n 805)
- prop_injury_clear: 21 graded, 14-7, +5.85u, closing line value +0.24 points (90% -0.29 to +0.86, n 21)
- prop_market_not_trailing: 723 graded, 371-352, +6.72u, closing line value +0.47 points (90% +0.37 to +0.58, n 719)
- prop_not_in_longshot: 90 graded, 45-45, -4.66u, closing line value +0.15 points (90% -0.11 to +0.45, n 71)
- prop_one_per_player: 16 graded, 9-7, +1.09u, closing line value +0.00 points (90% -0.64 to +0.64, n 11)
- prop_price_floor: 5 graded, 2-3, -2.15u, closing line value +0.67 points (90% +0.00 to +1.00, n 3)
- prop_raw_edge: 127 graded, 62-65, -20.21u, closing line value +0.00 points (90% -0.06 to +0.06, n 84)
- prop_settled_role: 46 graded, 21-25, -6.67u, closing line value -0.07 points (90% -0.48 to +0.35, n 46)
- prop_window_cap: 160 graded, 78-82, -16.01u, closing line value +0.31 points (90% +0.12 to +0.50, n 160)
- qb-change-recent: 3 graded, 2-1, +0.72u
- qb_available: 19 graded, 3-15-1, -12.18u, closing line value +0.21 points (90% -0.05 to +0.50, n 19)
- ticket_research: 0 graded, 0-0, +0.00u
- totals_policy: 103 graded, 46-57, -14.32u, closing line value +0.10 points (90% -0.09 to +0.29, n 103)
- two_sided_straight: 22 graded, 9-13, -4.47u, closing line value +0.36 points (90% -0.04 to +0.73, n 22)
- x_window: 317 graded, 160-154-3, -12.48u, closing line value +0.17 points (90% +0.03 to +0.32, n 161)

## The judge

- published: 78 graded, 34-44, -10.76u, closing line value +0.00 points (90% -0.30 to +0.32, n 62)
- argues against: 19 graded, 5-14, -9.43u, closing line value +0.14 points (90% -0.25 to +0.58, n 18)
- rule of thumb: 477 graded, 239-235-3, -16.49u, closing line value +0.00 points (90% -0.11 to +0.11, n 249)
- unsure: 10 graded, 4-6, -2.32u, closing line value -1.10 points (90% -1.70 to -0.50, n 10)

## Sources the researcher cited

- 1069thefan.com: 3 of 4 checked out
- 146.freechallenge.14.racing.cbssports.com: 0 of 2 checked out
- 49ers.com: 6 of 7 checked out
- abqjournal.com: 16 of 17 checked out
- ajc.com: 2 of 2 checked out
- amp.nfl.com: 5 of 7 checked out
- aol.com: 1 of 1 checked out
- appstatesports.com: 4 of 4 checked out
- arizonasports.com: 5 of 5 checked out
- arizonawildcats.com: 2 of 3 checked out
- astateredwolves.com: 2 of 2 checked out
- atlantafalcons.com: 2 of 2 checked out
- attheroost.com: 3 of 3 checked out
- azcardinals.com: 6 of 7 checked out
- azdesertswarm.com: 2 of 2 checked out
- bceagles.com: 1 of 1 checked out
- bluehens.com: 2 of 2 checked out
- boston.com: 3 of 3 checked out
- buffalobills.com: 11 of 11 checked out
- bythebelt.com: 1 of 1 checked out
- chicagobears.com: 12 of 13 checked out
- chiefs.com: 2 of 2 checked out
- clevelandbrowns.com: 3 of 4 checked out
- clickondetroit.com: 2 of 2 checked out
- cmuchippewas.com: 4 of 4 checked out
- commanders.com: 6 of 7 checked out
- conven.org: 4 of 4 checked out
- cuse.com: 1 of 1 checked out
- d1tacpi2k4cwvj.cloudfront.net: 2 of 3 checked out
- dailylobo.com: 1 of 1 checked out
- dallascowboys.com: 7 of 9 checked out
- db5y6jlvyeaqj.cloudfront.net: 5 of 5 checked out
- denverbroncos.com: 9 of 10 checked out
- denvergazette.com: 1 of 1 checked out
- df5u1lzgdv707.cloudfront.net: 3 of 3 checked out
- espn.com: 2 of 2 checked out
- evanscutchmorepress.com: 3 of 3 checked out
- fightingillini.com: 1 of 1 checked out
- fiusports.com: 4 of 4 checked out
- floridagators.com: 2 of 3 checked out
- fox11online.com: 1 of 1 checked out
- fox34.com: 2 of 2 checked out
- gamedaynd.com: 1 of 1 checked out
- georgiastatesports.com: 2 of 2 checked out
- giants.com: 5 of 6 checked out
- goairforcefalcons.com: 1 of 1 checked out
- goarmywestpoint.com: 5 of 5 checked out
- goaztecs.com: 5 of 6 checked out
- gobearcats.com: 3 of 3 checked out
- gobearkats.com: 6 of 6 checked out
- goccusports.com: 3 of 3 checked out
- goheels.com: 7 of 7 checked out
- gohuskies.com: 2 of 2 checked out
- golobos.com: 2 of 2 checked out
- gophersports.com: 3 of 3 checked out
- gotigersgo.com: 7 of 7 checked out
- gousfbulls.com: 2 of 2 checked out
- goutsa.com: 2 of 2 checked out
- hawkeyesports.com: 2 of 3 checked out
- hoosierhuddle.com: 4 of 5 checked out
- hottytoddy.com: 2 of 4 checked out
- houstonchronicle.com: 4 of 4 checked out
- houstontexans.com: 7 of 9 checked out
- huskers.com: 1 of 1 checked out
- insidethehall.com: 3 of 4 checked out
- iuhoosiers.com: 7 of 7 checked out
- jaguars.com: 7 of 8 checked out
- jaxstatesports.com: 1 of 1 checked out
- kait8.com: 1 of 1 checked out
- kcci.com: 1 of 1 checked out
- kentstatesports.com: 3 of 3 checked out
- kolotv.com: 3 of 3 checked out
- kstatesports.com: 2 of 2 checked out
- ksuowls.com: 3 of 3 checked out
- kwqc.com: 1 of 1 checked out
- latechsports.com: 2 of 2 checked out
- libertyflames.com: 1 of 1 checked out
- masslive.com: 0 of 1 checked out
- mgoblue.com: 5 of 5 checked out
- miamihurricanes.com: 3 of 3 checked out
- miamiredhawks.com: 3 of 3 checked out
- miamistudent.net: 3 of 3 checked out
- minutemancommand.com: 0 of 3 checked out
- missouristatebears.com: 2 of 2 checked out
- nationalfootballpost.com: 3 of 4 checked out
- navysports.com: 6 of 6 checked out
- nbcmiami.com: 0 of 2 checked out
- nevadawolfpack.com: 1 of 1 checked out
- neworleanssaints.com: 2 of 3 checked out
- newson6.com: 1 of 1 checked out
- nfl.com: 5 of 6 checked out
- nmstatesports.com: 6 of 6 checked out
- odusports.com: 4 of 4 checked out
- on3.com: 4 of 5 checked out
- osubeavers.com: 1 of 2 checked out
- packers.com: 4 of 5 checked out
- panthers.com: 2 of 2 checked out
- patriots.com: 13 of 20 checked out
- philadelphiaeagles.com: 18 of 19 checked out
- purduesports.com: 2 of 2 checked out
- raiders.com: 3 of 4 checked out
- riceowls.com: 1 of 1 checked out
- s3.us-east-2.amazonaws.com: 2 of 2 checked out
- seahawks.com: 8 of 10 checked out
- si.com: 35 of 40 checked out
- smumustangs.com: 1 of 1 checked out
- soflobulls.com: 2 of 4 checked out
- southernmiss.com: 3 of 3 checked out
- sports.yahoo.com: 25 of 28 checked out
- startribune.com: 0 of 2 checked out
- statenews.com: 2 of 2 checked out
- steelers.com: 3 of 5 checked out
- theacc.com: 4 of 4 checked out
- thedailyhoosier.com: 3 of 4 checked out
- therams.com: 18 of 24 checked out
- thescore.com: 4 of 4 checked out
- tulsahurricane.com: 4 of 4 checked out
- txst.com: 3 of 3 checked out
- uconnhuskies.com: 4 of 4 checked out
- umassathletics.com: 1 of 1 checked out
- underdogdynasty.com: 9 of 10 checked out
- usajaguars.com: 2 of 2 checked out
- usforacle.com: 1 of 2 checked out
- utahutes.com: 2 of 2 checked out
- utepminers.com: 3 of 4 checked out
- wjr.com: 2 of 2 checked out
- wkusports.com: 2 of 2 checked out
- wsbtv.com: 1 of 1 checked out
- wvmetronews.com: 5 of 5 checked out
- wvusports.com: 1 of 1 checked out

## Posts

- reason kind injury: 7 posts, 5.82 engagements per thousand views
- reason kind none: 27 posts, 6.15 engagements per thousand views
- reason kind other: 7 posts, 8.28 engagements per thousand views
- reason kind role: 1 posts, 0.0 engagements per thousand views
- reason kind stats: 5 posts, 9.35 engagements per thousand views

## Which posts and which hours

- announcement: 1 posts, 0.0 engagements per thousand views
- book: 1 posts, 32.26 engagements per thousand views
- cashed: 19 posts, 10.7 engagements per thousand views
- community: 18 posts, 9.44 engagements per thousand views
- conversation: 4 posts, 22.6 engagements per thousand views
- menu: 4 posts, 0.0 engagements per thousand views
- news: 1 posts, 0.0 engagements per thousand views
- play: 47 posts, 6.62 engagements per thousand views
- receipt: 24 posts, 7.9 engagements per thousand views
- research: 32 posts, 4.34 engagements per thousand views
- sheet: 6 posts, 3.55 engagements per thousand views
- before 9 AM: 17 posts, 5.9 engagements per thousand views
- 9 to 11 AM: 61 posts, 7.92 engagements per thousand views
- 11 AM to 2 PM: 52 posts, 5.52 engagements per thousand views
- 2 to 6 PM: 10 posts, 15.56 engagements per thousand views
- after 6 PM: 17 posts, 7.68 engagements per thousand views

## Card themes by the same post category

- book / legacy: 1 posts, 32.26 engagements per thousand views (small sample)
- cashed / legacy: 10 posts, 10.47 engagements per thousand views
- community / legacy: 14 posts, 6.11 engagements per thousand views
- menu / legacy: 4 posts, 0.0 engagements per thousand views (small sample)
- play / legacy: 47 posts, 6.62 engagements per thousand views
- receipt / legacy: 22 posts, 8.62 engagements per thousand views
- research / legacy: 27 posts, 5.14 engagements per thousand views
- sheet / legacy: 6 posts, 3.55 engagements per thousand views (small sample)

## Matchup-supported leans

- 136 graded, distinct matchup-supported observations. Reporting only; this changes no gate.
- NFL/CFB: player defense-vs-position and opponent-quality splits are active.
- NBA/CBB: team projections are active; player defense-vs-position is not live yet.
- EPL/MLS: team-level score and market shadows only.
- MLB: scores and market collection only; no batter-vs-pitcher lean yet.
- NHL: scores and market collection only; no skater/goalie lean yet.
- NFL WR over rec vs bottom-half defense: 9-3, +5.04u (n 12).
- NFL WR over recYds vs bottom-half defense: 7-5, +1.33u (n 12).
- NFL RB over rushYds vs bottom-half defense: 6-4, +1.33u (n 10).
- NFL TE over rec vs bottom-half defense: 4-5, -1.50u (n 9).
- NFL TE over recYds vs bottom-half defense: 2-7, -5.23u (n 9).
- NFL WR under recYds vs top 10 defense: 7-1, +5.26u (n 8).
- NFL WR under rec vs top 10 defense: 6-1, +3.55u (n 7).
- NFL RB over recYds vs bottom-half defense: 5-2, +2.62u (n 7).
- NFL QB over att vs bottom-half defense: 5-1, +3.37u (n 6).
- NFL RB under car vs top 10 defense: 5-1, +3.20u (n 6).
- NFL QB over cmp vs bottom-half defense: 4-2, +1.46u (n 6).
- NFL TE under rec vs top 10 defense: 4-2, +0.86u (n 6).
- NFL RB over rec vs bottom-half defense: 2-4, -2.48u (n 6).
- NFL QB over rushYds vs bottom-half defense: 3-2, +0.62u (n 5).
- NFL QB under cmp vs top 10 defense: 2-2, -0.17u (n 4).
- NFL QB over passYds vs bottom-half defense: 1-3, -2.12u (n 4).
- NFL QB under att vs top 10 defense: 2-1, +0.84u (n 3).
- NFL RB under rushYds vs top 10 defense: 2-1, +0.79u (n 3).
- NFL RB over car vs bottom-half defense: 1-2, -1.21u (n 3).
- NFL QB under passYds vs top 10 defense: 2-0, +1.77u (n 2).
- NFL RB under rec vs top 10 defense: 1-1, -0.18u (n 2).
- CFB WR under rec vs top-half defense: 1-0, +1.20u (n 1).
- CFB WR over rec vs bottom-half defense: 1-0, +1.12u (n 1).
- NFL QB under rushYds vs top 10 defense: 1-0, +0.88u (n 1).
- NFL RB under recYds vs top 10 defense: 1-0, +0.88u (n 1).
- NFL WR over rushYds vs bottom-half defense: 1-0, +0.88u (n 1).
- CFB WR under recYds vs top-half defense: 0-1, -1.00u (n 1).

## Released multi-leg tickets

- 10 released and graded tickets. Unreleased ideas are excluded.
- Climb / 2-leg / all alternates: 2-2-0-0, -0.24u on 4 with stored units (n 4).
- Climb / 1-leg / all alternates: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Climb / 2-leg / main lines: 1-0-0-0, +0.18u on 1 with stored units (n 1).
- Fun ticket / 3-leg / main lines: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 5-leg / main lines: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 5-leg / mixed alternates: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 3-leg / unclassified: 0-1-0-0, units unavailable (n 1).

## Engagement scorecard

- 157 measured posts; 114 human interactions across 25720 impressions; 4.43 per thousand.
- announcement: 1 posts, 0.0 per thousand (small sample)
- book: 1 posts, 32.26 per thousand (small sample)
- cashed: 19 posts, 9.75 per thousand
- community: 18 posts, 2.76 per thousand
- conversation: 4 posts, 21.05 per thousand (small sample)
- menu: 4 posts, 0.0 per thousand (small sample)
- news: 1 posts, 0.0 per thousand (small sample)
- play: 47 posts, 5.13 per thousand
- receipt: 24 posts, 7.11 per thousand
- research: 32 posts, 3.4 per thousand
- sheet: 6 posts, 5.18 per thousand (small sample)

## The number against the close (season to date)

- CFB v1: 381 games, total miss 13.24 vs the close's 12.67
- CFB v2.0: 259 games, total miss 12.72 vs the close's 12.3
- CFB v2.1: 118 games, total miss 14.31 vs the close's 13.69
- NFL v1: 92 games, total miss 11.23 vs the close's 10.24
- NFL v2.0: 60 games, total miss 11.34 vs the close's 10.1
- NFL v2.1: 30 games, total miss 10.78 vs the close's 10.57

## Prop formula review

Earlier 60% of kickoff dates train; later dates test. Both error scores must improve. Repeated retrospective evaluation; future shadow results required before promotion. Counts are prop observations, not independent games; no ROI claim without captured prices.

p = 0.5 + k * (raw - 0.5); k = w*k_market + (1-w)*k_league; w = n_train/(n_train+300)

- CFB/prop:passYds: 212 earlier / 136 later observations; later-game squared probability error 0.2530 league / 0.2516 pooled; shadow candidate.
- CFB/prop:rec: 262 earlier / 254 later observations; later-game squared probability error 0.2488 league / 0.2493 pooled; keep league formula.
- CFB/prop:recYds: 479 earlier / 362 later observations; later-game squared probability error 0.2485 league / 0.2481 pooled; shadow candidate.
- CFB/prop:rushYds: 375 earlier / 267 later observations; later-game squared probability error 0.2494 league / 0.2496 pooled; keep league formula.
- NFL/prop:att: 114 earlier / 56 later observations; later-game squared probability error 0.2509 league / 0.2506 pooled; shadow candidate.
- NFL/prop:car: 208 earlier / 98 later observations; later-game squared probability error 0.2504 league / 0.2505 pooled; keep league formula.
- NFL/prop:cmp: 114 earlier / 57 later observations; later-game squared probability error 0.2512 league / 0.2530 pooled; keep league formula.
- NFL/prop:passYds: 112 earlier / 54 later observations; later-game squared probability error 0.2513 league / 0.2510 pooled; shadow candidate.
- NFL/prop:rec: 665 earlier / 360 later observations; later-game squared probability error 0.2482 league / 0.2473 pooled; shadow candidate.
- NFL/prop:recYds: 664 earlier / 359 later observations; later-game squared probability error 0.2496 league / 0.2496 pooled; shadow candidate.
- NFL/prop:rushYds: 329 earlier / 171 later observations; later-game squared probability error 0.2522 league / 0.2510 pooled; shadow candidate.


## Silent results shadows

- These observations changed no play, card, post, record, gate or request budget.
- R0: 4192 raw rows, 2872 distinct
- R1: observation active; public behavior unchanged
- R2: observation active; public behavior unchanged
- R3: 11 prop markets observed
- R4: observation active; public behavior unchanged
- R5: 78 heavy alternates observed; default unchanged
- R6: observation active; public behavior unchanged
- R7: observation active; public behavior unchanged
