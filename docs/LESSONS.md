# Operating lessons

### L-2026-10-04-1 · Buffer queue capacity blocked published plays
- What: six free-queue refusals on October 3–4 included the KC–LV official total, a POTD relabel and rescheduling.
- Why missed: the code described fifty scheduled slots and tested only the twenty-post daily ceiling.
- Guard: `tests/test_buffer_post.py::test_free_queue_preserves_three_places_and_defers_at_ten` verifies the ten-slot queue and three-slot reserve.
- State: guarded.

### L-2026-10-07-1 · Shadow failures must preserve weekly learning
- What: silent snapshot generation and append preceded the live policy save.
- Why missed: happy-path tests did not simulate a failing private evidence writer.
- Guard: `tests/test_learn.py::test_shadow_failure_cannot_lose_live_weekly_policy` and `test_shadow_dedupe_keeps_post_pause_near_miss` verify save isolation and window-before-dedupe.
- State: guarded.

## 2026-10-07 · SVG text fitting must use the embedded font's real widths

Character-count estimates can understate Barlow Condensed capitals and let otherwise realistic selections cross a
card's safe margin. The felt-card browser test now measures long CFB names and short receptions/completions markets
with the embedded font before release. Straight spreads are not currently generated, but their longer single-token
school names need the durable version before that path returns: read the embedded TTF `cmap`/`hmtx` advances with
the standard library, include letter spacing, and assert every returned line fits instead of trusting a family ratio.

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
