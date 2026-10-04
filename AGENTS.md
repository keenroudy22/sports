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
   an extra Climb settlement/qualification scan at 10:00 AM, 1:30, 4:00 and 8:00 PM, the pre-post check every 30
   minutes, the Discord mirror every 5 minutes, the heartbeat at 7:15 AM, and the weekly review Monday 9:30 AM. The run settles and closes plays, builds the
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
| launchd jobs | `~/Library/LaunchAgents/com.keenroudy.sports.{run,ladder,precheck,discord,heartbeat,review}.plist` (copies in `deployment/mac/`) |
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

- **Games-tab team strength ranks (2026-10-04):** every Games projection card shows each team's current model
  offense and defense rank within its league; No. 1 is strongest. Rank the margin model's offense effect from high
  to low and its opponent-points defense effect from low to high, include only active NFL/FBS teams, share ranks on
  exact ties, and label them as model ranks rather than standings or raw points-per-game ranks. Keep them compact on
  mobile and do not add them to the Today cards.
- **Performance raises the bar; it does not veto a market (2026-10-04):** poor recent results or the book's
  line beating our projection are evidence to consider, not a reason by themselves to suppress every post.
  An underperforming player market must clear its exact price by at least five adjusted percentage points;
  an underperforming game market must clear by at least three. A line that clears the higher threshold may still
  qualify and carries a visible performance caution. Missing calibration, stale or missing prices, thin or limited
  roles, injury holds and negative value remain hard stops. Existing publications and the record do not change.
- **Game-page model leans (2026-10-04):** the owner wants useful line-versus-projection research even when
  no official play qualifies. Show a separate compact Model leans section with exact captured lines, projection
  differences, season hit counts and explicit weak-sample/performance cautions. These descriptive directions
  are not price-qualified recommendations and carry no confidence rank. Hide stale prices and limited roles;
  never flip a quoted side or reuse a price for another side. Season trends use their own full-season data,
  independent of favorite admission. Official selection, favorite gates, social posts and the record are unchanged.
- **Playbook tagging (2026-10-04):** tag `@Playbook` only on a new official play/ticket posted to X
  so readers can get its play link. Never tag it on Discord, results, research, recaps, menus or updates.
  Discord keeps the wager, odds, card and timing but removes the X-only mention, including pending older mirrors.
  Do not delete or repost existing publications just to change the tag.
- **Season Trends (2026-10-04):** the Board and game pages link to a full-season player threshold browser with
  70/80/90/100% minimum-hit filters, stat/type/sample filters and player research links. Show exact hits/games,
  regular-season recorded appearances only; unknown stats suppress the row rather than inflate its rate.
  Main and alternate lines require captured prices no older than four hours; unpriced statistical milestones
  are explicitly separate and are never sportsbook offers or picks. Use existing stores, with no new requests.
  At least three recorded games on-site; at least five and a fresh public-book quote for social research.
  Season trends get first consideration on even-numbered dates in the existing optional research slot,
  with existing editorial priority on odd dates and trends as a fallback. At most one research post per date
  across all families, including already queued posts. Nothing changes official selection or the record.
- **No straight/parlay player stacking (2026-10-04):** block reuse of the same player in the same game across
  straight plays and any ticket, including the ladder, in either publication order. A different stat, side, book
  or alternate does not remove the shared exposure; expired quotes still count. Filter before ticket selection
  and enforce again at admission. Preserve player IDs on legs. Regular longshots try main lines first; use an
  alternate fallback or easy-props ticket at most once per league per rolling seven days, never as a daily quota.
  Check that allowance before fetching easy-prop prices. Ladder alternates remain allowed, with no weekly cap,
  but the no-stacking rule applies. No historical play, result, or already-published ticket is rewritten.
- **Evidence and selection review (2026-10-04):** new official props need at least two adjusted percentage points
  above their exact price. A third prop in the same league/market on one slate needs at least five points;
  the existing five-play and three-player ceilings still apply. This is a conservative selection policy, not
  a claim that those cutoffs have proved profitable. Existing publications and grading are unchanged.
  Future X/Discord play copy may include one saved supporting sentence selected from structured evidence,
  within the existing length and spacing limits. The website's Why this play shows saved history, role,
  matchup, probability/price comparison and explicit counterarguments. Never turn opposing evidence into support.
  Weekly learning splits whole kickoff dates and activates only the fitted coefficient actually tested;
  `market_review.py` compares market-specific pooled formulas offline and joins both weekly learning and the
  Monday owner review. A retrospective improvement only nominates a future shadow trial; it never changes live
  market weights automatically. All evaluation uses stored data and adds no metered requests.
