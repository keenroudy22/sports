# Basketball: NBA and men's college

A first slice of basketball: a store of every final with its lines, a team-rating model, and one honest
look at whether the model is good enough to publish leans. It is not wired into the site, the desk or
the refresh workflow. Nothing here is published.

## The store

`scripts/hoops_store.py` keeps one line per final in `data/hoops/<league>-<season>.jsonl` (`nba`, `cbb`),
with `data/hoops/ledger.json` hashing what each file holds. Append-only, like the box-score store, and
with the same helpers; `tests/test_hoops_store.py` fails if a recorded line changes.

- **Sources.** ESPN's scoreboard, one day at a time (college with `groups=50`, all of Division I), and
  ESPN's core odds feed for every final. Python's default User-Agent; the feed refuses custom ones.
  A quarter-second pause after every request.
- **A line** is the teams (id, abbreviation, school, short name, colour), the score, the neutral-site
  flag, ESPN's season (named by its end year: 2025-26 is 2026) and season type (2 regular season,
  college conference tournaments included; 3 postseason; 5 the NBA play-in), and the close and open.
- **The close and open** are the consensus across books: the median of each book's closing (opening)
  total and home spread, with the number of books. Live in-game feeds and projection services
  (ESPN's accuscore) are not books and are left out; Caesars' three state listings count once. With
  an even number of books the median can land on a quarter point no book offered. It is a yardstick
  for grading, never a quote to bet. A game no book priced has no line.
- **Books by season.** 2023-24: eight to nine books a game (Betfair, Caesars, DraftKings, ESPN BET,
  MGM, SugarHouse, Titanbets, Unibet). 2024-25: ESPN BET only. 2025-26: DraftKings, with ESPN BET in
  the first weeks. The 2024-25 ESPN BET openers sit further from the close than the others (NBA
  totals moved 3.4 points on average from open to close, against 2.4 in 2023-24 and 2.6 in 2025-26).

```
python scripts/hoops_store.py backfill NBA 2026     every final of 2025-26 (resumable)
python scripts/hoops_store.py refresh               new finals from the last three days
```

What is stored (backfilled 2026-09-24, about 11 MB):

| Season | NBA games | with a close | College games | with a close |
|---|---|---|---|---|
| 2023-24 | 1,319 | 1,319 | 6,243 | 5,443 |
| 2024-25 | 1,321 | 1,321 | 6,292 | 5,762 |
| 2025-26 | 1,322 | 1,321 | 6,300 | 5,748 |

NBA seasons are the regular season (the Cup final included), the play-in and the playoffs. College
seasons are every Division I game, its non-Division I opponents (about 350 of the 700-odd teams a
season), conference tournaments and the postseason tournaments. The college games without a close
are mostly against non-Division I schools (six in ten in 2023-24, nine in ten since).

## The model

`scripts/hoops_model.py`. Each side's points are the league mean, plus the home edge (none at a neutral
site), plus its offense, plus the opponent's defense. The ratings come from the season's games before a
daily 08:00 UTC refit, by ridge regression:

- `halfLife`: a game's weight halves every this many days;
- `carry`: last season's closing ratings, shrunk toward average by this factor, are this season's start;
- `ridge`: how many games' worth of evidence that start counts for.

Margin and total are fitted separately, each with its own three knobs. College schools outside Division
I (fewer than five stored games in every season) share one rating. The system is solved by
preconditioned conjugate gradients on the sparse design, warm-started from the day before, so a
walk-forward of a whole college season takes seconds. Forecasts carry a standard deviation from the
fit's own residuals. No market input, no injuries, no rest days.

```
python scripts/hoops_model.py backtest NBA 2026     walk-forward grade of one season
python scripts/hoops_model.py tune CBB              grid on 2024-25, then 2025-26 once
```

## How it was tested

