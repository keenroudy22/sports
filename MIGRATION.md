# Moving KeenRoudy Sports to the Mac Studio

Everything below the line is the prompt. Paste it into Claude Code on the Mac, in an empty
directory where you want the repo to live.

Three things to know before you start, because they shape the whole plan:

- **The pipeline has no third-party Python packages.** Every script runs on the standard library.
  There is no virtualenv to recreate, no `pip install`, no lockfile to go stale. Python and Node
  and a clone are the entire dependency list.
- **The hosted GitHub workflow keeps running whether the Mac is awake or not.** Captures, forecasts
  and the deploy happen on GitHub's runners on their own schedule. The Mac is where research and
  publishing happen, not where the data lives. If the Mac is off for a day, nothing is lost.
- **The record is the thing to protect.** `tests/test_integrity.py` hashes every published file.
  If it passes on the Mac after cloning, the move is clean. If it ever fails, something was
  rewritten and the fix is to undo the rewrite, never to regenerate the ledger.

---

You are setting up the KeenRoudy Sports research desk on a new Mac Studio. The project is an NFL
and FBS football stats engine graded against the betting market, published at
https://keenroudy.com/sports/ from the repo `keenroudy22/sports`. It is for the owner and their
friends, entertainment only: nobody places these bets.

Work through the phases in order. Each one ends in a check. Do not start a phase until the
previous check passes, and tell me plainly if one fails rather than working around it.

## Phase 1: environment

Confirm, and install what is missing with Homebrew:

- Python 3.12 or newer (`python3 --version`). CI pins 3.12; the old machine ran 3.14. Either is fine.
- Node 18 or newer (`node --version`). Node is only used to run the browser-script tests.
- `git` and the GitHub CLI `gh`.

There are no Python packages to install. If you find yourself writing a `requirements.txt`, stop
and re-read `scripts/` first: everything is `json`, `urllib`, `pathlib`, `statistics`, `zoneinfo`
and friends. Keeping it that way is a design goal, not an accident. Anything you add later should
also be standard library, including the local model client in Phase 4.

**Check:** print the three versions.

## Phase 2: clone and prove the record survived

1. `gh auth login` as `keenroudy22`, then clone the repo. It is about 70 MB.
2. Confirm `.gitattributes` is in place and that `*.jsonl` files came down with LF endings. The
   append-only stores are hashed line by line, so a CRLF conversion would break every ledger. On
   the Windows machine git kept warning about this; on macOS it should be silent.
3. Run the full Python suite: `python3 -m unittest discover -s tests`. Expect 222 tests passing.
4. Run the integrity test on its own: `python3 -m unittest tests.test_integrity -v`.
5. Run the browser tests: `node --test tests/`. Expect 25 passing.
6. Run `python3 scripts/refresh.py` then `python3 scripts/build_site.py`. The build writes about
   440 page files into `site/data/app/`, which is gitignored and rebuilt on every deploy.

**Check:** all tests green, and `git status` clean afterwards except for the ignored build output.
If the integrity test fails here, stop and tell me. It means the clone is not faithful.

## Phase 3: move the rules out of prose and into code

This is the most valuable part of the migration, so do it before the model work.

Today `PROMPT.md` describes the publishing rules in English and a language model applies them by
hand on every run. That has worked, but it has also failed in ways the record shows: three picks
went out on a single book's number on 2026-09-21 and all three finished holding the worst number
available. The rule that would have caught it existed only as a sentence.

Build `scripts/gates.py`: one function per rule, each taking a candidate pick plus the current
board and returning a pass or a refusal with a reason. Write tests for each in
`tests/test_gates.py`. The rules currently in force, with where they came from:

- **Model lean bar.** A total, never a spread. Calibrated chance clears break-even by at least one
  point. Priced on the board at its best book. Nothing sourced arguing against it. Cap four a day.
- **Prop lean bar.** Raw read of 60% or better on a settled role, meaning three games this season or
  eight or more for the same team last season, and five points clear of the price. Cap three per
  kickoff window, one per player, never worse than -200, never a player the injury report lists
  questionable or worse.
- **One book.** If only one book has posted a market, refuse unless kickoff is inside three hours.
  Say so in the quote note. This is the 2026-09-21 lesson.
