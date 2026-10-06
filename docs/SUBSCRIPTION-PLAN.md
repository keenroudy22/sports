# Kook'n Sports subscription plan

Updated October 6, 2026 to the approved product plan and redesign direction. This prepares membership readiness, not an activated
paywall, account system, processor, tip jar, referral program or paid data contract. The present product stays free.

## The product promise

Kook'n should be the fastest way to answer either of these questions:

1. **Show me Kook'n's plays.** Today opens to compact published selections, exact price/book and status.
2. **Let me research.** Charts and Games expose useful evidence immediately and preserve the user's context.

The advantage is not having the most rows. It is turning a large slate into a short, trustworthy starting point, then making the supporting research unusually easy to inspect.

Sell saved time, dependable research and useful workflows. Do not sell “AI” as proof of quality, guaranteed winning
picks, or an assumed edge from a high favorite-win percentage. Keep Kook'n Sports as the umbrella; Kook'n Lines
can describe research and Kook'n Pro can name a later membership. The owner-approved Kook'n visual and copy redesign
supersedes the earlier “no public rebrand” sentence, but it does not activate a paid product or change the public
record, play gates or delivery rules.

## What the established products sell

- **OddsJam:** speed and market breadth. Its premium product scans many books for positive-EV bets, arbitrage, middles, low holds, line movement and promo conversion. Its Platinum price is listed at $499.99 per month.
- **Props.Cash:** approachable player-prop research. It emphasizes clear charts, advanced filters, injuries, matchup context and correlations. Its all-sports price is listed at $19.99 per month or $199.99 per year.
- **LineStar:** one subscription across sports, projections and tools on web and mobile. Its listed monthly price is $39.99.
- **Stathead:** deep historical querying. Football subscriptions are advertised from $9 per month.

These are dated offers and marketing descriptions, not independently verified effectiveness or a price Kook'n
has earned. The October 5 direct props.cash session observed accessible Props, Markets, Watchlist, player research
and an upgrade dialog, not paid-only depth or account syncing. Doink's public pricing advertises a free example
game per league and all-game research at $19.99/month; the text scrape does not establish exact Starter/Pro feature
differences. Linemate's official listing emphasizes fast discovery with free access and in-app purchases.

Product pages reviewed October 4, with the additional October 5 observations above:

- https://oddsjam.com/lp/ads/zeke-platinum
- https://labs.props.cash/
- https://www.linestarapp.com/Pricing
- https://stathead.com/getting_started.html
- https://props.cash/nfl
- https://doinksports.com/research/pricing
- https://apps.apple.com/us/app/linemate-find-your-next-bet/id1635246793

## Where Kook'n can win

- A clear sortable **Research** board instead of making a user build several line/trend tabs before seeing anything useful.
- Best bets, research references and fun tickets kept visibly separate.
- A permanent public record, including losses and the original posted price.
- Game pages that combine projected score, game lines, player props, injuries, depth changes, red-zone work, team strength and trends.
- Plain language and strong mobile design instead of a professional trading terminal.
- A recognizable voice, graphics, community and live-game follow-through.
- A curated football product first. Depth and trust matter more than claiming every sport immediately.

## Where Kook'n should not compete yet

- Second-by-second odds from hundreds of books.
- Live arbitrage at national scale.
- Native iOS and Android apps.
- Every sport and every market.
- Claims of guaranteed profit or a promised win rate.

Those require licensed data, significantly more infrastructure and customer support. Trying to imitate them now would make the free product slower and less trustworthy.

## Product structure

| Main destination | User job |
|---|---|
| Today | Current published POTD, active Climb, best bets and fun tickets; compact results and useful context. |
| Research | One sortable board for player props, game lines and trends; main lines and value rank first. |
| Games | Upcoming / Live / Final, matchups, projections, ranks, news/weather and relevant research. Old Scores links work here. |
| Record | Published straights, parlays, Climb dollars, model accuracy and prospective trials, visibly separated. |
| More | Arb calculator, Lab, Saved, Digest, schedule, help and community. |

The same selected sport stays active across sections. Player/game detail links remain stable. Research selections,
official published plays and ticket-building actions have distinct labels and records. Confidence only appears
when its existing price/evidence/calibration requirements pass.

The same underlying line should have one stable identity so it can move between the fast lane, game page, player page, saved ticket and future member alerts without duplicating logic.

## Free now, paid later

### Free should remain useful; current free features are not removed by this plan

- Today's official plays and public record.
- Model season scorecard under Record → Model, separate from Today's official-results strip.
- A curated daily research preview.
- Basic game projections and player pages.
- Discord community and selected alerts.

### A future Kook'n Pro could add

- Advanced trend, role, matchup and injury filters.
- Saved players, games and lines across devices.
- Price-change, injury and kickoff alerts.
- Licensed line movement and historical snapshots.
- Research organization and exports only where source terms permit them.
- Reliable configurable alerts with quiet hours when legally and operationally appropriate.

Do not hide the public record, responsible-gaming language or grading rules behind a paywall.
Do not automatically sell earlier official plays by delaying the free feed. Any change to public delivery timing
or the free/paid play boundary needs a separate owner decision and fresh-price review.

## Technical preparation

The current GitHub Pages site is a public static application. A visual login placed on top of it would not protect paid data because the JSON files would still be publicly downloadable.

Before charging:

1. Keep the public site shell and free payloads static.
2. Move premium payloads behind an authenticated serverless API.
3. Give every account an entitlement such as `free`, `trial` or `pro`; enforce it on the API, not only in the browser.
4. Choose billing only after processor eligibility and owner launch approval; Stripe is a candidate, not clearance.
   Verify signed webhooks and process them idempotently. Handle cancellation/access expiry, failed payments, refunds
   and duplicate/out-of-order events. Never trust a browser “payment succeeded” flag.
