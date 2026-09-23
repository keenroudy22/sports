# Mac Studio setup and model rebuild

Paste everything below the line into Claude Code on the Mac Studio, in an empty directory where
you want the repo to live.

---

You are setting up the KeenRoudy Sports research desk on a new Mac Studio and then rebuilding the
parts of its model that the owner has correctly identified as too thin. The project is an NFL and
FBS football stats engine graded against the betting market, published at
https://keenroudy.com/sports/ from the repo `keenroudy22/sports`. It is for the owner and their
friends, entertainment only: nobody places these bets and nobody should read them as advice.

Work the phases in order. Each ends in a check. Do not start a phase before the previous check
passes, and tell me plainly when one fails instead of working around it.

## Phase 0: what is already true, so you do not re-derive it

- **No third-party Python packages.** Every script is standard library: `json`, `urllib`, `pathlib`,
  `statistics`, `zoneinfo`. There is no virtualenv to rebuild and no lockfile to go stale. Keep it
  that way, including the local model client in Phase 5.
- **The hosted GitHub workflow runs whether the Mac is awake or not.** Captures, forecasts and the
  deploy happen on GitHub's runners six times a day. The Mac is where research and publishing
  happen, not where the data lives.
- **The record is the thing to protect.** `tests/test_integrity.py` hashes every published file.
  If it passes after cloning, the move is clean. If it ever fails, something was rewritten, and the
  fix is to undo the rewrite, never to regenerate the ledger.
- **The append-only stores are hashed line by line**, so a CRLF conversion breaks every ledger.
  `.gitattributes` pins `*.jsonl` to LF. Verify it rather than trusting it.

## Phase 1: environment

Confirm and install with Homebrew what is missing: Python 3.12 or newer, Node 18 or newer, `git`,
and the GitHub CLI `gh`. Nothing else.

**Check:** print the versions.

## Phase 2: clone and prove the record survived

1. `gh auth login` as `keenroudy22`, then clone. About 70 MB.
2. Confirm `*.jsonl` files came down with LF endings.
3. `python3 -m unittest discover -s tests` expects 222 passing.
4. `python3 -m unittest tests.test_integrity -v` on its own.
5. `node --test tests/` expects 25 passing.
6. `python3 scripts/refresh.py` then `python3 scripts/build_site.py`.

**Check:** all green, and `git status` clean apart from the gitignored build output in
`site/data/app/`. If the integrity test fails here, stop and tell me.

## Phase 3: move the publishing rules out of prose and into code

Today the rules live in English in `PROMPT.md` and a language model applies them by hand every run.
That has already failed on the record: on 2026-09-21 three picks went out on a single book's number
and all three finished holding the worst number available. The rule that would have caught it
existed only as a sentence.

Build `scripts/gates.py`, one function per rule, each taking a candidate pick and the current board
and returning a pass or a refusal with a reason. Test each in `tests/test_gates.py`.

In force today:

- **Model lean bar.** A total, never a spread. Calibrated chance clears break-even by one point or
  more. Priced at its best book. Nothing sourced arguing against it. Four a day.
- **Prop lean bar.** Raw read of 60% or better on a settled role, meaning three games this season or
  eight or more for the same team last season, and five points clear of the price. Three per kickoff
  window, one per player, never worse than -200, never a player listed questionable or worse.
- **One book.** Refuse when only one book has posted a market, unless kickoff is inside three hours.
- **Rank quotes by expected value, not by number.** The board picks the best number then the best
  price at it. On 2026-09-23 that surfaced BetRivers 53 at -113 worth 2.1 points when ESPN BET 52.5
  at -105 was worth 4.0. Rank by the desk's `evPerUnit`.
- **Check a pick's move against the book it was taken at.** `scripts/desk.py` prices an open game
  pick from the relayed ESPN feed, which carries DraftKings only, while a prop is checked against the
  multi-book capture. On 2026-09-23 that reported our ESPN BET pick at DraftKings's price. It can
  report a close that has not happened, and it can miss one that has. Check the pick's own book from
  the capture, and fall back to the feed only when that book has no current quote.
- **Cutoffs and expiry.** A pick closes to new entries when the line passes its published cutoff.
  Never re-price, never extend an expiry, never void a pick because the line moved.
- **Never publish on a started game.** Check kickoff against the clock at publish time.
- **Data sanity.** A line the game cannot produce, such as a completions line above the attempts
  line, is a data error and not an edge.

Two more are recommended and not yet adopted. Build both, default on, and tell me they are on:

- **No prop lean in a market where our projection trails the closing line.** As of the week 2 review,
  across 538 graded player markets the book's line is closer than our projection in six of seven.
  Receiving yards is worst at 66 of 158, and that is where most prop leans were published. The
  programme went 2-7 and lost 4.23 units in week 2. Read the live numbers from
  `site/data/scoreboard.json` rather than hard-coding the market list, so it reopens on its own.
