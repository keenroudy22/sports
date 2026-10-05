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
| Private operations | Distinguish qualified/no-play/held/queued/delivered; identify overdue/failed output; unchanged healthy polls remain quiet. | Implemented cached checks on the existing half-hour precheck, local-only HTML and JSON, two-observation change alerts and weekly evidence. No new feed/model calls. Private Discord is prepared but disabled. |
| Deployment safety | Both Python and Node exit statuses stop promotion; lock held during sync/tests/promotion; isolated offline rehearsal exercises real `_run`. | Helper and documentation prepared. Initial actual smoke passed October 5; final release rerun still required. |
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
- Deployed revision, hosted-build result and final responsive evidence must be recorded at release handoff, not inferred here.

## Not finishable in this coding release

| Gate | What remains | Authority/state |
|---|---|---|
| Four-week reliability | Four consecutive observed weeks, measured eligible freshness denominator, delivery metrics and grading reconciliation. | Future evidence; cannot backfill success. |
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