The same protocol as model v2. Every knob was tuned on 2024-25 (2023-24 as history, so the tuning
season starts from a real prior): a grid of 240 settings per target (half-life 20 to 365 days, ridge
2 to 40 games, carry 0.3 to 1), the lowest average miss against the result on priced games wins, ties
to the longer memory. The chosen setting was then scored once
on 2025-26, which nothing was tuned on. `data/model/hoops-nba.json` and `hoops-cbb.json` hold the grid,
every trial, both seasons' grades, the calibration and the record of each look at the holdout;
`data/model/hoops-backtest-*.json` hold every walk-forward forecast in the shape of
`backtest-v2.json`.

The records take **our side against the opening line** (over when our total is above the opening total,
home when our margin is above the opening margin), because that is roughly where the desk would bet,
and grade it **at the closing line**, the conservative grade. The same side graded at the opening
number, and how far the line moved toward us, are shown beside it. Gaps to the opening line are
bucketed 0-1, 1-2, 2-4 and 4+ points for the NBA and 0-1.5, 1.5-3, 3-6 and 6+ for college, where our
number and the market disagree more; the **lean** is the top two buckets (2+ NBA, 3+ college).
Break-even at -110 is 52.4%.

The calibration is `calibrated = 50% + k * (raw - 50%)`, the rule in `scripts/pricing.py`, with k fitted
on 2024-25 by log-likelihood against the close and checked on 2025-26: does the tuning season's k
predict the holdout better than a coin?

## What it found

The settings chosen on 2024-25 (half-life in days, ridge in games, carry):

| | Margin | Total |
|---|---|---|
| NBA | 45, 5, 1.0 | 30, 5, 1.0 |
| College | 365, 5, 1.0 | 45, 5, 0.75 |

Three of the four took full carry, the top of the grid, and college margins also took the grid's
longest memory, so a longer one might do a little better; trying it would be a second look at the
holdout and must be recorded as one. On the holdout the tuned college setting beat the untuned one
(half-life 60, ridge 10, carry 0.6) clearly: margins 0.64 points better a game, totals 0.10, both WINS by
model_v2's paired bootstrap, and margins by 1.4 points a game in the first month, where last season's
ratings matter most.
The tuned NBA setting was a wash against the untuned one (noise on both).

The NBA holdout was computed twice with the same model code: a first run printed it without writing, and
the recorded run added only the line-move columns. `hoops-nba.json` says so in its `looks`.

**2025-26, scored once** (average miss against the final score, points, on games with a close):

| | Our miss | Close | Open | Ours closer than the close | Ours minus close, 90% interval |
|---|---|---|---|---|---|
| NBA margin (1,321) | 11.48 | 11.01 | 11.21 | 45.4% | +0.47 (+0.30 to +0.62) |
| NBA total (1,321) | 15.06 | 14.50 | 14.70 | 46.9% | +0.56 (+0.36 to +0.79) |
| College margin (5,743) | 9.34 | 8.94 | 9.07 | 46.0% | +0.40 (+0.33 to +0.47) |
| College total (5,748) | 13.87 | 13.38 | 13.62 | 45.2% | +0.49 (+0.40 to +0.59) |

The close beats our number in every market, by about half a point a game. Even the opening line beats it.

**Our side against the opening line, graded at the close** (won-lost, pushes aside; the lean in bold):

| 2025-26 | NBA sides | NBA totals | | College sides | College totals |
|---|---|---|---|---|---|
| 0-1 | 156-160 (49.4%) | 124-123 (50.2%) | 0-1.5 | 1240-1210 (50.6%) | 780-790 (49.7%) |
| 1-2 | 133-143 (48.2%) | 106-129 (45.1%) | 1.5-3 | 796-791 (50.2%) | 744-697 (51.6%) |
| 2-4 | 192-222 (46.4%) | 189-176 (51.8%) | 3-6 | 630-649 (49.3%) | 946-924 (50.6%) |
| 4+ | 166-145 (53.4%) | 235-238 (49.7%) | 6+ | 189-224 (45.8%) | 438-421 (51.0%) |
| **Lean** | **358-367 (49.4%)** | **424-414 (50.6%)** | | **819-873 (48.4%)** | **1384-1345 (50.7%)** |
| Lean, 90% interval | 46.3-52.4% | 47.8-53.4% | | 46.4-50.4% | 49.1-52.3% |
| Lean in 2024-25 | 364-360 (50.3%) | 416-424 (49.5%) | | 862-894 (49.1%) | 1208-1195 (50.3%) |

