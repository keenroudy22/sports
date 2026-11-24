# What the kitchen learned, 2026-11-24

9250 recorded candidate rows, 6828 distinct game/side/player observations, 8671 graded. Closing line value is how far the market moved toward our side by kickoff; it is the first thing learning trusts.

## Changes this week

- **Climb/alternate-offers** ladderSegments: 0 to 0. Weekly stored pregame alternate offers versus official final boxes.
- **researcher** domains: {'preferDomains': ['si.com', 'on3.com', 'abqjournal.com', 'sports.yahoo.com', 'philadelphiaeagles.com', 'chicagobears.com', 'fausports.com', 'seahawks.com'], 'avoidDomains': ['startribune.com', 'storage.googleapis.com']} to {'preferDomains': ['si.com', 'on3.com', 'abqjournal.com', 'sports.yahoo.com', 'philadelphiaeagles.com', 'chicagobears.com', 'fausports.com', 'ballstatesports.com'], 'avoidDomains': ['startribune.com', 'storage.googleapis.com']}. Which sites the researcher cites keep checking out.
- **CFB/prop:passYds** twoWay.trust: 0.839 to 0.866. CFB/prop:passYds trust 0.84 to 0.87.
- **CFB/prop:recYds** twoWay.trust: 0.985 to 1.014. CFB/prop:recYds trust 0.98 to 1.01.
- **CFB/spread** twoWay.trust: 0.909 to 0.916. CFB/spread trust 0.91 to 0.92.
- **NFL/moneyline/plus_money** twoWay.trust: 0.85 to 0.8. NFL/moneyline/plus_money trust 0.85 to 0.80.
- **NFL/prop:car** twoWay.trust: 0.9 to 0.883. NFL/prop:car trust 0.90 to 0.88.
- **NFL/prop:cmp** twoWay.trust: 1.095 to 1.07. NFL/prop:cmp trust 1.09 to 1.07.
- **NFL/prop:cmp/plus_money** twoWay.trust: 0.95 to 0.94. NFL/prop:cmp/plus_money trust 0.95 to 0.94.
- **NFL/prop:rec** twoWay.trust: 1.001 to 0.965. NFL/prop:rec trust 1.00 to 0.96.
- **NFL/prop:rec/plus_money** twoWay.trust: 1.048 to 0.998. NFL/prop:rec/plus_money trust 1.05 to 1.00.
- **NFL/prop:recYds** twoWay.trust: 1.023 to 0.976. NFL/prop:recYds trust 1.02 to 0.98.
- **NFL/spread** twoWay.trust: 0.975 to 0.948. NFL/spread trust 0.97 to 0.95.
- **NFL/spread/plus_money** twoWay.trust: 1.0 to 1.034. NFL/spread/plus_money trust 1.00 to 1.03.
- **NFL/total** twoWay.gap: 6.0 to 8.0. NFL/total gap floor +2 points.

## Direction changes

Owner-approved bounded moves (2026-10-07): they only tighten, pause, shift weight between approved categories, or restore what they tightened. Nothing loosens below the Oct 7 baseline, no market is added, and the record and published plays are untouched.

Applied:
- none

In force now:
- NFL totals: paused as a best bet since 2026-10-08 (research and shadow only); edge bar +6 since None

Report only (nothing loosens):
- Diagnostic only after October31 owner reset: Weekend card back to 5 best bets (since the cut 20-19, 51% vs 50% break-even).
- Diagnostic only after October31 owner reset: Fun tickets back to their usual shape (2 wins in the next 6).

## Segments (published since their last change)

