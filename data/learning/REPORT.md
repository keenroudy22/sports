# What the kitchen learned, 2026-11-10

6925 recorded candidate rows, 5027 distinct game/side/player observations, 6733 graded. Closing line value is how far the market moved toward our side by kickoff; it is the first thing learning trusts.

## Changes this week

- **Climb/alternate-offers** ladderSegments: 0 to 0. Weekly stored pregame alternate offers versus official final boxes.
- **researcher** domains: {'avoidDomains': ['startribune.com'], 'preferDomains': ['si.com', 'abqjournal.com', 'sports.yahoo.com', 'philadelphiaeagles.com', 'chicagobears.com', 'on3.com', 'seahawks.com', 'buffalobills.com']} to {'avoidDomains': ['startribune.com'], 'preferDomains': ['si.com', 'abqjournal.com', 'sports.yahoo.com', 'on3.com', 'philadelphiaeagles.com', 'chicagobears.com', 'seahawks.com', 'buffalobills.com']}. Which sites the researcher cites keep checking out.
- **CFB/moneyline/plus_money** twoWay.trust: 1.0 to 0.95. CFB/moneyline/plus_money trust 1.00 to 0.95.
- **CFB/prop:passYds** twoWay.trust: 0.85 to 0.839. CFB/prop:passYds trust 0.85 to 0.84.
- **CFB/prop:rec/plus_money** twoWay.trust: 1.0 to 0.966. CFB/prop:rec/plus_money trust 1.00 to 0.97.
- **CFB/prop:rushYds** twoWay.trust: 0.965 to 1.009. CFB/prop:rushYds trust 0.96 to 1.01.
- **NFL/moneyline/plus_money** twoWay.trust: 0.95 to 0.9. NFL/moneyline/plus_money trust 0.95 to 0.90.
- **NFL/prop:car/plus_money** twoWay.trust: 1.0 to 0.95. NFL/prop:car/plus_money trust 1.00 to 0.95.
- **NFL/prop:passYds** twoWay.trust: 0.923 to 0.954. NFL/prop:passYds trust 0.92 to 0.95.
- **NFL/prop:recYds** twoWay.trust: 1.06 to 1.023. NFL/prop:recYds trust 1.06 to 1.02.
- **NFL/prop:recYds/plus_money** twoWay.trust: 1.05 to 1.087. NFL/prop:recYds/plus_money trust 1.05 to 1.09.
- **NFL/prop:rushYds** twoWay.trust: 0.85 to 0.8. NFL/prop:rushYds trust 0.85 to 0.80.
- **NFL/spread** twoWay.trust: 0.95 to 0.975. NFL/spread trust 0.95 to 0.97.
- **NFL/total** twoWay.gap: 2.0 to 4.0. NFL/total gap floor +2 points.
- **NFL/total** twoWay.pause: False to True. Pause NFL/total; research and shadow continue.
- **Climb/alternate-offers** ladderSegments: 0 to 0. Weekly stored pregame alternate offers versus official final boxes.
- **Climb/alternate-offers** ladderSegments: 0 to 0. Weekly stored pregame alternate offers versus official final boxes.

## Direction changes

Owner-approved bounded moves (2026-10-07): they only tighten, pause, shift weight between approved categories, or restore what they tightened. Nothing loosens below the Oct 7 baseline, no market is added, and the record and published plays are untouched.

Applied:
- none

In force now:
- NFL totals: paused as a best bet since 2026-10-08 (research and shadow only); edge bar +4 since None

## Segments (published since their last change)

