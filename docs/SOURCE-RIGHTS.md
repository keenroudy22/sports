# Source and asset rights register

Reviewed October 5, 2026 from the primary sources below. This is a readiness register, not legal advice,
a provider contract, or a claim that public access grants reuse permission. Existing integrations do not prove
commercial rights. No counterpart has been contacted, no new feed activated, and no budget raised by this review.

## Decision rule

Before expanding a source into a paid feature, promotional asset, raw export or new public feed, record the exact
use, applicable plan/license, attribution and retention requirements, and evidence of permission. Where terms are
unclear or restrictive, obtain written confirmation or use a properly licensed replacement. Do not interpret the
absence of a technical access barrier as consent. An entertainment disclaimer does not replace those checks.

The unresolved ESPN/asset questions below merit review of current use as well as future monetization. This
document does not grant permission to continue or expand a use; it also does not silently reconfigure production.
Any approved source migration must preserve the historical public record and explain coverage changes.

| Source / current role | Verified primary-source position | Status and next checkpoint |
|---|---|---|
| ESPN public scoreboards, summaries, rosters, supplied pregame quotes | ESPN's support page directs users to Disney terms. Those terms restrict unlicensed commercial/business use and automated extraction. No affirmative public sports-feed commercial license was identified. Browser reachability and a one-minute polling interval are not an SLA or license. | **Unresolved, high priority.** Document endpoint fields and display/storage uses; seek appropriate written permission or a licensed replacement before commercial expansion. Keep explicit observation time and failure/stale states. |
| ESPN athlete portraits and team/league marks | No blanket promotional/commercial image license was verified. Access to a CDN image is not evidence of permission; image rights and trademarks are distinct from numerical sports facts. | **Unresolved, high priority.** Inventory origin and usage by asset. Identify owned/licensed alternatives or permission. Avoid implying player, league or sportsbook endorsement. Generated Kook'n layouts do not create rights to embedded photos. |
| nflverse historical play-by-play, player stats and upstream datasets | The project distinguishes MIT-licensed code from underlying NFL data belonging to their respective owners and subject to their terms. Published update schedules are chiefly nightly for player stats/play-by-play, with later corrections. | **Dataset-by-dataset review required.** Record the specific upstream owner/license and attribution for each input, not “MIT” for all sports data. Not a live player-stat substitute. |
| The Odds API: budgeted quotes | Terms allow indefinite storage, commercial UI display, derived analytics and model training. They prohibit standalone raw-data resale/redistribution, including raw feeds/downloads. | **Value-added UI permission documented; scope still matters.** Keep the 500-credit guard. Review public JSON and any future export/API against the raw-data restriction. Obtain clarification for ambiguous uses; never expose a key. |
| SharpAPI: player/main/alternate prices | Terms allow display to own end users, including paid users, at the appropriate tier; comparison may be a feature. A comparison screen/feed as the product itself needs a separate written agreement. Internal retention is allowed; stored-data publication has separate restrictions. | **Clarification required** for the current plan, historical/public quote archives and any paid odds-grid/arb proposition. Free pricing is advertised for evaluation with a 60-second delay, not verified in-play execution. No plan upgrade approved. |
| SportsGameOdds: silent evaluation | Terms allow end-user applications with independent material value, but restrict redistribution, bulk downloads and certain competing uses. Termination generally requires deletion, with a transformed-output exception. Free pricing lists 2,500 objects/month and ten-minute updates. | **Evaluation only.** Existing stricter usage guard stays. Resolve archive/retention compatibility and product scope before public use. A source that requires raw-data deletion cannot casually become the foundation of the append-only raw archive. |
| National Weather Service: U.S. weather | The desk uses the existing weather integration. The exact applicable usage, attribution, rate-limit and downstream display conditions were not re-audited in this rights pass. | **Review pending.** Record the relevant official policy before adding a commercial claim; no new weather service or request cadence authorized. |
| Kook'n name, chef, logo, original layout and copy | Existing house assets are in the repository. Original layout work is distinct from rights to incorporated third-party assets. No new logo or avatar has been approved for replacement. | **Provenance inventory pending.** Record who supplied/created each source asset and permitted uses before paid branding/merchandise. Keep the existing identity in this release. |
| User-submitted winning slips/screenshots | Permission to share a specific submission is not general permission to expose account details or republish unrelated submissions. | Obtain applicable owner permission; redact account/bet IDs and private information. Do not convert a personal slip into a retrospectively “official” pick. |
| Competitor screenshots and research | Reviewed as design references, not data inputs, source assets or product code. Account access does not authorize scraping/exporting proprietary datasets. | Borrow general interaction patterns only. Do not copy logos, branded templates, text, proprietary data or hidden paid content into Kook'n. |

## Primary sources and bounded conclusions

- ESPN terms routing: <https://support.espn.com/hc/en-us/articles/360035445091-Terms-of-Use>
- Disney U.S. terms: <https://disneytermsofuse.com/english/>. Sections concerning commercial use and automated
  extraction are the reason for escalation; exact application to each proposed use requires qualified review.
- nflverse terms: <https://nflverse.nflverse.com/>; schedules:
  <https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html>.
- The Odds API terms: <https://the-odds-api.com/terms-and-conditions.html>; cadence:
  <https://the-odds-api.com/sports-odds-data/update-intervals.html>; allowance: <https://the-odds-api.com/>.
  Published update intervals are not proof every quote is executable or an uptime guarantee.
- SharpAPI terms (September 26, 2026), especially sections 5.1–5.3: <https://sharpapi.io/terms>;
  plan limits: <https://sharpapi.io/pricing>. “Appropriate tier” is not yet resolved for Kook'n's intended paid scope.
- SportsGameOdds terms: <https://sportsgameodds.com/terms>; pricing: <https://sportsgameodds.com/pricing>.
  Account-specific reported limits, not a marketing headline, continue to control the local evaluation guard.

## Evidence to retain privately

For each approved use retain provider, exact source fields/assets, purpose, audience, plan, applicable terms/date,
written permission reference, attribution, retention/deletion obligations, permitted derived outputs, geography,
commercial/export constraints, renewal date and accountable reviewer. Keep contracts, email addresses, keys and
private correspondence out of public site payloads. Summaries may be public where useful, never a false “licensed” badge.

## Public payload review before membership

- Separate necessary displayed facts and audit evidence from raw provider dumps and internal model details.
- Review quote-history exports separately from ordinary in-app research; they are not the same licensed use.
- Keep public outcomes, original published selections and dated corrections available. If provider obligations
  conflict with retained raw inputs, resolve the contract/storage design rather than silently rewriting history.
- Store secrets and future premium payloads server-side. A hidden card over publicly downloadable JSON is not access control.
- Do not market second-by-second scores, stats or odds without measured delivery and rights supporting that promise.

No item is “cleared” merely because this register exists. The owner must approve counterpart contact, any replacement
provider/spend, and the eventual paid launch separately.
