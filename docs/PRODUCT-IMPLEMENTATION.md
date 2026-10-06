# October 5 product implementation tracker

Owner approved implementation of the October 5 product plan after reviewing it. This tracker separates work that
can ship now from observation, counterpart permission and later owner decisions. It is not proof a staged change
is deployed. The existing append-only reports and public record remain unchanged by presentation work.

## Effective scope

Today / Games / Charts / Record / Tools; compact published selections first; shared correct chart geometry and
quote states; coherent research filters; private operating visibility; bounded captions and tested creative variants.
Current sources, free budgets and approved release categories only. Full plan: owner's local
`kookn-product-plan-2026-10-05.html` (dated audit baseline, not a deployment receipt).

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
| Website | Free Today / Games / Charts / Record / Tools; sport-specific Today; Scores aliases Games Live. | Posted plays first; research/model records clearly separate. No subscription or hidden premium gate. | Release receipts above; AGENTS product approval. |
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
  subprocesses, outside writes or private-state reads. Production receipt follows after deployment; these local
  checks alone are not proof that the release is live.

## External and elapsed-time gates

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

No forced plays, missing/stale price bypass, weakened calibration or availability checks, rewritten record,
straight/parlay player stacking, new API spend, public private-arb payloads, automatic X replies/likes/follows,
unreviewed new social categories, hidden tracking, account signup or payments. Evaluation windows do not become
publication quotas. Green/red visuals express actual selected-side support/outcome, not certainty.

AGENTS.md is the effective operating contract. SOURCE-RIGHTS.md and SUBSCRIPTION-PLAN.md explain unresolved
commercial conditions. Older audit release documents remain historical evidence, not a second conflicting policy.
