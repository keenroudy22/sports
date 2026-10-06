# Results proposals: same-or-better results, tested before anything changes

Every proposal here runs as a **silent shadow** first. It's logged and graded, but it changes no play, post, card or
record. Each needs its own owner yes, backed by before/after counts. The market supplies prices, gates and grades
only; it is never blended into the model (MIGRATION.md §4d). No new metered requests and no paid feeds.

## Where results stand (public payloads, 2026-10-06)

| Slice | Record | Units | Closing-line value (CLV) |
|---|---|---|---|
| All published straights | 35–35 | −4.11u at captured prices | avg +0.01 pts (12 beat / 15 tied / 13 lost of 40) |
| Player props | 26–21 | about +2.8u | **+0.29 avg, 6 beat / 2 lost of 17** |
| Game picks | 9–14 | −4.26u | **−0.20 avg, 6 beat / 11 lost of 23** |
| NFL totals (published) | 2–5 | −3.0u | |
| CFB totals (published) | 6–8 | −1.25u | −0.18 avg (n=14), median about 52 h before kickoff |
| Fun parlays | 4–11 | small stakes | |

Model vs market:
- In all seven prop markets the sportsbook line was closer to the result than our projection (for example, receiving
  yards: line miss 21.4 vs our 22.6).
- Calibration keeps only 13% (NFL) and 23% (CFB) of the raw prop lean.
- `docs/EDGE.md`: the only demonstrated game-line edge is **CFB totals at the opening number** (54.0% at the open in
  2025 vs 52.3% at the close; break-even 52.4%).

The honest summary: props are the one category beating the close, and game lines are not. The model's raw numbers run
hot and need the shrink they get. Better results come from betting where the evidence is, at the best and freshest
price, at the right time. They don't come from prettier pages.

## R0: count each game once (prerequisite)

`learn.joined()` can hold up to 7 rows for the same game. Refused NFL totals went 6–42, but those 48 rows come from 15
games. Add `learn.distinct()`: one row per segment, game, side and athlete, keeping the published row or else the
earliest. Use it in every shadow report and in the `learn.learn_segments` (L170) sample counts. **Show the owner the
before and after numbers** (AGENTS.md: "do not change how the record counts" applies in spirit to learning numbers too).

## R1: take CFB totals at the opener

- **Why.** The edge exists at the open and fades by the close. We currently publish CFB totals about 52 hours out,
  after the move.
- **What blocks early candidates today:** `card_cap` (48), `lean_nothing_against` (31), `not_duplicate` (26),
  `one_book` (24, up to 147 h out) and `held` (18).
- **Change (shadow):** a new `scripts/opener_lab.py`, modeled on `market_lab.py`.
  - Store the first total per FBS game.
  - Take the v2 snapshot via `desk.current` and the edge via `pricing.price`.
  - Grade like `learn.grade_row`.
  - Backfill weeks 1–6 as a retrospective only (labeled as such).
- **If approved:** move the one daily early capture (`odds_api.due`, `EARLY_CAP=1`) to Sunday 6–10 PM ET, at no
  extra credits. Let up to 2 of the 3 Saturday game-line slots fill Sunday–Tuesday (`gates.card_cap` L557,
  `gates.one_book` L460; slots live in `deployment/mac/com.keenroudy.sports.run.plist`).
- **Success bar** (each game counted once):
  - at least 150 forward rows with edge ≥ +2;
  - a hit rate of 53.5% or better at the captured price;
  - a CLV 90% interval whose low end is above 0 (`learning.interval`).

## R2: take NFL game totals off the official card

- **Why.** Published 2–5 (−3u). Model totals vs the close went 17–29 this season, and the model misses by more
  than the market (11.4 vs 10.2 points).
- **Change.** An owner-set `policy.segments['NFL/total'].offCard` in `gates.RULES` (L899). Rows keep grading as
  research, and there are no Save-this rings for them in `sheet.watches`.
- **Reopen** at 40+ graded games with a CLV low bound above 0 and a 52.4%+ hit rate.
- **Note:** this reverses the Oct 4 rule "performance raises the bar; it does not veto a market", but only for this
  market and only on the owner's yes.

## R3: per-market prop calibration

- **Change.** Fit a per-market k next to the pooled k in `learn.learn_calibration` (L251), using `market_review.py`.
  Log what would publish under per-market k.
- **Adopt a market** only with 300+ graded lines and a better held-out score than the pooled k. Markets that fail
  keep the existing +5 caution.

## R4: stale-price guard

- **Change.** `gates.fresh_quote` (L275) allows 12 hours today. Shadow 3 hours for props and 6 hours for game lines.
  Record quote age, and use `line_timing.measure` by age bucket.
- **Tighten only if** quotes older than 3 hours show at least 0.5 points of worse movement or CLV across 30+ plays.
  This means fewer plays, so the owner decides.

## R5: research hygiene (display only)

Hide alternate-line trends priced shorter than −300 in `season_trends.build` (L51, rung loop L86). That's 131 of 208
alternate rows; no main lines are affected. A 4-of-4 run at −900 still needs 90%. The prototype already hides them
behind "Show heavy favorites".

## R6: better line shopping inside free quotas

- **Budget.** 178 of 500 Odds API credits were used by Oct 6 (`work/quota/odds.jsonl`), so there's no spare budget.
- **Change.** Pace credits evenly (`odds_api.due`, `quota.guarded_json`). Run `sharp_odds.py --probe` for
  DraftKings/FanDuel game totals, after a SharpAPI terms check.
- **Success bar:** beat the close on 50% or more of 60+ plays (now 12 of 40).

## R7: closing-line value as the headline proof

- **Change.** `scoreboard.pick_rows` (L402) measures points only. Add no-vig price CLV from `data/odds` and
  `data/prop-odds`. Show "Beat the closing line X of Y" next to W–L and units on Record and receipts (the prototype
  already does).
- **Wording rule:** a missing close shows as unknown, never as zero. This is a public headline change, so the owner
  decides.

## How Codex runs a shadow

1. Put the proposal behind a default-off flag in `data/learning/policy.json`.
2. Write verdicts to `data/learning/shadow-<season>.jsonl` via `learning.append` (not the main memory: `run.remember`
   only records a row when a decision changes).
3. Grade with `learn.grade_pending` (L96) and report weekly in `review.packet` with n, record, units and the CLV
   interval.
4. After four weeks, or when the sample bar is met, ask the owner with before/after counts. Record the yes or no as a
   dated AGENTS.md rule.