5. Store saved lines and alert preferences per user.
6. Add privacy, terms, cancellation, responsible-gaming and data-licensing review before collecting payment.
7. Provide appropriately scoped account deletion/export, support access, recovery, backups and an outage/revocation
   path. Test authorization failures. Keep public results independent of login/billing and never expose the Mac.

Cloudflare Pages/Workers with D1 and Whop are candidates for a later costed comparison, not approved vendors or
active integrations. The choice belongs to the launch gate after rights, retention, processor eligibility and the
complete billing lifecycle are reviewed; no paid vendor or additional request budget is needed during free validation.

## What to prove before charging

These are Kook'n acceptance targets, not industry standards or evidence already achieved. Four-week validation
cannot be completed by one coding release.

| Gate | Evidence required | Current status |
|---|---|---|
| Reliability | Four consecutive weeks without an unresolved critical display/grading incident; every settled published play reconciled or visibly pending with a reason; at least 95% of targeted freshness checks within their stated windows. Report delivery success separately from qualified/no-play/held decisions. | Pending prospective observation; record start/date and eligible-check denominator. |
| Usability | At least 8 of 10 first-time volunteers find the current play and supporting chart within 30 seconds without coaching; include narrow-phone and keyboard tasks. | Pending actual sessions. Automated screenshots are not a substitute. |
| Repeat value | A consenting 10–20-person cohort across four real slates; return visits, saved research and completed tasks identify one repeat-use workflow. | Pending recruitment/consent. Local counters are not cross-device retention. |
| Willingness to pay | At least five cohort members explicitly choose a clearly priced founding concept in a no-payment test. | Pending costed concept; a small signal, not a market-size claim. |
| Rights and trust | Source/image permission for actual uses, processor acceptance, jurisdictional review, terms/privacy, support, cancellation/refund and security review complete. | Unresolved external checks; see SOURCE-RIGHTS.md. |
| Product economics | A costed data/infrastructure/support budget and downside case, including fees, tax obligations and refunds. | Pending approved offer and counterpart terms. |

Model promotion remains separate: pre-register forward trials, evaluate probability accuracy and captured-price
returns by market, preserve untouched evaluation dates and report uncertainty. No automatic weight promotion
from backtests, no chasing yesterday's results and no new-sport picks from a scoreboard alone.

### Privacy-conscious measurement

Saved is browser-local. Current feedback is manually copied/sent with optional local section counts. No external
analytics, account creation, email collection, cohort identifier or Discord role subscription is activated here.
For a later consenting cohort, explain purpose/retention, collect only needed task/return information, allow
withdrawal/deletion and aggregate findings without identifying volunteers. Do not collect sportsbook credentials,
exact wagering amounts or private slips. Local counters are not unique visitors or willingness to pay.

## Source rights and payment readiness

SOURCE-RIGHTS.md records unresolved ESPN/portrait rights, nflverse upstream terms, SharpAPI tier/comparison/history
scope and other provider constraints. Public availability is not a commercial license. Review current use and
planned monetization, including raw public JSON/exports, and obtain appropriate written permission or licensed
replacement inputs where needed. Do not remove historical outcomes or provenance to conceal a rights problem.

Before money is accepted, accurately describe the research-only product to the processor and obtain its needed
acceptance. Review jurisdiction-specific requirements with qualified counsel; an entertainment disclaimer is not
blanket legal clearance. Publish understandable renewal, cancellation, refund and support terms.

### Optional tips

A content tip may be simpler than membership after those checks. Do not call it a charitable donation unless
that is genuinely the approved purpose. Stripe distinguishes tips for supplied content/services from charitable
donations, and its restricted-business policy includes gambling-related categories. Eligibility for this exact
research service remains unresolved. Never relabel a sale to bypass restrictions, pool wagering funds or charge
a share of users' winnings. No tip jar is activated by this plan.

- https://support.stripe.com/questions/requirements-for-accepting-tips-or-donations?locale=en-GB
- https://stripe.com/legal/restricted-businesses

### Creator referrals after retention

No outreach is authorized by this implementation. After the workflow retains users and a paid offer is approved,
consider 3–5 relevant creators who use it. Use single-level agreements and unique links with approved privacy-conscious
first-party attribution. Pay only on eligible genuine subscriptions after the refund window; reverse refunds/abuse
and disallow self-referral. Never tie commission to wagering losses.

Require clear nearby disclosure of commission/free access or other material connections. A referral code alone
may not explain compensation. Do not require positive reviews or hide negative feedback. Judge the pilot on relevant
visitors, research activation, retained subscriptions, refunds and support burden rather than follower counts.

- https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers
- https://consumer.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking

## Recommended rollout

1. **Now:** keep everything free, improve the fast lane, data freshness and mobile clarity.
2. **Validation:** complete reliability and volunteer usability/repeat-use work; introduce optional free account
   sync only after it is justified and separately approved.
3. **Founding access:** resolve rights, processor acceptance and a costed concept, then seek explicit approval for
   a small paid pilot once all readiness gates pass.
4. **Broader launch:** price against Props.Cash and LineStar, not OddsJam Platinum, until Kook'n has comparable real-time market breadth.
5. **Expansion:** add another sport only when its data, grading and game-page experience meet the football standard.

The near-term goal is not to look expensive. It is to become the site people instinctively open before they place a football bet.
Use PRODUCT-IMPLEMENTATION.md for release evidence and outstanding work. “Prepared” never means “launched.”
