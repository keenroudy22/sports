# Player-prop parlay workbench

The November 16 owner request starts MNF/TNF player-prop and NBA alternate-ticket
work without new subscriptions, requests, stakes or exposure allowances.
`scripts/prop_ticket_review.py` is private review tooling, not an automatic
selector or proof that a ticket was posted. The separate NFL release adapter
below is a new candidate requiring canonical deployment and live proof.

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

## Private settlement review

`scripts/prop_ticket_settlement.py` adds a pure offline `review(spec, evidence,
now)` function. It binds a frozen reviewed packet and original combined quote
to exact per-leg identities, terminal official actuals, participation, injury
review and an observed book settlement with its jurisdiction and rule version.
A loss returns the original 0.25u loss; all void/push returns zero; all wins use
the original combined price. A reduced winning ticket requires the book's actual
revised joint price matching every remaining leg. No division or multiplication
of individual prices is allowed. Unknown injury protection, DNP decisions,
changed terms, missing actuals and contradictory book outcomes stay held.

The result is `settled-private`, never a public ledger write or publication.
Receipt authenticity still requires attended verification; this function does
not fetch a sportsbook or establish a new automatic settlement route. Its tests
use synthetic fixtures, not evidence that a real ticket was published or graded.
The new NFL adapter below integrates this review with the ordinary result worker;
its deployment and real full-game ticket proof remain outstanding.

## NFL admission and release adapter — candidate

`scripts/prop_ticket_release.py` validates a public-safe full-game NFL candidate,
then `--queue --spec /private/path.json` reserves it in the existing private
release queue. The packet must additionally provide `settlementPolicy`: verified
book and Indiana jurisdiction, official book rules URL, rule version, private
receipt, fresh check clock, and reviewed participation, push/void, early-exit and
SGP repricing terms. No hidden sportsbook collection or new request is made.

Private proof lives in `~/.config/keenroudy/prop-ticket-releases/`, mode0600.
`--recheck ID --spec /private/fresh.json` appends a fresh attended check retaining
all original identities, thresholds, periods, book and actual combined price.
Until that post-admission check exists, the normal worker retains the private
reservation without sending. Ordinary expiry, exposure, result-first, caption,
card, Discord lead and Buffer checks still apply. Neither a private queue row
nor passing tests establishes publication.

`--settlement /private/evidence.json --id ID` validates and stores evidence for
a published original; the ordinary results worker owns the append-only revision.
A `basis: official-stats-and-rules` packet uses `statSettlement` instead of
`bookSettlement` and must match the original reviewed book rules. Every leg must
be a clear played/final win or loss. This grades the published0.25u allocation
without requesting a personal wager screenshot, and records that distinct basis.
Nonparticipation, push/void, unresolved injury or protection stays held; actual
book decisions and any reduced joint price use the observed-book pathway.
No cash fields, private receipts or source filenames enter the public revision.

Continue O-20261019-ALTFUN: release this NFL candidate canonically, verify hosted
and natural worker behavior, complete the separate NBA ledger/delivery adapter,
and obtain real full-game ticket/publication/grading proof. NBA-alts can be
reviewed privately but `--queue` explicitly refuses them. The separately published
Nov16 owner Q1 ticket is not a full-game adapter test. No recurring automatic
series is claimed and the existing calls, stakes and caps remain unchanged.

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


For an injury-related raw loss, the NFL release adapter preserves the existing
12-hour deadline. After kickoff+12h, an attended `deadline-stats` injury review
must be fresh, include sources and a public-safe note, and explicitly establish
that no different official book decision is known. It can then grade the loss
from official final stats, preserving the injury note and verified injured
player names for receipts. It cannot infer protection, a void or SGP repricing.
Before that deadline, or with missing checks, the result remains held.
