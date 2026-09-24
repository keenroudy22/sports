# Where the edge is

A look on 2026-09-24 at the walk-forward backtest (`data/model/backtest-v2.json`, the model as published, each
game predicted from earlier games only), graded against the opening and the closing numbers in the store. "Our
side" is the side our number likes against the **opening** line, for gaps of a point or more. A -110 price needs
52.4% to break even. 2025 is the season the model was never tuned on.

| Market | 2024 at the open | 2025 at the open | 2025 at the close |
|---|---|---|---|
| College totals | 788-637, 55.3% | 798-679, 54.0% | 773-704, 52.3% |
| NFL totals | 211-204, 50.8% | 203-206, 49.6% | 196-213, 47.9% |
| College sides | 716-734, 49.4% | 787-748, 51.3% | 779-756, 50.7% |
| NFL sides | 216-201, 51.8% | 197-208, 48.6% | 195-215, 47.6% |

What follows from it:

- **College totals are the one market with a real edge, and it lives at the opening number.** The market moves
  toward our number during the week, so the same play graded at the close is close to break-even. The desk
  publishes college totals as soon as it sees them, and the record grades them at the number published.
- **NFL totals have none.** NFL model leans are paused (`data/learning/policy.json`, segment `NFL/total`). The
  learning step reopens the segment if the plays it now refuses keep beating the close.
- **Sides have none in either league.** Model leans are totals only, as before.
- Basketball and soccer, built the same way from scores, showed no edge either (`docs/HOOPS.md`,
  `docs/SOCCER.md`). One signal carries over: in basketball totals the line also moves toward our number, so a
  paper trial at the opening number is set up for when those seasons start.

Posts on X go out on game day, after the number has moved. A post therefore shows the number available when it
goes out as well as the number the play was published at, so a follower sees what they can actually get.
