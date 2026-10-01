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
   the pre-post check every 30 minutes, the Discord mirror every 5 minutes, the heartbeat at 7:15 AM, and the weekly review Monday 9:30 AM. The run settles and closes plays, builds the
   board, judges candidates through `scripts/gates.py`, publishes reports to `research/`, pushes, and schedules X
   posts in Buffer. Confirmed official plays reach Discord about 10-15 minutes before X; other post types mirror
   after Buffer confirms X. The same words and card use one incoming webhook; the card is uploaded as a durable
   Discord attachment rather than left as a temporary site embed. Logs:
   `~/Library/Logs/KeenRoudy/run-YYYY-MM-DD.log` (times in UTC).
2. **GitHub Actions** (`.github/workflows/publish.yml`) on a schedule and on every push: captures scores, odds and
   prop prices, publishes model forecasts, grades against the close, builds the site and the cards, and deploys.
3. **Routed models on the Mac**: Ollama `qwen3.8:27b` (override: `KEENROUDY_LLM_MODEL`) weighs verified facts. The
   deterministic, sourced templates are the live prose by default, so routine cards do not spend local-model calls
   merely rewording them. Optional guarded rewriting uses `qwen3.5:9b-mlx` only when `KEENROUDY_LLM_POLISH=1`; judgment
   never falls through to it. The live web researcher uses `codex exec` with `gpt-6-sol` at low reasoning by default; the weekly review
   uses the same model at medium reasoning. Both use the owner's ChatGPT plan and can be overridden with the named
   researcher/review settings in `deployment/mac/env.example`.

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
- **Discord:** one-way publisher only. The append-only site record remains the source of truth. Confirmed official
  plays use the same words and card and go to Discord about 10-15 minutes before X; receipts, news and engagement
  posts mirror only after Buffer confirms X. Image cards are uploaded to Discord so an old message cannot lose its
  art when generated site files roll forward; recent receipt URLs also stay live for eight days as a retry fallback.
  Once Discord publishes a play it is public and stays in the record. A
  hard-news pull before X gets a Discord update and cancels X, but never erases the play. The webhook stays in
  `~/.config/keenroudy/env`, never the repo or a log. Arb alerts are explicitly not official plays and may go only
  to Discord under the separate Arb Radar rule.
- **Deploy only while holding the run lock** `~/.config/keenroudy/run.lock` (below), never mid-run.
- **Do not change how the record counts** without telling the owner the before and after numbers.
- **Keep the operating stack free.** Do not add a paid service, increase a metered request budget or buy reach
  without the owner's approval. Build the audience with free plays first; a paid tier and compliant bonus links are
  future options only after the owner explicitly decides to launch them.

## Where things are

| What | Where |
|---|---|
| The desk's own clone (the runs work here; do not edit by hand) | `~/Projects/sports` (branch `main`) |
| Your working copy for changes | `~/Projects/sports-dev` (git worktree of the same repo, branch `dev`) |
| Wrapper, settings, lock, drafts, failed reports | `~/.config/keenroudy/` (`run.sh`, `env`, `run.lock`, `x-drafts/`, `failed/`, `pending/`) |
| launchd jobs | `~/Library/LaunchAgents/com.keenroudy.sports.{run,precheck,discord,heartbeat,review}.plist` (copies in `deployment/mac/`) |
| Logs | `~/Library/Logs/KeenRoudy/` (`run-YYYY-MM-DD.log`, `launchd.*.log`, `ALERT.txt` when the heartbeat found a problem) |
| Post log (every X post, Buffer id, tweet id, metrics) | `data/x-posted.json` |
| Learning (what the desk learned, weekly) | `data/learning/` (`policy.json`, `REPORT.md`) |
| Site source / built data | `site/` / `site/data/app/` (built, not committed) |
| Operating guide and history | `DESK.md`; what the accounts we follow post: `docs/X-NOTES.md`; edges: `docs/EDGE.md` |
| Private arb rules and feed evaluation | `docs/ARB-RADAR.md` |

Handy commands (from `~/Projects/sports`):
- `~/.config/keenroudy/run.sh doctor`: versions, identities, which settings are set (never their values).
- `~/.config/keenroudy/run.sh py scripts/buffer_post.py plan`: what the next run would schedule on X.
- `~/.config/keenroudy/run.sh py scripts/buffer_post.py reconcile`: record what became of past posts.
- `~/.config/keenroudy/run.sh py scripts/ladder.py`: where the ladder stands and the rung it would build now.
- `GH_CONFIG_DIR=/Users/keen/.config/keenroudy/gh gh run list -R keenroudy22/sports -L 10`: the hosted runs.

