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
| `scripts/llm.py`, `scripts/llm_tasks.py` | The local model (Ollama, on this machine), its structured fact judgment, and the two guards on optional prose rewrites: the house style and the numbers guard. It never adds a number. |
| `scripts/x_post.py` | The post text: one shape for every play (player prop, game line, fun parlay), with `data/x-posted.json` as the posted log. |
| `scripts/buffer_post.py` | Scheduling those posts to @keenkooks through Buffer's free plan, around noon on game day, each with its card. |

Nothing here edits an existing file in `research/`, `market-observations/` or a ledger. A quiet run
writes nothing.

## What a run may publish

Exactly what `PROMPT.md` allows, and only when every gate passes:

- **Settlements and closes**: revisions of published picks, graded from the box score or closed to
  new entries when the line moved past the published cutoff. An outcome the code cannot grade (a player
  with no line in the box score, a parlay leg that pushed) is left for a person and named in the log.
- **The daily card** (the owner, 2026-09-28, after a Sunday with no NFL post: "post like 5 plays you like when there
  are multiple games like a Sunday. Monday and Thursday you can just do one play. I want a good mix of game lines and
  player props"): five straight plays on a Saturday or a Sunday, three of a kind at most; one on any other day, and on
  a night with an NFL game, that game's (`gates.card_cap`, counting the day's plays whenever published, apart from one
  pulled before its post). The runs judge candidates best first (`run.rank_card`): by our calibrated number against
  the price (a player's chance shrunk by the league's learned k, 0.2 before there is one), with a paused market, a
  player market where the line has been closer than our projection, or a chance that does not clear its price after
  the rest. Those three rules (`learned_pause`, `prop_market_not_trailing`, `prop_calibrated_value`) order the card
  now instead of refusing; so college props can make the card too. A card prop is priced -200 to +120 (past +120 the
  calibration overstates a plus-money over). One pick per bet, open or closed: a bet the desk closed is never
  published again at another number (`gates.not_duplicate`). Fun parlays and the ladder are apart. (For two days
  before, 2026-09-26 to 28, the rule was "favorites only": three a day at three points; it left NFL Sunday empty.)
- **Model leans**: totals only, a calibrated chance one point or more clear of break-even, at the best expected value
  across the books, none when a starting quarterback is doubtful or worse.
- **Prop leans**: raw chance 60% or better on a settled role, five points clear of the price, never worse
  than -200, three per kickoff window, one per player, never a player listed questionable or worse, never in
  a market where the closing line has been closer than our projection (read live from the scoreboard),
  and never on one book's number unless kickoff is inside three hours. College player props are legal pregame in
  Indiana (the Gaming Commission kept them on 2026-09-24; only in-game college props are barred), so they are judged
  like the NFL's, but a league's player chances publish only once learning has calibrated them against that league's
  own graded lines (`gates.OWN_CALIBRATION`, college until then; see "College player props" below).
- **Longshots**: one a game day from `scripts/parlay.py`.
- **The Kook'n 80/20 Climb**: one bankroll-ladder rung at a time from `scripts/ladder.py` (below), never while a rung is open, one a day.
  Bank 20% of each winning return and ride 80%; never force a rung when fewer than two clean games are available.
  Pick of the Day is independent and may use any qualifying game, including the only game on a slate.
- **Favorites**: only with a verified, sourced reason attached by the run. The web-reading researcher
  that supplies those reasons is off until the owner turns it on, so the desk publishes no favorites yet.

Everything is priced at the quote with the best expected value, not the best-looking number. The
`expiresAt` is the next scheduled run or kickoff, whichever comes first.

The listed book's official settlement outranks a raw box-score grade. Injury protection is applied only when the
book's sourced terms covered that wager, never merely because a player got hurt. A protected parlay leg is voided;
the remaining legs are repriced only from their captured prices. On Sep 27, 2026, FanDuel's automatically applied,
free September Bet Protect+ removed De'Von Achane after his first-quarter injury. Ayomanor and Knox won, so the
easy-props ticket was corrected on Sep 30 from a loss to a +138 two-leg win (0.346u on its 0.25u stake).

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
2. **The news**: the web researcher (`scripts/researcher.py`: `codex exec` with live web search in a read-only
   sandbox since 2026-09-28, when the owner moved to GPT; it runs in its own
   empty folder with a research-only prompt, because run from the repository it had picked up the folder's context
   and spent its turns trying to run code) reads injury,
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

