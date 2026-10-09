# October 5 product implementation tracker

## 2026-10-09 — KOOKN-PLAN adoption

The owner adopted [`KOOKN-PLAN.md`](KOOKN-PLAN.md) as the single current authority for play selection, posts,
graphics, the site, engagement and learning. It supersedes conflicting dated operating decisions; the immutable
record, free-stack rules and locked deployment recipe remain unchanged. Work is tracked as `KP-T0` through
`KP-T27`, `KP-T-SITE` and `KP-T-ART` in `product-status.json`, and ships in the plan's three gated releases.

Release 1 starts from the unchanged public headline: **35–36 (1 void), −5.11u at posted prices (21–25 with a
recorded price), 5 pending**. The stored Oct. 1–9 acceptance replay is produced by
`scripts/replay_selection.py`; it makes no network calls and does not write the record.

### Release 1 replay acceptance (Oct. 1–9, stored inputs only)

The deterministic replay found a qualifying lane on every football game day. None of these replay rows changes
the public record.

| Day | Replayed plays |
|---|---|
| Oct. 1 | Jimmy Calloway under 39.5 receiving yards (Best bet; pending in stored replay data) |
| Oct. 2 | Aidan Chiles over 12.5 rushing yards (Best bet; win); Jeffrey Overton Jr. under 85.5 rushing yards (Best bet; win) |
| Oct. 3 | Antonio Martin over 51.5 rushing yards; Messiah Burch under 48.5 rushing yards; Sedrick Alexander over 27.5 rushing yards; Marquis Johnson over 30.5 receiving yards; Caden High over 46.5 receiving yards (Best bets; 1–4) |
| Oct. 4 | Tommy Tremble over 13.5 receiving yards; Ryan Flournoy over 33.5 receiving yards; Justice Hill under 10.5 receiving yards; Matthew Stafford over 250.5 passing yards; Puka Nacua over 73.5 receiving yards (Best bets; 3–2) |
| Oct. 5 | Jahan Dotson over 19.5 receiving yards (Best bet; win) |
| Oct. 6 | Gavin Griffin under 9.5 receiving yards (Gut call; loss) |
| Oct. 7 | JJ Kohl over 10.5 rushing yards; James Jones under 84.5 rushing yards (Best bets; 0–2) |
| Oct. 8 | David Amador II over 41.5 receiving yards; Mudia Reuben over 30.5 receiving yards (Best bets; 1–1); Jake Ferguson under 3.5 catches (TNF Gut call; win) |
| Oct. 9 | Washington State at Utah State over 44.5 (Gut call; pending) |

Replay command: `python3 scripts/replay_selection.py --from 2026-10-01 --to 2026-10-09`. Acceptance also verifies
that role/QB holds do not reach a play and narrow one-book exceptions use fresh quotes with a gap no larger than 15.
Best bets before/after Release 1: **35–36 (1 void), −5.11u at posted prices (21–25 priced), 5 pending**.

Owner approved implementation of the October 5 product plan after reviewing it. This tracker separates work that
can ship now from observation, counterpart permission and later owner decisions. It is not proof a staged change
is deployed. The existing append-only reports and public record remain unchanged by presentation work.

## Effective scope

Today / Research / Games / Record / More; compact published selections first; shared correct chart geometry and
quote states; coherent research filters; private operating visibility; bounded captions and tested creative variants.
Current sources, free budgets and approved release categories only. Full plan: owner's local
`kookn-product-plan-2026-10-05.html` (dated audit baseline, not a deployment receipt).

## October 6 redesign handoff

The owner approved a casino-felt redesign and staged release. The live navigation is Today / Research / Games /
Record / More. C0 recorded the rules and queue, C1 published a noindex preview at `/sports/next/`, C2 added parity
tests, and the owner approved C3 on October 6. C3 replaces only the presentation shell, retires the preview and
reuses the current public data and unchanged `core.js` record math; it changes no pick, result, feed, post, card or
pipeline rule.

Remaining owner-choice defaults stay explicit: no public CLV or ROI headline, no R5 trend default, no new post
types, slots or frequency, no Playbook change, no browser automation on X and no paid service. Felt-card cutover
still requires approved renders and the quiet-window gate. R0–R7 may run only as silent logged shadows with no
public-output effect. The local redesign audit stays excluded from the public repository pending an owner decision
about its X analytics figures; the remaining redesign source and strategy files are retained as implementation
evidence under `redesign/`.

The finite follow-through queue is `docs/product-status.json`. Read it before continuing work. Each item has an
owner, next action, completion condition and dated evidence. The existing weekly review carries its open items
without relying on the local model to remember them. A model switch does not reset this queue. Its statuses are
dated assertions, not a live deployment/health monitor; missing, invalid and stale input must remain visible.

| Workstream | Acceptance evidence | State at implementation handoff |
|---|---|---|
| Chart correctness and quote clarity | Shared domain/baseline; below/equal/above, negative/zero/unknown fixtures; samples and quote ages match stored rows. | Implemented with regression fixtures; release verification below. No model or historical-grade change. |
| Navigation and Today | Five destinations; Scores alias opens Games Live; other aliases survive; sport context, back navigation, opening phone screen and no clipping. | Implemented. Local phone checks confirm the published play appears first and sport selection preserves its section. |
| Research workspace | Player/team/market search; main-line default; Season/L5/L10 samples; persistent filters; Saved distinct from ticket-building. | Initial filtering plus shared public context and cross-workspace search shipped; P02 records the closeout release. Unsupported sports remain explicit. |
| Captions and graphic variation | Overlong text has a factual bounded fallback; readable long-name cards; green/red reflect the selected side, with non-color cues. | Implemented within current categories/caps. Cached end-zone caption now fits 239 characters with all four exact preview rows. Aggregate outcome strips do not invent game order. |
| Private operations | Distinguish qualified/no-play/held/queued/delivered; identify overdue/failed output; unchanged healthy polls remain quiet. | Snapshot checks shipped in b4770d04; prospective daily reliability shipped in 164df194; distinct delivery cohorts shipped in ffc68f3b. Existing jobs and local-only evidence; no new feed/model calls. Private weekly Discord is prepared but disabled. |
| Deployment safety | Both Python and Node exit statuses stop promotion; lock held during sync/tests/promotion; isolated offline rehearsal exercises real `_run`. | Shipped in b4770d04 after both suites and the stored-input rehearsal passed. Every follow-up revision must repeat its relevant verification and the deployment gates. |
| Rights and membership preparation | Source-rights register, measurable gates, processor and entitlement design documented; no billing enabled. | Documents prepared; external permission and elapsed-time gates remain pending. |

## Initial verification of isolated rehearsal

`/opt/homebrew/bin/python3 scripts/rehearse.py --slot 1145` exercised the real dry-run `_run` against copied current
stored inputs on October 5. It returned exit 0 / outcome `ok`, screened 20 candidates, published nothing, and kept
drafts/status/build outputs in its own temporary workspace. Two attempted scoreboard reads were blocked offline;
there were no child processes, outside writes or production-private reads. Four focused helper tests passed.

This result is a stored-input smoke test, not evidence of fresh prices, injury confirmation, real message delivery or
the final integrated release. The helper retains `rehearsal.log`, `result.json` and private pending/draft artifacts.
Report the final integrated test counts, deployed revision, publication result and live QA separately at handoff.

## Release evidence to fill after integration

- Both full test suites and exact exit statuses.
- Stored build and isolated rehearsal result from the final integrated revision.
- Phone widths 320/375/390, tablet 768, desktop 1280/1440, enlarged text and keyboard/focus checks.
- Current/empty/settled/withdrawn play states; stale/missing quotes; short histories and unsupported sport states.
- Route aliases, sport switching, filters, back/forward, Saved and ticket-building interactions.
- Production revision, successful publish run, actual live-route verification and rollback reference.
- Any public/private delivery claimed: confirmed delivery ID, not merely a queued/scheduled timestamp.

## Integrated pre-release evidence · October 5

- Python suite: 828 tests run, 2 intentionally skipped, no failures. Frontend suite: all 80 tests passed after the visual fixes.
- Real stored-input rehearsal at the current 08:30 window: exit 0, outcome `ok`; two denied scoreboard requests,
  no subprocesses, no outside writes and no production-private reads. Nothing published.
- Browser interaction checks passed for Charts player search/sample, back-to-filtered charts, Trends rate/history/search,
  Record Climb category, old Scores route under Games, and MLB/NHL Today sport-context preservation.
- Responsive checks: no page overflow at 320, 375, 390, 768, 1280 and 1440 pixels in the inspected core views.
  Enter expands the official-play row with a visible focus outline. Long player histories scroll within their own
  chart; snap percentages show as percentages. Browser-zoom enlargement was not established by the available control,
  so a real enlarged-text user check remains on the volunteer usability checklist.
- A live-progress state file was not present at the private destination: zero recorded pilot attempts. This is not
  a completed pilot; X live updates remain off. Private weekly Discord has no configured verified destination.
- The verified deployed result is recorded below; the remaining enlarged-text volunteer check is not implied complete.

## Shipped product refresh · October 5

