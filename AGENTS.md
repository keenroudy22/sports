# AGENTS.md: running and changing the KeenRoudy Sports desk

Codex (or any coding agent) reads this first. It is the whole job in one place: what the desk is, the rules that
never bend, where everything lives, how to change and deploy it, and the owner's current decisions. The long
history and every mechanism in detail are in `DESK.md`; the research rules in `RESEARCH.md` and `PROMPT.md`.

## What this is

An automated sports picks desk for college football (CFB) and the NFL, entertainment only. It publishes plays to
https://keenroudy.com/sports/ (this repo, GitHub Pages) and posts them to X as @keenkooks through Buffer, and grades
every play in public, win or lose. Nobody should read anything here as betting advice, and nothing the desk writes
may say otherwise.

Three things run it, none of them an AI chat:
1. **launchd on the owner's Mac Studio** runs `~/.config/keenroudy/run.sh` (copy: `deployment/mac/`): the desk run
   at 6:45, 8:30 and 11:45 AM, 5:30 and 11:30 PM Eastern (plus 2:45 PM Sunday and 6:50 PM Sunday, Monday, Thursday),
   the pre-post check every 30 minutes, and the heartbeat at 7:15 AM. The run settles and closes plays, builds the
   board, judges candidates through `scripts/gates.py`, publishes reports to `research/`, pushes, and schedules X
   posts in Buffer. Logs: `~/Library/Logs/KeenRoudy/run-YYYY-MM-DD.log` (times in UTC).
2. **GitHub Actions** (`.github/workflows/publish.yml`) on a schedule and on every push: captures scores, odds and
   prop prices, publishes model forecasts, grades against the close, builds the site and the cards, and deploys.
3. **Local models on the Mac**: Ollama (`KEENROUDY_LLM_MODEL`, default `qwen3:32b`) polishes prose and weighs news;
   the web researcher (`scripts/researcher.py`) reads the news on game days through `codex exec` (GPT, the owner's
   ChatGPT plan) when `KEENROUDY_RESEARCHER=codex`.

Your job as the agent is what a person would do: answer the owner's questions, change the code, deploy it safely,
watch the runs, and fix what breaks.

## Talking to the owner

- Plain words, short sentences, the answer first. No jargon ("CLV", "calibration") without saying what it means.
- Use they/them for the owner.
- The owner delegates ("do what you think makes the most sense and get it done") but decides anything public: new
  post types, how the record counts, how many plays go out. Ask when a choice changes what followers see.
- Say plainly when something failed, including your own mistakes, and what you did about it.

## Rules that never bend

- **Separate from MyGolfLinks (MGL).** Never touch `com.mygolflinks.*`, `~/.mgl`, `~/.config/mgl`, `~/Library/Logs/MGL`,
  or the `cd2324-lgtm` GitHub login. Everything sports lives in the `keenroudy22` account.
- **Every commit and push as `keenroudy22`:** `GH_CONFIG_DIR=/Users/keen/.config/keenroudy/gh GIT_CONFIG_NOSYSTEM=1`.
- **The record is append-only.** Never hand-edit `research/*.json`, `site/data/forecasts.json`,
  `market-observations/*.json`, `tests/integrity-ledger.json` or any store's `ledger.json`, and never rewrite a
  published pick. A correction is a new dated report. `tests/test_integrity.py` hashes everything published.
- **Never invent a price, a stat or a source.** No price, no pick. No scraping sportsbook sites.
- **Secrets stay in `~/.config/keenroudy/env`** (names: `deployment/mac/env.example`) and GitHub Actions secrets. Never
  print, log, commit or paste a key. Never enter a password or answer an account-security prompt; the owner does that.
- **Python standard library only** in the repo. Node only for the site's tests.
- **X:** posts go through Buffer only. No browser automation on X, ever unattended. Never delete a post that went out
  (the owner decides). The owner pins big wins by hand from the phone ping.