## Changing the code and deploying (exactly)

1. Work in `~/Projects/sports-dev` on branch `dev`. First bring it up to date:
   `git -C ~/Projects/sports-dev fetch -q origin && git -C ~/Projects/sports-dev rebase origin/main`.
2. Change the code, add or update tests, and pass both suites in the development worktree:
   `cd ~/Projects/sports-dev && /opt/homebrew/bin/python3 -m unittest discover -s tests` and
   `cd ~/Projects/sports-dev && node --test tests/*.test.js`. Do not use `run.sh py` for these: that wrapper deliberately
   changes into the production checkout.
3. Rehearse the next run without publishing anything:
   `cd ~/Projects/sports-dev && /opt/homebrew/bin/python3 scripts/run.py run --dry-run --no-llm --slot HHMM`
   (a `--now` in the future stops at report validation on purpose; a dry run writes to `~/.config/keenroudy/pending/`).
   Move any file it leaves in `~/.config/keenroudy/failed/` out of there, so it is not mistaken for a real stop.
4. Commit on `dev` as keenroudy22, ending the message with an attribution line for the agent that wrote it.
5. Deploy while holding the run lock (it waits for a run in progress), then fast-forward and push:
   ```
   cd ~/Projects/sports
   /opt/homebrew/bin/python3 - <<'PY'
   import fcntl, subprocess, sys, time
   lock = open('/Users/keen/.config/keenroudy/run.lock', 'a')
   while True:
       try:
           fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); break
       except OSError:
           time.sleep(5)
   steps = 'git fetch -q origin && git merge -q --ff-only origin/main && git -C ../sports-dev rebase -q main && ' \
           '(cd ../sports-dev && /opt/homebrew/bin/python3 -m unittest discover -s tests 2>&1 | tail -1) && ' \
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

- **No brown house graphics** (2026-10-01): Kook'n-owned cards use midnight navy/black, electric mint and crisp
  cyan. Never use brown, tan, bronze, copper, amber, sepia or muddy burnt orange as a house-card background or
  accent. A real team's supplied colors may still appear on that team's play card.
- **Discord-only Arb Radar** (2026-09-29): exact-line, two-outcome opportunities from fresh captured prices may post
  to Discord, but never X, the live site, ntfy or the official record. Every alert says to move quickly and is valid
  only when both exact listed prices are still available or better; it also says to verify both apps, limits and
  settlement rules before acting. It never places a wager or calls a middle an arb. The same market/books alert at
  most once per six hours. Account-specific boosts use the manual calculator because feeds cannot see them. Hard
  Rock is comparison-only and cannot become an official play. The public `#arbs` page explains the scanner and
  calculates a user-entered split; it never exposes live candidates or the API key and never calls an odds feed.
- **SportsGameOdds stays free and silent** (2026-09-29): its Amateur key is evaluation-only. Shadow mode must check
  `/account/usage` before each event sample, run only when the reported monthly ceiling is exactly 2,500 objects,
  stop at 1,800, keep its six-hour/30-object daily caps, and never alert, publish or change a play. Never upgrade it.
  The same already-budgeted response may inventory fresh, two-sided team-total prices for a silent coverage trial;
  this adds no request and does not make team totals eligible for a card, watch or play. Public use waits for a
  documented calibration against settled team scores and the same price gates as every other market.
- **Daily presence, never a forced play** (2026-09-29): publish at least one useful X post every day. A receipt,
  menu, official play, watchlist, verified injury angle, cashed post or Climb update satisfies the day; when none
  exists, `receipts.book` schedules the public record at 6 PM. Daily posting never lowers a play gate or creates a
  pick. Add a sport to official plays only after its paper trial shows a real edge; schedules and scores may appear
  earlier as factual coverage.
- **Multi-sport buildout** (2026-09-29): the free score center covers NBA, WNBA, men's college basketball, MLB, NHL,
  the Premier League and MLS. `#lab` tells visitors whether each sport is score-only, research, paper trial or live.
  NBA and college totals use the existing silent paper trial when their seasons open; historical backtests alone do
  not authorize a post. MLB and NHL use `scripts/market_lab.py` to preserve supplied DraftKings pregame markets,
  changed snapshots and final scores before either sport gets a model. This uses ESPN's public feed, not a metered
  service, and never grades or publishes a play. Do not add public picks or cross-sport tickets merely because scores
  or market captures exist.