- **Confidence order and explained upsets (2026-10-03):** qualifying Board lines may show a confidence rank based
  on their calibrated chance to win after the ordinary freshness, sample and performance-threshold rules. Keep this separate
  from value rank, which measures how far the chance clears the exact price; the two may disagree and neither is a
  lock score. Thin, stale, unpriced and uncalibrated rows receive no confidence rank. Upset Watch ranks its
  fresh outright candidates by the raw model-versus-market probability disagreement and says why each is highlighted:
  exact projected score, spread disagreement and only rating drivers present in that forecast. A large line move and
  college schedule/role uncertainty are warnings, not supporting evidence. It remains research, never an official play.
- **Season futures are their own track (2026-10-03):** at the beginning of each covered sport's season, research
  championship, conference/division, playoff qualification and season-total markets; add awards only with reliable
  eligibility and settlement coverage. Preserve the first exact price, book, source, observation time and model
  snapshot, then append every movement and final settlement. Paper watches do not count as daily plays and open
  futures do not inflate the daily record. No scraping, paid call, invented price or automatic public future. The
  staged rollout and promotion gates are in `docs/FUTURES.md`.
- **Autonomous Climb loop and result graphics (2026-10-03):** every settled 80/20 Climb rung gets a dedicated
  1080x1350 result card: a win advances, a loss shows the protected bank and the next $50 restart, a push keeps the
  same stake, and the goal-reaching rung gets the completion version. The ticket and result cards share one
  persistent path: completed steps have green checkmarks, the current/next step is outlined, future checkpoints are
  muted and the $1,000 flag stays visible. Never print guessed future returns or a promised step count. Keep only the
  actual wager, its legs, bank and next stake; schedule explanations and motivational filler do not belong on the
  graphic. Artwork is confined to the header and cannot cover wording. Exact manual alternate spreads and totals
  retain `marketType` and auto-grade from the final score like feed-built game legs; do not send an ordinary
  non-pushing game leg to manual settlement. A late
  final remains eligible for 24 hours and the 6:45 AM run queues it for 9:05 AM, so an overnight result cannot miss
  the story. If a text-only advancement was already queued before settlement, the run safely replaces that future
  Buffer item with the same words plus the live card. Never create a duplicate post or change the rung's record.
  One rung may be open at a time. After it settles, a later qualifying scan may publish the next rung or restart on
  the same day; scans run at 10:00 AM, 1:30, 4:00 and 8:00 PM in addition to the regular desk. The owner gets a
  private 6:45 AM phone agenda on football days and an exact-ticket phone alert with both release times whenever a
  rung is scheduled. Discord gets the ticket about 10-15 minutes before X. No scan forces a rung or places a bet.
  Today and Record must use that same ledger state: name the most recent winning step as cashed, call the next step
  "being checked · not posted yet" until a real rung exists, and keep every completed rung's exact lines in a compact
  Past steps dropdown. The phone view must show this before the ordinary card.
- **Legibility first (2026-10-02):** the actual wager lines must be the dominant part of ticket graphics.
  Prefer large full-width leg panels and small branding over oversized mascots and tiny lists. Preserve all
  leg wording and prices; use real player/team art when available and rotate stable navy/mint/cyan treatments
  by ticket ID. The owner approved the preview on Oct 2; existing posted attachments are never replaced.
- **Simple Discord and ladder check-ins (2026-10-02, owner approved):** four active text destinations: Start Here,
  Plays & Results (the existing webhook channel, owner/publisher only), general chat, and Wins & Bad Beats.
  Eight retired channels are in private HISTORY (owner-accessible, hidden from ordinary members), without
  deleting history. Rules, sportsbook promos and links remain accessible under RESOURCES. Verified with
  Discord's @everyone preview on Oct 2; the official feed remains read-only. The live webhook and arb fallback
  both target plays-and-results. Saturday/Sunday are regular public Climb check-in days, not guaranteed ticket days;
  every day gets the private qualifying scans above. The existing run schedules a text status at/after 11:45 AM ET and before 2 PM
  through Buffer, mirrored to Discord after X. An actual same-day open ticket replaces the extra status. Each
  date is deduplicated and existing spacing/daily caps apply. Never lower thresholds to satisfy the calendar.
- **Closer pre-post review (2026-10-02):** the existing half-hour job checks plays 15–45 minutes before X instead
  of up to 150 minutes beforehand. It still checks once, uses existing feed snapshots, and does not add metered
  calls or change the Discord lead. Unconfirmed college availability is withheld, never guessed. Feed prices are
  not live guarantees; the post preserves the original quote and shows a current captured quote when available.