- **No model lean on a total when either starting quarterback is doubtful or worse.** Until Phase 4b
  lands, the team total has no quarterback input at all.

**Check:** replay every pick in `research/` through the gates and show me which would have been
refused and why. It should refuse the three props published on 2026-09-21 on the one-book rule.

## Phase 4: the model

This is the real work. The owner's judgment is that the numbers rest on too few things and lean on
last season as though nothing changed. Both halves of that are correct, and here is exactly how.

### What the score model uses today

`scripts/model_v2.py` fits two sets of team ratings per forecast, as recency-weighted ridge
regressions over the stored box scores:

- **margin ratings** on points actually scored;
- **total ratings** on a blend of points and efficiency-implied points, from success rate, explosive
  plays, pace, turnovers and red-zone drives.

Plus home field, an FCS group rating for college, and for NFL margin a 50% blend of the older Elo.
Its own docstring says the rest: *no market, injury or weather input; the market is only the
yardstick.* Injuries touch player volume only, in `scripts/projections.py`, where a player ruled out
is removed and a questionable player is cut to 75% of their share. Nothing about a quarterback
change, a new coordinator, a rebuilt secondary or the weather reaches the team number.

### 4a: per-team continuity instead of one global discount

This is the owner's main point and it has a precise home. `scripts/model_v2.py` weights every
historical game on one line:

```python
weight = 0.5 ** (max(age, 0.0) / params['halfLife']) * params['priorWeight'] ** (season - row['season'])
```

`priorWeight` is a single scalar per league per market: NFL margin 0.6, NFL total 0.3, CFB margin
0.3, CFB total 0.6. Last season is already discounted, so the model is not naive. But it applies the
same discount to a team that returned everyone and a team that fired its coordinator and lost six
starters, which is exactly the objection.

**Before you reach for the obvious fix, know that it was tested and it failed.** On 2026-09-19 the
weight was questioned and removing last season entirely made the model worse on the 2025 walk-forward
weeks 1 to 4: FBS margin miss went 13.4 to 16.5, NFL totals 11.5 to 19.2. A 10% prior was also
worse. So the answer is not less of last season. It is last season weighted per team.

Build a continuity score per team, per season, per side of the ball, computed strictly as of the
forecast cutoff with no future leakage:

- **NFL:** `data/nflverse/` holds per-game player data with snap counts back to 2023. For each team,
  measure the share of last season's snaps belonging to players who have appeared for that team this
  season. Keep offense and defense separate, since the owner's concern is specifically defenses.
- **College:** there is no snap feed. Use appearances weighted by usage from the box-score store and
  expect it to be cruder. Say so in the output rather than implying a precision it does not have.

Then let continuity modulate the per-season discount, so a team with high returning production keeps
more of last season and a rebuilt team keeps less. Add a coaching-change term only if you can source
it reliably; do not hand-maintain a list that will rot.

**This must earn its place.** Run `python3 scripts/model_v2.py tune` on 2024 with 2023 as prior, hold
out 2025 untouched, and ship only if it beats the current parameters on the holdout. Changing
`PARAMS` without releasing a new `VERSION` fails the tests by design, so bump the version and record
the tuning output under `data/model/`.

### 4b: injuries in the team number, not just player volume

Three totals in week 3 were passed by hand because our number could not see a quarterback change:
Seahawks at Commanders with Jayden Daniels doubtful, Titans at Giants with Jaxson Dart doubtful, and
the market had moved those totals six points while our number had not moved at all.

Start with the quarterback, because it is the largest single effect and the easiest to measure. From
the stored history, find games where a team's usual starter did not play and measure the actual
difference in points scored and allowed. Fit an adjustment from that, apply it when the listed
starter is doubtful or out, and carry the uncertainty rather than pretending to a point estimate.
Then consider a smaller term for a team missing several starters on one side.

Until it is fitted and passes the walk-forward, keep the Phase 3 gate that refuses those games.

### 4c: weather

Not in the model at all. Wind is the input that moves a total. Add a wind and precipitation
adjustment for outdoor venues, fitted on history, from a free forecast source such as the National
Weather Service. Note that the game files currently carry a null venue, so you will need a venue and
dome table first.

### 4d: the market, and why it stays a yardstick

The owner asked for Vegas lines to be taken into account, and there is a trap here worth stating
plainly before you build anything.

If you blend the market into the model, the model can no longer be honestly graded against the
market. Closing line value, the record against the close, and the whole scoreboard lose their
meaning, because the number being graded would contain the thing it is being graded against. The
honest grade is the entire point of this project.

So keep the score model market-free, and build the market read as a separate, visible layer in the
research and on the board:

- the opening number, the current number, and the direction and size of the move;
- which books disagree and by how much;
- where our gap against the line sits in the historical distribution of our gaps, since a large gap
  is more often our error than the market's;
- when a move followed a sourced event, name the event.

That answers "why does this line look good" with evidence, without corrupting the grade.

### 4e: news and press releases

