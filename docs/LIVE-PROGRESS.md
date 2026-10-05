# Local live-progress pilot

Owner authorization, Oct 5, 2026: use the local model for occasional midgame social updates such as how many
points or yards a posted play still needs, without repetitive posting. This release enables a bounded Discord
pilot only. It does not claim FanDuel-speed data or change the website, odds polling, picks or public record.

## Shadow review before release

Reviewed the private observer state at 2026-10-05 04:12 UTC: five requested game summaries succeeded, 24 official
settlements were reconciled, and stored events included eight close observations, four early crossings, 15 final-win
and 18 final-loss events. Each of the four crossing events had a later final-win for that same leg. These are event
counts, not an audited betting record or four independent tests (some tickets shared a leg). No Discord trial had
yet occurred. This supports a small pilot, not unrestricted X release or a measured feed-latency guarantee.

## Live behavior

- Existing five-minute Mac observer, maximum eight games; no new background job.
- Public unresolved football plays only. Player overs and full-game total overs; no spreads, unders, team totals
  or touchdown markets without a supported exact-stat mapping. Other sports remain outside this pilot.
- Two recent observations, moving game status, no declining stat, complete known ticket-leg states. Skip dead
  tickets. Exact integer target is floor(line) + 1. Actual alternate legs already store their threshold as a
  half-point line. Missing stats remain missing.
- Local Qwen chooses an allowed ID and one of two styles. One 20-second call at most per 15 minutes when a
  candidate exists. It can choose silence. Busy/offline/invalid output skips; no cloud fallback.
- Owner's casual-tone follow-up: mix quiet facts with "9 to go. Come on!" (number from the verified gap),
  exact player/line above and current stat/target plus clock below. No consecutive casual updates; no redundant
  "Posted play" label. Ticket-leg context stays explicit. This does not increase post volume or relax any gate.
- Re-fetch only the selected game's free summary after selection. Discard finals, changed/crossed targets,
  regressions, and selection cycles older than 90 seconds. Retrieval timestamps are not upstream latency claims.
- Short factual text, with game clock. At most two updates per Eastern date, at least 45 minutes apart, one per
  posted ticket, and ten minutes clear of scheduled/recent ordinary Discord releases. No mentions or Playbook.
- Persist a send reservation before network delivery. An ambiguous result cannot retry; pause for review instead.
- Three attempted pilot messages maximum. Next check notifies the owner and holds. Do not clear the state to
  bypass review or auto-promote. Saved evidence: `~/.config/keenroudy/live-progress.json`.
- `KEENROUDY_LIVE_PROGRESS=0` kills publishing. `KEENROUDY_LIVE_SHADOW=0` kills observation and publishing.
  Dry runs never select with the LLM or send. Ordinary settlement posts stay unchanged.

## Before enabling X

Review each pilot's exact source, target math, timeliness, clock, ticket context, delivery evidence and final result.
Three **sent** messages alone are not three clean reviews. Correct source-stat revisions honestly if a published
update became wrong. Any uncertain delivery needs manual reconciliation. Keep X off until separately released
through Buffer with the existing 20/day and ten-minute global limits plus the tighter progress-specific caps.
Never queue a live message far enough ahead that it becomes stale; revalidation must occur at delivery.

Automated standalone informational posts must follow [X automation rules](https://help.x.com/en/rules-and-policies/x-automation).
This feature does not authorize reply bots, likes, follows, unsolicited mentions or browser automation on X.
Early-hit celebrations, public live player-stat panels, faster-than-five-minute monitoring and live odds are
separate work, not delivered by this pilot.