- **Delivery clarity and portraits (2026-10-02):** Board cards show confirmed Discord/X delivery separately from
  scheduled X time and original-quote expiry. A due time alone is never evidence of delivery. Discord's legacy
  timestamp is the job-start time, so do not display it as the exact delivery minute. Missing delivery evidence
  stays unconfirmed. College and NFL cards both use the real athlete portrait when available, with the existing
  fallback when unavailable. A next ladder step is not a scheduled ticket; explicitly say when it is not scheduled.
  Completed or lost climbs restart at $50 on the next qualifying ticket; previously banked money stays banked.
- **Research rollout (2026-10-02):** favorites are grouped by market. Matchup Menu is exact-main-line historical
  evidence with at least five games, never a guarantee or fabricated head-to-head stat. Upset Watch requires a
  future game, a forecast published within 24 hours, and both same-book moneylines captured within four hours;
  it is a raw winner disagreement, not calibrated moneyline value. End-zone research ranks observed current-season
  red-zone/inside-10 work, requires three games and a role snapshot within seven days, displays its timestamp,
  excludes passing TDs, and discloses incomplete college injury coverage. It has no TD price or probability.
  Missing play-by-play and usage are unknown, not zero. These views never publish an official play.
- **Underdog/editorial release (2026-10-02, owner approved):** Today always shows Underdog Watch, including an
  honest empty state, and keeps outright-upset research separate from positive-spread cover value. At most one
  10:30 AM research graphic may publish per football slate: a fresh outright underdog first, then a priced spread
  dog, exact-line Matchup Menu, or End-zone Work. Every card and post says research, not an official play; it uses
  only current stored prices/evidence, becomes optional before queue limits, and mirrors to Discord only after X.
  Hard Rock remains comparison-only and never appears on the editorial research post.
- **Live progress shadow (2026-10-02):** the five-minute mirror job silently observes already-public football
  plays with one free ESPN summary per game. It is capped at eight games, records source time, early crossings,
  close calls, corrections and finals in `~/.config/keenroudy/live-watch.json`, and makes no odds or model call.
  It sends nothing. Discord needs a reviewed clean pilot; X still needs three clean Discord pilots and a separate
  release decision. `KEENROUDY_LIVE_SHADOW=0` is the kill switch.
- **Free-budget guard (2026-10-02):** every metered Odds API path uses `quota.guarded_json`: verify the account's
  500-credit allowance, serialize and reserve locally before requesting, preserve a 24-credit buffer (120 for
  easy parlays), and stop when usage cannot be verified. Existing caller limits remain. SportsGameOdds keeps its
  separate, stricter evaluation guard; no new service or subscription. No API keys in usage journals.
- **Evaluation outcome (2026-10-02):** offline CFB blowout/continuity/efficiency comparisons do not justify a live
  weight change. `docs/audit-evaluation-2026-10-02.json` is retrospective, not an untouched holdout. No candidate
  is promoted. Qwen 27B passed four small evidence tests; Ollama 8B timed out on three. Keep live routing and
  deterministic routine prose; this did not test the separate optional MLX rewrite runtime.
- **Audit implementation approved (2026-10-02):** card sizes are ceilings, never quotas. Paused segments,
  missing learned prop calibration, nonpositive calibrated price edges, stale quotes and the NFL prop-market
  underperformance check must block new official straight plays, including favorites and researched labels.
  Fewer or zero plays are valid. Existing publications and their results remain untouched. Calibrated prop pricing
  is shared by quote shopping, gates, prose and the site; new publications preserve their probability inputs.
- **Transparent Board (2026-10-02):** official plays first; future plays grouped separately. Navigation is Board,
  Games, Players, Scoreboard, More (old hashes remain valid). The headline separates all published W-L from
  captured-price returns, assumed historical prices and promotional credits. Combined legacy totals stay available
  and labeled in the detailed record. Do not turn an expired original quote into an Open badge. A yard/point gap
  is a projection gap, not a probability edge. College disagreements of at least seven spread points carry a
  caution, not an automatic bet. No team or player model weights change without held-out evaluation.
- **Rollout boundaries (2026-10-02):** no new paid feeds, quota increases or automatic X interactions. Live
  milestones require a shadow trial, a Discord pilot, then a separate public-release checkpoint. An AI reply bot
  remains off; X requires prior explicit written approval. Full remaining audit work is tracked in
  `docs/AUDIT-IMPLEMENTATION.md`; do not call an unfinished phase deployed.
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
- **The menu promises only approved plays** (2026-10-01): the morning menu's live text gives the exact count, games
  and times from the active postable card. Its reusable artwork never names player props, team props, a fun parlay
  or any other category. Do not advertise a category as coming unless its actual play has already cleared every
  gate and is scheduled. A later screen-out is not replaced with a forced bet.
