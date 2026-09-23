# The research desk, automated

The scheduled research runs described in `PROMPT.md` are now code, run on the owner's Mac Studio by
`launchd`. This file says what runs, what it may publish, and how to operate it. `RESEARCH.md` still
holds the report format and the rules of the record; `PROMPT.md` still holds the schedule and the
rules in words. When this file and the validator disagree, the validator wins.

## What runs

| Script | Job |
|---|---|
| `scripts/run.py` | One scheduled run: sync, capture prices, settle finals, close picks whose line moved, build the board, price the candidates our number likes, gather sourced facts, hold what the facts argue against, run every candidate through the gates, write one report per league, validate, commit the whitelisted paths and push. |
| `scripts/gates.py` | The publishing rules, one function per rule. A candidate passes every gate or it is not published. `python scripts/gates.py CANDIDATE.json` evaluates one. |
| `scripts/replay_gates.py` | Every published pick back through the gates as of its publication, with what would have been refused and why. |
| `scripts/llm.py`, `scripts/llm_tasks.py` | The local model (Ollama, on this machine) and the two guards on its prose: the house style and the numbers guard. The model polishes templated `why` and `risk`, drafts posts and weighs the facts against a candidate. It never adds a number. |
| `scripts/x_post.py` | Drafting and posting researched favorites to X, behind a review gate, with `data/x-posted.json` as the posted log. |

Nothing here edits an existing file in `research/`, `market-observations/` or a ledger. A quiet run
writes nothing.

## What a run may publish

Exactly what `PROMPT.md` allows, and only when every gate passes:

- **Settlements and closes**: revisions of published picks, graded from the box score or closed to
  new entries when the line moved past the published cutoff. An outcome the code cannot grade (a player
  with no line in the box score, a parlay leg that pushed) is left for a person and named in the log.
- **Model leans**: totals only, calibrated chance one point or more clear of break-even, at the best
  expected value across the books, four a day, none when a starting quarterback is doubtful or worse.
- **Prop leans**: raw chance 60% or better on a settled role, five points clear of the price, never worse
  than -200, three per kickoff window, one per player, never a player listed questionable or worse, never in
  a market where the closing line has been closer than our projection (read live from the scoreboard),
  and never on one book's number unless kickoff is inside three hours.
- **Longshots**: one a game day from `scripts/parlay.py`.
- **Favorites**: only with a verified, sourced reason attached by the run. The web-reading researcher
  that supplies those reasons is off until the owner turns it on, so the desk publishes no favorites yet.

Everything is priced at the quote with the best expected value, not the best-looking number. The
`expiresAt` is the next scheduled run or kickoff, whichever comes first.

## Operating it

Everything sports-related lives outside the repo under `~/.config/keenroudy/` (the `env` file with the
keys, `run.sh`, the sports-only `gh` login in `gh/`, `status.json`, `x-drafts/`, `pending/`) and logs to
`~/Library/Logs/KeenRoudy/`. The launchd jobs are `com.keenroudy.sports.run` (the schedule) and
`com.keenroudy.sports.heartbeat` (7:15 daily; speaks only when something is wrong). None of this touches
any other automation on the machine.

```
bash ~/.config/keenroudy/run.sh doctor                  versions, identities, which keys are set
bash ~/.config/keenroudy/run.sh run --dry-run           a run that writes its reports to pending/ and touches no git
bash ~/.config/keenroudy/run.sh run --publish-kinds settle,close     a live run limited to revisions
bash ~/.config/keenroudy/run.sh status                  the last run's status.json
python scripts/replay_gates.py --since 2026-09-14       what the gates would have refused
python scripts/x_post.py draft PICK_ID                  write a post draft; post PICK_ID --confirm posts it
python scripts/x_post.py recap --day 2026-09-27         a game day's results as a post
```

The schedule went live on 2026-09-23 with `--publish-kinds settle,close` (settlements and closes only).
Publishing widens one kind at a time by editing the job's `ProgramArguments` and reloading it (the plist
says how): next `settle,close,lean,prop,longshot`, then everything once the researcher is on.

Every commit the desk makes is authored and pushed as `keenroudy22` through the sports-only `gh` login;
the heartbeat checks that identity every morning and alerts if it changes.

