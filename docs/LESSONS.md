# Closed operating lessons

## 2026-10-07 · Provider identity must not use a public display name

Three append-only learning rows were written during the C4 display-name regression with `-thescore-bet` IDs.
The Iowa–Washington row was a valid duplicate refusal. The Georgia–Alabama and Hawai'i–Arizona State rows were
spurious jurisdiction refusals because `theScore Bet` reached the gate instead of canonical `ESPN BET`. All three
rows remain in the history. The two spurious refusals are annotated in code and excluded only from rule-level
learning statistics. Regression coverage requires provider identity to remain `ESPN BET`; the browser alone renders
the current public name.