**What can pull a play before it posts** (2026-09-28): on Sunday 2026-09-27 the local model's verdicts came back empty
on long checks, and the fallback rule pulled all three NFL fun tickets (the ladder, the easy parlay, the longshot) on
soft web notes: a receiver "remains in the rotation", a Week 2 snap share, two running backs listed questionable. Now
only hard news can: out, doubtful, inactive, suspended, benched, a lost job (`run.hard`, `run.HARD_NEWS`), or a
flagged forecast for a total. The fallback holds on hard web news only, and a fun ticket's leg stands on soft news
even when the model argues against it (the log says so).

**Moving to GPT** (2026-09-28): the owner moved the desk's AI work from Claude to OpenAI. `AGENTS.md` is the
operating manual Codex reads; `docs/MOVE-TO-GPT.md` has the owner's steps; `deployment/mac/` holds copies of the Mac's
`run.sh`, the launchd jobs and the settings' names. The desk itself never depended on a chat assistant.

## The local model

Ollama serves locally at `http://localhost:11434`. `KEENROUDY_LLM_MODEL` (default `qwen3.8:27b`) handles structured
fact judgment and uses an 8K context. The deterministic, sourced `why` and `risk` templates stay live by default. This
avoids rewriting text that is already complete, saves six calls on a three-play card, and removes a source of subtle
meaning drift. Guarded rewriting is still available for experiments with `KEENROUDY_LLM_POLISH=1`; it uses
`KEENROUDY_LLM_FAST_MODEL` (default `qwen3.5:9b-mlx`) with a 4K context and never receives judgment work. Every
rewrite passes `llm.check_style` (no em or en dashes, plain words, short sentences, no model or version names, no
marketing, no advice) and `llm.numbers_ok` (every number in the text appears in the pick's fields, the desk output or
the facts), or the template stands. A judgment counts only when it points at a fact by id; unsure means hold.
With Ollama down the run publishes on templates and holds on a quarterback rule of thumb. The run status records
only model names, latency, token counts and failures. It never records prompts or answers.

Live web extraction stays on GPT because a local model cannot verify current injuries by itself. The routine
researcher pins `gpt-6-sol` at low reasoning; the code-aware weekly review pins it at medium reasoning. This avoids
using the interactive Codex default for repetitive work while preserving verified URLs and the existing local guards.

## X

X gets plays and their receipts (the owner's call after the first post, a stats line, went out on 2026-09-23
and was deleted): **player props**, **game lines** (spreads and totals) and the day's **fun parlay**, and the
morning after, the **receipt** for those plays. Favorites, model leans, prop leans and the longshot all qualify;
the model scoreboard stays on the site. Every play post has the same shape, drafted by `scripts/x_post.py` from
the pick's own fields:

```
POTD: Iowa/Michigan over 38.5 (-105, ESPN BET)        ("POTD: " on the Pick of the Day only)
We have it at 47.

❤️ if you're tailing
@Playbook #CFB
```

