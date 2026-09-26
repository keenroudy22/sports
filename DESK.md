# The research desk, automated

The scheduled research runs described in `PROMPT.md` are now code, run on the owner's Mac Studio by
`launchd`. This file says what runs, what it may publish, and how to operate it. `RESEARCH.md` still
holds the report format and the rules of the record; `PROMPT.md` still holds the schedule and the
rules in words. When this file and the validator disagree, the validator wins.

## What runs

| Script | Job |
|---|---|
| `scripts/run.py` | One scheduled run: sync, capture prices, settle finals, close picks whose line moved, build the board, price the candidates our number likes, gather sourced facts, hold what the facts argue against, run every candidate through the gates, write one report per league, validate, commit the whitelisted paths and push. |
| `scripts/learning.py`, `scripts/learn.py` | The desk learning from its own record: every candidate recorded and graded, the weekly step that adjusts what it may (see Learning below). |
| `scripts/gates.py` | The publishing rules, one function per rule. A candidate passes every gate or it is not published. `python scripts/gates.py CANDIDATE.json` evaluates one. |
| `scripts/replay_gates.py` | Every published pick back through the gates as of its publication, with what would have been refused and why. |
| `scripts/llm.py`, `scripts/llm_tasks.py` | The local model (Ollama, on this machine) and the two guards on its prose: the house style and the numbers guard. The model polishes templated `why` and `risk`, drafts posts and weighs the facts against a candidate. It never adds a number. |
| `scripts/x_post.py` | The post text: one shape for every play (player prop, team prop, fun parlay), with `data/x-posted.json` as the posted log. |
| `scripts/buffer_post.py` | Scheduling those posts to @keenkooks through Buffer's free plan, around noon on game day, each with its card. |

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
bash ~/.config/keenroudy/run.sh run --dry-run           a rehearsal: reports and status go to pending/; no git, no Buffer, the live status and post log untouched
bash ~/.config/keenroudy/run.sh run --publish-kinds settle,close     a live run limited to revisions
bash ~/.config/keenroudy/run.sh status                  the last run's status.json
python scripts/replay_gates.py --since 2026-09-14       what the gates would have refused
python scripts/x_post.py draft PICK_ID                  write a post draft; post PICK_ID --confirm posts it
python scripts/x_post.py recap --day 2026-09-27         a game day's results as a post
```

The schedule went live on 2026-09-23 with `--publish-kinds settle,close` (settlements and closes only).
Publishing widens one kind at a time by editing the job's `ProgramArguments` and reloading it (the plist
says how): next `settle,close,lean,prop,longshot`, then everything once the researcher is on.

**Phone alerts** go through ntfy (free): a stopped or crashed run, a post that did not go out, a post held back because
its text failed the post check, a stopped last look,
and anything the 7:15 heartbeat finds are pushed to the private topic in `KEENROUDY_NTFY_TOPIC`, which the ntfy app
on the owner's phone subscribes to. The same alert is not repeated inside six hours; nothing secret is ever sent.

Every commit the desk makes is authored and pushed as `keenroudy22` through the sports-only `gh` login;
the heartbeat checks that identity every morning and alerts if it changes.

Two writers push to the repository: this desk and the hosted workflow. A rejected push is rebased and
retried on both sides. When both captured prices in the same window the rebase stops on `data/odds` or
`data/prop-odds`; `scripts/merge_store.py` keeps every record from both sides in retrieval order, recomputes
the store's ledger the way every capture script writes it, and merges the day's budget counts taking the
stricter side. A conflict anywhere else aborts the rebase and stops the run for a person. Nothing is ever forced.

## The judge, the news and the last look (2026-09-24)

A review on 2026-09-24 found the local model's judgment holding 24 of 26 candidates, 14 of them without naming a
fact, and treating the line's move as evidence against a pick. Backtests say otherwise: in 2024-25 college games
where the market moved two points or more away from our number, our side at the closing number went 232-149.
So, in this order, every run:

1. **The written rules first** (`gates.admit`). A candidate they refuse costs no research and no model time.
2. **The news**: the web researcher (`scripts/researcher.py`, `claude -p` with web search, run in its own empty
   folder with web search and page reads as its only tools and a research-only system prompt; run from the
   repository it had picked up the folder's context and spent its turns trying to run code) reads injury,
   availability and depth-chart reporting for every play that passes the rules, up to six a run, at every run
   except 6:45 AM and 11:30 PM. It asks first who is expected to play: each starting quarterback, key starters,
   and for a prop the player himself. Every fact is checked against its source page before it is used: an injury
   or lineup claim counts only when a status word from the claim sits next to the player's name on the page. A
   researcher that runs out of turns is asked once to answer with what it found.
3. **College needs the check**: no college play is published until the web check has come back with who is
   expected to play (`needs_research`, `lineup_confirmed`). College teams publish no injury report the desk can
   read, so without the check the desk would know nothing about injuries at all. The researcher does not always
   answer; a play it missed is held, not published blind.
4. **The judge** (the local model) sees only facts that can matter (`relevant_facts`): the player's own listing
   and his starting quarterback for a prop; the starting quarterbacks, a side missing three or more skill
   players, and a weather flag for a total; and everything the researcher verified. Not the line's move, not
   injured reserve, not backups. With nothing relevant there is nothing to hold on. A hold must name a fact.
   With the model down, a rule of thumb holds instead, and verified reporting against the pick always holds.

**The last look** (`run.py precheck`, launchd `com.keenroudy.sports.precheck`, every 30 minutes): a play
scheduled to post to X in the next 15 to 150 minutes gets the injury report read live from ESPN, the latest line,
the researcher's news and the judge once more. A play that no longer stands is taken off the Buffer queue and
closed to new entries on the site with a dated note saying why (the record keeps it and grades it as posted); a
play that stands is marked checked in the posted log; if its number moved, the post is scheduled again with a
"Now:" line (the new post is created first and the old one deleted after, so a failure never loses the play). A college play whose check comes back without who is
playing is tried again the next half hour, and inside 45 minutes of its post it is withheld from X (the pick
stays on the site and is graded). Quiet when nothing is due.

**A fun parlay gets the same look, leg by leg** (added 2026-09-25, after the 12:10 PM college longshot went out
carrying Navy at UAB over 51.5, the play the desk had pulled at 11:03 over Navy's quarterback): after the single
plays, every leg is matched against the single plays the desk has closed (same game, market and side, whatever the
line), then read like a single play (injury report, forecast, researcher, judge; a college leg is not held for want
of news). A pulled leg or a reason against takes the ticket off the queue and closes it with a note naming the leg.
The run does the same for any open ticket not yet under way (`run.parlay_closures`), and the next ticket leaves off
games with a closed play or a sourced reason against (`run.longshot_exclusions`). A published ticket is never
written again (`gates.not_republished`: a day's parlay id is fixed by date and book, and the 8:30 run had
rewritten the 6:45 ticket). A scheduled run now waits up to 15 minutes for a price check holding the lock
instead of losing its slot.

**The post's reason** is chosen when the play is published, from structured facts only (`run.post_reason`,
stored in `data/x-reasons.json`): a player's own record at the line when it backs the side ("Over 4.5 in 7 of
his last 10 games"), or for a game line a verified web fact or a weather flag that points the same way as the
play. It is never mined from the finished prose (the local model rewrites it, and lineup notes and line moves
read as reasons against). With nothing that backs the play, the post stands on the play and our number.

College teams are named by school in titles, posts and cards ("Central Michigan at Miami (FL)"), from ESPN's
school name in the slate (`pick_card.team_label`); published titles are never rewritten.

## The local model

Ollama serves the model at `http://localhost:11434`; `KEENROUDY_LLM_MODEL` in the env file names the
tag. The model is asked for prose and judgment only. Every rewrite passes `llm.check_style` (no em or en
dashes, plain words, short sentences, no model or version names, no marketing, no advice) and
`llm.numbers_ok` (every number in the text appears in the pick's fields, the desk output or the facts),
or the template stands. A judgment counts only when it points at a fact by id; unsure means hold.
With Ollama down the run publishes on templates and holds on a quarterback rule of thumb.

## X

X gets plays and their receipts (the owner's call after the first post, a stats line, went out on 2026-09-23
and was deleted): **player props**, **team props** (sides and totals) and the day's **fun parlay**, and the
morning after, the **receipt** for those plays. Favorites, model leans, prop leans and the longshot all qualify;
the model scoreboard stays on the site. Every play post has the same shape, drafted by `scripts/x_post.py` from
the pick's own fields:

```
🍳 PLAYER PROP                    (TEAM PROP, FUN PARLAY; "· FAVORITE" on a researched pick)
Player Seven over 4.5 receptions
-115 at DraftKings · 1 unit

Our number 5.8 vs the 4.5
He has caught 6 in each of his last 2 games.

@Playbook #NFL
```

The reason is one sentence of the pick's own `why`, short and free of the desk's arithmetic words; when
every sentence is arithmetic the post stands on the play and the number. No units anywhere a follower reads.
A parlay lists its legs and says "Just for fun."
Every post tags @Playbook, Action Network's betslip bot, which replies with the bet pre-loaded. There is no link
(X shows fewer people a post that leaves the site); the card carries keenroudy.com/sports and no confidence
score or date. Every post carries its card (`scripts/pick_card.py`), one frame for every kind:
the KOOK'N wordmark and pan, the same label as the post, the play, "Served at" its price, and the chef on the
plate (`site/kookn-chef.png`, the profile picture's chef cut out with macOS subject lifting), in the colours of
the side the play is on. Only the colours and the words change. A parlay lists its legs where a single play's
numbers go.

X meters posting through its API, so the desk posts through **Buffer** (`scripts/buffer_post.py`, free plan:
Buffer's own X access, 3,000 API requests a month, an exact `dueAt` per post, an image by public URL,
`deletePost`). The timing is the same every game day: plays post **around noon Eastern** (the owner's call,
2026-09-24), or two hours before a kickoff earlier than 2 PM (a parlay by its first leg), never before 9:00 AM;
player props first, then team props, then the parlay, ten minutes apart; a late injury after a play is out
cannot pull the post, though the site still closes the pick; a play published later than its time goes out at once unless
kickoff is inside 45 minutes. Buffer takes an image only by URL, so a post is scheduled only once its card is
live on the site: the hosted workflow renders a card for every open play as soon as it is published, the run
schedules after its own push and waits up to 15 minutes for that deploy, and a play whose card is still not
live waits for the next run. Nothing goes out bare.

**A post every day** (`scripts/receipts.py`, all in the same frame, never a stat line):

| When (Eastern) | Post |
|---|---|
| 8:45 AM on a game day with plays | **Today's menu**: how many plates, which games and when, never the side; plates go out around noon (card `site/img/kitchen-menu.png`) |
| 9:00 AM the morning after a game day | **Receipts** for every play of the day, with ✅ ❌ ➖ and the day's record |
| 9:00 AM Wednesday | **The week's receipts** by kind, with the week's dates |
| Around noon (two hours before a kickoff earlier than 2 PM; never before 9 AM) | **The plays**, the Pick of the Day first |
| 6:00 PM on a day with nothing else | **The book**: the season record of every play that went out on X (the two posted by hand on 2026-09-19 included), graded through yesterday and saying so ("Season through Sep 28"), so back-to-back quiet days never post the same words, which X refuses; with one kind of play only the season line (card `site/img/kitchen-book.png`) |

**What's on the plate** (owner, 2026-09-24): an NFL player prop's card shows the player's ESPN headshot, a team prop
the teams' logos (a total both, a spread its side), a parlay and the house cards the chef. Images are fetched when
the card is rendered and embedded; a failed fetch falls back to the chef. The photos are ESPN's and the logos the
teams' marks: `KEENROUDY_CARD_ART=0` (or `pick_card.CARD_ART = False`) turns them all off. No units on X: posts and
cards show the price and the book only.

**One record** (owner, 2026-09-25: "the record is confusing as hell"): every play the desk publishes counts, the
same on the site and on X, whether or not its post went out (a play pulled before its post stays in the record,
graded as posted); the Week 1 legs imported without prices are listed apart and never counted. The record is the
straight plays' wins and losses; money shows on the site only, as "Betting $100 on every play" (units x $100, at
the posted price). Fun parlays and the Pick of the Day have their own lines (a Pick of the Day counts once its post
went out, `posted` from `receipts.served`). The Record tab leads with three boxes (last game day, this week,
season), then every play with ✅ ❌ ➖ and what $100 on it made; the tables sit under "More numbers"
(`site/core.js theRecord`, `receipts.counted`). A pick pulled before its post shows "Pulled" and never the star.

**The easy parlay** (`scripts/easy_parlay.py`, owner's ask 2026-09-24: "dumbed down player props for a nice parlay"): on an
NFL day with three or more games left, the run takes DraftKings' and FanDuel's easier alternate lines (receiving and
rushing yards, from The Odds API: two credits a game, once a day, cached four hours in `~/.config/keenroudy/alt-props/`,
never below a 120-credit reserve, never on a rehearsal) and builds one leg per game where our projection clears the
line with room (80%+ on our numbers, 8+ points above the price's own, priced -350 to -150, settled role, not
questionable): three legs at one book paying +150 to +700, "Drake London 40+ receiving yards". A quarter unit, the
longshot's gates (one of each kind a day), kept with the longshots, and never called value: our player chances
are tuned for main lines. Every fun parlay carries an expiry (next run or first kickoff), which the longshot lacked.

**Posting time and the price** (`scripts/line_timing.py`, owner's question 2026-09-25: "are we posting early enough to
get the lines you like?"): for every single play, the number and price at its own book when it was published, when
its post went out (or would have, under the posting rule), and in the last capture before kickoff, each marked worse,
about the same or better (half a point, or ten cents at the same number). The rule: if most plays are worse by the
time they post, posts move earlier (`buffer_post.POST_AT`, about 10 AM); otherwise noon stays. First read, Sep 25:
7 plays measurable, none worse, one better. The Monday review runs it.

**Pick of the Day** (`scripts/featured.py`, `data/featured.json`): the first run of a game day that has plays names the one
whose calibrated chance clears its price by the most (never a parlay, never a game already started). It is named once and
never changes once it has posted; one the last look pulls before its post goes out is replaced by the best play left
that has not posted (`replaced` in the day's entry), and if that play is already queued, its post is swapped for the
Pick of the Day post at the same time once its card is live (`run.feature_scheduled`). Its post leads the noon batch with the kicker "PICK OF THE DAY · TEAM PROP" and its own card
(`cards/<id>-potd.png`, rendered by the hosted build, so a post never carries a stale copy), and the site's Today page
leads with it, starred.

**Receipts** (`scripts/receipts.py`) make it a post every day of the season. At 9:00 AM ET the morning after a
game day, once every play of that day is settled, the receipt lists each with ✅ ❌ ➖ and the day's record (the
straight plays' wins and losses; a fun parlay is listed but kept out of it), "Graded in public, win or lose." On
Wednesday at 9:00 AM the week's receipt sums the seven days before it by kind. Losing days post too. Every play the
desk published counts (`receipts.counted`, the same plays as the site's record), and a receipt not ready by 8:00 PM
the next day is skipped. Plays are named as their posts named them (schools by name).
A line break ends a sentence for the style check, so a long list is short lines, not one long sentence; a post that
fails its check anyway is named in the run log and on the phone, never dropped silently. Its card is the same frame in the kitchen's own colours (`pick_card.receipt_svg`), with W, L or P
beside each play and the chef on the plate.

Every post is logged in `data/x-posted.json` (kind `buffer:*`, committed on its own as "Posts <date> <time>
ET") so nothing goes out twice; once its time has passed the run records the X link it went out under, or the
failure (which fails the run, so the heartbeat alerts). A play that closes before its time is cancelled, and
the channel's own daily limit (50) is respected, with ours at eight.

One-time setup, done 2026-09-23: a free Buffer account with @keenkooks connected, and a personal API key as
`BUFFER_TOKEN` in `~/.config/keenroudy/env` (the free plan allows one key; replaced 2026-09-24 by one that also reads
engagement: account:read, posts:read, posts:write, insights:read; expires 2027-09-24).
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

## Learning

The desk keeps a record of every decision and grades it, so every part can be measured and the parts that may
be adjusted are adjusted by rule, not by feel (`scripts/learning.py`, `scripts/learn.py`, all under `data/learning/`).

- **The record.** Every run writes each candidate it priced to `candidates-<season>.jsonl`: the numbers it was
  decided on (projection, raw and calibrated chance, edge, price, book), what the facts and the judge said, what
  the researcher found and whether it checked out, and the decision (published, refused with every failing rule,
  or held). Only a changed decision is written again. Every run then grades whatever has finished into
  `graded-<season>.jsonl`: the result from the stored box score and the **closing line value**, how far the market
  moved toward our side by kickoff. Both files are append-only with a ledger, like every other store. The
  season's picks published before the record existed were put on it once (`learn.py backfill`).
- **The weekly step** runs at the Tuesday 8:30 AM slot, after Monday night is graded (`learn.py weekly`):
  - *Segments* (league and market: NFL totals, NFL receiving yards, ...), judged only on what each published
    since its last change. With 30 graded plays losing to the close (the 90% interval of closing line value below
    zero), its minimum edge rises one step; still losing at the strictest setting, it pauses (`learned_pause`).
    With 30 beating the close and 20 near misses (refused only by an edge rule) beating it too, it eases one step
    back. The floors are the written rules in `PROMPT.md`: learning makes the desk pickier, never looser than
    the rules, and a paused segment reopens only when what it refused kept beating the close.
  - *Player chances.* Raw prop chances are calibrated against every graded projection (each projected player
    against the last DraftKings line and the box score). A calibration ships only when it predicts the later part
    of the record better than the raw chances and better than the one in use; after that a prop must also clear
    its price on the calibrated chance (`prop_calibrated_value`). First run, 2026-09-23: 538 projections, the
    favoured side came in 52.4% against a raw 62.2%, k 0.13 shipped.
  - *Measured and reported*: what each rule refused and how it did, the judge's holds against what was published,
    the number against the close. The written rules for these stay as written; the report says what they cost.
  - *The researcher* is told which sites' facts keep checking out (preferred) and which keep failing (avoided).
  - *Posts*: each play post records the kind of reason it gave (injury, weather, market, role, stats). Two days
    after a post goes out its engagement is read from Buffer (needs the key's `insights:read` permission), and
    the reason ranking leans toward the kinds people engage with, within 0.8 to 1.25. The look, the timing and
    the format never change on their own.
- Every change is a line in `policy.json`'s history with its evidence, and the week's findings are in
  `data/learning/REPORT.md`. A learning error is reported and never fails a run. Changes to the model itself
  still ship only by the holdout rule (README).

## Paper trials

A market proves itself on paper before any of its plays is published (`scripts/paper.py`, `data/paper/`). The
first trial is basketball totals (NBA from 20 October, college from 1 November): in the backtest the line moved
toward our number from the open, so our side won about 53% graded at the opening number but not at the close
(`docs/HOOPS.md`). At the 11:45 AM, 5:30 PM and 11:30 PM runs the desk records, for every game tipping off in the
next day and a half, the first DraftKings total it sees (through ESPN's odds feed, with the opener and the
prices) and our number; a game where our number is 2 points (NBA) or 3 (college) from that line is a paper play.
Finished games are graded at the number recorded and at the opener, with closing line value against the books'
consensus close, and `data/paper/REPORT.md` keeps the record. Nothing is posted. Promoting a trial to published
plays is a person's decision on the graded record, and the soccer model's Premier League handicaps can follow
the same path.

