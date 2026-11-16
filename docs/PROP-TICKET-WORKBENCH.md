# Player-prop parlay workbench

The November 16 owner request starts MNF/TNF player-prop and NBA alternate-ticket
work without new subscriptions, requests, stakes or exposure allowances.
`scripts/prop_ticket_review.py` is private review tooling, not an automatic
selector, admission route or proof that a ticket was posted.

## Current implementation

The existing half-hour desk-health check reads at most 20 private JSON packets
from `~/.config/keenroudy/prop-ticket-reviews/`. It reports counts and seven-day
stored fixture coverage only. No receipt, caption, source filename or personal
accounting enters public payloads. It makes zero provider calls. No additional
Codex automation or routine chat is created.

A packet names `family` (`MNF`, `TNF`, `NBA-alts`), `parlayStyle` (`short` or
`lotto`), exact `book`, American `odds`, `priceEstimated: false`, and structured
`legs`. Current short/lotto shape limits and 0.25u stake remain unchanged.
Each leg has exact game/player IDs, player name, kickoff, market, direction,
line, full-game period, book, observed price/time/source, and whether it is an
alternate. An alternate also needs the observed main line it cushions.

The leg `review` must name `kookn-desk`, explicit approval and a current check
clock; include role, matchup, reason and countercase; and provide current source
facts for role, matchup and availability. Availability must identify the exact
player/game, active status, source and check clock. Questionable and unknown
players stay held. NBA scope is points, rebounds and assists; football scope is
carries, receptions, rushing/receiving/passing yards, attempts and completions.
Quarter markets, touchdowns, boosts and special-protection terms are held.

`ticketQuote` must contain a private receipt reference, visibly verified
sportsbook source and check time, and `terms` exactly equal to
`prop_ticket_review.terms(spec)`. This binds the actual combined price to every
exact leg. Never populate it from an odds product. Same-game tickets also require
`correlationReview.checkedAt`, `sharedScript` and `failureCase`. Neither marginal
probabilities nor past hit rates establish a joint win probability.

The CLI reads current stores and existing exposure:

```
python3 scripts/prop_ticket_review.py --spec /private/path/to/review.json
```

A successful review returns `reviewed-private`, an exact one-leg-per-line
caption, a terms fingerprint and **releaseReady: false**. It cannot queue, send,
place a wager, append a pick or settle a public record. Existing player overlap,
alternate frequency and per-style daily checks remain. The full daily unit cap
and all final admission checks belong to the subsequent production adapter.
Health counts describe packet review, not a capacity or publication promise.

## Tracked next implementation

Continue O-20261019-ALTFUN. First capture a real current combined book quote and
complete sourced player review. Then implement and test the same-game quote
adapter, release-time identity/price/availability and all exposure checks, plus
book-specific nonparticipant, push, void/reprice and early-exit settlement.
Missing participation or changed combined terms must hold. NBA primary straight
protection rules cannot be assumed to apply to SGPs. Require normal canonical
release and real hosted/site/X/Discord and grading receipts before enabling
recurring public tickets. No automatic series is claimed by this workbench.

## Daily operating plan

- Morning: finish the prior slate and delivery checks, then screen the whole supported
  slate and target five qualifying straights daily. Five is the release target; an unsupported quote or weak case does not become a pick to fill it.
- MNF/TNF: prepare player roles and matchup cases early, then verify the actual
  same-book ticket after current availability. Prefer a readable 3–4-leg short
  ticket when it clears the current +200 to +1500 shape; larger lottos remain a
  distinct, occasional review under their existing shape and exposure limits.
- NBA: research priced cushioned points/rebounds/assists with stable minutes.
  An unpriced milestone is a watch item. Existing once-per-league rolling-seven-
  day alternate-ticket allowance remains until the owner changes that policy.
- Keep players already reserved by straights or open tickets out of new tickets.
  Keep one Climb step open. Never promote a fun ticket to the straight record.
- Publish only useful new information: qualifying picks/tickets, material
  changes and complete results. Every actual public release needs site proof,
  X Sent/native quote where required, and Discord message/attachment receipts.
