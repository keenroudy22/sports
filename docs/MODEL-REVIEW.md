# Formula and selection review · October 4, 2026

This release tightens future selection, improves explanations, and adds an offline formula comparison. It does
not revise a published result, change the accounting, or claim a proven profit advantage.

## Equations

- American-price break-even: `q = 1 / (1 + profit_per_unit)`.
- Adjusted prop probability: `p = 0.5 + k * (raw_probability - 0.5)`.
- Price edge: `100 * (p - q)` percentage points. A projection-minus-line gap is a different quantity.
- Official-prop floor: two percentage points; a third prop from the same league/market needs five.
- Experimental pooled shrink: `k = w*k_market + (1-w)*k_league`, with `w = n_train/(n_train+300)`.
  The 300-observation prior is a declared experimental choice, not a fitted guarantee.

Fit both league and market coefficients using only the earlier 60% of unique kickoff dates. Keep all observations
from the same date together. Compare on later dates using mean squared probability error (Brier score) and log loss;
lower is better. A market needs 100 training observations on at least four dates and 50 testing observations on two
dates. These are observations, not independent games. Repeated retrospective tests nominate shadow candidates,
never production changes. No return calculation is made for projections without captured prices.

The existing weekly league calibration now uses whole-date splits too. It deploys the coefficient actually tested,
instead of fitting a different coefficient on the combined training and testing sample after the test passes.
The search is limited to 0–1, the same range accepted by the production pricing function.

## Initial stored-data evaluation

Run `python3 scripts/market_review.py` to reproduce from the current stored record. On October 4 before the early
slate, no eligible market-specific formula improved both scores. NFL receptions used 171 earlier and 175 later
observations: squared probability error was 0.2488 for the league formula and 0.2492 for the pooled alternative.
NFL receiving yards and college receiving/rushing yards also favored the league formula. Other markets did not
meet the sample minimums. This does not establish an edge for the league formula; it rejects this proposed change.

The Monday owner review computes a fresh comparison; Tuesday's existing learning job also includes it in its report.
Both read existing data only. Future live promotion needs a prospective shadow evaluation.

## Explanation and delivery

Future props save exact-line history, projected role, positional defense context and explicit counterarguments.
A poor recent hit rate or adverse positional matchup is described as a concern, never a supporting fact. Positional
defense is the whole group's allowance, and past hit rate is not a prediction. Verified opposing source links are
retained. The expanded website card surfaces the first concern; Why this play opens the complete explanation.

Future X and Discord posts share one saved supporting sentence when one is available. Existing delivered posts
are preserved. Buffer remains the only X publisher; limits, webhooks, API budgets and posting schedules are unchanged.
