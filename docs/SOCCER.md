# Soccer: Premier League and MLS

A first slice: results and prices in a store, a goals model, and one honest look at whether the
model can beat the market. **The recommendation is to publish no soccer model leans yet.** The
Premier League Asian handicap is the only market worth watching. Its leans should be recorded,
not published, through 2026-27 before anything is posted.

## What is here

| File | What it holds |
|---|---|
| `scripts/soccer_store.py` | football-data.co.uk CSVs as one line per match in `data/soccer/<league>.jsonl`, append-only with `ledger.json` |
| `data/soccer/epl.jsonl` | 3,850 Premier League matches, 2016-17 to 2026-27 (50 played so far this season) |
| `data/soccer/mls.jsonl` | 4,832 MLS matches, 2016 to 2026 (387 so far), playoffs included |
| `data/soccer/teams.json` | This season's 20 Premier League and 30 MLS clubs: ESPN id, abbreviation, colours. It also lists the 36 Champions League clubs by ESPN id, with the five English ones linked |
| `scripts/soccer_model.py` | The Dixon-Coles model, its walk-forward, the tuning and the one holdout look |
| `data/model/soccer-epl.json`, `soccer-mls.json` | Every tuning trial, the chosen knobs, the tuning season, the calibration, the holdout and its look |

```
python scripts/soccer_store.py                     the current EPL and MLS seasons (idempotent)
python scripts/soccer_store.py teams               rebuild the ESPN team map
python scripts/soccer_model.py predict EPL Arsenal Chelsea --line -0.75
```

What the files carry. The Premier League files have 1X2, over/under 2.5 and the Asian handicap,
each at a first collection and at the close, plus shots. The first collection is Friday
afternoon for a weekend game and Tuesday afternoon for a midweek one, so it is not the true
opener. The MLS file has **closing 1X2 prices only**: no totals, no handicap, no early prices and
no shots. Pinnacle's prices stop after 210 matches of 2025-26 and are absent from 2026-27 and MLS
2026. Where Pinnacle is missing, the market average stands in, and every record names the book
used. 2026-27 adds xG, which is stored but not yet used. football-data has no Champions League
file, so the Champions League is not modelled.

## The model

Each club has an attack and a defence rating. Expected goals are
`exp(mu + home + attack - opponent's defence)`, fitted by penalised, time-weighted Poisson
maximum likelihood. Dixon and Coles' rho corrects the low scores. Promoted and expansion clubs
start from the average of the clubs that went down. A 0 to 10 score grid prices every market,
and quarter handicaps are settled as two half stakes. The ratings are refitted every Tuesday and
Friday at 06:00 UTC, using earlier matches only. No market input goes into the number.

The knobs were tuned on EPL 2024-25 and MLS 2024 alone, by the log loss of 1X2 plus over/under
2.5. The tuning record was committed before the holdout was read.

- **EPL**: half-life 180 days, ridge 1, rho fitted at every refit, last season counted at 0.7, and
  rates fitted to half goals and half shot-implied goals.
- **MLS**: half-life 90 days, ridge 10, no rho, last season counted at 0.5, goals only.

## The one look at the untouched season

Log loss is set against the close with its margin removed (proportional de-vig). Leans bet our
side when our chance beats the de-vigged price by the threshold the tuning season picked. Each
lean is settled at the **market average**, the price a typical book offered. k is the
calibration shrink toward the price, `q + k * (ours - q)`, fitted on the tuning season. The
number in brackets is k refitted on the holdout.

**Premier League 2025-26** (380 matches):

| Market | Log loss, ours / close | k (holdout) | Leans at the close | Leans at the first price |
|---|---|---|---|---|
| 1X2 | 1.0255 / 1.0139 | 0.28 (0.05) | 2 pts: 314 bets, 89-225, **-6.0%** | 6 pts: 97 bets, 25-72, **-15.3%** |
| Draw-no-bet | | 0.19 (0.00) | 4 pts: 213 bets, 52-103-58, **-9.6%** | 4 pts: 206 bets, 53-100-53, **-7.3%** |
| Over/under 2.5 | 0.6982 / 0.6831 | 0.00 (0.00) | 4 pts: 205 bets, 91-114, **-11.7%** | 6 pts: 109 bets, 46-63, **-16.6%** |
| Asian handicap | | 0.18 (0.26) | 2 pts: 293 bets, 148-124-21, **+3.1%** (90%: -5.5 to +11.5) | 6 pts: 166 bets, 80-76-10, **-2.2%** |

**MLS 2025** (540 matches; closing 1X2 only):

| Market | Log loss, ours / close | k (holdout) | Leans at the close |
|---|---|---|---|
| 1X2 | 1.0491 / 1.0252 (worse; 90% interval +0.012 to +0.037) | 0.03 (0.00) | 6 pts: 265 bets, **-5.4%** |
| Draw-no-bet | | 0.03 (0.00) | 2 pts: 458 bets, **-13.0%** |

The tuning seasons told the same story. EPL 2024-25 1X2 log loss was 0.9721 against the close's
0.9664, and totals were 0.6841 against 0.6769. MLS 2024 was 1.0459 against 1.0296. Every table,
with all three thresholds and the Pinnacle-price returns, is in the JSON files.

## Recommendation

**Premier League: publish nothing yet. Record the Asian handicap leans without publishing them.** The handicap is
the only market that clears the written bar. At the average closing price it returned +3.1% on
293 bets, and its calibration held: k was 0.18 on the tuning season and 0.26 on the holdout, and
the shrunk chance beat the close. That is weak evidence, for four reasons:

- the return's 90% interval runs from -5.5% to +11.5%;
- the rule for early prices, which is when the desk bets, lost 2.2%;
- after the k shrink, most edges are under 2 points against the fair price. A typical book's
  margin on a 1.89 handicap price is about 3 points, so the desk's own calibrated-edge rule would
  post almost nothing. The 62 bets whose shrunk edge still reached 2 points lost 4%;
- US books' prices are not in this data.

Record every candidate handicap lean for 2026-27 at a price the desk could get, graded like
`data/learning`. Revisit once about 200 have been graded.

The 1X2, draw-no-bet and 2.5 total all lose to the close. Their holdout k was near zero, and the
total's k was zero in both seasons.

**MLS: nothing.** The model is clearly worse than the close in both seasons, and its k is about
zero. The file cannot test totals, handicaps or early prices anyway.

**Champions League: not built.** A model would need ratings spanning 15 or more domestic leagues.

The inputs most likely to help are the xG football-data now carries (to build up over seasons),
lineups and injuries, and prices from books the desk can use.

## Limits and what was not verified

- football-data's times are taken as UK time. Converted to UTC, they matched ESPN's kickoffs to the
  minute for 157 of 158 completed matches checked. The check covered 87 EPL and 70 MLS matches,
  around both clock changes in 2025-26 and in September 2026. The one miss was Brighton v Liverpool
  on 21 March 2026, 12:30 against ESPN's 12:45. Older seasons were not checked.
- Before 2019-20 the files give no kickoff time, so those matches count as midday on their date.
  Those seasons are history only.
- Draw-no-bet prices are **replicated** from the 1X2 prices at one book (a stake on the draw that
  returns the whole stake). They were not quoted.
- The market average's handicap price is used only when it is on the same line as the main book's.
- MLS playoffs are included. Whether the file's score counts extra time in the later rounds was
  not checked. The 2020 bubble-tournament games are treated as home games.
- The market average is European books. US prices for these markets, and ESPN's core odds, were
  not used.