## The local model

Ollama serves the model at `http://localhost:11434`; `KEENROUDY_LLM_MODEL` in the env file names the
tag. The model is asked for prose and judgment only. Every rewrite passes `llm.check_style` (no em or en
dashes, plain words, short sentences, no model or version names, no marketing, no advice) and
`llm.numbers_ok` (every number in the text appears in the pick's fields, the desk output or the facts),
or the template stands. A judgment counts only when it points at a fact by id; unsure means hold.
With Ollama down the run publishes on templates and holds on a quarterback rule of thumb.

## X

Favorites, model leans, prop leans and the day's longshot all go to X, each labeled for what it is (a lean
says "our number alone", the longshot "fun ticket, quarter unit"). Every post is drafted by
`scripts/x_post.py` in the kitchen's voice from the pick's own fields (the label, the line at its price, one
or two sentences of the pick's reasoning with the most specific first, our number against the line, the
receipt link `https://keenroudy.com/sports/#pick/<id>` and the league tag), and every pick gets a card (`scripts/pick_card.py`) in the colours of the side the
play is on, rendered by a headless Chrome and never committed.

X meters posting through its API, so the desk does not post there itself. It posts through **Buffer**
(`scripts/buffer_post.py`): Buffer's free plan connects an X account to Buffer's own developer access and
gives 3,000 API requests a month, an exact `dueAt` per post, a public image URL per post and a `deletePost`.
At each run the desk schedules the day's plays into their posting window (game day, Eastern, from 9:00 AM,
eight minutes apart, never inside 45 minutes of kickoff), the recap for 8:00 the next morning once every
pick of the day is settled, and the scoreboard for Tuesday at 9:00. Every post is logged in
`data/x-posted.json` (kind `buffer:*`) so nothing goes out twice, a play that closes before its time is
cancelled, and the channel's own daily limit is respected. Cards come from `site/data/cards/`, which the
hosted workflow deploys; a card that is not deployed yet means a text-only post, never a failure.

One-time setup (the owner): a free Buffer account with @keenkooks connected as an X channel, then
Settings → API → create a key and paste it as `BUFFER_TOKEN` in `~/.config/keenroudy/env`.
`python scripts/buffer_post.py channels` shows the connected channels; `plan` shows what the next run would
schedule; `post PICK_ID --confirm` schedules one by hand.

The same posts are also published as an RSS feed, `https://keenroudy.com/sports/data/feed.xml`
(`scripts/feed.py`), for any other relay and as a public record of what went out.

`x_post.py` can still post through the API (`post PICK_ID --confirm --card`) when credits exist, and
`data/x-posted.json` logs whatever it posts. The run writes every draft and card to
`~/.config/keenroudy/x-drafts/` as well, for a person to post by hand or for Claude to post through the
owner's browser when asked.

## Weather

`scripts/venues.py` keeps `data/venues.json`: for every venue the store or slate names, ESPN's roof
flag and city and a point from Open-Meteo's free geocoder; anything it cannot place is listed in
`data/venues-review.json` for a person. `scripts/weather.py` reads the National Weather Service hourly
forecast at that point for the hour of kickoff (wind, gusts, chance of precipitation, temperature) for
outdoor games inside six and a half days, and appends it to `data/weather/` when it changes, so the record
shows what was known and when. The run turns it into a fact: wind of 15 mph or more, a 60% chance of
precipitation or 25 degrees argues against an over and for an under; otherwise it is context. The score
model does not carry weather; this is evidence for the judgment, not a term in the number.

## The market read and the web researcher

`scripts/market_read.py` puts the market beside our number, never inside it: the move since open, which
books disagree, and where our gap sits among the model's historical gaps with the record of gaps that
large against the close. A model lean's `why` ends with it; game cards carry it as `marketRead`.

`scripts/researcher.py` is the only part of the desk that reads the web. Off unless the env file sets
`KEENROUDY_RESEARCHER=claude`; then, at the 8:30 and 17:30 runs on game days, it asks the `claude` command
line (headless, web search and fetch only) for sourced facts about the strongest candidates, fetches every
source URL itself and keeps a fact only when each named person is on the page. Verified facts feed the
gates' `favorite_needs_reason` rule; nothing unverified is argued from.