This is the one genuine job for a local model. Have it read team releases and beat reporting,
propose structured facts with a source URL and a retrieval time, and stop there. The pipeline
validates a proposal against the official injury report where one exists. Where none exists, as in
college, the proposal stays a proposal that a gate or a human confirms. Extracted text must never
become a number in the record.

### 4f: the pre-kickoff freeze

`scripts/forecast.py` publishes no new snapshot inside 60 minutes of kickoff. On 2026-09-21 that left
the last Rams snapshot holding Puka Nacua at 75% of his share when he was in fact inactive, so every
Rams receiving number was wrong and the game had to be stood down entirely.

Allow a late snapshot marked `late: true`, excluded from the model-versus-close scoreboard so the
grading stays clean, but usable for a pick.

**Check for the whole phase:** for each change, show me the walk-forward result before and after on
the untouched holdout season. Anything that does not beat the current numbers does not ship, and I
want to be told that plainly rather than have it shipped anyway.

## Phase 5: the local model

Almost nothing here needs a language model, and being precise about that is what makes a local one
work. After Phase 3 the rules are code and after Phase 4 the numbers are fitted. What is left is
prose, the news reading in 4e, and drafting posts.

1. Install Ollama with Homebrew and start it.
2. Check unified memory and pick a model that fits with room to spare. For prose at this length a 14B
   is enough, a 32B is comfortable on 48 GB or more, a 70B wants 64 GB or more. Tell me what you
   picked and why.
3. Write `scripts/llm.py` against Ollama's OpenAI-compatible endpoint at
   `http://localhost:11434/v1/chat/completions` using `urllib`, so the zero-dependency property
   holds. Short timeout, and raise rather than silently returning empty prose if Ollama is down.
4. Put the house style in the system prompt: no em dashes or en dashes anywhere, plain words, short
   sentences, no model-version names in anything a reader sees, and never a number that did not come
   from the pipeline. Add `tests/test_llm_style.py` that fails on a dash, an invented figure, or
   marketing language.
5. Add a numbers guard: before generated prose is written into a report, extract every number in the
   text and assert each appears in the pick's own fields or the desk output. A hallucinated stat
   should fail the run, not reach the record.

**Check:** generate a `why` for the open pick, Iowa at Michigan over 38.5 at ESPN BET -105, and show
me the text and the guard result.

## Phase 6: X posting

The account is @keenkooks. Only researched favorites go to X. Model leans, prop leans and longshots
never do.

1. I will create an X developer app and give you the four OAuth 1.0a credentials. Set the app to Read
   and Write **before** generating the access token; a token minted while the app was read-only fails
   to post with an error that does not explain itself.
2. Credentials go in the login shell environment, never in the repo.
3. Write `scripts/x_post.py` that builds a draft from an open favorite (the line, the price, one or
   two short reasons taken only from that pick's own `why`, and https://keenroudy.com/sports/),
   enforces the voice (casual, short, under 280 characters, no dashes, nothing not in the record),
   and refuses if the game has started, if the pick is past its `expiresAt`, if it is not a favorite,
   or if its id is already in the posted log.
4. **Move the posted log into the repo** at `data/x-posted.json` and commit it. Today it lives in a
   temporary scratchpad that does not survive a session, so the only thing preventing a double post
   is that a human remembers. Seed it with the two ids posted on 2026-09-19,
   `CFB-2026-W3-tamu-minus-16-5-vs-uk-dk` and `CFB-2026-W3-duke-minus-10-vs-stan-dk`.
5. Default to a review gate: write the draft to a file and post only with `--confirm`. Build the
   autonomous path but leave it off, and ask me before turning it on.

**Check:** produce a draft, show the text and character count, and prove the refusals work against a
started game and an already-posted id. Post nothing.

## Phase 7: scheduling

Runs are 6:45, 8:30, 11:45, 17:30 and 23:30 Eastern, plus 14:45 Sundays and 18:50 before a night
game. `PROMPT.md` has the table.

Use `launchd`, not `cron`. Pin the timezone explicitly rather than assuming the machine is Eastern.
Set the Mac never to sleep. Log each run to `~/Library/Logs/` so a failure leaves evidence.

One behaviour to fix: between Tuesday and Thursday of a normal week there are no games and nothing to
publish. Write a report only when something settled, closed, published, or changed materially.
Filing near-identical empty reports clutters a record whose whole value is that it is readable.

**Check:** show me the plist and one job firing on a short test interval before you set real times.

## What not to do

- Never modify, delete or regenerate `research/*.json`, `site/data/forecasts.json`,
  `market-observations/*.json` or `tests/integrity-ledger.json`.
- Never rewrite a published pick. A correction is a new dated report reusing the pick id.
- Never invent a price, line, availability or edge. Sourced with a URL and a retrieval time, or it
  does not get published.
- Never put an API key in the repo, a log or a stored URL.
- No scraping sportsbooks.
- Never ship a model change that did not beat the current numbers on an untouched holdout.
- Fewer picks is a successful run. There is no quota.