- **Best quote by expected value, not by number.** The board currently picks the best number and
  then the best price at it. On 2026-09-23 that surfaced BetRivers 53 at -113 for a 2.1 point edge
  when ESPN BET 52.5 at -105 was worth 4.0. Rank candidate quotes by the desk's `evPerUnit`.
- **Cutoffs and expiry.** A pick closes to new entries when the line passes its published cutoff.
  Never re-price, never extend an expiry, never void a pick because the line moved.
- **Never publish on a started game.** Check kickoff against the clock at publish time.
- **Data sanity.** A line the game cannot produce, such as a completions line above the attempts
  line, is a data error and not an edge.

Two rules are recommended and not yet adopted. Implement both behind a flag, default on, and tell
me they are on:

- **No prop lean in a market where our projection trails the closing line.** As of the week 2
  review, across 538 graded player markets the book's line is closer than our projection in six of
  seven markets. Receiving yards is the worst at 66 of 158, and receiving yards is where most prop
  leans were published. That programme went 2-7 and lost 4.23 units in week 2. The gate should read
  the live numbers out of `site/data/scoreboard.json` rather than hard-coding the market list, so it
  reopens on its own if the projection improves.
- **No model lean on a total when either starting quarterback is doubtful or worse.** The team total
  comes from the margin and total model, which has no quarterback input at all; the injury report
  only scales player volume. Three totals in week 3 were passed by hand for this reason.

**Check:** `tests/test_gates.py` passes, and a short script replays the week 2 and week 3 picks from
`research/` through the gates and prints which ones would have been refused and why. I want to see
that output. It should refuse the three Monday props on the one-book rule.

## Phase 4: the local model

Almost nothing here needs a language model, and being precise about that is what makes a local one
viable. The hard rule in `PROMPT.md` already says it: the model writes explanation, never data.
Projections, chances, edges and cutoffs come from `scripts/desk.py`. Prices come from a capture.
Stats come from the box-score store. After Phase 3 the rules come from code. What is left for a
model is prose and judgment:

- the `summary`, `takeaways`, `why` and `risk` text in a research report;
- the draft of an X post;
- reading an injury report or a news item and saying whether it argues against a candidate.

The first two a small local model does well. The third is genuine reasoning and is where a local
model will be weakest, so build it to hand that judgment back to me when it is unsure rather than
guessing.

1. Install Ollama with Homebrew and start it.
2. Check the machine's unified memory and pick a model that fits with room to spare. For prose at
   this length a 14B is enough; a 32B is comfortable on 48 GB or more; a 70B needs 64 GB or more.
   Tell me what you picked and why. Pull it and confirm it answers.
3. Write `scripts/llm.py` as a thin client against Ollama's OpenAI-compatible endpoint at
   `http://localhost:11434/v1/chat/completions`, using `urllib` so the zero-dependency property
   holds. Give it a `draft(system, user, max_tokens)` function, a short timeout and a clear failure
   mode: if Ollama is not running, raise rather than silently returning empty prose.
4. Write the house style into the system prompt: no em dashes or en dashes anywhere, plain words,
   short sentences, no model-version names in anything the reader sees, and never a number that did
   not come from the pipeline. Add `tests/test_llm_style.py` that runs a few fixed prompts and fails
   on a dash, on an invented figure, or on marketing language.
5. Add a numbers guard: before a generated `why` or `risk` is written into a report, extract every
   number from the text and assert each one appears in the pick's own fields or the desk output.
   A model that hallucinates a stat should fail the run, not reach the record.

**Check:** generate a `why` for the currently open pick, Iowa at Michigan over 38.5 at ESPN BET
-105, and show me both the text and the numbers-guard result.

## Phase 5: X posting

The account is @keenkooks. Only researched favorites go to X. Model leans, prop leans and longshots
never do, and that rule predates this migration.

1. I will create an X developer app and give you the four OAuth 1.0a credentials. Set the app to
   Read and Write **before** generating the access token; a token minted while the app was read-only
   will fail to post and the error will not say why. The free tier's monthly post cap is far above
   what this account will use.
