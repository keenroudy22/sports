# Operating lessons

### L-2026-10-07-3 · International morning plays had no delivery window
- What: a 9:30 AM NFL play targeted 9 AM while its 45-minute deadline was 8:45; planning silently skipped it.
- Why missed: schedule fixtures covered noon/night games but no international kickoff or admission-window check.
- Guard: `tests/test_post_windows.py::test_international_best_bet_and_ticket_have_the_eight_thirty_window` and `test_unreachable_window_is_refused_at_admission_and_named_in_the_plan` cover the shared target, admission, POTD and feed.
- State: guarded.

### L-2026-10-07-4 · Optional items and results competed for the free Buffer reserve
- What: ordinary scheduling could fill all ten places and did not protect cashed/Climb results.
- Why missed: the reserve test checked optional deferral but not essential creation order or a free reschedule place.
- Guard: `tests/test_post_windows.py::test_buffer_results_are_essential_and_tenth_slot_stays_free` and the ten-pending fixture protect results and the ninth-place ceiling.
- State: guarded.

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

### L-2026-10-07-2 · The real product queue exceeded its own reader limits
- What: P20 evidence and P29 action text exceeded the reader bounds; the approved October 7 twist added a forty-first item to a forty-item queue.
- Why missed: fixtures tested the validator but no test validated the checked-in queue itself.
- Guard: `tests/test_product_followthrough.py::test_current_checked_in_owner_queue_is_valid` checks the real queue; full details stay in linked review/implementation documents. The local item bound is now forty-eight.
- State: guarded.

### L-2026-10-03-1 · An em-dash prompt reached X through an unguarded path
- What: conversation:day:2026-10-03 posted "Props, sides or totals—what are you looking at?". buffer_post.plan inserts conversation prompts and fun teasers without x_post.x_style, and the Discord pull update (buffer_post.py:452) has no guard either.
- Why missed: the style guard runs only on plays and house posts.
- Guard: one send-path guard for every Buffer and Discord text. tests/test_buffer_post.py asserts that every CONVERSATION and FUN_TEASERS string, plus a rendered Climb teaser, passes x_style. State: open.

### L-2026-10-03-2 · The fallback rule pulled three plays while the local model was running
- What: the pre-post pulls of McKenzie over 179.5 ("showers and 71 degrees"), Mich/Minn over 43.5 (offensive linemen ruled out) and a Climb step ("upgraded from doubtful") all used hold_reason's wording, not the judge's.
- Why missed: judge() returns None on any LLMUnavailable (lock busy, 90 s timeout, malformed reply), and nothing logs which one happened.
- Guard: log the unavailable reason and count fallback decisions in status.json; the pre-post check alone waits up to 90 s for the lock; the AVAILABILITY_UPGRADE test has landed. A narrower fallback rule comes only after a 4-week shadow and the owner's yes. State: open.

### L-2026-10-06-1 · Today called a function core.js does not export
- What: Today's extras called C.routePath after the async load. It shipped in 3bac89df under a "20 routes, no console error" receipt and was fixed in app v119.
- Why missed: the error fires only after the data loads, unit tests never run that callback, and the browser audit was not run with a fresh cache on the final build.
- Guard: tests/ui-contract.test.js checks that every C.<name> referenced in site/app.js exists in Object.keys(require('../site/core.js')). State: open (only a routePath-specific test exists).

### L-2026-10-06-2 · A filename filter stripped '.' and the CFB defense panel silently disappeared
- What: /[^a-z0-9/_-]/gi turned teams/CFB-defense.json into CFB-defensejson. Fixed in 1e33010b.
- Why missed: QA looked for errors, not for whether the section was there.
- Guard: the ui-board filter test has landed. Still to add: tests/test_payload_paths.py (every *File path the build writes survives the loader's filter and exists on disk) and an expect map in tests/browser-audit.mjs (a CFB game page must show the defense panel, with the cache disabled). State: open.

### L-2026-10-06-3 · Felt cards needed three owner rounds to get their figures right
- What: the cards computed record, receipt-season and Climb-bank figures separately from the site (mixed vs straight record, season cutoff, legacy bank). Fixed with the shared record_scope.py (902fa605, 148cd375).
- Why missed: no test compared card figures with the site's numbers.
- Guard: tests/test_felt_cards.py asserts that each card figure equals record_scope and the site output at the same as-of time. render_felt_review writes a table next to each PNG that maps every number to its source field. State: open.

### L-2026-10-06-4 · The game page counted a Model signal on lines our board grades below break-even
- What: TB at DAL Matchup edges showed "3 of 3 signals" for Hurst over 21.5 (−1.3), Godwin over 27.5 (−1.2) and Irving over 13.5 (−0.4). Because signals = 1 + trend + defense, the model always counted, and modelReads carried chance, needs and edge as null. Baker Mayfield OUT appeared about 2,000 px lower on the page.
- Why missed: no test tied that view to the grades in lines.json.
- Guard: a node test pinned to this fixture: a Model signal requires a calibrated clear. State: open.

### L-2026-10-06-5 · A "why" bullet argued against its own bet
- What: Bills at Rams UNDER 54.5 led with Bills defensive injuries, which point toward more points. whyLines() promotes pick.reason unless the text literally contains "against this side".
- Why missed: support is filtered by phrase, not by the fact's direction.
- Guard: the build carries each fact's direction; on modelLean picks, a fact whose direction is not 'for' never goes into support. Fixture test. State: open.

### L-2026-10-06-6 · Cards in production lack the required 21+, and retired words are still public
- What: with FELT_FROM = None, the legacy renderers post "Entertainment only. Not advice." with no 21+. The research card footer reads "DATA + CONTEXT". "desk" is in the Climb check-in, "PLATES" is on the receipt card and "Ladder" is in the week receipt.
- Why missed: the Oct 6 rules were applied only to the felt templates, and no test scans rendered cards or captions for required or retired words.
- Guard: tests/test_voice.py fails on any card SVG without "21+" and on retired words in rendered captions. State: open.

### L-2026-10-06-7 · Cloudflare adds an analytics beacon that was never approved
- What: static.cloudflareinsights.com/beacon.min.js is appended to every HTML response at the edge, and the browser makes /cdn-cgi/rum requests. AGENTS.md lists analytics and Cloudflare as not approved.
- Why missed: it is injected outside the repo, so the publication guard cannot see it.
- Guard: none is possible in the repo. The owner turns it off in the Cloudflare dashboard, or approves it and discloses it. State: owner-needed.
