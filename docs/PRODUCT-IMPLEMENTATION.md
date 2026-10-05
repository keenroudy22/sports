# October 5 product implementation tracker

Owner approved implementation of the October 5 product plan after reviewing it. This tracker separates work that
can ship now from observation, counterpart permission and later owner decisions. It is not proof a staged change
is deployed. The existing append-only reports and public record remain unchanged by presentation work.

## Effective scope

Today / Games / Charts / Record / Tools; compact published selections first; shared correct chart geometry and
quote states; coherent research filters; private operating visibility; bounded captions and tested creative variants.
Current sources, free budgets and approved release categories only. Full plan: owner's local
`kookn-product-plan-2026-10-05.html` (dated audit baseline, not a deployment receipt).

| Workstream | Acceptance evidence | State at implementation handoff |
|---|---|---|
| Chart correctness and quote clarity | Shared domain/baseline; below/equal/above, negative/zero/unknown fixtures; samples and quote ages match stored rows. | Implemented with regression fixtures; release verification below. No model or historical-grade change. |
| Navigation and Today | Five destinations; Scores alias opens Games Live; other aliases survive; sport context, back navigation, opening phone screen and no clipping. | Implemented. Local phone checks confirm the published play appears first and sport selection preserves its section. |
| Research workspace | Player/team/market search; main-line default; Season/L5/L10 samples; persistent filters; Saved distinct from ticket-building. | Implemented; local search/sample/back and trend filtering checks passed. Unsupported sports remain explicit. |
| Captions and graphic variation | Overlong text has a factual bounded fallback; readable long-name cards; green/red reflect the selected side, with non-color cues. | Implemented within current categories/caps. Cached end-zone caption now fits 239 characters with all four exact preview rows. Aggregate outcome strips do not invent game order. |
| Private operations | Distinguish qualified/no-play/held/queued/delivered; identify overdue/failed output; unchanged healthy polls remain quiet. | Snapshot checks shipped in b4770d04 on the existing half-hour precheck, with local-only HTML/JSON, two-observation change alerts and weekly evidence. Prospective daily reliability measurement is added in the follow-up below, pending its own release. No new feed/model calls. Private Discord is prepared but disabled. |
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
This follow-up is implemented and focused tests pass; its production deployment must be recorded separately.

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
incidents, settled-play reconciliation, actual delivery event rates, coverage gaps and four genuine observed weeks
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
  These are pre-release results; the final deployment receipt must be recorded separately.

### October 5 POTD audit: finding, not a selection-policy change

Falcons at Saints under 48 at -108 was published September 30 with a 43.43 total projection (ATL 20.3 / NO 23.1).
The raw 62.48% under chance was reduced to 55.24%; its stored conservative edge cleared the existing 3pp NFL-total
caution threshold. The 17-29 scoreboard is all final pregame total directions against the close, not the posted
selection record. Neither fact proves the selected play will win.

The October 5 POTD designation ranked already-published open singles by saved edge, not the entire current market.
Original research logged opposing statistical evidence, despite an overly broad all-clear explanation. The future
copy fix above preserves such counterpoints. A fresh comparative review requirement for POTD is recommended for
owner consideration, but is not implemented or represented as an existing rule in this release.

## Not finishable in this coding release

| Gate | What remains | Authority/state |
|---|---|---|
| Four-week reliability | Four consecutive observed weeks, measured eligible freshness denominator, delivery metrics and grading reconciliation. | Prospective local sampling implemented in the follow-up above; four-week evidence, incident review and reconciliation remain pending. Cannot backfill success or treat missing windows as healthy. |
| Volunteer usability/cohort | 8/10 usability target, 10–20 consenting users across four slates and five explicit priced-concept choices. | Recruit/consent and real feedback still needed. No synthetic user claimed as a human test. |
| Data/image rights | ESPN and portraits, upstream nflverse rights, SharpAPI appropriate tier/history/comparison scope, other register questions. | Written counterpart/legal review pending; no outreach or new license authorized here. |
| Processor and business terms | Accurate eligibility review, cancellation/refund/privacy/support and costed offer. | Pending external checks and separate launch approval. |
| Accounts and paid access | Optional free sync first; server-side premium authorization, tested billing lifecycle later. | Not active. Public JSON is not a paywall. |
| Creator referrals/tips | Clearly disclosed, processor-approved, costed pilot after retention. | No outreach, billing or tip jar activated. |
| Discord guide/private review | Verify actual owner-only destination and confirmed delivery/permissions; use approved existing channels. | Public guide mutation and any new destination still need the applicable owner confirmation. |
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