2. Store the credentials in the login shell environment, never in the repo. `.env` is already
   gitignored; if you use one, confirm it is ignored before writing anything into it.
3. Write `scripts/x_post.py`:
   - builds a draft from an open favorite: the line, the price, one or two short reasons taken only
     from that pick's own `why`, and the link https://keenroudy.com/sports/;
   - enforces the voice: casual, short, under 280 characters, no dashes, nothing that is not in the
     record;
   - refuses to post if the game has started, if the pick is past its `expiresAt`, if the pick is not
     a favorite, or if its id is already in the posted log;
   - appends `{id, postedAt, tweetId}` to the log on success.
4. **Move the posted log into the repo** at `data/x-posted.json` and commit it. Today it lives in a
   temporary scratchpad directory that does not survive a session, which means the only thing
   stopping a double post is that a human remembers. Seed it with the two ids already posted on
   2026-09-19: `CFB-2026-W3-tamu-minus-16-5-vs-uk-dk` and `CFB-2026-W3-duke-minus-10-vs-stan-dk`.
5. Default to a review gate: the script writes the draft to a file and posts only when run with
   `--confirm`. Build the autonomous path but leave it off. Ask me before turning it on, and when
   you do ask, tell me what happens if the model drafts something wrong at three in the morning.

**Check:** produce a draft for a hypothetical favorite, show me the text and the character count,
and prove the refusals work by running it against a started game and against an already-posted id.
Do not post anything.

## Phase 6: scheduling

The runs are 6:45, 8:30, 11:45, 17:30 and 23:30 Eastern, plus 14:45 on Sundays and 18:50 before a
night game. `PROMPT.md` has the table and what each run is for.

Use `launchd`, not `cron`: it handles reboots properly and gives real logs. A Mac Studio is a
desktop, so set it never to sleep, and have each job log to a file under `~/Library/Logs/` with the
run's output so a failed run leaves evidence.

Each job runs `claude -p` headless against `PROMPT.md`. Two things the old setup got wrong that you
should fix:

- **Timezone.** The schedule is Eastern and the machine may not be. Pin it explicitly rather than
  assuming.
- **An empty run should stay quiet.** Between Tuesday and Thursday of a normal week there are no
  games and nothing to publish, and filing near-identical "nothing happened" reports clutters a
  record whose whole value is that it is honest and readable. Write a report only when something
  settled, closed, published, or changed materially.

**Check:** show me the plist, load one job, and show me it firing once on a short test interval
before you set the real times.

## Phase 7: carry-over

Three improvements are agreed in principle and not built. In priority order:

1. **Weight a player's projected share by recent snap share, not by last season's role.** Two losses
   on 2026-09-21 came straight from this. Theo Johnson projected 26.5 receiving yards on 3.5 targets
   while playing 46% of snaps behind Isaiah Likely, and caught none of four targets. Devin Singletary
   projected 27.2 rushing yards as the third back in a four-way split and ran three times for 9 yards.
   Test it on the 2025 walk-forward with `scripts/calibrate.py` before it touches a live number.
2. **Calibrate the player curve the way game lines are calibrated.** Player chances are published raw
   because there was no graded history to shrink them with. There is now a little, and it points one
   way. If SharpAPI's closing-odds endpoint reaches back into last season, grade every 2025 player
   projection against a real closing line and fit the shrink.
3. **Give every pick a shareable page**, a `#pick/<id>` route that opens the card with the last-ten
   chart and the matchup, so a post can link straight to the reasoning.

Do not start these until Phases 1 through 6 are done and checked.

## What not to do

- Never modify, delete or regenerate `research/*.json`, `site/data/forecasts.json`,
  `market-observations/*.json` or `tests/integrity-ledger.json`. If the integrity test fails, you
  broke something; undo it rather than regenerating the ledger.
- Never rewrite a published pick. A correction is a new dated report that reuses the pick id.
- Never invent a price, a line, an availability or an edge. Sourced with a URL and a retrieval time,
  or it does not get published.
- Never put an API key in the repo, a log or a stored URL.
- No scraping sportsbooks. Prices come from the capture APIs or from reading a page the way a person
  would, one market at a time.
- Fewer picks is a successful run. There is no quota.