- **Multi-sport buildout** (2026-09-29): the free score center covers NBA, WNBA, men's college basketball, MLB, NHL,
  the Premier League and MLS. `#lab` tells visitors whether each sport is score-only, research, paper trial or live.
  NBA and college totals use the existing silent paper trial when their seasons open; historical backtests alone do
  not authorize a post. MLB and NHL use `scripts/market_lab.py` to preserve supplied DraftKings pregame markets,
  changed snapshots and final scores before either sport gets a model. This uses ESPN's public feed, not a metered
  service, and never grades or publishes a play. Do not add public picks or cross-sport tickets merely because scores
  or market captures exist.
- **The daily card** (2026-09-28, ceilings clarified 2026-10-02): up to five straight plays on Saturday and Sunday, a mix of game lines and player props
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
- **Tweets are short and human** (2026-09-26, reason sentence added Oct 4): the play with price
  and book, "We have it at 47.", one saved supporting reason when available, "❤️ if you're tailing", @Playbook
  and the league tag. No labels or slogans. POTD: "POTD: ..." first. Lotto: "🎰 +2506 COLLEGE LOTTO (ESPN BET)" then the legs.
- **The Kook'n 80/20 Climb** ($50 to $1,000 bankroll ladder, `scripts/ladder.py`): bank 20% of every winning return and ride 80% on
  the next rung, so a miss cannot take what was banked. Prefer two independently strong legs around -400 at one book,
  together -180 to -130, so protection does not make the climb take forever. Feed-priced player alternates and exact,
  freshly verified sportsbook alternate spreads/totals may mix, but every leg must agree with the model and stay in a
  different game. One rung open at a time; after it settles, the next scheduled scan may advance or restart the
  climb the same day. NFL player legs run now; college player legs wait until their own numbers are calibrated.
  Never force it on a one-game slate: the two legs stay
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
- **Projected-winner record** (2026-10-02): every pregame score projection also grades the team it made more likely
  to win straight up. Show that moneyline-style W-L-P record and hit rate by league, model, season and week on Today
  and the model scoreboard. It is model accuracy, never an official play or a profit claim; do not calculate units
  without a real captured moneyline price.
- **Weekly "📌 Save this" projection sheet**: the full NFL slate or 16 college games, college Saturday and NFL
  Sunday at 10 AM (`scripts/sheet.py`). Every spread and total read carries the exact captured line, price and book.
  Numbered mint rings identify up to four markets where the calibrated chance clears that price by the Board's value
  threshold and name the wager itself (`OVER 45.5`, `MINN +3.5`), not merely `TOTAL` or `SPREAD`; the selected priced
  line, rather than the model projection, is mint. Missing, stale, thin and pass prices never get a ring;
  performance-caution lines must clear their higher threshold. They are watches, not official plays.
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
- **The site**: the projection-card look everywhere (logos, photos, tiles), tabs Board, Games, Players, Scoreboard,
  More. The Board leads with official plays; its season scorecard follows the official record before any optional
  research, shows the graded-game count and last graded kickoff, and links to the full scoreboard. The separately
  labeled model scorecard shows spread vs close, projected
  moneyline winner, total vs close, player projection vs captured line, and published fun parlays. The first four
  are model accuracy and the parlay tile is labeled separately; never imply the mixed card is a profit record.
  Every upcoming game page has **Kook'n favorite lines**: every fresh, actually priced main line the calibrated
  Board likes, ranked by edge against the price with line vs projection and exact-line last-ten/season hit rates
  shown when stored history exists. Alternates are the reader's optional choice, not the listed favorite; an empty
  panel is better than a forced line. These are optional reads, never extra official plays. When a current hard
  QB/RB/FB/WR/TE injury appears, the game page pairs it with ESPN's listed offensive depth order, names the next
  player up and shows the model's already-adjusted workload without calling it a touchdown projection. The same card
  compares that player's own season usage with the team's actual depth role by offensive snaps, including red-zone
  carries/targets and inside-the-10 work from stored play-by-play. It may label a backup **Sleeper watch** only when
  both the historical role and the adjusted current projection show useful volume. A lower-volume backup can be a
  clearly qualified **Deep sleeper** only when the role has real red-zone work; call it a touchdown dart, never a
  touchdown projection or official play. Always check changes at 375 px.
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