- CFB/moneyline (min edge 1): published 2-4, -2.40u; near misses 0-0, +0.00u
- CFB/moneyline/plus_money (min edge 1): published 0-6, -6.00u; near misses 0-0, +0.00u
- CFB/parlay/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/prop:passYds (min edge 5): published 2-0, +1.88u; near misses 3-9, -6.37u
- CFB/prop:rec (min edge 5): published 2-0, +2.20u; near misses 5-11, -6.56u
- CFB/prop:rec/plus_money (min edge 5): published 4-4, +0.74u; near misses 0-0, +0.00u
- CFB/prop:recYds (min edge 5): published 2-1, +0.70u; near misses 12-10, +0.63u
- CFB/prop:recYds/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/prop:rushYds (min edge 5): published 1-2, -1.12u; near misses 13-11, +0.39u
- CFB/prop:rushYds/plus_money (min edge 5): published 2-0, +2.08u; near misses 0-0, +0.00u
- CFB/spread (min edge 1): published 1-2, -1.05u, closing line value -0.17 points (90% -0.33 to +0.00, n 3); near misses 0-0, +0.00u
- CFB/spread/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- CFB/total (min edge 1): published 16-20, -5.01u, closing line value +0.22 points (90% -0.12 to +0.60, n 36); near misses 0-0, +0.00u
- CFB/total/plus_money (min edge 1): published 1-1, +0.00u, closing line value -2.00 points (90% -2.00 to -2.00, n 2); near misses 0-0, +0.00u
- NFL/moneyline (min edge 1): published 1-0, +0.93u; near misses 0-0, +0.00u
- NFL/moneyline/plus_money (min edge 1): published 0-1, -1.00u; near misses 0-0, +0.00u
- NFL/parlay/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:att (min edge 5): published 2-0, +1.94u, closing line value +0.00 points (90% +0.00 to +0.00, n 1); near misses 0-0, +0.00u
- NFL/prop:att/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/prop:car (min edge 5): published 1-2, -1.10u, closing line value +0.00 points (90% +0.00 to +0.00, n 3); near misses 0-0, +0.00u
- NFL/prop:car/plus_money (min edge 5): published 1-1, +0.04u, closing line value -0.50 points (90% -1.00 to +0.00, n 2); near misses 0-0, +0.00u
- NFL/prop:cmp (min edge 5): published 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1); near misses 0-0, +0.00u
- NFL/prop:cmp/plus_money (min edge 5): published 0-2, -2.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 2); near misses 0-0, +0.00u
- NFL/prop:passYds (min edge 5): published 0-0, +0.00u; near misses 0-1, -1.00u, closing line value -8.00 points (90% -8.00 to -8.00, n 1)
- NFL/prop:rec (min edge 5): published 4-2, +2.04u, closing line value +0.00 points (90% +0.00 to +0.00, n 5); near misses 0-1, -1.00u, closing line value +0.00 points (90% +0.00 to +0.00, n 1)
- NFL/prop:rec/plus_money (min edge 5): published 7-11, -2.36u, closing line value +0.00 points (90% +0.00 to +0.00, n 18); near misses 0-0, +0.00u
- NFL/prop:recYds (min edge 5): published 8-3, +4.42u, closing line value +0.70 points (90% -0.20 to +1.70, n 10); near misses 3-1, +1.76u, closing line value +0.75 points (90% -1.50 to +3.00, n 4)
- NFL/prop:recYds/plus_money (min edge 5): published 1-1, +0.05u, closing line value -2.00 points (90% -2.00 to -2.00, n 2); near misses 0-0, +0.00u
- NFL/prop:rushYds (min edge 5): published 0-3, -3.00u, closing line value -1.33 points (90% -3.33 to +1.00, n 3); near misses 0-0, +0.00u
- NFL/prop:rushYds/plus_money (min edge 5): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/spread (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/spread/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u
- NFL/total (higher-bar caution): published 0-4, -4.00u, closing line value -0.50 points (90% -1.00 to +0.12, n 4); near misses 22-22, -1.60u, closing line value +0.02 points (90% -0.10 to +0.15, n 44)
- NFL/total/plus_money (min edge 1): published 0-0, +0.00u; near misses 0-0, +0.00u

## Two-way Autopilot learning

- Applied trust:CFB/prop:passYds: CFB/prop:passYds trust 0.84 to 0.87.
- Applied trust:CFB/prop:recYds: CFB/prop:recYds trust 0.98 to 1.01.
- Applied trust:CFB/spread: CFB/spread trust 0.91 to 0.92.
- Applied trust:NFL/moneyline/plus_money: NFL/moneyline/plus_money trust 0.85 to 0.80.
- Applied trust:NFL/prop:car: NFL/prop:car trust 0.90 to 0.88.
- Applied trust:NFL/prop:cmp: NFL/prop:cmp trust 1.09 to 1.07.
- Applied trust:NFL/prop:cmp/plus_money: NFL/prop:cmp/plus_money trust 0.95 to 0.94.
- Applied trust:NFL/prop:rec: NFL/prop:rec trust 1.00 to 0.96.
- Applied trust:NFL/prop:rec/plus_money: NFL/prop:rec/plus_money trust 1.05 to 1.00.
- Applied trust:NFL/prop:recYds: NFL/prop:recYds trust 1.02 to 0.98.
- Applied trust:NFL/spread: NFL/spread trust 0.97 to 0.95.
- Applied trust:NFL/spread/plus_money: NFL/spread/plus_money trust 1.00 to 1.03.
- Applied gap:NFL/total: NFL/total gap floor +2 points.
- Waiting for a second Tuesday: trust:CFB/moneyline (CFB/moneyline trust 0.95 to 0.94).
- Waiting for a second Tuesday: trust:CFB/moneyline/plus_money (CFB/moneyline/plus_money trust 0.94 to 0.95).
- Waiting for a second Tuesday: trust:CFB/prop:rushYds (CFB/prop:rushYds trust 1.01 to 0.99).
- Waiting for a second Tuesday: trust:CFB/total/plus_money (CFB/total/plus_money trust 1.00 to 0.99).
- Waiting for a second Tuesday: trust:NFL/moneyline (NFL/moneyline trust 1.06 to 1.05).
- Waiting for a second Tuesday: trust:NFL/prop:car/plus_money (NFL/prop:car/plus_money trust 0.93 to 0.94).
- Waiting for a second Tuesday: trust:NFL/prop:passYds (NFL/prop:passYds trust 0.95 to 0.93).
- Waiting for a second Tuesday: trust:NFL/prop:rushYds (NFL/prop:rushYds trust 0.75 to 0.76).
- Waiting for a second Tuesday: trust:NFL/total/plus_money (NFL/total/plus_money trust 0.96 to 0.98).

## Player chances

- CFB/prop: 4196 graded projections; our favoured side came in 53.0% against a raw 60.5%; tested shrink k 0.12 (previous: 0.16).
- NFL/prop: 5455 graded projections; our favoured side came in 50.7% against a raw 61.4%; tested shrink k 0.09 (previous: 0.09).

## What each rule refused

- bar-4: 109 graded, 52-57, -12.39u, closing line value -0.01 points (90% -0.46 to +0.39, n 35)
- best_quote_by_ev: 175 graded, 71-102-2, -40.06u, closing line value -0.14 points (90% -0.31 to +0.02, n 170)
- card_cap: 1712 graded, 875-831-6, -49.79u, closing line value +0.10 points (90% +0.04 to +0.16, n 1278)
- cfb_jurisdiction: 47 graded, 25-22, +1.20u, closing line value -0.37 points (90% -0.77 to +0.05, n 31)
- daily_exposure: 1224 graded, 608-613-3, -83.10u, closing line value +0.01 points (90% -0.05 to +0.08, n 1046)
- expiry_ok: 20 graded, 12-8, +2.51u
- fresh_quote: 227 graded, 118-109, -10.90u, closing line value +0.13 points (90% -0.08 to +0.34, n 61)
- held: 2637 graded, 1377-1245-15, -63.04u, closing line value -0.11 points (90% -0.15 to -0.06, n 1385)
- lean_daily_cap: 26 graded, 11-15, -4.67u, closing line value -0.50 points (90% -0.86 to -0.14, n 26)
- lean_edge: 8 graded, 3-5, -2.26u, closing line value -1.25 points (90% -2.62 to -0.12, n 8)
- lean_nothing_against: 474 graded, 222-250-2, -52.07u, closing line value +0.17 points (90% +0.05 to +0.29, n 471)
- learned_pause: 242 graded, 100-137-5, -44.17u, closing line value -0.13 points (90% -0.26 to -0.01, n 242)
- longshot_one_per_day: 0 graded, 0-0, +0.00u
- moneyline_projection_agreement: 249 graded, 76-173, -29.88u
- not_duplicate: 71 graded, 28-43, -15.75u, closing line value +0.10 points (90% -0.09 to +0.29, n 63)
- one_book: 2681 graded, 1351-1324-6, -210.53u, closing line value +0.13 points (90% +0.06 to +0.21, n 1464)
- plan_selection: 2284 graded, 1128-1154-2, -171.43u, closing line value +0.13 points (90% +0.07 to +0.18, n 2152)
- player_overlap: 110 graded, 67-43, +17.14u, closing line value +0.26 points (90% -0.02 to +0.58, n 93)
- prop_calibrated_value: 1091 graded, 556-535, -66.78u, closing line value +0.47 points (90% +0.37 to +0.56, n 805)
- prop_injury_clear: 33 graded, 15-18, -4.13u, closing line value +0.21 points (90% -0.24 to +0.73, n 33)
- prop_market_not_trailing: 723 graded, 371-352, +6.72u, closing line value +0.47 points (90% +0.37 to +0.58, n 719)
- prop_not_in_longshot: 151 graded, 84-67, +8.76u, closing line value +0.19 points (90% -0.05 to +0.44, n 123)
- prop_one_per_player: 16 graded, 9-7, +1.09u, closing line value +0.00 points (90% -0.64 to +0.64, n 11)
- prop_price_floor: 5 graded, 2-3, -2.15u, closing line value +0.67 points (90% +0.00 to +1.00, n 3)
- prop_raw_edge: 127 graded, 62-65, -20.21u, closing line value +0.00 points (90% -0.06 to +0.06, n 84)
- prop_settled_role: 88 graded, 31-57, -29.74u, closing line value +0.03 points (90% -0.23 to +0.31, n 88)
- prop_window_cap: 160 graded, 78-82, -16.01u, closing line value +0.31 points (90% +0.12 to +0.50, n 160)
- qb-change-recent: 37 graded, 14-23, -10.69u, closing line value -0.06 points (90% -0.32 to +0.21, n 34)
- qb_available: 39 graded, 13-25-1, -12.90u, closing line value +0.18 points (90% -0.04 to +0.42, n 39)
- straight_price_margin: 30 graded, 10-20, -10.19u, closing line value -0.10 points (90% -0.27 to +0.07, n 30)
- ticket_research: 0 graded, 0-0, +0.00u
- totals_policy: 191 graded, 90-101, -16.78u, closing line value +0.02 points (90% -0.12 to +0.16, n 191)
- two_sided_straight: 22 graded, 9-13, -4.47u, closing line value +0.36 points (90% -0.04 to +0.73, n 22)
- withdrawn_quote: 4 graded, 1-3, -1.89u, closing line value +0.00 points (90% +0.00 to +0.00, n 4)
- x_window: 681 graded, 353-324-4, -23.51u, closing line value +0.03 points (90% -0.07 to +0.13, n 284)

## The judge

- published: 134 graded, 60-74, -14.17u, closing line value +0.00 points (90% -0.21 to +0.20, n 97)
- argues against: 32 graded, 9-23, -13.84u, closing line value +0.02 points (90% -0.31 to +0.36, n 29)
- rule of thumb: 1645 graded, 868-765-12, -10.05u, closing line value -0.07 points (90% -0.13 to -0.01, n 1004)
- unsure: 10 graded, 4-6, -2.32u, closing line value -1.10 points (90% -1.70 to -0.50, n 10)

## Sources the researcher cited

- 1069thefan.com: 7 of 8 checked out
- 146.freechallenge.14.racing.cbssports.com: 0 of 2 checked out
- 49ers.com: 6 of 7 checked out
- abcnews.com: 2 of 2 checked out
- abqjournal.com: 30 of 34 checked out
- accsports.com: 4 of 5 checked out
- admin.theacc.com: 1 of 1 checked out
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
- ballstatesports.com: 15 of 17 checked out
- baylorbears.com: 3 of 5 checked out
- bceagles.com: 1 of 1 checked out
- bengals.com: 7 of 10 checked out
- bgsufalcons.com: 2 of 2 checked out
- bigten.org: 2 of 2 checked out
- bluehens.com: 3 of 3 checked out
- boston.com: 3 of 3 checked out
- buffalobills.com: 15 of 15 checked out
- bythebelt.com: 1 of 1 checked out
- ca.sports.yahoo.com: 1 of 1 checked out
- cfb-model-lab.vercel.app: 3 of 3 checked out
- chicagobears.com: 17 of 18 checked out
- chiefs.com: 2 of 2 checked out
- clevelandbrowns.com: 7 of 9 checked out
- clickondetroit.com: 2 of 2 checked out
- cmuchippewas.com: 7 of 7 checked out
- colts.com: 4 of 6 checked out
- commanders.com: 9 of 12 checked out
- conven.org: 7 of 7 checked out
- csurams.com: 4 of 4 checked out
- cuse.com: 3 of 4 checked out
- d1hg55pco9dr97.cloudfront.net: 1 of 1 checked out
- d1iubivivot1gj.cloudfront.net: 2 of 2 checked out
- d1tacpi2k4cwvj.cloudfront.net: 2 of 3 checked out
- d3h8hkdb4o069q.cloudfront.net: 2 of 2 checked out
- dailyillini.com: 2 of 2 checked out
- dailylobo.com: 1 of 1 checked out
- dallascowboys.com: 7 of 9 checked out
- davecampbells.com: 3 of 3 checked out
- db5y6jlvyeaqj.cloudfront.net: 5 of 5 checked out
- denverbroncos.com: 9 of 10 checked out
- denvergazette.com: 10 of 10 checked out
- deseret.com: 7 of 7 checked out
- df5u1lzgdv707.cloudfront.net: 3 of 3 checked out
- ecupirates.com: 2 of 2 checked out
- espn.com: 2 of 2 checked out
- evanscutchmorepress.com: 3 of 3 checked out
- expressnews.com: 5 of 7 checked out
- fausports.com: 15 of 18 checked out
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
- giants.com: 11 of 12 checked out
- goairforcefalcons.com: 3 of 3 checked out
- goarmywestpoint.com: 5 of 5 checked out
- goaztecs.com: 5 of 6 checked out
- gobearcats.com: 3 of 3 checked out
- gobearkats.com: 9 of 9 checked out
- gobison.com: 1 of 1 checked out
- goblueraiders.com: 6 of 6 checked out
- gobulldogs.com: 1 of 1 checked out
- gocards.com: 0 of 1 checked out
- goccusports.com: 3 of 3 checked out
- goducks.com: 1 of 1 checked out
- goduke.com: 0 of 1 checked out
- gofrogs.com: 1 of 1 checked out
- goheels.com: 8 of 10 checked out
- gohuskies.com: 2 of 2 checked out
- golobos.com: 2 of 2 checked out
- gophersports.com: 3 of 3 checked out
- gopsusports.com: 2 of 2 checked out
- gotigersgo.com: 12 of 12 checked out
- gousfbulls.com: 13 of 17 checked out
- goutsa.com: 5 of 6 checked out
- gowyo.com: 2 of 2 checked out
- gozips.com: 5 of 8 checked out
- hawkeyesports.com: 5 of 6 checked out
- hokiesports.com: 1 of 1 checked out
- hoosierhuddle.com: 5 of 6 checked out
- hornetsports.com: 5 of 5 checked out
- hottytoddy.com: 6 of 8 checked out
- houstonchronicle.com: 4 of 4 checked out
- houstontexans.com: 13 of 18 checked out
- huskers.com: 2 of 2 checked out
- insidethehall.com: 5 of 7 checked out
- iuhoosiers.com: 7 of 7 checked out
- jaguars.com: 8 of 9 checked out
- jaxstatesports.com: 7 of 7 checked out
- jmusports.com: 1 of 1 checked out
- kait8.com: 1 of 1 checked out
- kcci.com: 1 of 1 checked out
- kentstatesports.com: 12 of 13 checked out
- kolotv.com: 3 of 3 checked out
- kstatesports.com: 4 of 4 checked out
- ksuowls.com: 3 of 3 checked out
- kwqc.com: 1 of 1 checked out
- ky3.com: 2 of 2 checked out
- latechsports.com: 4 of 4 checked out
- libertyflames.com: 1 of 1 checked out
- march2thepod.substack.com: 3 of 3 checked out
- masslive.com: 0 of 1 checked out
- meangreensports.com: 3 of 5 checked out
- mgoblue.com: 7 of 7 checked out
- miamihurricanes.com: 3 of 3 checked out
- miamiredhawks.com: 13 of 13 checked out
- miamistudent.net: 5 of 5 checked out
- minutemancommand.com: 0 of 3 checked out
- missouristatebears.com: 4 of 5 checked out
- nationalfootballpost.com: 3 of 4 checked out
- navysports.com: 8 of 8 checked out
- nbcmiami.com: 0 of 2 checked out
- ncfootballnews.com: 2 of 2 checked out
- nevadawolfpack.com: 4 of 4 checked out
- neworleanssaints.com: 4 of 6 checked out
- newson6.com: 1 of 1 checked out
- nfl.com: 9 of 11 checked out
- nmstatesports.com: 9 of 9 checked out
- nusports.com: 1 of 1 checked out
- odusports.com: 4 of 4 checked out
- ohiobobcats.com: 14 of 14 checked out
- olemisssports.com: 2 of 2 checked out
- on3.com: 49 of 57 checked out
- osubeavers.com: 3 of 4 checked out
- packers.com: 4 of 5 checked out
- panthers.com: 8 of 8 checked out
- patriots.com: 13 of 20 checked out
- philadelphiaeagles.com: 18 of 19 checked out
- phlsportsnow.com: 1 of 1 checked out
- pittsburghpanthers.com: 3 of 3 checked out
- purduesports.com: 2 of 2 checked out
- ragincajuns.com: 2 of 2 checked out
- raiders.com: 3 of 4 checked out
- riceowls.com: 1 of 1 checked out
- rolltide.com: 1 of 1 checked out
- s3.us-east-2.amazonaws.com: 2 of 2 checked out
- seahawks.com: 15 of 17 checked out
- secsports.com: 0 of 1 checked out
- si.com: 85 of 92 checked out
- sicem365.com: 3 of 3 checked out
- sjsuspartans.com: 1 of 1 checked out
- smumustangs.com: 9 of 9 checked out
- soflobulls.com: 2 of 4 checked out
- soonersports.com: 3 of 3 checked out
- southernmiss.com: 6 of 7 checked out
- sports.ksl.com: 1 of 2 checked out
- sports.mynorthwest.com: 1 of 1 checked out
- sports.yahoo.com: 28 of 31 checked out
- staging-aws.sports.yahoo.com: 1 of 1 checked out
- startribune.com: 0 of 5 checked out
- statenews.com: 2 of 2 checked out
- static.clubs.nfl.com: 0 of 1 checked out
- steelers.com: 12 of 15 checked out
- storage.googleapis.com: 0 of 5 checked out
- sunbeltsports.org: 1 of 1 checked out
- sundevildaily.com: 1 of 1 checked out
- supertalk.fm: 3 of 3 checked out
- techlunchpail.com: 2 of 3 checked out
- temple-news.com: 0 of 2 checked out
- tennesseetitans.com: 2 of 2 checked out
- theacc.com: 12 of 12 checked out
- theclemsoninsider.com: 7 of 7 checked out
- thedailyhoosier.com: 3 of 4 checked out
- thekeyplay.com: 3 of 3 checked out
- thepostathens.com: 9 of 9 checked out
- therams.com: 18 of 24 checked out
- thescore.com: 4 of 4 checked out
- thesundevils.com: 8 of 8 checked out
- tide1009.com: 1 of 1 checked out
- toledoblade.com: 0 of 2 checked out
- troytrojans.com: 10 of 10 checked out
- tucson.com: 2 of 2 checked out
- tulanegreenwave.com: 2 of 2 checked out
- tulsahurricane.com: 9 of 11 checked out
- txst.com: 4 of 4 checked out
- ubbulls.com: 4 of 4 checked out
- ucfknights.com: 2 of 2 checked out
- uclabruins.com: 5 of 5 checked out
- uconnhuskies.com: 4 of 4 checked out
- ulmwarhawks.com: 3 of 3 checked out
- umassathletics.com: 6 of 6 checked out
- underdogdynasty.com: 9 of 10 checked out
- unlvrebels.com: 3 of 3 checked out
- usajaguars.com: 2 of 2 checked out
- usforacle.com: 1 of 2 checked out
- utahstateaggies.com: 1 of 1 checked out
- utahutes.com: 2 of 2 checked out
- utepminers.com: 4 of 5 checked out
- utrockets.com: 3 of 3 checked out
- vikings.com: 2 of 2 checked out
- wdrbwave.com: 2 of 2 checked out
- whsv.com: 4 of 4 checked out
- wjr.com: 2 of 2 checked out
- wkusports.com: 11 of 11 checked out
- wmubroncos.com: 0 of 1 checked out
- wndu.com: 3 of 3 checked out
- woub.org: 4 of 4 checked out
- wsbtv.com: 1 of 1 checked out
- wvmetronews.com: 5 of 5 checked out
- wvusports.com: 3 of 3 checked out

## Posts

- reason kind injury: 7 posts, 5.82 engagements per thousand views
- reason kind market: 1 posts, 4.26 engagements per thousand views
- reason kind none: 27 posts, 6.15 engagements per thousand views
- reason kind other: 11 posts, 6.28 engagements per thousand views
- reason kind role: 1 posts, 0.0 engagements per thousand views
- reason kind stats: 6 posts, 7.79 engagements per thousand views

## Which posts and which hours

- announcement: 1 posts, 0.0 engagements per thousand views
- book: 1 posts, 32.26 engagements per thousand views
- cashed: 28 posts, 7.26 engagements per thousand views
- cbb-pick: 2 posts, 9.06 engagements per thousand views
- community: 20 posts, 9.16 engagements per thousand views
- conversation: 4 posts, 22.6 engagements per thousand views
- menu: 4 posts, 0.0 engagements per thousand views
- nba-trial: 2 posts, 4.28 engagements per thousand views
- news: 1 posts, 0.0 engagements per thousand views
- play: 53 posts, 6.16 engagements per thousand views
- receipt: 29 posts, 7.74 engagements per thousand views
- research: 33 posts, 4.21 engagements per thousand views
- sheet: 6 posts, 3.55 engagements per thousand views
- before 9 AM: 17 posts, 5.9 engagements per thousand views
- 9 to 11 AM: 62 posts, 8.04 engagements per thousand views
- 11 AM to 2 PM: 57 posts, 5.45 engagements per thousand views
- 2 to 6 PM: 20 posts, 8.71 engagements per thousand views
- after 6 PM: 28 posts, 5.83 engagements per thousand views

## Card themes by the same post category

- book / legacy: 1 posts, 32.26 engagements per thousand views (small sample)
- cashed / legacy: 19 posts, 5.51 engagements per thousand views
- cbb-pick / legacy: 2 posts, 9.06 engagements per thousand views (small sample)
- community / legacy: 16 posts, 6.19 engagements per thousand views
- menu / legacy: 4 posts, 0.0 engagements per thousand views (small sample)
- nba-trial / legacy: 2 posts, 4.28 engagements per thousand views (small sample)
- play / legacy: 53 posts, 6.16 engagements per thousand views
- receipt / legacy: 27 posts, 8.31 engagements per thousand views
- research / legacy: 27 posts, 5.14 engagements per thousand views
- sheet / legacy: 6 posts, 3.55 engagements per thousand views (small sample)

## Matchup-supported leans

- 317 graded, distinct matchup-supported observations. Reporting only; this changes no gate.
- NFL/CFB: player defense-vs-position and opponent-quality splits are active.
- NBA/CBB: team projections are active; player defense-vs-position is not live yet.
- EPL/MLS: team-level score and market shadows only.
- MLB: scores and market collection only; no batter-vs-pitcher lean yet.
- NHL: scores and market collection only; no skater/goalie lean yet.
- NFL WR over recYds vs bottom-half defense: 20-17, +0.91u (n 37).
- NFL WR over rec vs bottom-half defense: 19-9, +8.31u (n 28).
- NFL TE over recYds vs bottom-half defense: 9-13, -4.96u (n 22).
- NFL WR under recYds vs top 10 defense: 13-8, +3.59u (n 21).
- NFL WR under rec vs top 10 defense: 11-10, -1.79u (n 21).
- NFL RB over rushYds vs bottom-half defense: 10-8, +0.88u (n 18).
- NFL RB over recYds vs bottom-half defense: 8-8, -0.64u (n 16).
- NFL QB over att vs bottom-half defense: 8-6, +0.81u (n 14).
- NFL QB over cmp vs bottom-half defense: 7-6, +0.21u (n 13).
- NFL RB over car vs bottom-half defense: 5-7, -2.77u (n 12).
- NFL TE under rec vs top 10 defense: 8-3, +2.59u (n 11).
- NFL QB under passYds vs top 10 defense: 7-4, +2.24u (n 11).
- NFL QB under cmp vs top 10 defense: 5-6, -1.61u (n 11).
- NFL QB over passYds vs bottom-half defense: 4-7, -3.44u (n 11).
- NFL QB over rushYds vs bottom-half defense: 4-7, -3.49u (n 11).
- NFL TE over rec vs bottom-half defense: 4-7, -3.50u (n 11).
- NFL QB under att vs top 10 defense: 5-4, +0.46u (n 9).
- NFL RB under car vs top 10 defense: 5-3, +1.20u (n 8).
- NFL RB under rec vs top 10 defense: 4-4, -0.13u (n 8).
- NFL RB over rec vs bottom-half defense: 4-4, -0.80u (n 8).
- NFL RB under rushYds vs top 10 defense: 3-1, +1.67u (n 4).
- CFB WR under rec vs top-half defense: 3-0, +3.58u (n 3).
- CFB WR over rec vs bottom-half defense: 1-0, +1.12u (n 1).
- CFB RB over rushYds vs bottom-half defense: 1-0, +1.08u (n 1).
- NFL QB under rushYds vs top 10 defense: 1-0, +0.88u (n 1).
- NFL RB under recYds vs top 10 defense: 1-0, +0.88u (n 1).
- NFL TE under recYds vs top 10 defense: 1-0, +0.88u (n 1).
- NFL WR over rushYds vs bottom-half defense: 1-0, +0.88u (n 1).
- NFL QB under car vs top 10 defense: 1-0, +0.72u (n 1).
- CFB WR under recYds vs top-half defense: 0-1, -1.00u (n 1).
- NFL QB over car vs bottom-half defense: 0-1, -1.00u (n 1).

## Released multi-leg tickets

- 21 released and graded tickets. Unreleased ideas are excluded.
- Climb / 2-leg / all alternates: 5-3-0-0, -0.09u on 8 with stored units (n 8).
- Climb / 1-leg / all alternates: 0-2-0-0, -0.50u on 2 with stored units (n 2).
- Fun ticket / 2-leg / all alternates: 1-1-0-0, +0.00u on 2 with stored units (n 2).
- Climb / 2-leg / main lines: 1-0-0-0, +0.18u on 1 with stored units (n 1).
- Fun ticket / 4-leg / all alternates: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 7-leg / all alternates: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 3-leg / main lines: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 5-leg / main lines: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 4-leg / mixed alternates: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 5-leg / mixed alternates: 0-1-0-0, -0.25u on 1 with stored units (n 1).
- Fun ticket / 6-leg / mixed alternates: 1-0-0-0, +1.74u on 1 with stored units (n 1).
- Fun ticket / 3-leg / unclassified: 0-1-0-0, units unavailable (n 1).

## Engagement scorecard

- 184 measured posts; 127 human interactions across 28456 impressions; 4.46 per thousand.
- announcement: 1 posts, 0.0 per thousand (small sample)
- book: 1 posts, 32.26 per thousand (small sample)
- cashed: 28 posts, 8.17 per thousand
- cbb-pick: 2 posts, 8.96 per thousand (small sample)
- community: 20 posts, 2.97 per thousand
- conversation: 4 posts, 21.05 per thousand (small sample)
- menu: 4 posts, 0.0 per thousand (small sample)
- nba-trial: 2 posts, 3.29 per thousand (small sample)
- news: 1 posts, 0.0 per thousand (small sample)
- play: 53 posts, 4.99 per thousand
- receipt: 29 posts, 7.51 per thousand
- research: 33 posts, 3.3 per thousand
- sheet: 6 posts, 5.18 per thousand (small sample)

## The number against the close (season to date)

- CFB v1: 577 games, total miss 13.37 vs the close's 12.57
- CFB v2.0: 259 games, total miss 12.72 vs the close's 12.3
- CFB v2.1: 314 games, total miss 13.87 vs the close's 12.87
- NFL v1: 148 games, total miss 11.16 vs the close's 10.21
- NFL v2.0: 60 games, total miss 11.34 vs the close's 10.1
- NFL v2.1: 86 games, total miss 10.7 vs the close's 10.3

## Prop formula review

Earlier 60% of kickoff dates train; later dates test. Both error scores must improve. Repeated retrospective evaluation; future shadow results required before promotion. Counts are prop observations, not independent games; no ROI claim without captured prices.

p = 0.5 + k * (raw - 0.5); k = w*k_market + (1-w)*k_league; w = n_train/(n_train+300)

- CFB/prop:passYds: 355 earlier / 224 later observations; later-game squared probability error 0.2481 league / 0.2490 pooled; keep league formula.
- CFB/prop:rec: 540 earlier / 471 later observations; later-game squared probability error 0.2479 league / 0.2482 pooled; keep league formula.
- CFB/prop:recYds: 871 earlier / 635 later observations; later-game squared probability error 0.2492 league / 0.2485 pooled; shadow candidate.
- CFB/prop:rushYds: 659 earlier / 441 later observations; later-game squared probability error 0.2493 league / 0.2493 pooled; shadow candidate.
- NFL/prop:att: 170 earlier / 97 later observations; later-game squared probability error 0.2507 league / 0.2504 pooled; shadow candidate.
- NFL/prop:car: 306 earlier / 182 later observations; later-game squared probability error 0.2534 league / 0.2536 pooled; keep league formula.
- NFL/prop:cmp: 171 earlier / 100 later observations; later-game squared probability error 0.2504 league / 0.2505 pooled; keep league formula.
- NFL/prop:passYds: 166 earlier / 94 later observations; later-game squared probability error 0.2499 league / 0.2499 pooled; keep league formula.
- NFL/prop:rec: 1025 earlier / 661 later observations; later-game squared probability error 0.2494 league / 0.2492 pooled; shadow candidate.
- NFL/prop:recYds: 1023 earlier / 659 later observations; later-game squared probability error 0.2502 league / 0.2504 pooled; keep league formula.
- NFL/prop:rushYds: 500 earlier / 301 later observations; later-game squared probability error 0.2511 league / 0.2504 pooled; shadow candidate.


## Silent results shadows

- These observations changed no play, card, post, record, gate or request budget.
- R0: 9241 raw rows, 6824 distinct
- R1: observation active; public behavior unchanged
- R2: observation active; public behavior unchanged
- R3: 11 prop markets observed
- R4: observation active; public behavior unchanged
- R5: 95 heavy alternates observed; default unchanged
- R6: observation active; public behavior unchanged
- R7: observation active; public behavior unchanged
