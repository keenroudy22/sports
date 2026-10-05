# Kook'n Sports subscription plan

Internal product plan. Nothing here launches a paywall or changes the free site.

## The product promise

Kook'n should be the fastest way to answer either of these questions:

1. **What does the model like right now?** Open **Best lines** and see the current line, price, book, confidence, timing and one short reason.
2. **Why might I play it?** Open the game or player and see the useful supporting data without reading a model report.

The advantage is not having the most rows. It is turning a large slate into a short, trustworthy starting point, then making the supporting research unusually easy to inspect.

## What the established products sell

- **OddsJam:** speed and market breadth. Its premium product scans many books for positive-EV bets, arbitrage, middles, low holds, line movement and promo conversion. Its Platinum price is listed at $499.99 per month.
- **Props.Cash:** approachable player-prop research. It emphasizes clear charts, advanced filters, injuries, matchup context and correlations. Its all-sports price is listed at $19.99 per month or $199.99 per year.
- **LineStar:** one subscription across sports, projections and tools on web and mobile. Its listed monthly price is $39.99.
- **Stathead:** deep historical querying. Football subscriptions are advertised from $9 per month.

Product pages reviewed October 4, 2026:

- https://oddsjam.com/lp/ads/zeke-platinum
- https://labs.props.cash/
- https://www.linestarapp.com/Pricing
- https://stathead.com/getting_started.html

## Where Kook'n can win

- A clear **Best lines** fast lane instead of making a user build filters before seeing anything useful.
- Official plays, model references and fun tickets kept visibly separate.
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

### Fast lane

- **Plays:** the official card, Climb and published tickets.
- **Best lines:** every current game or player line that clears the site's price and evidence checks.
- Each row shows the wager, price, sportsbook, kickoff, confidence and status.
- One tap opens the supporting player or game research.

### Research

- **Games:** projections, team strength, favorite lines, injuries, weather and player opportunities.
- **Props:** the full priced player board.
- **Players:** game logs, hit rates, role, opponent and red-zone usage.
- **Trends:** 70/80/90/100% season filters.
- **Record:** official results and the separate model scorecard.

The same underlying line should have one stable identity so it can move between the fast lane, game page, player page, saved ticket and future member alerts without duplicating logic.

## Free now, paid later

### Free should remain useful

- Today's official plays and public record.
- Season scorecard.
- A small rotating preview of Best lines.
- Basic game projections and player pages.
- Discord community and selected alerts.

### A future Kook'n Pro could add

- The complete Best lines board.
- Every qualifying game and player model favorite.
- Advanced trend, role, matchup and injury filters.
- Saved players, games and lines across devices.
- Price-change, injury and kickoff alerts.
- Full line movement and historical snapshots.
- Personal bet tracking and export.
- Faster Discord or mobile delivery when legally and operationally appropriate.

Do not hide the public record, responsible-gaming language or grading rules behind a paywall.

## Technical preparation

The current GitHub Pages site is a public static application. A visual login placed on top of it would not protect paid data because the JSON files would still be publicly downloadable.

Before charging:

1. Keep the public site shell and free payloads static.
2. Move premium payloads behind an authenticated serverless API.
3. Give every account an entitlement such as `free`, `trial` or `pro`; enforce it on the API, not only in the browser.
4. Add Stripe Checkout and its customer portal only when the owner approves pricing and launch. Webhooks, not the browser, update entitlement state.
5. Store saved lines and alert preferences per user.
6. Add privacy, terms, cancellation, responsible-gaming and data-licensing review before collecting payment.

A lightweight future stack could use Cloudflare Pages/Workers with D1 or an equivalent managed auth/database service. The choice should be made at launch time; no paid vendor or additional request budget is needed during the free validation phase.

## What to prove before charging

- At least four reliable weeks of fresh prices and on-time updates.
- A stable public record with no unexplained grading gaps.
- Users repeatedly opening Best lines, player pages and game pages.
- Returning users on multiple football slates, not only traffic from one winning post.
- Clear evidence of which feature creates repeat use: quick favorites, trend research, alerts or community.
- A support and cancellation process one person can realistically maintain.

Track page views, return visits, Discord joins, Best lines opens, research opens and saved-line actions. Do not track sportsbook credentials or private bet slips.

## Recommended rollout

1. **Now:** keep everything free, improve the fast lane, data freshness and mobile clarity.
2. **Validation:** add optional accounts for saved lines and alert preferences, still free.
3. **Founding access:** invite a small group to a low-priced Pro tier after the reliability gates pass.
4. **Broader launch:** price against Props.Cash and LineStar, not OddsJam Platinum, until Kook'n has comparable real-time market breadth.
5. **Expansion:** add another sport only when its data, grading and game-page experience meet the football standard.

The near-term goal is not to look expensive. It is to become the site people instinctively open before they place a football bet.
