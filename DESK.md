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
| `scripts/x_post.py` | The post text: one shape for every play (player prop, team prop, fun parlay), with `data/x-posted.json` as the posted log. |
| `scripts/buffer_post.py` | Scheduling those posts to @keenkooks through Buffer's free plan, three hours before kickoff, each with its card. |

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
bash ~/.config/keenroudy/run.sh py scripts/X.py ...     any repo script with the sports environment loaded
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

Two writers push to the repository: this desk and the hosted workflow. A rejected push is rebased and
retried on both sides. When both captured prices in the same window the rebase stops on `data/odds` or
`data/prop-odds`; `scripts/merge_store.py` keeps every record from both sides in retrieval order, recomputes
the store's ledger the way every capture script writes it, and merges the day's budget counts taking the
stricter side. A conflict anywhere else aborts the rebase and stops the run for a person. Nothing is ever forced.

## The local model

Ollama serves the model at `http://localhost:11434`; `KEENROUDY_LLM_MODEL` in the env file names the
tag. The model is asked for prose and judgment only. Every rewrite passes `llm.check_style` (no em or en
dashes, plain words, short sentences, no model or version names, no marketing, no advice) and
`llm.numbers_ok` (every number in the text appears in the pick's fields, the desk output or the facts),
or the template stands. A judgment counts only when it points at a fact by id; unsure means hold.
With Ollama down the run publishes on templates and holds on a quarterback rule of thumb.

## X

X gets plays only (the owner's call after the first post, a stats line, went out on 2026-09-23 and was
deleted): **player props**, **team props** (sides and totals) and the day's **fun parlay**. Favorites, model
leans, prop leans and the longshot all qualify; recaps and scoreboards stay on the site. Every post has the
same shape, drafted by `scripts/x_post.py` from the pick's own fields:

```
🍳 PLAYER PROP                    (TEAM PROP, FUN PARLAY; "· FAVORITE" on a researched pick)
Player Seven over 4.5 receptions
-115 at DraftKings

Our number: 5.8
He has caught 6 in each of his last 2 games.

#NFL
```

The reason is one sentence of the pick's own `why`, short and free of the desk's arithmetic words; when
every sentence is arithmetic the post stands on the play and the number. A parlay lists its legs and says
"Quarter unit. Just for fun." There is no link (X shows fewer people a post that leaves the site); the card
carries keenroudy.com/sports. Every post carries its card (`scripts/pick_card.py`): the kitchen, the same
label as the post, in the colours of the side the play is on; a parlay's card lists the legs and serves the
price on the plate.

X meters posting through its API, so the desk posts through **Buffer** (`scripts/buffer_post.py`, free plan:
Buffer's own X access, 3,000 API requests a month, an exact `dueAt` per post, an image by public URL,
`deletePost`). The timing is the same every game day: each play posts **three hours before its kickoff**
(a parlay's first leg), never before 9:00 AM ET; plays sharing a kickoff go player props first, then team
props, then the parlay, ten minutes apart; a play published later than its time goes out at once unless
kickoff is inside 45 minutes. Buffer takes an image only by URL, so a post is scheduled only once its card is
live on the site: the hosted workflow renders a card for every open play as soon as it is published, the run
schedules after its own push and waits up to 15 minutes for that deploy, and a play whose card is still not
live waits for the next run. Nothing goes out bare.

Every post is logged in `data/x-posted.json` (kind `buffer:*`, committed on its own as "Posts <date> <time>
ET") so nothing goes out twice; once its time has passed the run records the X link it went out under, or the
failure (which fails the run, so the heartbeat alerts). A play that closes before its time is cancelled, and
the channel's own daily limit (50) is respected, with ours at eight.

One-time setup, done 2026-09-23: a free Buffer account with @keenkooks connected, and a personal API key
(account:read, posts:read, posts:write; expires 2027-09-23) as `BUFFER_TOKEN` in `~/.config/keenroudy/env`.
`run.sh py scripts/buffer_post.py channels` shows the connected channels; `plan` shows what the next run would
schedule; `schedule --confirm [--soon 20]` schedules exactly that by hand; `post PICK_ID --confirm` schedules
one pick; `reconcile` records what became of past posts. Buffer's queue (keenkooks, Queue) shows every
scheduled post and can delete one before it goes.

The same plays are published as an RSS feed, `https://keenroudy.com/sports/data/feed.xml` (`scripts/feed.py`),
as a public record. `x_post.py` can still post through X's API (`post PICK_ID --confirm --card`) when credits
exist, and writes review drafts to `~/.config/keenroudy/x-drafts/`.

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
