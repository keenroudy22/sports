# Kook'n Arb Radar

The radar is private. It never places a wager, changes an official Kook'n play, enters the public record, or posts to
X or Discord. It reads captured prices, accepts only exact complementary outcomes, calculates equal-return stakes and
sends a phone alert through the existing ntfy topic when every guard passes.

## What counts

- Same event, full-game period, market, participant and line at two different books.
- Two outcomes that exhaust every result. Player totals must be half-point lines so a push is impossible.
- Both book timestamps no more than ten minutes old and a capture no more than fifteen minutes old.
- At least 1% locked return after stakes are rounded to cents.
- Pregame only in the first release. Live prices move too quickly for the free capture cadence.

Different spreads or totals may create a middle, but they are not called guaranteed arbitrage. Account-specific odds
boosts are not visible in normal feeds; use `python scripts/arbs.py boost +298 50 -195` to compare a true equal-profit
hedge with a break-even-downside free roll. Every alert says to verify the event, line, limit and settlement rules in
both apps before placing either side.

## Feeds

The first release uses Kook'n's existing The Odds API captures at no additional request cost. DraftKings, FanDuel,
BetMGM, Caesars, BetRivers, ESPN BET and Fanatics remain the official-pick pool. Hard Rock Bet is an eighth captured
comparison book, but `odds_api.PICK_BOOKS` prevents it from changing a public selection.

SportsGameOdds was reviewed on 2026-09-29. Its Amateur plan is genuinely free and includes player props, alternate
lines and live prices, with 2,500 event objects per month, ten requests per minute, eight leagues and nine books.
The important limitation is a roughly ten-minute update frequency; the free book list shown on its pricing page also
does not include Hard Rock, Fanatics or BetRivers. Its own arb guide says these windows can close in seconds. That
makes the free tier promising as a shadow feed for broader sports and comparison testing, but not yet trustworthy as
the sole source of an executable phone alert.

`scripts/sgo_shadow.py` is that shadow mode. The key stays in `~/.config/keenroudy/env` as
`SPORTSGAMEODDS_API_KEY` and is sent only in the `x-api-key` header. Before every event sample it calls the free
`/account/usage` endpoint. It refuses to sample unless the account reports the Amateur plan's exact 2,500-object
monthly ceiling, stops at 1,800 used (a 700-object reserve), asks for at most ten events, takes at most 30 objects a
day, waits six hours between samples and runs only when an NFL or college game is inside 48 hours. The local state is
`~/.config/keenroudy/sgo-shadow.json`; it holds compact counts and never the key or a full odds response.

This feed never sends an alert. It silently measures fresh exact-line candidates so we can learn whether a
ten-minute free feed is still actionable. Only evidence that it materially improves executable coverage can justify
proposing a paid feed to the owner, and no upgrade happens without their explicit approval.

Sources: [SportsGameOdds pricing](https://sportsgameodds.com/pricing),
[rate limits](https://sportsgameodds.com/docs/info/rate-limiting),
[arb API guide](https://sportsgameodds.com/use-cases/arbitrage-betting-api), and
[bookmaker identifiers](https://sportsgameodds.com/docs/data-types/bookmakers).