- **The daily card** (2026-09-28): five straight plays on Saturday and Sunday, a mix of game lines and player props
  (three of a kind at most); one play on other days, the NFL game's on an NFL night (`gates.card_cap`, ordered by
  `run.rank_card`). Never leave an NFL day without a post. A fun parlay with alternate lines every Saturday (college,
  `easy_parlay.sharp_candidate`) and Sunday (NFL easy props), plus the lotto when one qualifies. Pick of the Day is
  independent of every challenge and may come from any qualifying game, including a one-game slate.
- **Alternate lines are for fun tickets** (2026-09-28): the ladder, lotto/longshot, easy parlay and any other fun
  parlay may use a book's feed-priced alternate when our number likes it at that price. One book, one leg per game,
  full-game half-point rungs from that market's own ladder only (`sharp_odds.consistent`); college player legs wait
  for college calibration. Straight card plays stay on main lines. Never invent a price, scrape one or spend new
  Odds API credits for a lotto.
- **Only hard news pulls a play** before it posts: out, doubtful, inactive, suspended, benched (`run.hard`). A lotto
  or easy parlay pulled before its post is replaced the same day under a new id (`gates.fresh_id`). A ladder rung is
  never replaced.
- **Tweets are short and human** (2026-09-26: "Not so AI looking. And straight to the point"): the play with price
  and book, "We have it at 47.", "❤️ if you're tailing", @Playbook and the league tag. No labels, slogans or
  reason sentences. POTD: "POTD: ..." first. Lotto: "🎰 +2506 COLLEGE LOTTO (ESPN BET)" then the legs.
- **The Kook'n 80/20 Climb** ($50 to $1,000 bankroll ladder, `scripts/ladder.py`): bank 20% of every winning return and ride 80% on
  the next rung, so a miss cannot take what was banked. Two safer player lines at one book, each priced -500 to -180
  and together -250 to -110. A slower climb is preferred to forcing an even-money rung. One rung open at a time, one
  a day, NFL legs until college player numbers are calibrated. Never force it on a one-game slate: the two legs stay
  in different games. It must post; alternates
  are allowed and expected. A rung pulled before its X post still counts, win or lose; while ungraded it blocks the
  next rung, and after grading the climb moves from its result.
- **College player props** are legal pregame in Indiana (Gaming Commission, 2026-09-24). Their board rows come from
  SharpAPI's own lines; learning calibrates them weekly (`CFB/prop`).
- **One record** everywhere: every published play counts, win or lose; straight-play units stay on the site (one unit
  a play, saved at grading). Receipt posts may label fun parlays as their smaller 0.25u stake and say how many legs
  hit, but keep them apart from the straight record and never imply a near miss was a win. The ladder stays apart;
  the 26 Week 1 plays are at an assumed -115, marked.
- **The listed book's official settlement wins over the raw box score.** If a sourced injury-protection program
  removes a leg, show that leg as void and reprice the remaining parlay only from its captured leg prices. Never
  assume protection from an injury alone. The Sep 27 FanDuel easy-props ticket is 2/2 on its live legs and a win:
  Achane's first-quarter injury leg was automatically protected during FanDuel's free September promotion. Its
  Sep 30 correction is appended to the record; the original settlement is never rewritten.
- **Every raw player-prop loss gets a postgame injury check** (2026-10-01), including a losing leg on a fun ticket.
  Before the loss is graded, the web researcher checks whether the player left hurt, when it happened and whether
  the player returned. A verified injury, an unverified report or a failed check pauses settlement through 12 hours
  after kickoff and sends an informational alert; the owner never has to supply a wager screenshot. Never auto-push
  or void it. If no different official book settlement is known by the deadline, grade from the official stats,
  preserve the review note and sources, name the verified in-game injury on the final receipt, and append a dated
  correction later if stronger evidence appears.
- **Weekly "📌 Save this" projection sheet**: the full NFL slate or 16 college games, college Saturday and NFL
  Sunday at 10 AM (`scripts/sheet.py`). Every spread and total read carries the exact captured line, price and book.
  Numbered mint rings identify up to four markets where the calibrated chance clears that price by the Board's value
  threshold and name the wager itself (`OVER 45.5`, `MINN +3.5`), not merely `TOTAL` or `SPREAD`; the selected priced
  line, rather than the model projection, is mint. Missing, stale, thin, paused and pass prices never get a ring.
  They are watches, not official plays.
  Never show a moneyline watch without both sides' captured book prices to compare with the projected win chance.
  The complete college slate stays on the site.