- **Deploy only while holding the run lock** `~/.config/keenroudy/run.lock` (below), never mid-run.
- **Do not change how the record counts** without telling the owner the before and after numbers.

## Where things are

| What | Where |
|---|---|
| The desk's own clone (the runs work here; do not edit by hand) | `~/Projects/sports` (branch `main`) |
| Your working copy for changes | `~/Projects/sports-dev` (git worktree of the same repo, branch `dev`) |
| Wrapper, settings, lock, drafts, failed reports | `~/.config/keenroudy/` (`run.sh`, `env`, `run.lock`, `x-drafts/`, `failed/`, `pending/`) |
| launchd jobs | `~/Library/LaunchAgents/com.keenroudy.sports.{run,precheck,heartbeat}.plist` (copies in `deployment/mac/`) |
| Logs | `~/Library/Logs/KeenRoudy/` (`run-YYYY-MM-DD.log`, `launchd.*.log`, `ALERT.txt` when the heartbeat found a problem) |
| Post log (every X post, Buffer id, tweet id, metrics) | `data/x-posted.json` |
| Learning (what the desk learned, weekly) | `data/learning/` (`policy.json`, `REPORT.md`) |
| Site source / built data | `site/` / `site/data/app/` (built, not committed) |
| Operating guide and history | `DESK.md`; what the accounts we follow post: `docs/X-NOTES.md`; edges: `docs/EDGE.md` |

Handy commands (from `~/Projects/sports`):
- `~/.config/keenroudy/run.sh doctor`: versions, identities, which settings are set (never their values).
- `~/.config/keenroudy/run.sh py scripts/buffer_post.py plan`: what the next run would schedule on X.
- `~/.config/keenroudy/run.sh py scripts/buffer_post.py reconcile`: record what became of past posts.
- `~/.config/keenroudy/run.sh py scripts/ladder.py`: where the ladder stands and the rung it would build now.
- `GH_CONFIG_DIR=/Users/keen/.config/keenroudy/gh gh run list -R keenroudy22/sports -L 10`: the hosted runs.

## Changing the code and deploying (exactly)

1. Work in `~/Projects/sports-dev` on branch `dev`. First bring it up to date:
   `git -C ~/Projects/sports-dev fetch -q origin && git -C ~/Projects/sports-dev rebase origin/main`.
2. Change the code, add or update tests, and pass both suites:
   `python3 -m unittest discover -s tests` and `node --test tests/*.test.js`.
3. Rehearse the next run without publishing anything:
   `cd ~/Projects/sports-dev && python3 scripts/run.py run --dry-run --no-llm --slot HHMM`
   (a `--now` in the future stops at report validation on purpose; a dry run writes to `~/.config/keenroudy/pending/`).
   Move any file it leaves in `~/.config/keenroudy/failed/` out of there, so it is not mistaken for a real stop.
4. Commit on `dev` as keenroudy22, ending the message with an attribution line for the agent that wrote it.
5. Deploy while holding the run lock (it waits for a run in progress), then fast-forward and push:
   ```
   cd ~/Projects/sports
   python3 - <<'PY'
   import fcntl, subprocess, sys, time
   lock = open('/Users/keen/.config/keenroudy/run.lock', 'a')
   while True:
       try:
           fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); break
       except OSError:
           time.sleep(5)
   steps = 'git fetch -q origin && git merge -q --ff-only origin/main && git -C ../sports-dev rebase -q main && ' \
           '(cd ../sports-dev && python3 -m unittest discover -s tests 2>&1 | tail -1) && ' \
           'git merge -q --ff-only dev && git push -q origin main'
   sys.exit(subprocess.call(steps, shell=True, env={**__import__('os').environ,
            'GH_CONFIG_DIR': '/Users/keen/.config/keenroudy/gh', 'GIT_CONFIG_NOSYSTEM': '1'}))
   PY
   ```
   If `~/Projects/sports` is not clean (a stopped run left captures), commit those as "Captures left by a stopped
   run" first; if a rebase stops on a store, `python3 scripts/merge_store.py` resolves it, then `git rebase --continue`.
