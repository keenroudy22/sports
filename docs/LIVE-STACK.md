# Kook'n live-data plan

October 5 product update: live scores now belong inside Games; old `#scores` links remain aliases. Source
accessibility is not a commercial license: see `SOURCE-RIGHTS.md` before expanding or monetizing feeds/assets.
This document's free/paid options are evaluations, not permission to buy, increase budgets or activate services.

## What runs now

- The always-on Mac remains the private desk: it captures prices, verifies news and weather, grades results, prepares
  cards, queues approved X posts through Buffer and sends Discord alerts. Ollama may summarize verified evidence; it
  is never treated as a score, injury or odds source.
- GitHub Actions refreshes the static site several times daily and hourly during weekend football. Those builds keep
  forecasts, prices, records and research reproducible at their captured timestamps.
- While a visitor has Today, Games, a game page or Scores open, the browser now requests factual score/status updates
  once a minute from ESPN's public scoreboard response. NFL, college football, NBA, WNBA, college basketball, MLB,
  NHL, Premier League and MLS are covered. A blocked or failed request keeps saved scores and displays a stale or
  unavailable label. Refreshes preserve open sections, focus and scroll. Hidden tabs pause; returning resumes.
- Scores can show ESPN-supplied DraftKings pregame quotes from the same response, at no metered feed cost. The
  label distinguishes retrieval time from the unavailable book update time. These disappear at kickoff, after a
  failed refresh or after two minutes without a successful observation. They are not verified in-play odds.
- Live score refreshes never replace official-play odds, projections or grading inputs.

This is deliberately two-speed: scores can move quickly; anything that could be mistaken for a betting recommendation
keeps a visible, auditable capture time.

## Free-first next layer

No new service is required for the current score layer. If direct browser access becomes unreliable, put the same
factual score request behind one Cloudflare Worker with a 30-60 second edge cache. The Workers free plan currently
allows 100,000 requests per day, which is enough for a small public site if requests are cached by league and date.
Do not expose the Mac itself to the public internet.

The current free sources are still the right fit for research:

- ESPN public scoreboards for schedules, scores and status, with stored fallbacks.
- National Weather Service for U.S. kickoff weather.
- nflverse and the existing public football sources for historical/snap context.
- The existing budgeted Odds API and supplied book quotes for lines. Never ask the local model to guess a price.

## What the local model can and cannot do

The local model can run all day at no per-call cost, read facts the desk already verified, summarize a matchup, write a
clean draft, categorize news and flag contradictions for review. It cannot independently know a live score, current
line, injury designation or roster move. A deterministic collector must fetch those facts first, attach source and
time, and reject stale or conflicting inputs before any model sees them.

## Paid options, only when the free layer becomes the bottleneck

1. **Cloudflare Workers paid** starts at $5/month and is the smallest useful infrastructure upgrade if traffic or
   authenticated feeds outgrow the free edge proxy.
2. **football-data.org** offers delayed scores on its free plan. Its live-score plan is currently €12/month and is a
   reasonable soccer-only upgrade, not a replacement for U.S. prop or odds coverage.
3. **API-Sports** lists a 100-request/day free tier and a $19/month single-sport tier with 7,500 requests/day. It is
   useful only after one new sport has a defined product and evidence plan.
4. **The Odds API** is already integrated and metered. Scores cost credits and historical/live odds consume more;
   increasing its plan makes sense only after the existing quota report proves missed coverage.
5. **Sportradar** provides a small trial (about 1,000 calls over 30 days at 1 request/second); production is sales-led.
   Treat it as an evaluation source, not a free long-term foundation.

Sources checked October 4, 2026:

- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/platform/limits/
- https://www.football-data.org/pricing
- https://www.football-data.org/documentation/api
- https://api-sports.io/sports/football
- https://the-odds-api.com/liveapi/guides/v4/
- https://developer.sportradar.com/football/docs/football-ig-account-maintenance

## Promotion order for new sports

1. Scores and schedules.
2. Historical charts and transparent data coverage.
3. Market capture and grading in private shadow mode.
4. Paper model with prospective results.
5. Public research after a stable sample.
6. Official plays only after evidence and owner approval.

NBA and college basketball remain paper-only. MLB and NHL remain market-lab tracks. Soccer remains factual/shadow.
The site can show all of their live scores now without implying the unfinished models are ready.