No lean clears 52.4% in either season. The one bucket over it (NBA sides 4+, 53.4% on 311) was 52.9%
on 2024-25 and sits beside a 2-4 bucket at 46.4%; it is what noise looks like.

**Calibration against the close.** On 2024-25 the side our number favoured won 49.5% of NBA spreads,
49.2% of NBA totals, 49.6% of college spreads and 50.2% of college totals, whatever the raw chance said.
The fitted k is 0 in all four markets: the raw chance carries no information against the closing line,
so there is nothing to calibrate and nothing that could "fit". 2025-26 agrees (49.3%, 51.3%, 50.2%,
49.6%; a k refitted on it is 0.00 to 0.01).

**The one thing that holds up: totals against the opening number.** The market moves toward our total
between the open and the close. In the 2025-26 lean it moved our way in 53% of NBA games (0.84 points on
average) and 55% of college games (0.86), and our side graded at the opening number went 451-387 (53.8%,
90% interval 51.0-56.6%) in the NBA and 1434-1293 (52.6%, 51.0-54.1%) in college. 2024-25 said the same
(53.6% and 52.1%). Against the open, the totals calibration fits on the holdout too (college k 0.18
fitted, 0.21 on 2025-26; NBA k 0.42 fitted, 0.22 on 2025-26, a small gain). Sides show none of it (48.8%
NBA, 50.4% college at the open). By the close the market has priced whatever our number knew: the edge is
in the opening number, not in the model's view of the game.

## Recommendation

**Publish no basketball model leans: not NBA sides, not NBA totals, not college sides, not college
totals.** None meets the bar. On the untouched season our side at the close in the lean bucket went 49.4%,
50.6%, 48.4% and 50.7%, every one under 52.4% on 700 to 2,700 plays, and the calibration against the close
is k = 0 in every market. That is not a thin sample; it is a model that knows less than the closing line.

Totals deserve a paper trial, not a publication. Our side at the opening number has cleared 52.4% in both
seasons and both leagues, but that grade uses ESPN's opening line: the first number the book posted,
which may have been up only briefly and at low limits, and in 2024-25 a single book whose openers include
some stray numbers (2% of NBA spreads moved 10 points or more by the close). Whether the desk can get a
number like it is unknown. The way to find out is to record our total beside the prices the desk actually
captures before publishing anything: capture basketball totals when the seasons start (NBA 20 October,
college 1 November), log our number beside the first price captured for each game, and grade those at
the close for a month. Publish totals leans only if that record clears 52.4% at the captured price, and
only with a calibration fitted on it.

## Limits and next steps

- The model knows scores only. No injuries or rest (both are large in the NBA and priced by the
  market), no travel, no lineups, no pace or shot-quality inputs. These are the obvious next terms,
  each to be shipped only by the holdout rule.
- The standard deviations come from in-sample residuals and run 4 to 10% under the walk-forward misses
  (2025-26 NBA margin 13.4 against 14.7; college total 15.8 against 17.5).
- One season of 2024-25 closes is a single book (ESPN BET); 2025-26 is DraftKings. Consensus lines
  from many books exist only for 2023-24, the history season.
- The first stored season (2023-24) has no prior and is not graded. Its opening day has no forecast.
- Not built: a daily forecast file, site pages, the desk's gates for basketball, settlement rules
  (overtime counts toward totals and spreads at the major books, which is what the store's scores
  are). These wait for a model that clears the bar.
