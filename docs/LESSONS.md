# Closed operating lessons

## 2026-10-07 · Provider identity must not use a public display name

Three append-only learning rows were written during the C4 display-name regression with `-thescore-bet` IDs.
The Iowa–Washington row was a valid duplicate refusal. The Georgia–Alabama and Hawai'i–Arizona State rows were
spurious jurisdiction refusals because `theScore Bet` reached the gate instead of canonical `ESPN BET`. All three
rows remain in the history. The two spurious refusals are annotated in code and excluded only from rule-level
learning statistics. Regression coverage requires provider identity to remain `ESPN BET`; the browser alone renders
the current public name.

## 2026-10-07 · “Verified” must reject a caught error state

App 122 caught a lazy-view `ReferenceError` and replaced the Record page with a friendly error panel. The live
check looked only for console errors, overflow and clipping, so it reported the route as loaded even though the
requested content was absent. A caught exception is still a failed page. Browser verification now fails when the
rendered page contains `did not load`, and the lazy bundle is exercised against the real app exports across every
moved view before a release can be called verified.