- CFB/moneyline (min edge 1): published 1-2, -1.38u; near misses 0-0, +0.00u
- CFB/moneyline/plus_money (min edge 1): published 0-5, -5.00u; near misses 0-0, +0.00u
- CFB/parlay/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/prop:passYds (min edge 5): published 1-0, +1.00u; near misses 3-9, -6.37u
- CFB/prop:rec (min edge 5): published 2-0, +2.20u; near misses 5-11, -6.56u
- CFB/prop:rec/plus_money (min edge 5): published 4-3, +1.74u; near misses 0-0, +0.00u
- CFB/prop:recYds (min edge 5): published 1-1, -0.17u; near misses 12-10, +0.63u
- CFB/prop:recYds/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/prop:rushYds (min edge 5): published 1-2, -1.12u; near misses 13-11, +0.39u
- CFB/prop:rushYds/plus_money (min edge 5): published 1-0, +1.00u; near misses 0-0, +0.00u
- CFB/spread (min edge 1): published 1-1, -0.05u, closing line value -0.25 points (90% -0.50 to +0.00, n 2); near misses 0-0, +0.00u
- CFB/spread/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/total (min edge 1): published 14-17, -3.89u, closing line value +0.16 points (90% -0.21 to +0.58, n 31); near misses 0-0, +0.00u
- CFB/total/plus_money (min edge 1): published 0-1, -1.00u, closing line value -2.00 points (90% -2.00 to -2.00, n 1); near misses 0-0, +0.00u
- NFL/moneyline (min edge 1): published 1-0, +0.93u; near misses 0-0, +0.00u
- NFL/moneyline/plus_money (min edge 1): published 0-1, -1.00u; near misses 0-0, +0.00u
- NFL/parlay/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:att (min edge 5): published 2-0, +1.94u, closing line value +0.00 points (90% +0.00 to +0.00, n 1); near misses 0-0, +0.00u
- NFL/prop:att/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:car (min edge 5): published 1-2, -1.10u, closing line value +0.00 points (90% +0.00 to +0.00, n 3); near misses 0-0, +0.00u
- NFL/prop:car/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:cmp (min edge 5): published 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1); near misses 0-0, +0.00u
- NFL/prop:cmp/plus_money (min edge 5): published 0-2, -2.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 2); near misses 0-0, +0.00u
- NFL/prop:passYds (min edge 5): published 0-0, +0.00u; near misses 0-1, -1.00u, closing line value -8.00 points (90% -8.00 to -8.00, n 1)
- NFL/prop:rec (min edge 5): published 4-2, +2.04u, closing line value +0.00 points (90% +0.00 to +0.00, n 5); near misses 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1)
- NFL/prop:rec/plus_money (min edge 5): published 4-6, -1.10u, closing line value +0.00 points (90% +0.00 to +0.00, n 10); near misses 0-0, +0.00u
- NFL/prop:recYds (min edge 5): published 8-3, +4.42u, closing line value +0.70 points (90% -0.20 to +1.70, n 10); near misses 3-1, +1.76u, closing line value +0.75 points (90% -1.50 to +3.00, n 4)
- NFL/prop:recYds/plus_money (min edge 5): published 1-1, +0.05u, closing line value -2.00 points (90% -2.00 to -2.00, n 2); near misses 0-0, +0.00u
- NFL/prop:rushYds (min edge 5): published 0-3, -3.00u, closing line value -1.33 points (90% -3.33 to +1.00, n 3); near misses 0-0, +0.00u
- NFL/prop:rushYds/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/spread (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/spread/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/total (higher-bar caution): published 0-4, -4.00u, closing line value -0.50 points (90% -1.00 to +0.12, n 4); near misses 15-18, -4.13u, closing line value +0.01 points (90% -0.14 to +0.17, n 33)
- NFL/total/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u

## Two-way Autopilot learning

- Waiting for a second Tuesday: gap:NFL/total (NFL/total gap floor +2 points).
- Waiting for a second Tuesday: trust:CFB/moneyline (CFB/moneyline trust 0.97 to 0.96).
- Waiting for a second Tuesday: trust:CFB/moneyline/plus_money (CFB/moneyline/plus_money trust 0.95 to 0.94).
- Waiting for a second Tuesday: trust:CFB/prop:rec (CFB/prop:rec trust 0.90 to 0.91).
- Waiting for a second Tuesday: trust:CFB/spread/plus_money (CFB/spread/plus_money trust 1.00 to 0.99).
- Waiting for a second Tuesday: trust:CFB/total (CFB/total trust 0.88 to 0.89).
- Waiting for a second Tuesday: trust:CFB/total/plus_money (CFB/total/plus_money trust 0.95 to 0.97).
- Waiting for a second Tuesday: trust:NFL/moneyline (NFL/moneyline trust 1.04 to 1.08).
- Waiting for a second Tuesday: trust:NFL/moneyline/plus_money (NFL/moneyline/plus_money trust 0.90 to 0.85).
- Waiting for a second Tuesday: trust:NFL/prop:att (NFL/prop:att trust 1.00 to 0.97).
- Waiting for a second Tuesday: trust:NFL/prop:car (NFL/prop:car trust 0.95 to 0.92).
- Waiting for a second Tuesday: trust:NFL/prop:car/plus_money (NFL/prop:car/plus_money trust 0.95 to 0.94).
- Waiting for a second Tuesday: trust:NFL/prop:cmp (NFL/prop:cmp trust 1.15 to 1.11).
- Waiting for a second Tuesday: trust:NFL/prop:cmp/plus_money (NFL/prop:cmp/plus_money trust 1.00 to 0.95).
- Waiting for a second Tuesday: trust:NFL/prop:rec (NFL/prop:rec trust 1.00 to 1.01).
- Waiting for a second Tuesday: trust:NFL/prop:rushYds (NFL/prop:rushYds trust 0.80 to 0.75).
- Waiting for a second Tuesday: trust:NFL/total/plus_money (NFL/total/plus_money trust 1.00 to 0.98).

## Player chances

- CFB/prop: 3504 graded projections; our favoured side came in 52.4% against a raw 60.5%; tested shrink k 0.18 (previous: 0.16).
- NFL/prop: 4439 graded projections; our favoured side came in 51.4% against a raw 61.3%; tested shrink k 0.08 (previous: 0.09).

## What each rule refused

- bar-4: 109 graded, 52-57, -12.39u, closing line value -0.01 points (90% -0.46 to +0.39, n 35)
- best_quote_by_ev: 148 graded, 63-83-2, -28.39u, closing line value -0.05 points (90% -0.22 to +0.14, n 144)
- card_cap: 1480 graded, 761-716-3, -41.38u, closing line value +0.13 points (90% +0.07 to +0.20, n 1060)
- cfb_jurisdiction: 47 graded, 25-22, +1.20u, closing line value -0.37 points (90% -0.77 to +0.05, n 31)
- daily_exposure: 1224 graded, 608-613-3, -83.10u, closing line value +0.01 points (90% -0.05 to +0.08, n 1046)
- expiry_ok: 20 graded, 12-8, +2.51u
- fresh_quote: 177 graded, 94-83, -5.90u, closing line value +0.13 points (90% -0.08 to +0.34, n 61)
- held: 1902 graded, 983-910-9, -58.14u, closing line value -0.09 points (90% -0.14 to -0.02, n 950)
- lean_daily_cap: 26 graded, 11-15, -4.67u, closing line value -0.50 points (90% -0.86 to -0.14, n 26)
- lean_edge: 8 graded, 3-5, -2.26u, closing line value -1.25 points (90% -2.62 to -0.12, n 8)
- lean_nothing_against: 408 graded, 199-207-2, -29.74u, closing line value +0.18 points (90% +0.05 to +0.31, n 406)
- learned_pause: 187 graded, 72-111-4, -44.16u, closing line value -0.14 points (90% -0.31 to +0.01, n 187)
- longshot_one_per_day: 0 graded, 0-0, +0.00u
- moneyline_projection_agreement: 145 graded, 41-104, -26.59u
- not_duplicate: 64 graded, 24-40, -16.80u, closing line value +0.11 points (90% -0.10 to +0.32, n 57)
- one_book: 2232 graded, 1120-1108-4, -168.01u, closing line value +0.15 points (90% +0.07 to +0.22, n 1266)
- plan_selection: 1504 graded, 782-720-2, -33.11u, closing line value +0.13 points (90% +0.06 to +0.20, n 1409)
- player_overlap: 75 graded, 45-30, +9.93u, closing line value +0.24 points (90% -0.13 to +0.66, n 62)
- prop_calibrated_value: 1091 graded, 556-535, -66.78u, closing line value +0.47 points (90% +0.37 to +0.56, n 805)
- prop_injury_clear: 27 graded, 15-12, +1.87u, closing line value -0.11 points (90% -0.63 to +0.44, n 27)
- prop_market_not_trailing: 723 graded, 371-352, +6.72u, closing line value +0.47 points (90% +0.37 to +0.58, n 719)
- prop_not_in_longshot: 116 graded, 62-54, +1.55u, closing line value +0.15 points (90% -0.14 to +0.45, n 92)
- prop_one_per_player: 16 graded, 9-7, +1.09u, closing line value +0.00 points (90% -0.64 to +0.64, n 11)
- prop_price_floor: 5 graded, 2-3, -2.15u, closing line value +0.67 points (90% +0.00 to +1.00, n 3)
- prop_raw_edge: 127 graded, 62-65, -20.21u, closing line value +0.00 points (90% -0.06 to +0.06, n 84)
- prop_settled_role: 63 graded, 24-39, -17.96u, closing line value -0.06 points (90% -0.38 to +0.24, n 63)
- prop_window_cap: 160 graded, 78-82, -16.01u, closing line value +0.31 points (90% +0.12 to +0.50, n 160)
- qb-change-recent: 25 graded, 8-17, -10.29u, closing line value -0.14 points (90% -0.55 to +0.23, n 22)
- qb_available: 29 graded, 8-20-1, -12.55u, closing line value +0.21 points (90% -0.12 to +0.50, n 29)
- ticket_research: 0 graded, 0-0, +0.00u
- totals_policy: 156 graded, 74-82, -12.96u, closing line value +0.04 points (90% -0.11 to +0.18, n 156)
- two_sided_straight: 22 graded, 9-13, -4.47u, closing line value +0.36 points (90% -0.04 to +0.73, n 22)
- x_window: 591 graded, 307-281-3, -19.37u, closing line value +0.06 points (90% -0.05 to +0.17, n 246)

## The judge

- published: 109 graded, 49-60, -11.64u, closing line value +0.00 points (90% -0.24 to +0.24, n 80)
- argues against: 27 graded, 9-18, -8.84u, closing line value +0.08 points (90% -0.28 to +0.46, n 25)
- rule of thumb: 1126 graded, 584-533-9, -26.69u, closing line value -0.05 points (90% -0.12 to +0.01, n 651)
- unsure: 10 graded, 4-6, -2.32u, closing line value -1.10 points (90% -1.70 to -0.50, n 10)

## Sources the researcher cited

- 1069thefan.com: 7 of 8 checked out
- 146.freechallenge.14.racing.cbssports.com: 0 of 2 checked out
- 49ers.com: 6 of 7 checked out
- abcnews.com: 2 of 2 checked out
- abqjournal.com: 30 of 34 checked out
- accsports.com: 4 of 5 checked out
- ajc.com: 3 of 3 checked out
- amp.nfl.com: 5 of 7 checked out
- aol.com: 3 of 3 checked out
- appstatesports.com: 4 of 4 checked out
- arizonasports.com: 10 of 10 checked out
- arizonawildcats.com: 7 of 8 checked out
- astateredwolves.com: 2 of 2 checked out
- atlantafalcons.com: 2 of 2 checked out
- attheroost.com: 3 of 3 checked out
- azcardinals.com: 6 of 7 checked out
- azdesertswarm.com: 2 of 2 checked out
- ballstatesports.com: 10 of 12 checked out
- baylorbears.com: 1 of 2 checked out
- bceagles.com: 1 of 1 checked out
- bengals.com: 3 of 4 checked out
- bgsufalcons.com: 2 of 2 checked out
- bigten.org: 2 of 2 checked out
- bluehens.com: 3 of 3 checked out
- boston.com: 3 of 3 checked out
- buffalobills.com: 15 of 15 checked out
- bythebelt.com: 1 of 1 checked out
- ca.sports.yahoo.com: 1 of 1 checked out
- chicagobears.com: 17 of 18 checked out
- chiefs.com: 2 of 2 checked out
- clevelandbrowns.com: 7 of 9 checked out
- clickondetroit.com: 2 of 2 checked out
- cmuchippewas.com: 4 of 4 checked out
- commanders.com: 6 of 7 checked out
- conven.org: 7 of 7 checked out
- csurams.com: 4 of 4 checked out
- cuse.com: 3 of 4 checked out
- d1hg55pco9dr97.cloudfront.net: 1 of 1 checked out
- d1tacpi2k4cwvj.cloudfront.net: 2 of 3 checked out
- d3h8hkdb4o069q.cloudfront.net: 2 of 2 checked out
- dailyillini.com: 2 of 2 checked out
- dailylobo.com: 1 of 1 checked out
- dallascowboys.com: 7 of 9 checked out
- davecampbells.com: 3 of 3 checked out
- db5y6jlvyeaqj.cloudfront.net: 5 of 5 checked out
- denverbroncos.com: 9 of 10 checked out
- denvergazette.com: 10 of 10 checked out
- deseret.com: 4 of 4 checked out
- df5u1lzgdv707.cloudfront.net: 3 of 3 checked out
- ecupirates.com: 2 of 2 checked out
- espn.com: 2 of 2 checked out
- evanscutchmorepress.com: 3 of 3 checked out
- expressnews.com: 2 of 3 checked out
- fausports.com: 13 of 13 checked out
- fightingillini.com: 1 of 1 checked out
- fiusports.com: 4 of 4 checked out
- floridagators.com: 2 of 3 checked out
- fox11online.com: 1 of 1 checked out
- fox32chicago.com: 1 of 1 checked out
- fox34.com: 2 of 2 checked out
- gamedaynd.com: 1 of 1 checked out
- gazette.com: 3 of 4 checked out
- georgiadogs.com: 1 of 1 checked out
- georgiastatesports.com: 2 of 2 checked out
- giants.com: 5 of 6 checked out
- goairforcefalcons.com: 3 of 3 checked out
- goarmywestpoint.com: 5 of 5 checked out
- goaztecs.com: 5 of 6 checked out
- gobearcats.com: 3 of 3 checked out
- gobearkats.com: 9 of 9 checked out
- gobison.com: 1 of 1 checked out
- goblueraiders.com: 6 of 6 checked out
- gobulldogs.com: 1 of 1 checked out
- goccusports.com: 3 of 3 checked out
- gofrogs.com: 1 of 1 checked out
- goheels.com: 7 of 7 checked out
- gohuskies.com: 2 of 2 checked out
- golobos.com: 2 of 2 checked out
- gophersports.com: 3 of 3 checked out
- gotigersgo.com: 7 of 7 checked out
- gousfbulls.com: 9 of 10 checked out
- goutsa.com: 4 of 4 checked out
- gowyo.com: 2 of 2 checked out
- hawkeyesports.com: 5 of 6 checked out
- hokiesports.com: 1 of 1 checked out
- hoosierhuddle.com: 5 of 6 checked out
- hornetsports.com: 2 of 2 checked out
- hottytoddy.com: 2 of 4 checked out
- houstonchronicle.com: 4 of 4 checked out
- houstontexans.com: 7 of 9 checked out
- huskers.com: 2 of 2 checked out
- insidethehall.com: 5 of 7 checked out
- iuhoosiers.com: 7 of 7 checked out
- jaguars.com: 8 of 9 checked out
- jaxstatesports.com: 4 of 4 checked out
- jmusports.com: 1 of 1 checked out
- kait8.com: 1 of 1 checked out
- kcci.com: 1 of 1 checked out
- kentstatesports.com: 12 of 13 checked out
- kolotv.com: 3 of 3 checked out
- kstatesports.com: 4 of 4 checked out
- ksuowls.com: 3 of 3 checked out
- kwqc.com: 1 of 1 checked out
- ky3.com: 2 of 2 checked out
- latechsports.com: 2 of 2 checked out
- libertyflames.com: 1 of 1 checked out
- march2thepod.substack.com: 3 of 3 checked out
- masslive.com: 0 of 1 checked out
- meangreensports.com: 2 of 4 checked out
- mgoblue.com: 5 of 5 checked out
- miamihurricanes.com: 3 of 3 checked out
- miamiredhawks.com: 8 of 8 checked out
- miamistudent.net: 4 of 4 checked out
- minutemancommand.com: 0 of 3 checked out
- missouristatebears.com: 4 of 5 checked out
- nationalfootballpost.com: 3 of 4 checked out
- navysports.com: 8 of 8 checked out
- nbcmiami.com: 0 of 2 checked out
- ncfootballnews.com: 2 of 2 checked out
- nevadawolfpack.com: 4 of 4 checked out
- neworleanssaints.com: 2 of 3 checked out
- newson6.com: 1 of 1 checked out
- nfl.com: 9 of 11 checked out
- nmstatesports.com: 9 of 9 checked out
- nusports.com: 1 of 1 checked out
- odusports.com: 4 of 4 checked out
- ohiobobcats.com: 5 of 5 checked out
- olemisssports.com: 2 of 2 checked out
- on3.com: 21 of 26 checked out
- osubeavers.com: 3 of 4 checked out
- packers.com: 4 of 5 checked out
- panthers.com: 2 of 2 checked out
- patriots.com: 13 of 20 checked out
- philadelphiaeagles.com: 18 of 19 checked out
- phlsportsnow.com: 1 of 1 checked out
- purduesports.com: 2 of 2 checked out
- raiders.com: 3 of 4 checked out
- riceowls.com: 1 of 1 checked out
- s3.us-east-2.amazonaws.com: 2 of 2 checked out
- seahawks.com: 15 of 17 checked out
- si.com: 66 of 72 checked out
- sicem365.com: 3 of 3 checked out
- sjsuspartans.com: 1 of 1 checked out
- smumustangs.com: 5 of 5 checked out
- soflobulls.com: 2 of 4 checked out
- southernmiss.com: 3 of 3 checked out
- sports.ksl.com: 1 of 2 checked out
- sports.mynorthwest.com: 1 of 1 checked out
- sports.yahoo.com: 28 of 31 checked out
- staging-aws.sports.yahoo.com: 1 of 1 checked out
- startribune.com: 0 of 5 checked out
- statenews.com: 2 of 2 checked out
- steelers.com: 5 of 7 checked out
- storage.googleapis.com: 0 of 3 checked out
- sundevildaily.com: 1 of 1 checked out
- supertalk.fm: 3 of 3 checked out
- techlunchpail.com: 2 of 3 checked out
- temple-news.com: 0 of 2 checked out
- tennesseetitans.com: 2 of 2 checked out
- theacc.com: 8 of 8 checked out
- thedailyhoosier.com: 3 of 4 checked out
- thekeyplay.com: 3 of 3 checked out
- therams.com: 18 of 24 checked out
- thescore.com: 4 of 4 checked out
- thesundevils.com: 3 of 3 checked out
- toledoblade.com: 0 of 2 checked out
- troytrojans.com: 10 of 10 checked out
- tucson.com: 2 of 2 checked out
- tulanegreenwave.com: 2 of 2 checked out
- tulsahurricane.com: 4 of 4 checked out
- txst.com: 4 of 4 checked out
- ubbulls.com: 2 of 2 checked out
- ucfknights.com: 1 of 1 checked out
- uclabruins.com: 3 of 3 checked out
- uconnhuskies.com: 4 of 4 checked out
- umassathletics.com: 1 of 1 checked out
- underdogdynasty.com: 9 of 10 checked out
- unlvrebels.com: 3 of 3 checked out
- usajaguars.com: 2 of 2 checked out
- usforacle.com: 1 of 2 checked out
- utahstateaggies.com: 1 of 1 checked out
- utahutes.com: 2 of 2 checked out
- utepminers.com: 4 of 5 checked out
- vikings.com: 2 of 2 checked out
- wdrbwave.com: 2 of 2 checked out
- whsv.com: 4 of 4 checked out
- wjr.com: 2 of 2 checked out
- wkusports.com: 8 of 8 checked out
- wndu.com: 3 of 3 checked out
- woub.org: 2 of 2 checked out
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

- 185 graded, distinct matchup-supported observations. Reporting only; this changes no gate.
- NFL/CFB: player defense-vs-position and opponent-quality splits are active.
- NBA/CBB: team projections are active; player defense-vs-position is not live yet.
- EPL/MLS: team-level score and market shadows only.
- MLB: scores and market collection only; no batter-vs-pitcher lean yet.
- NHL: scores and market collection only; no skater/goalie lean yet.
- NFL WR over rec vs bottom-half defense: 14-3, +9.76u (n 17).
- NFL WR over recYds vs bottom-half defense: 9-8, +0.10u (n 17).
- NFL TE over recYds vs bottom-half defense: 7-8, -1.76u (n 15).
- NFL RB over rushYds vs bottom-half defense: 6-6, -0.67u (n 12).
- NFL WR under recYds vs top 10 defense: 8-3, +4.15u (n 11).
- NFL WR under rec vs top 10 defense: 8-3, +3.13u (n 11).
- NFL RB over recYds vs bottom-half defense: 6-3, +2.57u (n 9).
- NFL QB over att vs bottom-half defense: 6-3, +2.16u (n 9).
- NFL TE over rec vs bottom-half defense: 4-5, -1.50u (n 9).
- NFL QB over cmp vs bottom-half defense: 4-4, -0.54u (n 8).
- NFL QB over passYds vs bottom-half defense: 3-5, -2.34u (n 8).
- NFL RB under car vs top 10 defense: 5-2, +2.20u (n 7).
- NFL QB over rushYds vs bottom-half defense: 3-4, -1.38u (n 7).
- NFL TE under rec vs top 10 defense: 4-2, +0.86u (n 6).
- NFL RB over rec vs bottom-half defense: 2-4, -2.48u (n 6).
- NFL QB under att vs top 10 defense: 2-3, -1.16u (n 5).
- NFL QB under passYds vs top 10 defense: 4-0, +3.57u (n 4).
- NFL RB under rec vs top 10 defense: 2-2, -0.12u (n 4).
- NFL QB under cmp vs top 10 defense: 2-2, -0.17u (n 4).
- NFL RB over car vs bottom-half defense: 1-3, -2.21u (n 4).
- CFB WR under rec vs top-half defense: 3-0, +3.58u (n 3).
- NFL RB under rushYds vs top 10 defense: 2-1, +0.79u (n 3).
- CFB WR over rec vs bottom-half defense: 1-0, +1.12u (n 1).
- NFL QB under rushYds vs top 10 defense: 1-0, +0.88u (n 1).
- NFL RB under recYds vs top 10 defense: 1-0, +0.88u (n 1).
- NFL WR over rushYds vs bottom-half defense: 1-0, +0.88u (n 1).
- NFL QB under car vs top 10 defense: 1-0, +0.72u (n 1).
- CFB WR under recYds vs top-half defense: 0-1, -1.00u (n 1).

## Released multi-leg tickets

- 13 released and graded tickets. Unreleased ideas are excluded.
- Climb / 2-leg / all alternates: 5-2-0-0, +0.16u on 7 with stored units (n 7).
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

- CFB v1: 500 games, total miss 13.3 vs the close's 12.55
- CFB v2.0: 259 games, total miss 12.72 vs the close's 12.3
- CFB v2.1: 237 games, total miss 13.88 vs the close's 12.91
- NFL v1: 121 games, total miss 11.33 vs the close's 10.35
- NFL v2.0: 60 games, total miss 11.34 vs the close's 10.1
- NFL v2.1: 59 games, total miss 10.95 vs the close's 10.64

## Prop formula review

Earlier 60% of kickoff dates train; later dates test. Both error scores must improve. Repeated retrospective evaluation; future shadow results required before promotion. Counts are prop observations, not independent games; no ROI claim without captured prices.

p = 0.5 + k * (raw - 0.5); k = w*k_market + (1-w)*k_league; w = n_train/(n_train+300)

- CFB/prop:passYds: 289 earlier / 207 later observations; later-game squared probability error 0.2525 league / 0.2510 pooled; shadow candidate.
- CFB/prop:rec: 406 earlier / 422 later observations; later-game squared probability error 0.2493 league / 0.2493 pooled; keep league formula.
- CFB/prop:recYds: 688 earlier / 560 later observations; later-game squared probability error 0.2493 league / 0.2492 pooled; shadow candidate.
- CFB/prop:rushYds: 528 earlier / 404 later observations; later-game squared probability error 0.2488 league / 0.2487 pooled; shadow candidate.
- NFL/prop:att: 142 earlier / 81 later observations; later-game squared probability error 0.2500 league / 0.2500 pooled; shadow candidate.
- NFL/prop:car: 262 earlier / 138 later observations; later-game squared probability error 0.2523 league / 0.2529 pooled; keep league formula.
- NFL/prop:cmp: 142 earlier / 82 later observations; later-game squared probability error 0.2506 league / 0.2516 pooled; keep league formula.
- NFL/prop:passYds: 137 earlier / 79 later observations; later-game squared probability error 0.2502 league / 0.2501 pooled; shadow candidate.
- NFL/prop:rec: 848 earlier / 513 later observations; later-game squared probability error 0.2484 league / 0.2465 pooled; shadow candidate.
- NFL/prop:recYds: 845 earlier / 514 later observations; later-game squared probability error 0.2495 league / 0.2494 pooled; shadow candidate.
- NFL/prop:rushYds: 420 earlier / 236 later observations; later-game squared probability error 0.2513 league / 0.2505 pooled; shadow candidate.


## Silent results shadows

- These observations changed no play, card, post, record, gate or request budget.
- R0: 6916 raw rows, 5023 distinct
- R1: observation active; public behavior unchanged
- R2: observation active; public behavior unchanged
- R3: 11 prop markets observed
- R4: observation active; public behavior unchanged
- R5: 126 heavy alternates observed; default unchanged
- R6: observation active; public behavior unchanged
- R7: observation active; public behavior unchanged