6. Watch the publish run until it passes (`gh run watch <id> --exit-status`), then check the live site at phone
   width (375 px): no sideways scroll, no console errors.

## The owner's current rules (newest first; `DESK.md` has the reasons)

- **The daily card** (2026-09-28): five straight plays on Saturday and Sunday, a mix of game lines and player props
  (three of a kind at most); one play on other days, the NFL game's on an NFL night (`gates.card_cap`, ordered by
  `run.rank_card`). Never leave an NFL day without a post. A fun parlay with alternate lines every Saturday (college,
  `easy_parlay.sharp_candidate`) and Sunday (NFL easy props), plus the lotto when one qualifies.
- **Only hard news pulls a play** before it posts: out, doubtful, inactive, suspended, benched (`run.hard`). A fun
  ticket pulled before its post is replaced the same day under a new id (`gates.fresh_id`).
- **Tweets are short and human** (2026-09-26: "Not so AI looking. And straight to the point"): the play with price
  and book, "We have it at 47.", "❤️ if you're tailing", @Playbook and the league tag. No labels, slogans or
  reason sentences. POTD: "POTD: ..." first. Lotto: "🎰 +2506 COLLEGE LOTTO (ESPN BET)" then the legs.
- **The Kook'n Ladder** ($50 to $1,000, `scripts/ladder.py`): two easier player lines at one book near even money,
  one rung open at a time, one a day, NFL legs until college player numbers are calibrated. It must post; alternates
  are allowed and expected.
- **College player props** are legal pregame in Indiana (Gaming Commission, 2026-09-24). Their board rows come from
  SharpAPI's own lines; learning calibrates them weekly (`CFB/prop`).
- **One record** everywhere: every published play counts, win or lose; units on the site only (one unit a play,
  saved at grading), none on X; fun parlays and the ladder apart; the 26 Week 1 plays at an assumed -115, marked.
- **Weekly "📌 Save this" projections sheet**: college Saturday and NFL Sunday at 10 AM (`scripts/sheet.py`).
- **The site**: the projection-card look everywhere (logos, photos, tiles), tabs Today, Board, Games, Stats, Record,
  More; always check changes at 375 px.
- **Posting**: plays around noon Eastern (two hours before an earlier kickoff), ten minutes apart and from every
  queued post, twenty posts a day at most; receipts at 9 AM; cashed posts as wins settle.

## Weekly review (Mondays)

Read the weekend's run logs for `STOPPED|CRASHED|Traceback|held back|not scheduled|failed to post|holds the lock`;
list what each run published, settled and closed; check every X post went out (`data/x-posted.json`: `sentAt`,
`tweetId`, `error`, `cancelledAt`, `precheck`); the weekend record in the one-record terms; the GitHub runs; any
`ALERT.txt`; `scripts/line_timing.py --since <last Monday>`; and `data/learning/REPORT.md` after Tuesday's learning
step. Report to the owner in plain words: what went out, what broke, what you fixed, at most three recommendations.

## When something breaks

- **"STOPPED: ... fails validation"**: a report broke a rule in `scripts/refresh.py validate_report`; the report is
  kept in `~/.config/keenroudy/failed/`. Fix the code that wrote it, test, deploy. Never edit the report to pass.
- **A run left files uncommitted** (`data/odds`, `data/prop-odds`): commit them as captures and push under the lock.
- **"git fetch raced another git client"**: another app refreshed the repo; the run retries by itself.
- **A post did not go out**: `run.sh py scripts/buffer_post.py reconcile` shows the error; the phone gets an alert.
- **The local model is down** (`curl -s localhost:11434/api/version`): the desk falls back to templates and rules.
- **The web researcher fails**: `codex login status`; the desk keeps running without it.
