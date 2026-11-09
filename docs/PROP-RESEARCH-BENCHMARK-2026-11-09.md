# Kook'n prop-research benchmark — 2026-11-09

## Owner direction

Make player research faster, cleaner and more familiar to bettors while keeping Kook'n's own projection beside the sportsbook line. First-quarter research, last-five and last-ten form, and position-vs-defense context must be easy to reach. Do not solve the problem by adding more prose.

## What bettors currently pay for

The reviewed products converge on a scan-first workflow:

| Product | Current paid promise | Pattern worth adopting |
| --- | --- | --- |
| Props.Cash | $19.99/month for updated prop lines, analysis, filters and visualizations | Player-first charts, fast filters, recent-form windows |
| BettingPros | Plus from $9.99/month billed annually; Prop Bet Analyzer includes projection, line, cover probability, EV and L5/L10/L15 hit rates | Dense comparison board before detail |
| Outlier | Premium $19.99/month; higher tiers add positive-EV, line movement, arbitrage and deeper filters | Best price, implied probability, L5/L10/opponent/season in one view |
| Rithmm | Core $29.99/month; model projections, edge, matchup research and line shopping | Model number beside market number, with an honest pass state |
| Doink | Player game logs, splits and quarter splits; game prop-progress tables include Q1/H1 markets | Quarter research as a first-class path; compact status tables |
| OddsJam | Premium real-time pricing tools organized around EV, exact book, line and market | Market scanning and line shopping, not long narratives |
| StatMuse+ | $20/month for unlimited natural-language searches and more result depth | Fast question-to-stat retrieval, subject to StatMuse's terms and licensing |

Official references checked 2026-11-09:

- https://props.cash/
- https://www.bettingpros.com/premium/
- https://help.outlier.bet/en/articles/6711738-research-player-propositions-with-outlier-s-prop-finder
- https://help.outlier.bet/en/articles/12556823-choosing-the-right-outlier-plan-for-your-betting-style
- https://www.rithmm.com/ai-sports-betting
- https://www.doinksports.com/research/nfl/player/pl_w776gqed4a2ko64ecmwcuoeu/prop-analysis
- https://www.doinksports.com/research/nfl/game/gm_ekk6u5ksygxwmsflzvwteate/prop-progress
- https://oddsjam.com/betting-tools/positive-ev
- https://www.statmuse.com/terms

## Product decision

Kook'n should feel familiar in the first ten seconds and differentiated in the next thirty:

1. Lead with a compact player-prop board, not explanatory cards.
2. Put the sportsbook line and Kook'n projection next to each other.
3. Always show L5, L10 and season hit rates against the exact displayed direction and line.
4. Show the opponent's position-vs-defense rank and a plain soft/middle/tough label.
5. Expand a row in place for the game-by-game chart and deeper evidence.
6. Keep 1Q research beside full-game research, not in a buried tools drawer.
7. Keep unavailable projections visibly unavailable. History never substitutes for a model number.
8. Keep exact price freshness and data-source caveats. Do not scrape or republish StatMuse content without a licensed data contract.

## Shipped first slice

The NFL/college Matchups surface now uses a responsive prop-explorer board. On every priced row it shows player/team/position, exact over-or-under line and price, Kook'n projection and difference, L5/L10/season hit rates, and opponent position-vs-defense rank. Tapping a row reveals the existing full chart and supporting evidence. NFL adds a first-class `1Q trends` switch.

This is the base component for subsequent sports. Reuse it for NBA and future quarter-priced feeds rather than creating another unrelated card layout.

## Explicit data boundary

The interface can expose only facts Kook'n has collected and can publish. Real-time multi-book shopping, movement alerts, correlated-prop models and priced 1Q props require durable provider coverage and terms that permit public display. Until then, Kook'n must label historical 1Q milestones as trends, not sportsbook lines or expected value.