- Production revision: `b4770d0405f61989dd2819b5b3fd8a09cff483ed`.
- [Hosted publish run 37322030013](https://github.com/keenroudy22/sports/actions/runs/37322030013) completed
  successfully at `2026-10-05T14:09:41Z`.
- Live assets verified: app 106, core 63 and CSS 70. Five main destinations are present. At 375 px, Today expands,
  Charts search finds Drake London's actual three-game history, and sample/quote-age labels work. The old Scores
  route highlights Games. At 1440 px, Today had no horizontal page overflow or reported browser errors.
- Release suites: 828 Python tests run, two intentionally skipped, no failures; all 80 frontend tests passed.
  Local owner receipt: `kookn-release-2026-10-05.html`. This is evidence for that revision only, not later staged work.

## Follow-up: prospective reliability measurement

The shipped snapshot/change alerts did not retain a freshness denominator. `scripts/desk_health.py` now adds local
daily evidence on the **existing** half-hour precheck, without a new job, source/model request or notification rule.
This follow-up shipped in 164df194; its production receipt is recorded below.

- Private journal: `~/.config/keenroudy/desk-health-reliability.json`, mode 0600, beside the existing private
  health HTML/JSON. It is never included in the site, a public payload, a post or an analytics provider.
- One immutable first observation per actual UTC half-hour window, grouped by Eastern calendar date; retain the
  latest 56 days. Repeated checks cannot inflate the denominator or overwrite an earlier sample. Samples older
  than five minutes, future samples, incomplete sources and non-live/replayed summaries are not recorded.
- The eligible denominator is **required source checks actually observed**. Fresh / stale / failed / unknown /
  invalid-time counts are separate. Required unknowns remain in the denominator; off-slate optional sources do not.
  Preserve the existing four-hour quote and six-hour schedule/context/snapshot thresholds in the journal.
- The private page and weekly summary show observed half-hours and unobserved gaps since the retained start.
  Missing windows have unknown source eligibility: they are neither invented checks nor successes. The current
  half-hour is still pending until observed or finished. This is sampling, not feed latency or service uptime.
- Desk failures, late completion and unknown status are separate. An explicit completed run with zero newly
  published plays is `no-new-play`, not failure; withheld counts stay separate. Delivery counts remain each day's
  latest **last-48-hour snapshot**, never summed into fake delivery totals or a success rate. A missing delivery
  log records unknown counts, not zero successful/failed events.
- Corrupt/incompatible history is preserved and shown unavailable, never silently replaced with a fresh success
  streak. The first recording date is prospective; no past days are backfilled. No retention/user/payment facts
  are generated by this measurement.
- Focused verification: all 19 desk-health tests passed, including denominator/unknown handling, optional sources,
  duplicate windows, missing coverage, replay rejection, privacy, bounded retention and unchanged alerts/public files.
  Run `/opt/homebrew/bin/python3 -m unittest discover -s tests -p test_desk_health.py` in the development worktree.

The four-week gate remains **not assessed**. This supplies the sampled-freshness denominator only. Critical display
incidents, settled-play reconciliation, delivery-cohort review, coverage gaps and four genuine observed weeks
still require review; an observed 95% fraction alone cannot approve subscriptions or a model.

## Follow-up: research usability and truthful explanations

- Charts, Trends and Lines have workspace-specific Reset filters. Saved items, personal tickets and sport context
  are preserved. Invalid remembered choices are discarded, chart dates persist, and a vanished date returns to
  Next slate with a visible note. League changes clear the league-specific opponent filter.
- Chart samples apply venue/opponent filters before Last 5/Last 10. Counts reflect actual matching histories;
  missing data does not become a zero and an empty filter cannot show an unrelated player's history.
- Future model-lean explanations no longer claim that nothing sourced argues against the pick. Verified opposing
  statistical claims remain in the risk text with source links; optional language polishing cannot remove them.
  This is a copy correction, not a new hold, changed threshold, new POTD policy or rewritten historical report.
- The hosted upload now runs a reviewed-public-file boundary check. It rejects unknown file families, linked files,
  known private artifacts and selected credential signatures/fields. See PUBLIC-PAYLOADS.md for scope and limits.
- Integrated verification before promotion: 848 Python tests run, two skipped, no failures; 85 frontend tests passed.
  Stored-input rehearsal at slot 1000 returned exit 0 / outcome `ok`, with no outside writes or private reads.
  Browser checks confirmed Chart date persistence, all three resets, zero-result chart filtering, and no page
  overflow in inspected research views at 320/375/1440 px. No browser errors were reported in that session.
  These test results belong to the release receipt below, not subsequent staged changes.

## Shipped reliability and research follow-up · October 5

- Production revision: `164df194e1d62d2a398a8e6b034d7a86d2d5d981`.
- [Hosted publish run 37325485646](https://github.com/keenroudy22/sports/actions/runs/37325485646) completed
  successfully at `2026-10-05T14:35:15Z`; the live release receipt was verified.
- Integrated release evidence above: 848 Python tests run, two skipped, no failures; 85 frontend tests passed;
  stored-input rehearsal exited 0 with no outside writes/private reads.
- A read-only check found the private mode-0600 reliability journal had begun at `2026-10-05T14:33:41Z`.
  Its first sample contained two required checks, both fresh, no observed gap and a no-new-play desk outcome.
  This proves collection started, not four-week reliability or readiness to charge.

## Shipped follow-up: distinct delivery-outcome cohorts

`scripts/desk_health.py` adds two private views of the **current stored post log**: distinct publication IDs whose
saved `dueAt` is between the observation time minus 7 or 28 days and that time, inclusive. Each channel counts its
own event. These are recomputed evidence cohorts, never totals added from repeated health snapshots. The seven-day
cohort is contained in the 28-day cohort, so the two must not be added together.

- The denominator is known eligible due posts per channel. Confirmed, recorded failure, overdue/unconfirmed,
  pending and unclear outcome remain separate; unclear eligible outcomes remain inside the denominator.
- Deliberately withheld/cancelled posts are counted separately and excluded. A confirmed channel delivery remains
  confirmed even if the post was subsequently pulled; for example, Discord may have delivered before X was held.
  A no-new-play run creates no delivery event. Future/older scheduled posts are outside that window.
- Missing channel intent, invalid/missing stable IDs or scheduled times, and conflicting duplicate outcomes are
  explicitly unknown. Missing/corrupt log input is unknown, not an empty successful period. Duplicate rows with
  conflicting due times cannot be placed into a window; no made-up date is substituted from a send/creation time.
- The report shows confirmed/eligible counts, not an on-time percentage. Stored X times may reflect reconciliation;
  legacy Discord times are job-start times. Pending mirrors can legitimately await X confirmation. Unconfirmed is
  not proof of failure, and a current grace-period check is not measured historical latency.
- Coverage is limited to the available log, not all historical deliveries. No percentage is assigned to zero
  eligible events. Nothing here proves retention, betting performance, a complete four-week gate or paid readiness.
- Output is allowlisted counts in the existing private health JSON/HTML and weekly markdown. No post IDs, bodies,
  provider IDs, response details or credentials are copied. No new file, job, request, alert rule, social category,
  public payload, ledger correction or selection policy is added.
- Focused verification: 28 desk-health tests and eight weekly-review tests passed; `git diff --check` passed.
  Fixtures cover deduplication, both exact window boundaries, post-time versus due-time selection, contradictory
  duplicates, channel-specific cancellation, unknown eligibility, future confirmation times, privacy and no calls.
  This item shipped in ffc68f3b; integrated release receipt follows below.

### October 5 POTD audit and approved follow-up

Falcons at Saints under 48 at -108 was published September 30 with a 43.43 total projection (ATL 20.3 / NO 23.1).
The raw 62.48% under chance was reduced to 55.24%; its stored conservative edge cleared the existing 3pp NFL-total
caution threshold. The 17-29 scoreboard is all final pregame total directions against the close, not the posted
selection record. Neither fact proves the selected play will win.

The October 5 POTD designation ranked already-published open singles by saved edge, not the entire current market.
Original research logged opposing statistical evidence, despite an overly broad all-clear explanation. The future
copy fix above preserves such counterpoints. The owner approved the recommended fresh comparison later on October 5.
The implementation requires every first designation to pair each open official single with a matching fresh board
market from that run and rank the official choices at the current calibrated edge. A market that was not admitted
cannot become POTD or create another play, and an old official play with no fresh match receives no POTD label yet.
The label stays fixed after designation unless the existing pre-post pull rule applies. The verified production
receipt is recorded below and in P12 of the finite queue.

### Verified fresh-comparison and private-delivery receipt

- Production revision: `3848fdd1d2df0a2f24b01931559bb27fb45eae37`.
- [Publish run 37393941544](https://github.com/keenroudy22/sports/actions/runs/37393941544) succeeded on
  `2026-10-06`. All workflow refresh, record-boundary and deploy steps passed.
- Verification passed with 873 Python tests (two intentionally skipped), 128 frontend tests, the stored-site build,
  publication guard and isolated slot-2000 rehearsal. The live 375 px Today audit reported zero layout issues and
  zero browser errors.
- The owner-only `#weekly-growth-report` destination visibly states that only the owner can see it. A dedicated
  `Kook'n Private Desk` webhook delivered the verification message there at 8:22 PM ET on October 5. The guarded
  delivery has no public fallback.

## Follow-up: current-season player history and readable thresholds

- Player detail opens on the provider's current season, not the latest season in an individual player's history.
  Season and All games / Last 5 / Last 10 / Last 20 controls sit above the summaries. Older years and All seasons
  require an explicit selection. The selected rows drive the chart, averages, hit counts, splits and game log.
- Landry Lyddy's regression uses four 2026 passing observations (46, 25, 194, 243), not all 13 games from 2023–2026.
  Current average is 127.0; an explicitly selected All seasons has 13 games and an average of 79.6. No prior-year
  appearances fill an empty current season, and unknown observations do not become zero.
- The shared chart has a readable side/line legend and a threshold number in a dedicated right gutter. Bars,
  value labels and opponent labels are centered together. The threshold shares the bars' numerical scale; 206.5
  sits between 194 and 243. Value-label backgrounds prevent the dashed line cutting through the text.
- Prop research modals use their event's season and pre-kickoff observations. Present-day aggregate defense
  rankings are not shown as historical pregame evidence; per-game defense history retains season/date cutoffs.
- Pre-release verification: 857 Python tests run, two skipped, no failures; all 97 frontend tests passed. The
  stored build and public-file guard passed. Isolated slot-1000 rehearsal returned exit 0 / outcome ok, two blocked
  network reads, no subprocesses, outside writes or private-state reads. No posts or wagers were made.
- Local browser checks: 320/375/1440 px, current/all/last-five history, positive/negative/missing observations,
  aligned threshold and value labels, long-history internal scrolling, and a compact research-grid chart.
  Inspected views had no horizontal page overflow. Verified production receipt follows below.

## Shipped player-history and delivery-cohort follow-up · October 5

- Production revision: `ffc68f3b0c8f368842ef24860d264828d81dcb2e`.
- [Hosted publish run 37328565406](https://github.com/keenroudy22/sports/actions/runs/37328565406) completed
  successfully at `2026-10-05T14:59:38Z`. Live app 108, core 65 and CSS 72 were verified.
- At 375 px, Landry's current/all/current controls showed four versus 13 actual games; no page overflow or browser
  errors were observed. Release verification: 857 Python tests, two skipped; 97 frontend tests passed; stored
  build, publication guard and isolated slot-1000 rehearsal passed with zero outside writes/private reads.
- Owner receipt: `kookn-player-charts-2026-10-05.html`; image evidence:
  `implementation-evidence-2026-10-05/live-player-season-mobile.png` in the owner's Kook'n workspace.

## Current operating-policy summary · October 5

This table summarizes current rules; **AGENTS.md remains authoritative**. It does not approve a new release,
increase caps or claim a configured integration is working. Existing append-only records remain unchanged.

| Feature | Current state and scope | Limits / release condition | Evidence / authority |
|---|---|---|---|
| Website | Free Today / Research / Games / Record / More; sport-specific Today; legacy routes preserved. | Posted plays first; research/model records clearly separate. No subscription or hidden premium gate. | Release receipts above; AGENTS product approval. |
| Scores, stats and odds | Current supported sources on existing refresh schedules; visible capture ages. | Not FanDuel-speed odds. No added paid feed, scraping or metered-budget increase. | AGENTS free stack; existing capture/build jobs. |
| Official plays and Climb | Scheduled evaluation windows, not promised picks. One real Climb rung at a time; may advance after settlement on a later qualified scan. | Preserve price, availability, overlap, calibration and record gates; no forced quota. | AGENTS; existing run/ladder jobs. |
| Delivery | X through Buffer; official Discord leads X about 10–15 minutes, other types follow confirmed X. | Playbook tag on new X plays only; no automatic replies/likes/follows. A queue entry is not a delivery receipt. | AGENTS and stored channel receipts. |
| Research / graphics | Tested original variants within approved categories; truthful green/red/gray with non-color cues. | Public trend slot: fresh main lines, at least five games. Alternate/milestone category needs separate approval. | AGENTS creative/category rules; regression fixtures. |
| Local models | Evidence judgment and bounded homepage/weekly evidence selection; deterministic live prose by default. | No autonomous website deployment; optional small-model polish stays off unless explicitly enabled. | AGENTS routing; existing local_brief and review jobs. |
| Live-progress posts | Bounded Discord pilot only, actual attempts reviewed after three. | Existing two/day, 45-minute spacing, one/ticket and freshness/recheck gates; X remains off. | AGENTS live-progress approval; actual pilot log, not simulated attempts. |
| Arb Radar | Website calculator/research plus qualified private Discord alerts under separate arb rules. | Exact fresh prices; never expose private candidates as public live arb. | docs/ARB-RADAR.md; AGENTS. |
| New sports and futures | Supported website research, prospective trials and paper tracking. | No official new-sport release without forward evidence and separate approval. | Existing supported stores; P11. |
| Private review / follow-through | Existing Monday 9:30 AM review; local/phone delivery; deterministic queue integration shipped in 4660ba13. | Dedicated owner-only Discord delivery verified October 5; no public fallback or new job. | scripts/review.py; P03 and P05. |
| Paid access, tips, referrals | Readiness design only, not active. | Real reliability/retention, source rights, processor eligibility, terms and explicit launch approval first. | docs/SUBSCRIPTION-PLAN.md; P06–P09. |
| POTD comparison | Fresh comparison among official singles using current-board markets from the designation run is shipped. | Never creates an extra pick, bypasses the card cap or promotes an unadmitted market. | Dated POTD audit and verified receipt above; P12; AGENTS current rule. |

## Shipped closeout verification · October 5

The October 5 closeout found real missing shared-link/search behavior and stale release labels; it did not
declare the plan complete from the earlier summary. P02–P04 are now verified in the closeout release below.
Technical checks are not a substitute for the volunteer/cohort gate.

- The weekly follow-through integration adds one bounded local status-file read to the existing review. The full
  queue is in its packet and a deterministic summary leads saved, phone and verified-private-Discord excerpts.
  Ten new fixtures cover success/fallback/cloud/packet-only, malformed/future/stale state and no extra calls or
  status writes. Eight existing review fixtures also pass. No real notification or model call was used to test it.
- Genuine Chrome 200% zoom was established through the test tab's browser controls (device-pixel ratio 2,
  532 CSS-pixel effective viewport). Today, Games, Charts, Prop lines, Record, Tools and Saved had no horizontal
  page overflow in the inspected states. Today's details open with Enter; the research dialog closes with Escape
  and returns focus to its opener. This replaces the earlier inability to establish zoom, not the human test.
- Final local integration checks passed: copied Charts links reopen the same search and sample; carries charts
  open Carries on the player, and Back/Forward retains chart Last 5 versus an explicitly changed player Last 10.
  Query matching follows Charts, Prop lines and Trends. Save and ticket toggles retain their own keyboard focus.
  At 320/375/1440 px the inspected player view has no page overflow. Long All-seasons charts scroll internally
  with ArrowRight (40 px observed). Copy exposes a selectable fallback, styled consistently with other inputs.
  No browser errors were reported in the verification session.
- Sharing is offered on the main Charts workspace, Lines, Trends and player detail; legacy Search/Defenses/Teams
  subtabs do not claim to share unsupported controls. Chart-to-player links retain stat and season/window, while
  venue/opponent/date filters remain in Charts and return with Back. Player detail labels its actual broader sample.
- Integrated suites: 867 Python tests, two intentionally skipped; 123 frontend tests passed. Stored build and
  publication guard passed. Isolated slot-1000 rehearsal exited 0 / outcome ok, with two blocked network reads,
  zero subprocesses, outside writes or production-private reads. No posts, extra model calls or wagers were made.

### Verified release receipt

- Production revision: `4660ba1387a78b0686c2e74670388f26a983656c`.
- [Publish run 37333009159](https://github.com/keenroudy22/sports/actions/runs/37333009159) succeeded at
  `2026-10-05T15:30:45Z`. Live assets app 109, core 66 and CSS 73 were confirmed.
- Live 375 px: a public Charts query for Bijan carries restored Carries / Last 5 and the exact player link opened
  the same stat/sample. Document and viewport widths both measured 375; no browser errors were observed.
- Owner receipt: `kookn-product-closeout-2026-10-05.html`; live image:
  `implementation-evidence-2026-10-05/live-closeout-player-mobile.png` in the owner's Kook'n workspace.
- The dated queue now has no ready implementation item. Remaining owner-needed, observing and gated items are
  listed explicitly, not declared complete. Its receipt-only update changes no runtime code or selection rule.

## Shipped player touchdown and prop-stat expansion · October 5

Player detail now includes the touchdown and usage stats people most commonly research, limited to fields the
recorded history actually contains. Any TD is the observed sum of rushing and receiving touchdowns; it remains
missing when neither component was recorded, so the page does not turn absent data into a zero.

- TE and WR pages add Any TD, receiving TD, inside-10 targets and the existing receiving, target, long-gain,
  red-zone and snap-share views. WR also retains rushing work where recorded.
- RB/FB pages add Any TD, rushing TD, receiving TD, inside-10 and inside-5 carries alongside rushing, receiving,
  target, long-gain, red-zone and snap-share views.
- QB pages add passing TDs, interceptions, carries, rushing TDs, scrambles, sacks and long rush alongside passing
  and rushing volume. A player's menu only shows stats present in that player's recorded history.
- Any TD is a history view, not an invented sportsbook quote, projection or official pick. No selection, grading,
  posting, API-budget or public-record rule changed.
- Verification passed with 871 Python tests (two intentionally skipped), 125 frontend tests, the stored-site build,
  publication guard and isolated rehearsal. Live Juwan Johnson Any TD passed at 375 and 1440 px with no overflow,
  clipping or browser errors; the game log visibly includes Any TD.

### Verified release receipt

- Production revision: `0e40d6deec54ee135e4b593ffd3ba18acea5a90c`.
- [Publish run 37346323493](https://github.com/keenroudy22/sports/actions/runs/37346323493) succeeded at
  `2026-10-05T17:13:11Z`. Live assets app 110 and core 67 were confirmed.
- Live page: `https://keenroudy.com/sports/#player/NFL/3929645?stat=anyTD&season=current&sample=all`.

## October 6 season and postseason record lifecycle

- The owner approved a per-sport season archive. Record now defaults to each sport's active provider season and
  active stage, so an NFL 2026 record and NHL 2027 record can coexist without one hiding the other.
- The first official postseason play changes that sport's default to a fresh Playoffs slice. The first official
  play in the next provider season changes it to a fresh Regular season slice. Previous regular seasons and
  playoffs remain selectable; no published play, price, result or unit value is rewritten.
- Official straight plays, published fun parlays and Climb steps remain distinct. Personal tickets shown on X or
  Discord never enter the official record. The Climb keeps its own run lifecycle and is not restarted by a sport's
  season selector.
- NBA/CBB paper trials and MLB/NHL collection coverage now retain season/stage fields prospectively and show
  season history separately. Old collection rows that predate stage capture are labeled unclassified rather than
  guessed. Trial records remain separate from official plays; line/final collection is not called a prediction win.
- A deterministic hosted reconciliation now requires the public record to contain exactly the official IDs from
  the append-only research history, with matching publication/settlement fields and valid season metadata. Any
  extra personal/social ticket, missing official pick, stale grade, duplicate ID or missing season stops release.
- Pre-release verification passed 878 Python tests (two intentionally skipped), 129 frontend tests, the complete
  stored-site build, the public-file boundary and the new reconciliation across all 90 official entries. Local
  Record and Trial views passed 320/375/1440 px Chrome checks with no page overflow, clipped headings, load failures
  or browser errors. The isolated slot-1000 rehearsal finished `ok`, with two expected blocked network reads and no
  subprocesses, outside writes or private-state reads.

### Verified release receipt

- Production revision: `80b40b4303bb2ab9b3884242ef1d3d194173c7b1`.
- [Publish run 37475297200](https://github.com/keenroudy22/sports/actions/runs/37475297200) succeeded on
  October 6. The hosted reconciliation checked all 90 official entries before publication; live assets app 114,
  core 68 and CSS 76 were confirmed.
- Live Record and Trial views passed a 375 px Chrome check with no horizontal overflow, clipped headings, load
  failures or browser errors. The live Record exposes Season and Stage selectors, defaults NFL to 2026 regular
  season, keeps Playoffs and Full season selectable, and preserves sport-specific records. The NFL parlay slice
  visibly includes both official wins and reports 2–5; the all-sports official parlay record remains 2–9.

## October 6 CFB visibility, matchup edges and research-card release

- The blank-looking CFB Best Lines page was a hidden-state problem, not a missing-data problem. Switching sports
  now clears player/team searches that do not transfer across leagues, while preserving useful research controls.
  Best Lines also shows the current slate coverage before any filter: matchups, qualifying best lines, priced
  player props and game lines. An active search is called out and can be cleared in one tap.
- Game pages now put a compact Matchup edges section beneath strict favorites. A ranked edge must have a current
  priced player line and at least two visible signals across the stored projection, exact-line season history and
  opponent defense by position/stat. Opposing defense evidence stays visible as `Defense disagrees`; it is never
  hidden to make a line look stronger. These rows remain research and never create an official play.
- The existing research-post category now renders as a 1200×675 X card instead of a tall card with empty space.
  A single line leads with the play and price, includes an exact hit/miss strip, and uses one hero portrait rather
  than repeating the same image. The owner-supplied Landry Lyddy action-photo cutout is a visual prototype only;
  unattended action-photo use still requires an approved/licensed or explicitly owner-supplied asset source under
  P08. The safe current portrait remains the automated fallback.
- Verification passed 879 Python tests (two intentionally skipped), 129 frontend tests, the complete stored-site
  build, public-file boundary, and an isolated slot-1000 rehearsal. Local 375/1440 px checks covered CFB Best Lines
  and the USM–Troy game page after rebasing onto the latest captured data, with no overflow, missing required
  sections or browser errors.

### Verified release receipt

- Production revision: `a7d9038138e5e9f9808c27a0e9888d0bffd0e138`.
- [Publish run 37482789725](https://github.com/keenroudy22/sports/actions/runs/37482789725) succeeded on
  October 6 after the hosted record reconciliation and public artifact boundary passed. Live assets app 115,
  core 68 and CSS 77 were confirmed.
- Live 375 px Chrome checks passed on CFB Best Lines and `#game/CFB-401871090`: page width equaled viewport width,
  the slate totals and Matchup edges were present, and the browser reported no script or console errors.

## October 6 defense-supported trends and CFB game-script release

- Game-page research now pairs each qualifying exact line with the opponent's allowed production and defensive
  rank for the matching position/stat. Supporting and disagreeing defense evidence remains visible instead of
  being hidden to make a trend look stronger.
- A CFB player on a team projected to lose by at least 14 points receives a visible game-script caution and ranks
  below otherwise comparable research rows. The caution is context only: it does not change gates, projections,
  official-play selection, records or suggested stakes.
- The existing Matchup Trend social candidate now requires a public, priced main line observed within four hours,
  at least five exact-line games, an 80% or better hit rate and opponent-defense support for the selected side.
  It keeps the existing research slot and daily cap, shows no Playbook tag and never forces a post. CFB mismatch
  candidates remain eligible only as visibly cautioned, lower-ranked research.
- Verification passed 880 Python tests (two intentionally skipped), 130 frontend tests, the complete stored-site
  build, public-file boundary and an isolated slot-1145 rehearsal. The actual current Landry Lyddy research card
  rendered at 1200×675 with his exact-line history and Troy's matching QB passing-yards defense context.

### Verified release receipt

- Production revision: `0425f07e113641c9ab244cba0fb065f057050dfe`.
- [Publish run 37487457842](https://github.com/keenroudy22/sports/actions/runs/37487457842) succeeded on October 6
  after hosted record reconciliation and the public artifact boundary passed. Live assets app 116 and CSS 77 were
  confirmed.
- The live 375 px check on `#game/CFB-401871090` reported page width 375, scroll width 375, no clipped or overflowing
  elements, no load failure and no browser errors. The page visibly showed exact-line history, opponent defense
  context and the research-only selection boundary. No new paid service or API call was introduced.

## October 6 C4 data and feed release candidate

- Public line payloads now carry build-time fair price, expected value, display-safe chance, 80% range, quote age,
  freshness and exact-line best price. Picks carry frozen fair price, quote age, record-at-publication and bounded
  structured reasons/cautions. Game totals are typed as totals. Unnamed books do not reach public line rows and the
  public display uses theScore Bet; internal capture and shopping logic retains its source name.
- `today.json` keeps open picks and 72 hours of results; `record.json` holds the complete official history. Trends
  are dated NFL/CFB priced and milestone shards with histories and player context stored once. The CFB defense table
  is separate from team metadata. The unchanged record auditor reads the full split record through its command-line
  input. Narrow guard entries and hosted payload budgets cover each new public family.
- The RSS title is now Kook'n. It rolls 30 days with original pick GUIDs and daily receipt GUIDs; Buffer still uses
  `postable()` directly, so the archival feed changes no X category, slot or frequency.
- Release-candidate gates: 891 Python tests (2 skipped), 130 frontend tests under both Node runtimes, 91 reconciled
  committed-snapshot picks (the 9:00 PM source store then advanced to 92 for the hosted refresh), 509 guarded public
  files, and an isolated slot-2100 rehearsal with zero outside writes/private reads. Browser QA covered 126 responsive
  pages across 320/375/390/430/768/1280/1440, 54 pages at 1.3x text, and 16
  deep-link pages at 375/1440; all had zero overflow, clipping, load failure or browser errors.

## External and elapsed-time gates

## October 6 C6 silent results and creative-learning candidate

- R0 measures each segment, game, side and athlete once only in its silent comparison. Live learning continues to
  use the unchanged raw historical rows until the owner separately approves R0. A future approved deduplication
  would first apply the learning window and then deduplicate inside that window, so an older pre-window row cannot
  erase recent evidence. The weekly report shows raw and distinct counts before any later decision.
- R1 through R7 are enabled only as silent evidence snapshots. They use stored candidates, prices, grades, trends
  and projections, write append-only `shadow-<season>.jsonl` rows, make zero metered requests and explicitly record
  zero public effects. NFL totals remain governed by the existing rule; the trends default and closing-line
  headline remain unchanged.
- Future learning rows retain their quote time so the stale-price shadow can measure real age. This adds evidence
  to the learning store, not a tracked public schema or record-count change.
- Every newly scheduled card post records `cardTheme` from the renderer's current production theme before the
  external post is created; text-only posts record `none`. Theme timestamps are always timezone-aware, so a
  date-only cutover cannot create an unlogged duplicate after Buffer accepts a post. Missing historical labels
  count as legacy. The Tuesday learning report and Monday owner review compare felt versus legacy only within the
  same post category and mark fewer than eight settled posts as a small sample. They never cut over a theme,
  change a post category or move selection rules automatically.

### C6 verified release receipt

- Production revision: `d5ab6ed6`; [publish run 37558807025](https://github.com/keenroudy22/sports/actions/runs/37558807025)
  succeeded on October 6. The live audit covered 36 route/width combinations at 375 and 1440 px with no overflow,
  clipping, load failure or repeatable console error.
- Release gates passed 899 Python tests (2 skipped), 130 frontend tests under both Node runtimes, the 92-pick
  archive audit, payload budget, public guard and isolated slot-2100 rehearsal. The first real 11:30 PM shadow
  write remains an observation gate; no result policy, public play, card or post changed.

### C6 corrective release receipt

- Production revision `b1b301f1` shipped in [publish run 37563572847](https://github.com/keenroudy22/sports/actions/runs/37563572847)
  on October 6. It restores the unchanged live learning denominators, confines R0 deduplication to the silent
  comparison, applies its time window before any future deduplication, and makes card-theme logging safe before an
  external post is created. R0-R7 still have zero public effects and make zero new metered requests.
- The same release carries the approved UX cleanup and CFB-defense filename fix. Gates passed 910 Python tests
  (2 skipped), 134 frontend tests and 23 prototype parity tests under both Node runtimes, the 92-pick record audit,
  payload budget, 506-file public guard and isolated slot-2100 rehearsal. Local and live checks covered 42
  route/width combinations at 375 and 1440 px with no overflow, clipping, load failure or console error. The live
  CFB-defense payload returned successfully. The 11:30 PM shadow write remains the next observation gate.

### C4 verified release receipt

- Production revision: `3bac89df`; [publish run 37555731984](https://github.com/keenroudy22/sports/actions/runs/37555731984)
  succeeded on October 6. The live site serves app 118, core 70 and CSS 78.
- The hosted build reconciled all 92 official picks. The split trends index, CFB defense file, complete record
  archive and 78-item rolling RSS feed were present. Live checks across 20 routes at 375 and 1440 px found no
  sideways scroll, load failure or console error.
- Tracked schemas, `record_audit.py` and integrity checks were not changed.

### C4 regression-repair receipt

- Production revision `e65695a1` shipped in [publish run 37571505718](https://github.com/keenroudy22/sports/actions/runs/37571505718)
  on October 7. The source/display boundary is restored: the live 520-line catalog contains no `theScore Bet`
  provider rows, retains 52 canonical `ESPN BET` rows for selection and jurisdiction checks, and exposes the
  public rename only through `displayBook`. The Georgia at Alabama and Hawai'i at Arizona State totals that the
  prior build rejected now both retain `ESPN BET` as their source book.
- The release also repairs split-file CFB defense loading for matchup research, refreshes Today data in an open
  tab, and restores the documented legacy routes, player/team chart search, MLB/NHL recent-results fold, Model
  tiles and no-script fallback. The live site serves app 121 and the split CFB defense payload returns 200.
- Gates passed 917 Python tests (2 skipped), 139 frontend tests and 23 prototype parity tests under both Node
  runtimes, the 92-pick record audit, payload budget, 504-file public guard and isolated slot-0645 rehearsal.
  Local and live audits each covered the repaired routes at 375 and 1440 px with no overflow, clipping, load
  failure or console error. No tracked schema, record, social-delivery or felt-cutover setting changed.

### Weekend payload-resilience receipt

- Revisions `81b598e1` and `88f9c065` shipped in [publish run 37576340750](https://github.com/keenroudy22/sports/actions/runs/37576340750)
  on October 7. The first attempt, run 37576121536, stopped safely in the publication-rule check before card
  rendering or deployment; the follow-up restored the intentional pre-build empty-line fallback while keeping
  candidate and parlay loading strict.
- `lines.json` is now a 138-byte manifest for complete NFL and CFB shards. The verified live build contains 520
  rows (259 NFL and 261 CFB), zero `displayBook` fields and canonical `ESPN BET` provider rows. The browser maps
  presentation names without changing the source book used by jurisdiction, pricing, run or parlay logic.
- Historical replay measured the October 3 4:00 PM ET catalog at 972,440 bytes across shards versus the former
  1,068,624-byte monolith, and October 4 12:48 PM ET at 873,875 versus 970,119 bytes. Each individual league shard
  stayed below 786,432 bytes. Oversized data is now a private health warning, while the reviewed initial shell
  remains the only hard payload gate; cards and deployment cannot be stalled by a large slate.
- Secondary routes load through `app-more.js`; the initial shell is 80,577 gzip bytes. The release passed 928
  Python tests (2 skipped), 141 frontend tests and 23 prototype tests under both Node runtimes, a 447-page build,
  the 92-pick record audit, public guard and isolated slot-2330 rehearsal. Live checks covered 38 route/viewport
  combinations at 375 and 1440 px with no overflow, load failure or console error. The live site serves app 122.
  Records, play selection, social delivery and the unset felt-card cutover did not change.

**Correction · 2026-10-07:** The preceding live-check claim was too broad. App 122 caught a missing lazy-bundle
helper and rendered its fallback error panel on `#record` and `#record/fun`; the audit saw no console error or
overflow and incorrectly counted those pages as loaded. App 123 exported the complete shared helper interface and
added a real-app integration test for every moved view. The browser audit now treats any visible `did not load`
state as a failure. This correction is append-only; the original release receipt remains above as the record of
what was claimed at the time.

### Rollback boundary after C4

- `8eda349533167f202fbcfa0a0bda4e6c390c58f1` is the pre-redesign reference, but it is no longer a safe
  front-end-only rollback. The older shell expects the former monolithic trends payload and inline CFB defense
  table. Any rollback that far must revert the front end together with the C4 builder and publication-guard
  changes, then rebuild and pass the normal record, payload, guard, rehearsal and locked-deploy gates. Never copy
  only the old site files onto the current split payloads.

## October 6 C5 felt-card review candidate

- The felt renderers cover straight player and game plays, fun tickets, open and settled Climb cards, receipts,
  research cards and projection sheets. They embed the checked-in OFL fonts and retain ESPN photos/logos, filenames,
  dimensions and the 8 MB delivery ceiling.
- Theme choice is by publication time. `FELT_FROM` remains unset, so every production render still uses the legacy
  template and already-posted attachments cannot change. The private preview override exists only for local review.
- Eight review PNGs are in the owner-facing `card-review-2026-10-06` folder. Local gates passed 894 Python tests
  (two skipped), 130 frontend tests, a 92-pick archive reconciliation, 509-file public guard and isolated slot-2100
  rehearsal with zero outside writes or private reads.
- The remaining gate is human approval of all category renders. After approval, cutover may occur only after a
  green 11:30 PM run and before the 8:45 AM menu. Without approval by 6:30 AM, legacy cards stay live.

### C5 second-round owner review

- The eight files were re-rendered in the same owner review folder after correcting the public facts and owner
  rules: the site's current-season straight record now drives play and receipt proof, receipt headlines no longer
  recount fun tickets or Climb steps, overflow is explicit, and result rows identify their category.
- Climb art retains the dollar checkpoints, completed/current/future states, $1,000 flag, restart amount and
  separate this-climb versus all-climbs bank. Research art is built from a real stored choice and proof point.
  Projection sheets now use the real slate date and a native phone-readable felt layout.
- Open-play stubs are neutral, longshots use the felt palette, game totals carry both team marks, four-letter badges
  fit, and empty bands are tighter. `FELT_FROM` is still unset; these are review candidates, not live card changes.
- During fresh-cache phone/desktop QA, the Today extras callback exposed a private `routePath` call. The release
  candidate now uses the exported route parser, has a regression test and serves app version 119.

### C5 third-round owner review

- The eight review files were rendered again after correcting the legacy Climb bank reconstruction, receipt season
  cutoff, receipt hierarchy, final-stat ordering, Climb flag position, fun-ticket timing, research hierarchy and
  projection-sheet labels. The projection sheet names each wager, keeps the line green, displays theScore Bet as
  SCORE and prevents badges from covering text. The true all-climbs bank is $42 and receipts use their due-time
  season record.
- Production revision `b1b301f1` includes the corrected inactive renderers, but `FELT_FROM` remains unset. Legacy
  cards therefore remain live and already-posted attachments are unchanged. Owner approval of all eight PNGs and
  the quiet-window cutover are still required.

### C5 fourth-round owner review

- The same eight review files were rendered again from the current stored data after the final factual and
  legibility pass. Receipts now label the headline as best bets and identify hidden fun-ticket and Climb misses in
  neutral ink. Research cards use real game-by-game values, red misses, the plain history window and the named
  defense stat. Play cards use a wider neutral open stub, one-decimal probability proof and an explicit percentage-
  point edge.
- Projection sheets keep every projected score, use plain public copy and only ring a price captured within four
  hours. A watched college spread with a model/market gap of at least seven points carries the required caution.
  The current review sheet correctly shows no rings because its stored prices are older than four hours; the fresh-
  quote and college-caution paths are covered by deterministic tests.
- `FELT_FROM` remains unset. These corrected renders are still owner-review candidates; legacy cards remain live,
  no existing attachment changes and no social category, cadence or selection rule changes.

### C5 fifth-round owner review candidate

- Weekly receipts now render their stored category records as neutral rows instead of manufacturing push badges.
  A daily receipt with only fun tickets or only a Climb uses `FUN TICKETS` or `80/20 CLIMB` as its hero label;
  `Ladder` remains an internal name. The imminent Sep 30–Oct 6 review image shows best bets 7–7, player props
  6–2, game lines 1–5, fun tickets 0–5 and the 80/20 Climb 1–2 from the existing receipt record.
- Settled Climb cards mark each leg from the immutable `actual` result. Projection-sheet tiles measure and shrink
  long text to remain inside their frames, keep projected scores chalk, spell out public book names, and show the
  college-gap caution at the compact 16-game height. The review sheet is rendered at the stored snapshot's newest
  observation time, so its numbered green rings verify real captured prices without changing or inventing one.
- The same eight owner-facing PNGs were refreshed in `card-review-2026-10-06`. Deterministic coverage now includes
  a weekly receipt, days with no best bets, per-leg Climb results and a fresh 16-game ring/caution fixture.
  `FELT_FROM` remains unset; legacy cards remain live until the owner approves every category.

### C5 sixth-round owner review candidate

- Climb wins now understand the stored `all 2 legs won` settlement, mark every winning leg, show the next stake,
  and restore a distinct completion state with the final bank, $1,000 goal and next $50 climb. Review fixtures cover
  a real winning rung plus completed and pushed states.
- Daily receipts keep hidden best-bet outcomes in the headline record, map voids to `VOID`, and place fun tickets
  and the 80/20 Climb below a visible tracked-apart divider. Weekly category rows keep that same separation.
- Best-bet chance labels fit their neutral stubs. Multi-row research cards fit the complete stored title, price,
  metric and detail instead of silently slicing them. The review set now includes real three-row matchup and season
  boards, a six-best-bet day, a historical void and a compact sheet fixture with the college-gap caution in its own
  measured lane.
- `FELT_FROM` remains unset. All changes in this round are inactive renderer and review-fixture changes; legacy
  cards stay live until the owner approves the complete set.

### C5 round-six follow-up review candidate

- Daily receipts now preserve every same-day 80/20 Climb rung instead of displaying only the first one. The review
  set also includes the real weekly receipt. A pushed or voided rung says the same step and stake ride again, while
  a void is labeled `VOID`; a loss still shows only the next $50 restart.
- Single-row research art keeps the complete wager wording, adds the stored CFB game-script caution and fits long
  defense context without slicing words. Season boards give the exact line its own full-width row at 32 pixels or
  larger. Projection-sheet geometry keeps numbered lines away from their rings and keeps cautions inside compact,
  11/12-game and 16-game tiles.
- The owner-facing review folder now contains 18 PNGs, including weekly receipt, real loss, push/void, single- and
  multi-row research, season-board and sheet-geometry cases. Verification passed 935 Python tests (2 skipped), 142
  frontend tests under both Node invocations, a 447-page build, the size budget, 92-pick record audit, 507-file
  publication guard and isolated slot-2330 rehearsal. `FELT_FROM` remains unset, so the legacy cards stay live.

### C5 round-seven review candidate

- Projection-sheet geometry is now bounded for every supported layout from one through eight rows. The expanded
  review set includes the real 13-game Sunday NFL slate; every total and numbered LIKE line stays above its tile's
  lower edge instead of being painted over by the next row.
- Three-row matchup research gives each exact wager a full-width row at 32 pixels or larger, replaces internal
  fraction shorthand with plain last-games proof, and reserves a separate red, labeled zone for the stored CFB
  game-script caution. The current stored review slate has no 14-point underdog, so that caution is covered by a
  production-shaped deterministic fixture rather than a fabricated owner-facing fact.
- Daily receipts and best-bet cards shrink and wrap complete wording instead of silently slicing long matchups,
  lines or final scores. The review folder now contains 19 PNGs. Verification passed 947 Python tests (2 skipped),
  143 frontend tests under both Node invocations, the clean-export gate, a 447-page build, the warning-only size
  budget, 92-pick record audit, 507-file publication guard and isolated slot-2330 rehearsal. `FELT_FROM` remains
  unset, so legacy cards stay live until the owner approves the full set.

### C5 round-eight review candidate

- Best-bet subject lines now use a conservative embedded-font width for uppercase Barlow Condensed plus letter
  spacing. The Oct 10 James Madison/Georgia Southern and Sacramento State/Bowling Green pairings, Oklahoma
  State/West Virginia and Christopher Brooks-Washington all finish inside the 1016-pixel content margin when
  measured by headless Chrome. A signed spread also stays attached to the final word of its team name.
- At the $1,000 checkpoint, `NOW` and `AGAIN` are right-aligned left of the goal pole instead of sharing its x
  coordinate. Deterministic coverage exercises an open rung plus win, push and void results in the $501-$999
  stretch.
- All 19 owner-facing PNGs were refreshed in `card-review-2026-10-06`. Verification passed 949 Python tests (2
  skipped), 143 frontend tests in the worktree and clean export, a 447-page build, warning-only size budget,
  92-pick record audit, 507-file publication guard and isolated slot-2330 rehearsal. `FELT_FROM` remains unset, so
  these are still review candidates and legacy cards remain live pending the owner's final approval.

### C5 round-nine review candidate

- A player portrait now reserves the upper-right headline lane instead of letting a long prop subject paint through
  the photo ring. The deterministic browser fixture uses the real Na'eem Abdul-Rahim Gladding name with a portrait
  and requires the first line to finish left of the ring.
- Prop selection sizing is back on the narrower measured ratio, so wording such as `OVER 249.5 PASS YDS` remains a
  single readable line. The browser geometry check now uses matching James Madison/Georgia Southern, Sacramento
  State/Bowling Green and Oklahoma State/West Virginia CFB fixtures, and measures every subject, selection, ticket
  and season strip instead of accidentally rebuilding each total as Bills/Rams.
- All 19 owner-facing PNGs were refreshed in `card-review-2026-10-06`. Verification passed 949 Python tests (2
  skipped), 143 frontend tests in the worktree and clean export, a 447-page build, warning-only size budget,
  92-pick record audit, 507-file publication guard and isolated slot-2330 rehearsal. `FELT_FROM` remains unset;
  legacy cards remain live until the owner approves the complete set.

### C5 round-ten review candidate

- Prop selections try a measured single-line treatment down to 108 pixels before accepting a two-line split, so
  common wording such as `UNDER 249.5 PASS YDS` stays intact without changing the fallback ratio used by other
  selections. When a genuinely long selection still needs two lines, the season strip now follows the ticket and
  retains at least 12 measured pixels of clearance.
- Single-row research cards reserve the portrait lane for long player names. Browser fixtures use real-size image
  data and the real Jaron-Keawe Sagapolutele, Kamaehu Kopa-Kaawalauole and Khijohnn Cummings-Coleman names to
  measure the subject, selection, ticket, season strip and portrait ring with the embedded production fonts.
- All 19 owner-facing PNGs were refreshed in `card-review-2026-10-06`. Verification passed 949 Python tests (2
  skipped), 143 frontend tests in both Node invocations and clean export, a 447-page build, warning-only size
  budget, 92-pick record audit, 507-file publication guard and isolated slot-2330 rehearsal with no outside writes
  or private reads. `FELT_FROM` remains unset; legacy cards remain live until the owner approves the complete set.

### C5 round-eleven review candidate

- The play-card one-line estimate now allows for Barlow Condensed's wider capitals before choosing a font size or
  wrap. Real-font Chrome coverage includes `UNDER 2.5 RECEPTIONS` and `OVER 22.5 COMPLETIONS` beneath two-line CFB
  player names and a real-size portrait; every measured subject, selection and season line finishes inside the
  1016-pixel content margin while common passing- and rushing-yard selections keep their compact treatment.
- The future straight-spread edge case is recorded in `docs/LESSONS.md`: before that currently inactive path can
  return, replace character ratios with embedded-TTF advance-width measurement and assert every returned line fits.
- All 19 owner-facing PNGs were refreshed in `card-review-2026-10-06`. Verification passed 949 Python tests (2
  skipped), 143 frontend tests in both Node invocations and clean export, a 447-page build, warning-only size budget,
  92-pick record audit, 507-file publication guard and isolated slot-2330 rehearsal with no outside writes or
  private reads. `FELT_FROM` remains unset; legacy cards remain live until the owner approves the complete set.

### C6 first live shadow receipt

- The October 6 11:30 PM desk run completed normally with no forced publication and wrote exactly eight private
  append-only observations, one for each R0–R7 proposal. Every row is marked silent and records zero public effects
  and zero metered requests.
- R0 observed 1,663 raw rows and 917 distinct rows without changing the live learning denominator. R5 explicitly
  recorded no main-line or trends-default change. The remaining gate is four prospective weeks of evidence followed
  by a separate owner decision for each proposal.

| Gate | What remains | Authority/state |
|---|---|---|
| Four-week reliability | Four consecutive observed weeks, measured eligible freshness denominator, delivery metrics and grading reconciliation. | Prospective local sampling implemented in the follow-up above; four-week evidence, incident review and reconciliation remain pending. Cannot backfill success or treat missing windows as healthy. |
| Volunteer usability/cohort | 8/10 usability target, 10–20 consenting users across four slates and five explicit priced-concept choices. | Recruit/consent and real feedback still needed. No synthetic user claimed as a human test. |
| Data/image rights | ESPN and portraits, upstream nflverse rights, SharpAPI appropriate tier/history/comparison scope, other register questions. | Written counterpart/legal review pending; no outreach or new license authorized here. |
| Processor and business terms | Accurate eligibility review, cancellation/refund/privacy/support and costed offer. | Pending external checks and separate launch approval. |
| Accounts and paid access | Optional free sync first; server-side premium authorization, tested billing lifecycle later. | Not active. Public JSON is not a paywall. |
| Creator referrals/tips | Clearly disclosed, processor-approved, costed pilot after retention. | No outreach, billing or tip jar activated. |
| Discord guide/private review | Dedicated owner-only destination and confirmed private delivery are verified. | Preserve no-public-fallback behavior; public guide mutation and any additional destination still need applicable owner confirmation. |
| Live-progress X | Review the bounded Discord pilot's actual attempts and meet the separate release checkpoint. | X remains off. No blanket automation expansion. |
| Alternate/milestone social sheets | Separate category, labeling and release approval. | Not activated. Existing social trend posts remain fresh main lines with at least five games. |
| New sports/futures | Collection, prospective trial, measured evidence and release approval for each sport/market. | Website research/trials only at their actual supported stage; no invented edge. |

## Constraints deliberately retained

### October 7 urgent delivery candidate and new owner decisions

**Verified urgent release:** `375617555dc38c386018d62d6bc69f69b60f4573` shipped in
[run 37630609392](https://github.com/keenroudy22/sports/actions/runs/37630609392) on October 7.
965 Python tests (two skipped), 143 frontend tests under both Node runtimes and clean export passed.
The current stored-input 0830 rehearsal returned ok with no outside writes/private reads; the 92-pick audit
and public guard passed. All eighteen live 375/1440 route checks passed. The chef PNG's live SHA-256 equals
the supplied asset and the Cloudflare disclosure is present. Sunday delivery is a future observation, not claimed
complete. The rejected push was recovered non-destructively under the lock with hosted captures preserved.

- P0 revision a7a6b7bb shipped in successful run 37624845039. It passed 959 Python tests (two skipped),
  143 frontend tests under both Node runtimes/clean export and eighteen live 375/1440 route checks. The ticket
  mark returned 200 and Saturday's complete 2,676 milestone rows were indexed in two smaller files.
- The owner subsequently approved the focused basketball/soccer roadmap, kitchen twist, posting playbook v3,
  app autopilot, supplied clay-chef Discord avatar and existing Cloudflare analytics with a disclosure. These
  decisions are recorded in AGENTS and retained source documents. They do not imply unbuilt phases are live.
- Urgent A-20261007-3/4 now use one shared international target: 9:30 AM NFL games post at 8:30 AM.
  New-play admission, ticket admission, POTD eligibility, Buffer planning and RSS eligibility share the window.
  Admission also refuses a third simultaneous international play when ten-minute spacing leaves two places.
  Missing windows are named/counted rather than silently discarded.
- Queue pressure admits plays, receipts and cashed/Climb results first; ordinary creates stop at nine pending,
  leaving the tenth place for relabels/reschedules. Future deferrals do not become missed targets early.
- The owner-supplied 512-pixel chef replaces the publisher avatar. The ticket server icon and kookn.jpg remain.
  The site adds one Cloudflare Web Analytics disclosure. Prior P1 work is preserved in the named Git stash while
  this urgent candidate is verified; the full P1, twist and playbook are still in the finite queue.
- The queue's pre-existing overlong P20/P29 text is summarized with full-source links, and its local item bound
  covers the newly approved work. A test now validates the actual checked-in queue.

### October 7 approved work order and P0 candidate

**Verified P0 release:** revision `a7a6b7bbd64b8deb943ef22c8a2dc412add27285` shipped in
[publish run 37624845039](https://github.com/keenroudy22/sports/actions/runs/37624845039), successful October 7.
All 959 Python tests (two skipped), 143 frontend tests under both Node runtimes and clean export passed.
The rebuilt 0830 rehearsal returned ok with zero outside writes/private reads, and all eighteen live route/width
checks at 375/1440 passed. The public ticket mark returns 200; Saturday's index references both complete shards
(1,467 + 1,209 rows). Felt cutover is scheduled on this chat for 11:45 PM ET under automation
`finish-approved-felt-card-cutover`, which verifies the green 11:30 run before changing the approved switch.

- Owner approved the complete CODEX-WORK-ORDER and Claude's delegated decisions, dated
  `owner-delegated to Claude, 2026-10-06`. The retained work order, benchmark, voice, local routing and
  multi-sport plan are in docs. P30–P40 track the implementation and genuine observation gates.
- Buffer's actual ten-slot free queue replaces the erroneous fifty-slot assumption. Optional items defer
  at seven pending; best bets and receipts retain three places. Health and Monday outputs lead with
  unscheduled-official counts. This prospective fix cannot deliver the already-missed KC–LV post retroactively.
- Before: each league allowed three game-line captures daily, four on its big day; Odds API props could spend
  twelve credits any day and the easy ticket could fetch additional alternate markets. After: football shares
  eight weekday/six weekend game-line credits; Odds API props are weekend-only through October, twelve/day;
  easy tickets use stored SharpAPI alternates. October 7–31 maximum is about 280 additional credits, close to
  the approved 276 target; absent slates and existing October 7 captures reduce actual use. November caps are
  seventy per league for game lines and one hundred for props (Thursday through Monday), easy tickets zero.
- UTC-month rollover ignores stale stored balances and reaches the existing free allowance probe. Stored
  pace warns above 450 projected credits. Private count-only SharpAPI/Buffer journals contain no keys or URLs.
- Discord uses the approved 512-pixel ticket mark. Legacy cards retain kookn.jpg. Felt approval is recorded;
  execution waits for the next green 11:30 PM run and before the following menu.
- C6 failures cannot prevent live weekly learning from saving, and shadow deduplication follows each segment's
  since window. Theme labels resolve before external posting and use artifact publication/settlement time;
  invalid labels fall back safely. Cutover strings require an explicit offset; day-only artifact dates use Eastern.
- Saturday's 1,913,566-byte milestone file splits into complete player/stat groups at one megabyte with all rows
  retained through the existing index. Built budget and public boundary checks pass without warnings.
- Candidate checks: 956 Python tests (two skipped), 143 frontend tests under both Node runtimes, clean export,
  92-pick reconciliation, 509-file public boundary, isolated 0830 rehearsal and eighteen fresh-cache local route/
  width checks at 375/1440 passed. Final added budget-path fixtures and release verification follow.

No forced plays, missing/stale price bypass, weakened calibration or availability checks, rewritten record,
straight/parlay player stacking, new API spend, public private-arb payloads, automatic X replies/likes/follows,
unreviewed new social categories, hidden tracking, account signup or payments. Evaluation windows do not become
publication quotas. Green/red visuals express actual selected-side support/outcome, not certainty.

AGENTS.md is the effective operating contract. SOURCE-RIGHTS.md and SUBSCRIPTION-PLAN.md explain unresolved
commercial conditions. Older audit release documents remain historical evidence, not a second conflicting policy.

## October 7 owner carry-forward · invite, free plans and Kitchen Ticket

The owner confirmed that Codex carries the queue after Claude signs off. The owner chose the Kitchen Ticket
direction B, with CHEF_CLIP and ORDER_UP, removed the helpline and season strip from card images, and specified
record-equivalent unit labels. New card art is P45 and requires Claude's review of real renders before TICKET_FROM.
The five site invite references change to the newly verified non-expiring `discord.gg/ZnjubjsBPM`; a daily
heartbeat check verifies the server and expiry (A-20261007-8, P44). Existing posted images remain untouched.
The owner confirmed free plans only, with no upgrades, trials, payment methods or purchased credits. Local
request stops and 80% alerts are part of P44. As of the last available October 7 provider check, the Odds API
reported 194/500; local reservations reach 196. Count-only Buffer and SharpAPI journals begin at their October 7
installation, so their counts are not whole-month provider totals. The Monday packet reports those limits and
explicitly marks services whose usage is not accessible.

## October 7 verified invite release and Kitchen Ticket review gate

P44 is live: revision `e71ad86b` passed hosted run `37650607744`. The live `app.js?v=125` check covered
12 routes at 375 and 1440 px with no overflow, console errors or caught `did not load` state. The public
invite resolves to the Kook'n guild (`1554298777169297449`) without an expiry. The tested free-plan stops,
80% alerts, invite heartbeat and Monday usage section remain active. Buffer and SharpAPI local counts are
partial-month observations, not claimed provider totals.

P45 is not public. The first review requested a HOT PLATE (POTD) label and no WHY line when the saved
evidence does not support the selected side; both are implemented and tested. A second private review set
at `/tmp/kookn-kitchen-ticket-review-2026-10-07/` contains real open best bets, the Oct 4 Chef's Special,
Oct 3 Climb step, a ledger-derived Climb map with future steps labeled as a typical-price plan, a settled
Cooked player prop, the Oct 3 Final with every straight result and record-equivalent units, and a labeled
no-headshot simulation of a real pick. No preview was posted or used to replace existing cards.
`TICKET_FROM` is unset pending Claude's review and the owner's approved cutover gate.

Claude's October 7 round-two review (`CARDS-V2-REVIEW-2.md`) approved the Kitchen Ticket preview set for
cutover. The two requested copy details—consistent final-stat/margin wording where it fits, and no doubled
space in a game title—were fixed in the private rerender. That approval does not itself activate
`TICKET_FROM`; the green 11:30 PM run and locked quiet-window release still govern.

## October 7 systems-check release receipts and next green batch

A-20261007-12 is verified live before the felt cutover: revision `448edec1` removed both season-record
zones from felt card images, with a test and forced-felt sample renders. Hosted run `37655741412` passed;
12 live Today/Games/Record/Charts/Tools checks at 375 and 1440 px had no overflow, console exception or
caught load-error state. `FELT_FROM` remains unset for the approved quiet-window switch.

A-20261007-13 is also live: revision `7213b199` excludes a specifically pulled fun-ticket leg's game
from replacements and requires time for another pre-post check. The October 4 replay and Buffer timing
tests passed. Hosted run `37657219324` passed; six live 375/1440 Today/Record/Games checks were clean.
This does not rewrite either October 4 ticket or its result.

The next batch addresses rule conflicts, the anchored precheck clock, lock-wait alert, capped free-plan
pace, owner-ticket community routing, requote mentions and the ten-second Today. It has passed local
tests/build/record/guard/rehearsal and local phone/desktop browser checks, but is **not shipped** until a
quiet-window locked deploy, hosted success and fresh live checks are recorded.

## October 7 footer override and TNF Early Look preparation — not live

The owner removed the website-footer helpline and its Responsible gaming link. The entertainment-only,
21+, posted-price grading, Eastern-time and Cloudflare disclosures remain. The More › Responsible gaming
page remains reachable under the owner's latest direct wording; paid referral posts need separate legal
review rather than an assumed informational-site exception. The static footer test passes, but no live
footer change is claimed before a successful locked release and live width checks.

The owner also approved a Wednesday 7 PM TNF Early Look within the existing research category, counted
against Thursday's research slot. A stored-data selector now requires two to four positive-value, calibrated,
fresh main lines at public books, after the role/price sanity holds. It adds no odds requests. Kitchen Ticket
list and spotlight previews use real October 7 stored TB–DAL prices and ESPN photos; those quotes are too old
for the 7 PM post and the previews are local-only in `work/tnf-early-review/`. The scheduler switch remains
off pending Claude's first-real-render review and a gated release before a later Wednesday. No TNF Early
Look was queued or published October 7.

## October 7 later owner correction — Responsible gaming page removal, not live

The owner's subsequent direct instruction supersedes the page-retention sentence above: remove the More ›
Responsible gaming page, its menu entry, and any Start here links, together with the footer helpline/link change.
Legacy `#responsible` should quietly open More. Preserve the free site's entertainment-only and 21+ footer
disclosure, posted-price grading, Eastern-time and Cloudflare lines, and the cards' `21+ · Entertainment only`.
Revisit the page and helplines in `PAID-TIER-PLAN`'s legal checklist before any paid launch. This is a prepared
change, not a claim that the live site has changed; P54 remains open until the normal release and live checks.

## October 7 plain-language and QB-change preparation — not live

The owner asked for site copy that explains the price's required win rate in words, with every threshold
calculated from the actual quote. Upset Watch, line summaries, profile ranges and explanations have local
copy changes and tests. These are queued with P54; no live release is claimed (P56).

The owner also identified starter-change artifacts beyond Kohl. A conservative local guard now compares
the forecast quarterback with the recent full-game starter and holds suspect QB and receiving-teammate
markets from ranking and official selection. Replays cover Damante/TK King, Daniels and Bucky Irving.
This guard does not repair the underlying forecast or Javonte Williams's older receiving rate. Current-team,
same-QB and partial-game weighting plus snapshot refresh remain a separate root-fix item (P57), pending
review of the tested projection patch. No stored forecast or public record was rewritten.

Local checks for this prepared batch: 1,018 Python tests passed (two skipped), 152 frontend tests passed,
the clean-export tests passed, build and payload budget passed, record audit found all 92 published picks,
publication guard inspected 501 public files with no issues, and the isolated 11:45 rehearsal returned `ok`
with no outside writes. Real Chrome checked Today, Record, More, best lines, Trends and Games at 375 and
1440 pixels: 12 views, no sideways scroll, caught load-error state or console exception. This is local
verification, not hosted or live completion.

## October 7 A-24 price and projection follow-through — prepared, not live

The pre-release guard now also checks a recent QB rotation and projected attempt share, including Adam
Damante's under and the NMSU receivers. A book's two sides at the exact line must imply a combined
0.99–1.15 chance; a one-sided line can remain research but cannot become an official straight play.
The same-line price from another book also holds a main player row when its no-cut chance differs by
at least 15 percentage points. The five anomalous Sep 26–27 DraftKings prices (+700 to +1500) are
replayed in tests and refused. None of this changes a published pick or its result.

In the 14 stored UTC dates Sep 24–Oct 7, counting each distinct straight candidate ID once per date,
the added exact-line two-sided check retains 1,603 of 1,741 player candidate/day attempts and 181 of
210 game candidate/day attempts (1,784 of 1,951 overall). Those are historical candidate attempts,
including rows already refused by other rules; they are not new win rates or a revised public record.
The post-build record audit still matches all 92 public pick IDs. The root projection changes and
Reasoned-edges log remain separately tracked as silent shadows (P57/P58), with no owner-approved
promotion or new public panel.

## October 7 Vegas, Today and direction integration — locally gated, not live

The owner-delegated Claude series was applied to dev after the A-24 safety commit: Vegas vs reality
(`f529fc40`), 10-second Today (`5230497e`), and bounded results-led direction (`45cc8263`).
The asset-version-only fourth patch was already superseded by the dev shell version; no lower version
was introduced. The conflict fix-up preserves the removed free-site helpline/Responsible page and
plain-language copy. It also removes the old duplicate Today hint, keeps one early hero request,
and prevents an off-the-card line from appearing as a best bet during first paint. The direction
rule is documented in `docs/DIRECTION-RULES.md` with the owner's delegated clarifications.

The integrated tree passed 1,101 Python tests (2 skipped), 169 Node tests and both suites again
from a clean export; built 441 page files; publication guard checked 502 files with no issues;
payload budget and asset fingerprint checks passed; record audit matched all 92 public picks.
The isolated 17:30 rehearsal returned `ok` with no outside writes or private reads. Local Chrome
checked 24 Today, Record, Vegas, Games, Research, More, Start and legacy-route views across 375
and 1440 pixels with no overflow, caught load-error state or console exception. None of these
local checks proves a hosted publish or a live release. Next: locked deploy in the next routine
quiet window, watch its hosted run, then verify the live payload and both widths before marking
P46/P47 or the bundled safety items shipped.

## October 7 release receipt and content exception

Revision `480a22ac` was locked-deployed under the owner's one-night exception. Hosted publish run
`37695705262` succeeded, and the live site served app.js?v=130 and app.css?v=80. The 375- and
1440-pixel route checks had no sideways scrolling, browser exceptions or caught load-error state.
That is not a complete content pass: Today said “No best bet yet” even though TK King's POTD had
already reached X and Discord. The stored quote's old `expiresAt` appears to send the play through
the off-card filter. This must be reproduced and fixed without showing an expired quote as a fresh
bet; P60 tracks it. The bundled release is therefore not marked fully verified in the queue.

## October 7 80/20 Climb route preview

P59 is review-gated. The repo builder reads `ladder.state` over `gates.Stores().as_of(now)` and the
stored football slate, not the incomplete Today ladder summary. It prints real current-run rung
money and leg times, then explicitly labeled future windows at typical −160. One-league windows
need two or more confirmed games within 90 minutes and a scan more than 90 minutes before kickoff;
later windows wait for the prior last kickoff plus a 3.5-hour planning allowance. The first real
render is `/Users/keen/Projects/kookn-patches/design/final/codex-climb-route.png`. Three watermark-
labeled fixtures cover mid-climb, restart and an open rung with its true −173 price. Route posting
and site placement remain off until the owner/Claude review and a separate gated release. The
existing 11:45 PM Kitchen Ticket cutover is unchanged.

## October 7 Kitchen Ticket website release — verified live

The owner approved applying Claude's 11-patch `site-v2-2026-10-07.mbox` tonight as a one-night
exception. The mbox hash matched its handoff, it applied without conflicts to dev `87ae3c9e`,
and the result matched Claude's tested tree before the queue receipt commit. The lock-holding
deploy pushed `48e573914f1431210e1f50999bce4c3bbad6a9c0` to main. Hosted publish run
`37700211419` succeeded, including the public record, payload-budget and artifact checks.

On the final tree, 1,138 Python tests passed (two skipped), 196 frontend tests passed, both
suites passed again from a clean export, the site built, the publication guard found no issues,
the record audit matched 92 picks, the asset fingerprint was current, and the isolated 17:30
rehearsal returned `ok` with no outside writes or private reads. Local browser checks at 375 and
1440 pixels found no overflow, caught load-error state or console exception on Today, the play
and player pages, Record, Vegas, Games, Research and legacy links.

Live `https://keenroudy.com/sports/` served app.js?v=133 and app.css?v=82. With All sports
selected, Today showed delivered TK King and the Climb stub at 375 and 1440 pixels. The TK King
play showed its role hold with no chance or ORDER UP; JJ Kohl's player page showed Under review
and his real full-game attempt counts. The older Bills–Rams play said “Posted price may be gone”
and “I had it at”, not a fresh-price badge. The Vegas panel displayed stored-line samples and
coverage; Record, Games, Research and `#responsible` (to More) opened. No sideways scroll,
rendered load failure or console error appeared. This clears P47, P54, P60 and P61. P46 still
needs a cold-phone speed measurement and its first weekly direction packet; P53 still needs the
Damante/Egbuka live recheck; P56 still needs the Upset Watch live threshold check and copy sweep.

Claude approved the separate Climb route preview in `CLIMB-ROUTE-REVIEW.md`; this website release
does not enable route delivery or change the 11:45 PM Kitchen Ticket card cutover. P59 tracks
that separately.

## October 8 Today information restore — verified live

The owner narrowed the eight-day site-image guarantee to recent receipts and cards still referenced by
the site. The original uploaded X/Discord attachment bytes remain immutable; an older, unreferenced
missing image is logged and skipped, never fetched from an expired URL, regenerated, or allowed to fail
the build. A recent referenced card still fails closed if its original bytes cannot be restored. The
regression tests cover both sides of that boundary.

The isolated release `6dc3ebca3f7a2d1e5285520dd329988bbc6da6a7` was fast-forwarded under the
run lock after the green prior desk run. Local final-tree gates passed: 1,182 Python tests (two skipped),
222 frontend tests, both suites from a clean export, 441-page build, payload budget with no issues or
warnings, 92-pick record reconciliation, 79-item feed with 16 cards, 500-file publication guard,
asset and SVG checks, and isolated slot-0830 rehearsal (`ok`, zero outside writes/private reads).
Local 375/1440 browser checks found no overflow, caught load error or console exception.

Hosted publish [run 37795541437](https://github.com/keenroudy22/sports/actions/runs/37795541437)
passed at 10:55 AM Eastern. Live app.js?v=138 and app.css?v=86 passed 20 route checks at 375 and
1440 pixels with no overflow, caught load state or browser exception. CFB Today showed the first
ticket and spaced Climb stub, other best bets, last-game-day units and result, Prep List, Underdog
watch, research, games and off-card content without a fold. Record showed the October calendar;
College Games showed the filters and Worth your time; the Iowa–Washington game page showed
“Why my number differs”; Vegas and the legacy `#responsible`→More route loaded. The footer was
exactly `21+ · Entertainment only`; Start here retained Eastern times and the Cloudflare note.
The prior TK King card remained byte-identical (SHA-256
`07458d2d56b84d55e096869047f5e0a0a3ae7f70eb0d9143cdf2c92c485e30d1`). His displayed
result uses `6 targets, 0 catches, 0 yards · missed by 49.5` without changing the stored report.

The reviewed Kitchen Ticket selector is live but time-gated to
`TICKET_FROM=2026-10-08T12:00:00-04:00`, more than 30 minutes after hosted completion. No first
post-cutover card was observed at the time of this receipt, so P45 remains open for that check.
P64 also remains open for its later month art and weekly receipt strip; the calendar site portion
is live. No dossier/series/selection-rule or append-only-record change rode with this release.

## October 8 result-copy and first Kitchen Ticket art verification

Release `5e61eddc` passed hosted [run 37806752440](https://github.com/keenroudy22/sports/actions/runs/37806752440).
On the live app.js?v=140, Today, the TK King play page, and Record each include
`TK King · 6 targets, 0 catches, 0 yards · missed by 49.5`; the saved October 8 report remains
append-only. The 9:00 AM Leftovers X post preceded this release and was not edited or deleted.
Caption send paths (Buffer/X and Discord) now reject a bare five-plus-digit athlete ID, while
Leftovers, Final, Cooked and receipt text read the factual result helper. New SVG card rendering
also rejects that ID pattern. Tests cover the real TK King settlement and all send gates.

The five owner-named unposted play cards—Iowa–Washington, Arizona–West Virginia, Nevada–UTEP,
SDSU–Oregon State and Bills–Rams—each returned a live 1080×1350 PNG carrying the Kitchen Ticket
theme marker after hosted run 37806752440. SDSU is still closed to new entries; retaining its
image does not reopen or schedule it. Release `7052dbe6` passed hosted
[run 37808251104](https://github.com/keenroudy22/sports/actions/runs/37808251104); every
post-cutover image send now waits if the live PNG lacks that marker. The scheduler itself
accepted the five live PNGs. At verification there was no future Buffer entry, so the first
sent X attachment remains unobserved. The approved 9:30 Prep List posting path is not wired
yet; Iowa's existing play window targets Friday October 9 at 6:00 PM Eastern if its normal
price, news and last-look checks still pass. Live 375/1440 checks found no sideways overflow,
caught load-error state or console error. P45's card cutover is verified; its first X delivery
will be checked separately. P64's month art and weekly strip remain open.

### October 8 game-day morning posting rule (P73)

Owner item 38 supersedes the earlier noon/two-hours-before and 6 PM targets. The
isolated release `8bf33d9aedb0c561984b3b0c647e360d9f6e7aaa` passed 1,188 Python tests
(2 skipped), 223 Node tests, clean export, build, payload budget, 92-pick record audit,
502-file publication guard, asset/SVG checks, isolated 11:45 rehearsal and local phone/desktop
browser checks. The locked fast-forward deploy and [hosted run 37819749608](https://github.com/keenroudy22/sports/actions/runs/37819749608)
succeeded. The live 375/1440 Chrome check of Today, Record, Games and More found zero
overflow, console errors or caught load-error states. Future official plays and tickets
target game-day 9:30 AM Eastern (8:30 before a 10:30 kickoff), with Hot Plate first,
ten-minute X spacing, a Discord lead and a safe late-admission window. Iowa at Washington
now targets Friday October 9 at 9:30 AM Eastern, subject to its news and price checks.
No test post was forced; natural delivery remains to be observed.

### October 8, 2026 afternoon: safer selection and the Climb route

The owner-approved item 33/37 selection rules shipped at `44bd9c1d` in hosted run
`37823635779`. The release passed 1,199 Python and 223 Node tests, a clean export,
build, budget, 92-pick record audit, 502-file publication guard, isolated rehearsal,
and live 375/1440 browser checks. NFL totals are paused as official picks but continue
as forward shadows; CFB totals have a one-per-weekend, no-weekday, five-point limit.
New straights require the four-point calibrated edge floor, two numeric dossier reasons,
two-sided exact-line pricing and the recent-QB guard; Hot Plate needs five points.
Player props rank before sides and totals. Moneylines and Comfort Food remain open:
the former has no genuine free two-sided input yet and the latter has not been built.
The 21-day complete new-rule historical count is unknown because 39 of 48 published
straights lack saved numeric edges and none has a saved dossier.

The approved Climb route website view shipped at `0fbbb1e1` in hosted run
`37825913575`. Its image and HTML steps share one ledger snapshot; real cashed/open
steps are linked to the posted rung, and future dollars/windows are clearly labeled
as the typical −160 plan. This release passed 1,200 Python and 223 Node tests, clean
export, build, budget, 92-pick audit, 503-file guard, rehearsal and the 375/1440
browser checks. The live PNG returned HTTP 200; the live record showed Climb #3,
step 1, $42 banked, with nine rows. No rung, posting rule or historical attachment
was changed. A natural ledger update remains to be observed.

## October 9, 2026: Kook'n plan Release 1

The owner-approved selection plan (T0–T11b) shipped at
`6494be496816df991035a0b180015990daba46cc` in hosted run
[`37948447125`](https://github.com/keenroudy22/sports/actions/runs/37948447125). The final tree passed
1,218 Python tests (two skipped), 229 frontend tests, both suites from a clean export, the 447-file build,
payload budgets, the 93-pick record audit, the 489-file publication guard, asset checks and isolated
slot-0830 rehearsal. Live Chrome checks covered Today, Games, Record, Research, More and a game page at
375 and 1440 pixels with no sideways overflow, caught load state or console exception. Live assets were
`app.js?v=149` and `app.css?v=92`.

The October 1–9 stored-input replay produced a play lane on every football game day, including the October 8
primetime fallback, without changing the record. The new lane records remain separate from Best bets. The
Best bets headline before and after is 35–36 (one void), with the owner baseline −5.11u at posted prices.
Opponent-adjusted college trends (T-TREND) remain queued for Release 3 so this selection release was live
before Saturday's morning runs.

## October 9, 2026: Kook'n plan Release 2

The owner-approved voice and caption plan (T12–T17) shipped at
`ed68bf16325481e129c91a541d79a30da1466bdf` in hosted run
[`37956832655`](https://github.com/keenroudy22/sports/actions/runs/37956832655). The final tree passed
1,225 Python tests (two skipped), 230 frontend tests, both suites from a clean export, the 459-page build,
payload budgets, the 94-pick record audit, the 501-file publication guard, asset checks and isolated
slot-1145 rehearsal. Live Chrome checks covered Today, Games, Record and WSU–Utah State at 375 and 1440 pixels
with no sideways overflow, caught load state or browser exception. Live assets were `app.js?v=150` and
`app-games.js?v=sha256-0aa9bf8631fd`.

The exact owner caption pools, kill-list guard, deterministic variety selection, result wording and posting-time
jitter are live. A matchup page now includes only a play wholly tied to that one game: the five-leg multi-game Fun
Lotto no longer appears under WSU–Utah State or any other individual matchup. The live WSU–Utah State page says
`No official bet in this game` while retaining its matchup lines and season trends. No pick, result, historical
post or append-only record changed. The Best bets headline before and after remains **35–36 (one void), −5.11u at
posted prices**.