- **Growth goal** (2026-09-28): grow @keenkooks toward 10,000 followers by the end of football season without paid
  reach or account-risk shortcuts. One relevant league hashtag per post is enough. The ladder is a continuing story,
  not a claim of guaranteed profit. On a multi-play card, one short text-only conversation prompt goes between the
  first two plays; when a Climb rung or fun ticket is already ready, that prompt becomes a factual teaser for it.
  Single-play days get no filler. No automated replies, likes, follows, unfollows or trend posts; no bought or
  exchanged engagement. `docs/GROWTH.md` has the baseline, weekly scorecard and experiments.
- **Injury-angle posts** (2026-09-29): up to two timely text posts a day when ESPN lists a top QB/RB/WR/TE out,
  doubtful or inactive, a newer projection has removed them and redistributed the role, and a sportsbook price
  captured after the news still grades as a lean. Name the matchup, the priced teammate prop and the opponent's
  allowed-by-position stat when available; label it a board lean, not a posted play. These posts never enter the
  record, never displace a play or receipt, and mirror to Discord after X like every other post.
- **Discord community** (2026-09-29): the free Kook'n Sports server gets confirmed official plays and graphics about
  10-15 minutes before X; all other approved posts mirror after X. It has a read-only links/resources index and
  concise click-to-accept rules for 21+, legal-location, entertainment-only use. Sportsbook referral offers live in
  their own channel, use only the owner's exact links, and are clearly labeled with age, location, changing-terms and
  Kook'n-benefit language; never mix them into ordinary plays. The site's front-page community card is the main
  conversion path: it promises only early official plays, Discord-only Arb Radar candidates and the public record.
- **The site**: the projection-card look everywhere (logos, photos, tiles), tabs Today, Board, Games, Stats, Record,
  More; always check changes at 375 px.
- **Posting**: plays around noon Eastern (two hours before an earlier kickoff), ten minutes apart and from every
  queued post, twenty posts a day at most; receipts at 9 AM; cashed posts as wins settle.

## Posts and graphics

Everything that goes to X, its exact words, its card and when it posts is in **`docs/POSTS.md`**, with example cards
in `docs/examples/` (Pick of the Day, player prop, lotto, ladder step, receipt, the Save this sheet). The short
version: tweets are short and human (the play, price and book, "We have it at 47.", the ask, @Playbook, the tag); every
play and house post carries its card (`scripts/pick_card.py`, drawn by the hosted build into `site/data/cards/`);
nothing posts until its card is live; no straight-play units on X (a receipt may identify a fun ticket as 0.25u);
new post types need the owner's yes. Preview before changing
anything: `python3 scripts/pick_card.py <pick id>`, `python3 scripts/x_post.py draft <pick id>`,
`run.sh py scripts/buffer_post.py plan`.

## Weekly review (Mondays, automatic)

A launchd job, `com.keenroudy.sports.review` (Monday 9:30 AM Eastern; copy in `deployment/mac/`), runs
`scripts/review.py`: it gathers the week from the desk's own records (run logs, the post log, the record, the ladder,
the GitHub runs, `line_timing.py`), has Codex write the plain-words review read-only, saves it to
`~/Library/Logs/KeenRoudy/review-<date>.md` (the facts in `review-packet-<date>.md`) and sends its opening to the
owner's phone. It changes nothing. When the owner asks you to act on a review, read that file, then fix what it names
the way this file says. To run it by hand: `~/.config/keenroudy/run.sh py scripts/review.py` (`--no-codex` for the
packet only, `--no-push` to skip the phone).

## When something breaks

- **"STOPPED: ... fails validation"**: a report broke a rule in `scripts/refresh.py validate_report`; the report is
  kept in `~/.config/keenroudy/failed/`. Fix the code that wrote it, test, deploy. Never edit the report to pass.
- **A run left files uncommitted** (`data/odds`, `data/prop-odds`): commit them as captures and push under the lock.
- **"git fetch raced another git client"**: another app refreshed the repo; the run retries by itself.
- **A post did not go out**: `run.sh py scripts/buffer_post.py reconcile` shows the error; the phone gets an alert.
- **The local model is down** (`curl -s localhost:11434/api/version`): the desk falls back to templates and rules.
- **The web researcher fails**: `codex login status`; the desk keeps running without it.