Short and plain, the way a bettor types it (the owner, 2026-09-26: "Not so AI looking. And straight to the point on
the tweets"): the play, the price and book, and our number in a few words ("We have it at 47.", "We have Duke by
14."); no labels, no slogans, no reason sentences (the site keeps the reasons). A fun parlay leads with its price
and book (`x_post.parlay_head`): "🎰 +2506 COLLEGE LOTTO (ESPN BET)" from +1000 up, "🎯 +583 NFL LONGSHOT" under it,
"🍀 +450 NFL EASY PROPS", then its legs one a line ("Iowa/Michigan over 38.5", "Drake London 40+ rec yds"). A ladder
rung: "🪜 KOOK'N 80/20 CLIMB · STEP 2", "$75 → $146 (+95, FanDuel)", "$19 banked · win banks $29, $117 rides",
its legs, "❤️ if you're climbing". Receipts,
the book, the menu and cashed posts stay compact too ("Saturday: 5-3" with ✅ ❌ per play, "✅ Cashed: ...",
"Today: 3 plays.", "📌 Full NFL projections for the slate.").

The reason is one sentence of the pick's own `why`, short and free of the desk's arithmetic words; when
every sentence is arithmetic the post stands on the play and the number. Straight-play units stay off X. A receipt
may identify a fun ticket as 0.25u so followers do not read it as a full-unit play.
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
player props first, then game lines, the ladder, then the parlay, ten minutes apart, and ten minutes from every post
already in the queue (`buffer_post.free_slot`: on 2026-09-26 the 11:45 run put three plays eight seconds after three
queued ones); a late injury after a play is out
cannot pull the post, though the site still closes the pick; a play published later than its time goes out at once unless
kickoff is inside 45 minutes. Buffer takes an image only by URL, so a post is scheduled only once its card is
live on the site: the hosted workflow renders a card for every open play as soon as it is published, the run
schedules after its own push and waits up to 15 minutes for that deploy, and a play whose card is still not
live waits for the next run. Nothing goes out bare.

Discord is downstream of that same path (`scripts/discord_post.py`), not a second publisher. A five-minute launchd
job asks Buffer about posts whose time has passed; only after Buffer says the X post was sent does Discord receive
the exact same text and public card. The mirror downloads that card and uploads it as a Discord attachment, so an
old message does not break when a generated site card rolls out of a later build. Recent receipt card URLs remain
live for eight days as a retry fallback. The mirror state lives beside the Buffer entry in `data/x-posted.json`, so a
later check cannot post it twice. `DISCORD_WEBHOOK_URL` stays only in `~/.config/keenroudy/env`; a failure retries and
alerts the owner's phone through ntfy. Posts that predate this mirror have no payload and are never replayed.

**A post every day** (owner confirmed 2026-09-29; `scripts/receipts.py`, all in the same frame, never a stat line):
daily presence is a publishing rule, not a betting rule. Any useful scheduled post satisfies it. Never relax a play
gate to fill the calendar; if the day has nothing else, the public book closes the gap at 6 PM.

| When (Eastern) | Post |
|---|---|
| 9:00 AM the morning after a game day | **Receipts** for every play of the day, with ✅ ❌ ➖ and the day's record; final-result detail when stored; a 0.25u fun ticket says how many legs hit and calls out a one-leg miss without counting it as a win; on a game day it carries the menu too ("Today: 6 plays."), one morning post instead of two, keyed `receipt:day:<date>+menu:day:<date>` so neither goes out again alone |
| 8:45 AM on a game day with plays and no receipt that morning | **Today's menu**: how many plates, which games and when, never the side; plates go out around noon (card `site/img/kitchen-menu.png`) |
| 9:00 AM Wednesday | **The week's receipts** by kind, with the week's dates |
| Around noon (two hours before a kickoff earlier than 2 PM; never before 9 AM) | **The plays**, the Pick of the Day first |
| Between the first two plays on a multi-play card | **Conversation prompt or teaser**: one short slate question; when a Climb rung or fun ticket is already ready, tease that real post instead (for example, "The 80/20 Climb is back later today. Step 2 is already cooked."); text-only, one relevant league tag, at most once that day. Never added to a single-play day and never followed by automated replies |
| After verified top-player news | **Injury angle**: at most two text-only posts a day. ESPN must list a top QB/RB/WR/TE out, doubtful or inactive; a newer projection must remove them and redistribute the work; and the teammate prop must have a real price captured after the news that still grades as a lean. Add the opponent's allowed-by-position stat when stored. Clearly say it is a board lean, not a posted play; it stays outside the record and never displaces a play or receipt |
| As a win settles (9 AM to 12:30 AM, within three hours) | **Cashed**: "✅ Cashed: Iowa/Michigan over 38.5 (-105, ESPN BET)" (or "✅ POTD cashed: ...", "✅ +2506 5-leg lotto cashed (ESPN BET)"), and the original post quoted by its X link; text only. Losses are not singled out: the morning receipt lists every play, win or lose. The run feeds its own settlements forward (`run.absorb`), so the cashed post goes out from the run that settled it |
| 10:00 AM college Saturday and NFL Sunday | **📌 SAVE THIS**: the week's projection sheet (`scripts/sheet.py`), one 1080x1350 image with the full NFL slate or 16 college games: logos, projected score, win chances, and our spread and total beside the exact captured line, price and book. Numbered mint rings identify up to four markets where our calibrated chance clears the price by the Board's value threshold and label each **SPREAD** or **TOTAL**. Missing, stale, thin, paused and pass prices never get a ring; the rings are watches, not official plays. Never label a moneyline watch without both sides' captured book prices. The complete college slate stays on the site. Drawn by the hosted build (`feed.py`, `cards/sheet-<league>-<date>.png`), posted by the desk once the image is live, never after 11:45 AM. Not picks |
| As a rung wins | **80/20 Climb cashed**: "$75 → $146", "$48 banked. $117 rides step 3."; at $1,000 total bank plus ride, "🪜 80/20 CLIMB COMPLETE", and the phone gets "80/20 Climb complete: pin it" |
| 6:00 PM on a day with nothing else | **The book**: the season record, graded through yesterday and saying so ("Season through Sep 28"), so back-to-back quiet days never post the same words, which X refuses; with one kind of play only the season line (card `site/img/kitchen-book.png`) |

**What works on X** (`learn.post_times`): the weekly learning report adds engagement per thousand views by kind of post
(play, receipt, menu, book, cashed) and by the hour it went out. A report for the owner, not a knob. X posts carry no
links (the card and the bio carry the site).

**Growth without account risk**: `docs/GROWTH.md` is the operating plan for the owner's 10,000-follower stretch goal.
Keep the automated broadcast useful and varied. Never automate replies, likes, follows, unfollows or trending-topic
posts; X requires prior approval for AI reply bots and prohibits non-API website scripting. Human replies during live
football conversations are encouraged because they add a real point of view. Use exactly the relevant `#NFL` or
`#CFB` tag on desk posts, not extra or unrelated trending tags. The Monday review includes settled Buffer reach by
post type; the owner records the account-level Premium snapshot separately because Buffer does not expose follower or
profile-visit totals.

**Discord-only Arb Radar** (`scripts/arbs.py`): after each scheduled capture, compare only exact complementary sides at
the same line, event and market, at different books. Both the saved record and each book update must be fresh, the
game must not have started, and the default locked return must be at least 1%. Qualifying opportunities go only to
Discord with exact equal-return stakes, a move-fast warning and a rule that both listed prices must still be
available or better. They never create an official play or site record, never post to X or ntfy and never place a
wager. The same market/books alert at most once per six hours. Hard Rock is captured as an eighth comparison book without
adding an Odds API request group, but `odds_api.PICK_BOOKS` prevents it from changing official selections. Promo
boosts are personal and absent from feeds: `python scripts/arbs.py boost +298 50 -195` distinguishes a true locked
profit from a break-even-downside free roll.

**SportsGameOdds shadow feed** (`scripts/sgo_shadow.py`): a second, evaluation-only look at fresh NFL/college prices.
It is not an alert source. The key is header-only, every sample first checks the free usage endpoint, and an events
request is allowed only when the service reports the Amateur plan's 2,500-object ceiling. It stops at 1,800 objects,
reserves 700, fetches at most ten events with a six-hour gap and 30-object daily cap, and runs only with a football
game inside 48 hours. Its compact local history lives at `~/.config/keenroudy/sgo-shadow.json`; no key or full API
response is stored. A missing/changed usage limit or any request error fails closed and never stops the desk.

The site's **Kook'n Arb Radar** page (`#arbs`) is public but never shows the candidate feed. It explains the guards and
offers a local two-price equal-return calculator (`core.arbSplit`); no key or price feed reaches the browser. It must
never present an example as currently available or turn a shadow candidate into a public recommendation.

**House-card color** (owner, 2026-10-01): the Kook'n menu, book and other house-owned graphics use midnight
navy/black with electric mint and crisp cyan. Brown, tan, bronze, copper, amber, sepia and muddy burnt orange do not
belong in that system. A real team's supplied colors remain faithful on that team's own play card.

**What's on the plate** (owner, 2026-09-24): an NFL player prop's card shows the player's ESPN headshot, a game line
the teams' logos (a total both, a spread its side), a parlay and the house cards the chef. Images are fetched when
the card is rendered and embedded; a failed fetch falls back to the chef. The photos are ESPN's and the logos the
teams' marks: `KEENROUDY_CARD_ART=0` (or `pick_card.CARD_ART = False`) turns them all off. No straight-play units on X:
play cards show the price and the book only; receipt cards may label the fun-ticket stake.

**One record** (owner, 2026-09-25: "the record is confusing as hell"): every play the desk publishes counts, the
same on the site and on X, whether or not its post went out (a play pulled before its post stays in the record,
graded as posted). The 26 Week 1 player lines imported from a screenshot had no recorded price; at the owner's
request (2026-09-26) a correction report (`research/2026-09-26-NFL-week-1-prices.json`) gives each an assumed -115,
the usual main-line prop price and the one Week 1 price that was recorded, with the line and side from its title.
They count in the record (23-22, -0.44u that day, audited two ways: straight from the reports and through
site/core.js), and the site marks each price "assumed" (`priceAssumed`, `priceNote`); a published price is never
replaced (`build_site.first_of`). The record is the
straight plays' wins and losses; units show on the site only (the owner prefers units to dollars there, 2026-09-26),
one unit a play at the line and price it was published at. Each play's units are written into its settlement when it
is graded (`run.lock_units`, the `units` field) and the site sums the saved figure, so a graded play's units never
move; older plays are summed the same way from their saved prices (no published line, price or result has ever
changed: checked over all 56 plays on 2026-09-26). Fun parlays and the Pick of the Day have their own lines (a Pick
of the Day counts once its post went out, `posted` from `receipts.served`). The Record tab leads with three boxes
(last game day, this week, season), then every play with ✅ ❌ ➖, its price and its units; the tables sit under
"More numbers" (`site/core.js theRecord`, `receipts.counted`). A pick pulled before its post shows "Pulled" and
never the star. The owner pins the big fun-parlay wins by hand: when one cashes, the phone gets "Longshot hit: pin
it" five minutes later, opening the profile (`run.lotto_pings`); nothing on X is clicked by the desk.

**The easy parlay** (`scripts/easy_parlay.py`, owner's ask 2026-09-24: "dumbed down player props for a nice parlay"): on an
NFL day with three or more games left, the run takes DraftKings' and FanDuel's easier alternate lines (receiving and
rushing yards, from The Odds API: two credits a game, once a day, cached four hours in `~/.config/keenroudy/alt-props/`,
never below a 120-credit reserve, never on a rehearsal) and builds one leg per game where our projection clears the
line with room (80%+ on our numbers, 8+ points above the price's own, priced -350 to -150, settled role, not
questionable): three legs at one book paying +150 to +700, "Drake London 40+ receiving yards". A quarter unit, the
longshot's gates (one of each kind a day), kept with the longshots, and never called value: our player chances
are tuned for main lines. Every fun parlay carries an expiry (next run or first kickoff), which the longshot lacked.

**The Kook'n 80/20 Climb** (`scripts/ladder.py`, the owner's calls 2026-09-26 and 2026-09-28: "50 -> 1000 on 1-2 leg
safe bets", then bank 20% of each win): $50 to $1,000 total bank plus ride. Every winning return sends 20% to the
bank (rounded to whole dollars) and the other 80% becomes the next stake; a loss ends the climb but cannot take the
bank. A rung is two legs from different games at
one book (DraftKings or FanDuel), priced -250 to -110 together, built from safer player lines ("Bijan Robinson 50+
rushing yards") in SharpAPI's alternates (`data/prop-odds`, no credits, both leagues): only rungs of the main line's
own ladder (`sharp_odds.consistent`), priced -500 to -180, our projection clearing the line 85% or more and 4 to 18
points above the price's own chance (the price carries the safety; a bigger gap on an easy line is a data or role
problem, not a gift), the book's
main line within 0.6 to 1.6 times our projection, a settled role, nobody on the injury report, prices read within
twelve hours (the feed stamps each game when it reads it, `confirmed` in `data/prop-odds/sharp-status.json`, since the
store only grows when a number moves), games 90 minutes or more from kickoff; the pair with the best joint chance on our numbers wins.
A win splits the payout in whole dollars, a miss starts a new climb at $50, and bank plus next stake reaching $1,000
finishes the climb. Money banked across prior climbs remains visible as saved. The state is never stored:
`ladder.state` (and `site/core.js theLadder`) read it from the rungs and their
results, so it cannot drift. A rung pulled before its X post still counts, win or lose; it is not replaced, and while
ungraded it blocks the next rung. One rung open at a time, one played a day (`gates.ladder_one_rung`); NFL legs only
until learning calibrates college player numbers (college has no injury feed either), then college too, from the 6:45
AM run on. Because every rung uses one leg per game, a one-game slate gets no forced ladder. Pick of the Day remains
independent and may come from any qualifying game. Same-day replacement under a new id (`gates.fresh_id`) is for a
pulled lotto or easy parlay only.

**Alternate lines on every fun ticket** (the owner, 2026-09-28: "you don't have to take the full lines on those
bets"): the ladder, lotto/longshot, easy parlay and any other fun parlay may use a book's alternate line when our
numbers like it at that feed price. Straight plays on the daily card stay on main lines. `run.longshot_alternates`
reuses the SharpAPI records already captured in `data/prop-odds`, so the lotto makes no new Odds API request and
spends no credits. An alternate is a full-game half-point rung from its own market's monotonic ladder
(`sharp_odds.consistent`), never a period or combined market; every ticket stays at one book with one leg per game.
College player legs wait for `CFB/prop` calibration. The NFL easy parlay still runs Sunday, and Saturday's college
version still comes from `easy_parlay.sharp_candidate` (three games at one book, +150 to +700). These are fun
quarter-unit tickets, never called value, and only hard news pulls a leg.

The ladder stays apart from the record in dollars: the site has a ladder card on Today and Record, receipts list a
rung as "80/20 Climb step 2: $75 to $146", and the posts lead "🪜 KOOK’N 80/20 CLIMB · STEP 2" with the return,
the bank and the next ride, on a tall card in the kitchen's own colours with a winding route, the real current rung and deliberately
unpriced future checkpoints. The book's price carries the safety, our
number only agrees with room to spare. A rung with a void leg goes to a person (run.settle names it) and the ladder
waits.

**College player props** (owner, 2026-09-26: "Im not seeing any player props for cfb why not"): two reasons, both
fixed. A rule from the desk's first week said college player props are not offered in Indiana; the Gaming Commission
voted on 2026-09-24 to keep pregame ones, so `gates.cfb_jurisdiction` now only asks for a book available there. And
the board built player rows from ESPN's feed of DraftKings lines, which carries NFL players only: college rows now
come from the priced feed's own main numbers (`build_site.feed_captures`, `sharp_odds.main_lines`), matched to our
projections by name. Our college player numbers had never been graded against a line (98 graded on 2026-09-26: 55%
won against a 66% average raw chance, as overconfident as the NFL's were), so they wait for their own calibration:
learning grades every college projection against those lines (`scoreboard.feed_lines`) and ships a `CFB/prop` k after
300 when it predicts better than the raw chance. Until then the board shows college rows as "Grading first" and the
gates refuse them (`prop_calibrated_value`), which records each refusal for learning. The scoreboard's closer-than-line
gate stays the NFL's.

**The prop price feed** (SharpAPI, `scripts/sharp_odds.py`): its event list is every sport's events soonest first
unless filtered; on 2026-09-26 one page of 200 held none of Sunday's NFL games and 6 of 52 college games, so most games
were never priced. It now asks for upcoming events at DraftKings and FanDuel only (33 NFL, 58 college), and a college
team is found by its school as well as its full name (the feed writes "Oklahoma", the slate "Oklahoma Sooners"; a
short alias list covers "Connecticut", "Miami Ohio" and the like), which took college matches from 4 of 49 to all of
them. Reading every game takes the full sixty requests (about five and a half minutes), so a build started by a push,
usually the desk waiting for its cards, reads fifteen (`SHARP_REQUESTS` in the workflow) and the scheduled builds read
the rest. Combined and
longest-play markets are no longer read as the plain stat ("passing + rushing yards" was being filed as passing
yards), and a book's alternates keep only the main line's own ladder: DraftKings filed first-half and other period
ladders under the full-game market (Mahomes 14.5 to 49.5 passing yards beside a 222.5 main line).

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
Pick of the Day post at the same time once its card is live (`run.feature_scheduled`). Its post leads the noon batch with a precise kicker such as "PICK OF THE DAY · GAME TOTAL" and its own card
(`cards/<id>-potd.png`, rendered by the hosted build, so a post never carries a stale copy), and the site's Today page
leads with it, starred.

**Receipts** (`scripts/receipts.py`) make it a post every day of the season. At 9:00 AM ET the morning after a
game day, once every play of that day is settled, the receipt lists each with ✅ ❌ ➖ and the day's record (the
straight plays' wins and losses; a fun parlay is listed at its smaller 0.25u stake but kept out of it). Stored finals
make the report more useful; a settled parlay says how many legs hit and, when true, that it missed by one leg. It is
still a loss. The tall navy/mint card says "Graded in public, win or lose." On
Wednesday at 9:00 AM the week's receipt sums the seven days before it by kind. Losing days post too. Every play the
desk published counts (`receipts.counted`, the same plays as the site's record), and a receipt not ready by 8:00 PM
the next day is skipped. Plays are named as their posts named them (schools by name).
A line break ends a sentence for the style check, so a long list is short lines, not one long sentence; a post that
fails its check anyway is named in the run log and on the phone, never dropped silently. Its tall report card uses
the kitchen's navy/mint (`pick_card.receipt_svg`), with W, L or P beside each play and the chef in the header.

Every post is logged in `data/x-posted.json` (kind `buffer:*`, committed on its own as "Posts <date> <time>
ET") so nothing goes out twice; new entries also hold the exact public caption, card URL and Discord delivery state.
Once its time has passed the run records the X link it went out under, or the failure (which fails the run, so the
heartbeat alerts). A play that closes before its time is cancelled, and
the channel's own daily limit (50) is respected, with ours at twenty a day, counting what is already queued.

The Kook'n Sports Discord has a dedicated public feed, separate community and sportsbook-offer channels, and a
read-only links/resources index. Confirmed official plays go there first from the Buffer schedule: `readyAt` is 15
minutes before X, and the five-minute delivery job normally makes the real lead 10-15 minutes. Receipts, news and
engagement posts still wait for X confirmation. The same words and card go to both. Once Discord publishes a play,
it is public and remains in the append-only record. If confirmed hard news closes it before X, Buffer cancels X and
Discord receives a pull update; the play is still graded. Referral offers are not ordinary play copy: use only the
owner's exact URL, say plainly that Kook'n may receive a bonus, include age/location/terms language, and keep the
offer in its dedicated channel. Never guess a referral URL or claim a bonus whose current terms have not been checked.

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

## The site (2026-09-26)

For one night the site had three tabs (Picks, Record, Numbers); the owner preferred the Today page and the Board
where they were, so the tabs are Today, Board, Games, Stats, Record, More again. What stayed from the rework: plays
first on Today as cards in the X post's words (the Pick of the Day on top, "Open" with the age of its price until
kickoff, "Pulled" for a play pulled before its post), the one record in units on the Record tab, and games laid out
as **projection cards** like the projection posts the owner likes (Toad Sports' weekly grid): both teams with their
ESPN logos, our projected score big with the total and kickoff, our win probability as a bar in the teams' colours
(ESPN's, from the slate or `data/team-colors-cfb.json`, fetched once for every college team; a near-black colour uses
its alternate), and our spread and total against the line with the side our number likes and its chance. Names wrap
under their logos (the old game rows cut them off on phones). The Games tab and Today's "Our projections" and "In play
now" use the cards.

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
`KEENROUDY_RESEARCHER=codex` (OpenAI's Codex CLI, signed in with the owner's ChatGPT plan; any other value turns it off);
then, at the runs that publish on game days, it asks that command line (headless, web search only, answering to a
JSON schema) for sourced facts about the strongest candidates, fetches every
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

Before MLB or NHL has a model, `scripts/market_lab.py` builds the price history that a model will have to beat. At
the same three silent-trial runs it records the first supplied DraftKings full-game total, moneyline and run/puck
line, appends a snapshot only when that market changes, and joins the final score later. The append-only records and
ledger live in `data/market-lab/`; `site/data/market-lab.json` gives the public Lab honest coverage counts. It never
predicts a side, applies sport-specific settlement, becomes a play, or calls a metered service. Those missing layers
are promotion gates, not details to infer from the score.

## Multi-sport score center and Lab

`scripts/sports_refresh.py` uses ESPN's public scoreboards for NBA, WNBA, men's college basketball, MLB, NHL, the
Premier League and MLS. It requests today and the next two Indianapolis calendar dates, preserves each league's last
good snapshot independently and supplies no odds or picks. The site's `#scores/<league>` pages display that data;
`#lab` explains the actual stage of every sport. A score feed is factual coverage, never evidence of a betting edge.
This expansion adds no call to The Odds API, SharpAPI or SportsGameOdds and does not change their free-plan budgets.
