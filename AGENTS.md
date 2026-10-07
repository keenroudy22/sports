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
   at 6:45, 8:30 and 11:45 AM, 5:30, 9:00 and 11:30 PM Eastern (plus 2:45 PM Sunday and 6:50 PM Sunday, Monday, Thursday),
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
   never falls through to it. The live web researcher uses `codex exec` with `gpt-6-sol` at low reasoning by default.
   The local homepage editor selects exact research notes after social scheduling. The weekly review uses the local
   27B model to select exact evidence excerpts, with a deterministic packet fallback.
   Only an explicit `review.py --codex` uses the cloud review model at medium reasoning. Named researcher/review
   settings live in `deployment/mac/env.example`.

Your job as the agent is what a person would do: answer the owner's questions, change the code, deploy it safely,
watch the runs, and fix what breaks.

## Talking to the owner

- Plain words, short sentences, the answer first. No jargon ("CLV", "calibration") without saying what it means.
- Use they/them for the owner.
- The owner delegates ("do what you think makes the most sense and get it done") but decides anything public: new
  post types, how the record counts, how many plays go out. Tested layout/color/copy variants within an already
  approved category and its existing caps are approved; a new category, channel, market or release policy is not.
- Say plainly when something failed, including your own mistakes, and what you did about it.

## Product continuity: finish, verify, carry forward

Before continuing product work, read `docs/PRODUCT-IMPLEMENTATION.md` and `docs/product-status.json`. The dated
plan is the design baseline; the tracker holds release evidence; the status file is the finite outstanding-work
queue. Do not restart the audit or silently drop work when the owner changes model or sends another prompt.
Honor their latest priority, preserve unrelated changes, and give unfinished items a stable ID, owner, specific
next action and observable completion condition. Mark an item shipped only after its stated verification and
successful release, with evidence. Never substitute “later” or a queued publish for completion.

The existing weekly review includes this queue deterministically, even if the local model omits it. A missing,
invalid or stale queue must be visible, not reported as all done. The review surfaces work; it does not grant
permission to change code, publish new categories, spend money or activate paid access. External/time gates stay
explicit until real evidence clears them. The current operating-policy summary is in the implementation tracker;
this file remains the authority when a summary and rule disagree.

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
2. Change the code, add or update tests, and pass both suites in the development worktree, then repeat them from
   a clean export that contains the current Git-visible files but no generated `site/data/app/`:
   `cd ~/Projects/sports-dev && /opt/homebrew/bin/python3 -m unittest discover -s tests` and
   `cd ~/Projects/sports-dev && node --test tests/*.test.js`, then
   `cd ~/Projects/sports-dev && /opt/homebrew/bin/python3 scripts/clean_export_tests.py`. Do not use `run.sh py` for
   these: that wrapper deliberately changes into the production checkout. The clean-export gate catches hidden
   dependencies on ignored build output before a fresh hosted checkout does.
   After building the site, run `python3 scripts/publication_guard.py`. The hosted workflow also checks the exact
   upload folder before publishing. Unknown file families and known private artifacts/credential fields stop the
   upload; never weaken the guard just to copy owner-only evidence into the site. `docs/PUBLIC-PAYLOADS.md` lists
   the reviewed public families. This is not a paywall, license clearance or complete secret scanner.
3. Rehearse against isolated stored inputs, without any feed/model calls or production writes:
   `cd ~/Projects/sports-dev && /opt/homebrew/bin/python3 scripts/rehearse.py --slot HHMM`.
   Use the current scheduled window, not a fabricated future instant. This copies the desk inputs to a fresh
   temporary workspace, executes the real `run.py` dry-run there, blocks network/process calls and outside writes,
   and retains the log, reports and `result.json` there. Require exit 0 and outcome `ok`; inspect any denied outside
   write/private-state access. Missing network-only evidence is expected and must never be invented to make the
   rehearsal pass. This tests stored-input behavior, not fresh prices, current injury verification or real delivery.
   `run.py --dry-run --no-llm` alone is **not offline**: live scoreboard/news/weather paths and optional rendering
   may still run, and it can leave drafts/pending/failed files in the shared private desk. Do not use that command
   as an isolated test. Do not delete a real failure report to clean up a rehearsal.
4. Commit on `dev` as keenroudy22, ending the message with an attribution line for the agent that wrote it.
5. Deploy while holding the run lock (it waits for a run in progress), then fast-forward and push:
   ```
   cd ~/Projects/sports
   /opt/homebrew/bin/python3 - <<'PY'
   import fcntl, os, subprocess, time
   from pathlib import Path
   prod = Path('/Users/keen/Projects/sports')
   dev = Path('/Users/keen/Projects/sports-dev')
   env = {**os.environ, 'GH_CONFIG_DIR': '/Users/keen/.config/keenroudy/gh',
          'GIT_CONFIG_NOSYSTEM': '1'}
   def command(args, cwd):
       subprocess.run(args, cwd=cwd, env=env, check=True)
   def clean(path):
       state = subprocess.run(['git', 'status', '--porcelain'], cwd=path, env=env,
                              check=True, capture_output=True, text=True).stdout
       if state.strip():
           raise SystemExit(f'{path} is not clean; preserve and review changes before deployment')
   lock = open('/Users/keen/.config/keenroudy/run.lock', 'a')
   while True:
       try:
           fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); break
       except OSError:
           time.sleep(5)
   clean(prod)
   clean(dev)
   command(['git', 'fetch', '-q', 'origin'], prod)
   command(['git', 'merge', '-q', '--ff-only', 'origin/main'], prod)
   tested_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=dev, env=env,
                                check=True, capture_output=True, text=True).stdout.strip()
   command(['git', 'rebase', '-q', 'main'], dev)
   rebased_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=dev, env=env,
                                 check=True, capture_output=True, text=True).stdout.strip()
   if rebased_head != tested_head:
       raise SystemExit('Rebased dev; repeat rehearsal and affected visual checks, then retry deployment')
   command(['/opt/homebrew/bin/python3', '-m', 'unittest', 'discover', '-s', 'tests'], dev)
   node_tests = sorted(str(p.relative_to(dev)) for p in (dev / 'tests').glob('*.test.js'))
   if not node_tests:
       raise SystemExit('No frontend tests found; refusing deployment')
   command(['node', '--test', *node_tests], dev)
   command(['/opt/homebrew/bin/python3', 'scripts/clean_export_tests.py'], dev)
   clean(prod)
   clean(dev)
   command(['git', 'merge', '-q', '--ff-only', 'dev'], prod)
   command(['git', 'push', '-q', 'origin', 'main'], prod)
   PY
   ```
   Each test's exit code must stop deployment on failure; never pipe a test into `tail` without preserving the
   test's status. If the rebase changed code after the rehearsal/visual QA, repeat affected verification before
   promoting. If `~/Projects/sports` is not clean, inspect first: commit genuine stopped-run captures as "Captures
   left by a stopped run", preserving unrelated edits. If a rebase stops on a store, `python3 scripts/merge_store.py`
   resolves it, then `git rebase --continue`. Never discard data or force the merge.
6. Watch the publish run until it passes (`gh run watch <id> --exit-status`), then check the live site at phone
   width (375 px): no sideways scroll, no console errors, and no rendered `did not load` error state.

## The owner's current rules (newest first; `DESK.md` has the reasons)

- **Free queue protection (owner-delegated to Claude, 2026-10-06):** Buffer holds ten scheduled posts.
  At seven pending posts, reserve the last three places for best bets, POTD relabels, reschedules and receipts.
  Optional research, news, conversation, menus, sheets and other-sport posts defer. Every health and Monday
  report starts with the count of official plays not scheduled.
- **Football free-credit plan (owner-delegated to Claude, 2026-10-06):** use Option A. Game-line captures
  average about eight credits daily, Odds API props run on weekends only at twelve credits daily, and easy
  parlays use existing SharpAPI alternates with zero Odds API credits. Preserve the 24-credit reserve, repair
  monthly rollover, warn above a projected 450 credits and count SharpAPI/Buffer requests privately. From
  November, cap each football league's game lines at seventy credits and props at one hundred monthly.
  SharpAPI Free has no monthly cap, twelve requests/minute, two books and a sixty-second delay. No paid trial.
- **Publisher mark and felt cutover (owner-delegated to Claude, 2026-10-06):** use `kookn-mark.png` for the
  Discord publisher and retain `kookn.jpg` for legacy cards. The reviewed felt cards are approved. Set the
  cutover with an explicit -04:00 offset only after a green 11:30 PM run and before the next 8:45 AM menu.
  Preserve posted attachments. Track the final review's nonblocking hardening separately.
- **Resource and voice work order (owner-delegated to Claude, 2026-10-06):** implement the approved P1 order
  in `docs/CODEX-WORK-ORDER.md`: price checks on research, Good-to/latest quotes, human copy and universal
  send guards, QB news, combined hit windows/search/presets, player custom-line tools, game changes/history/books,
  publication proof/share pages, record market splits/calibration, research upset demotion, approved heart variants,
  website live progress, every-game research lists and factual result margins/line moves. One natural exclamation
  is allowed on cashed and receipt wins, never consecutive or on a pick. Record counting remains unchanged.
- **Learning loop (owner-delegated to Claude, 2026-10-06):** lessons are append-only and close with named
  deterministic tests. Read open lessons, the latest Monday review, benchmark and voice before product/copy work.
  Verification includes revision, successful checks, fresh-cache positive content and source-number comparison.
  Local Qwen selects IDs, tags feedback and flags copy from supplied evidence; code supplies numbers and public
  sentences. No cloud fallback. Monday packets carry delivery misses, lessons, voice hits, record/line movements,
  learning preview, judge/researcher counts, category/theme/copy results (no winner below eight posts), owner-entered
  audience deltas, health, payloads and local/cloud use. Proposals are tagged fix, shadow or owner-yes.
- **Other sports rollout (owner-delegated to Claude, 2026-10-06):** ESPN free feeds only; zero Odds API,
  SharpAPI or SportsGameOdds calls outside football. NHL first, NBA by October 20, EPL from October 17, CBB
  in November and MLB at Opening Day. Use lazy `sports.js`. Resume the existing slate card, add one rotating
  trend board daily and a weekly paper-trial receipt, subject to first-category render review by Claude.
  Other-sport caps are three weekdays/two weekends and one per league, dropped first under shared caps.
  Discord mirrors after X in Plays & Results with the league first. Trends require five current-season games,
  verified exact sides/prices no shorter than -200, no goalie saves and listed probable pitchers only.
  Last-season charts are separately labeled website-only until ten current games. ESPN data/art risk is
  accepted for free use and revisited before payment. Official new-sport releases still require P11.
- **Undecided choices retained (owner-delegated to Claude, 2026-10-06):** Cloudflare analytics disposition,
  R2 NFL-total pause, POTD-missed posts, primetime prop sheets, locked Climb phrase, dollar line under Units,
  owner biography and deletion of unused local models remain undecided. R0-R7 stay silent shadows.

- **Casino-felt palette (2026-10-06, owner approved):** Kook'n site and new card art use felt night `#07120D`,
  felt `#0E2219`, chalk `#F2F7F4`, dim `#A9C0B3`, Kook'n green `#20C774` and chip red `#F2414E` (fills only;
  `#FF6B75` for red text). This replaces the navy/mint/cyan foundation of Oct 1/2/5. Green means hit or support,
  red means miss and gray means unknown, always with a symbol or word. Brand green never implies a result on an
  open play. Text stays at WCAG AA; dark ink goes on green and red fills. Brown/tan/amber stay banned. Cards choose
  their theme by publication time; posted attachments never change.
- **Kook'n best bets (2026-10-06, owner approved):** “Best bets” is the public name for official plays, with the
  same set, gates, caps, grading and record. It is never advice. The research “Best lines” label is retired. Public
  copy drops “official card”, “plate”, “Served at” and “desk”. Internal names are unchanged. Entertainment-only
  and 21+ wording stays on every page and card. This supersedes “no public rebrand” in `SUBSCRIPTION-PLAN.md`.
- **Website redesign (2026-10-06, owner approved and live; supersedes the Oct 5 navigation):** the main
  navigation is Today · Research · Games · Record · More. Today shows beginner-first best-bet tickets with the
  published price/book, stored calibrated chance versus break-even, fair price, edge, why, one visible counterpoint
  and a hit chart. One sortable Research board replaces the line and trend tabs. The noindex preview passed review;
  production now uses this navigation. Every existing hash, `#pick/<id>` and shared research link
  keeps opening its equivalent view. Confidence badges are removed; value rank (edge) is the default sort. Thin,
  stale, unpriced and uncalibrated rows get no rank. Main lines stay the default, with the four-hour freshness limit
  and three-game minimum. Record math reuses `core.js` unchanged.
- **Share cards and X (2026-10-06, owner approved):** existing categories are restyled only. Filenames, dimensions
  and Discord's 8 MB limit are unchanged. Captions keep the Sep 26 shape; chance and break-even live on the card.
  No new post type, slot, frequency, Playbook use or automation is approved. The owner sets the bio, pinned post and
  banner and writes replies by hand. Claude may upload the new banner once, attended. ESPN player photos and team
  logos stay on the site and card art; team-color badges are the fallback.
- **Results proposals stay in shadow (2026-10-06, owner approved process):** R0–R7 run as silent, logged shadows.
  They make no new metered requests and change no play, card or record. Each needs its own owner yes with before/after
  counts. The NFL-totals pause would override the Oct 4 “not a veto” rule only on that yes.
- **Redesign boundaries (2026-10-06):** each new public file type gets a narrow guard entry, test fixtures and a
  `PUBLIC-PAYLOADS.md` line; never a wildcard. New built data only adds files under `site/data/app/`. Tracked schemas,
  `record_audit.py` and integrity checks do not change. The RSS feed is renamed “Kook'n” and keeps its item IDs.
  Not approved: analytics, domain purchase, homepage edits, Cloudflare, Whop, payments or referral links.
- **Logos and photos stay (2026-10-06, owner approved):** keep ESPN team logos and player headshots on the website
  and cards, with team-color badges as the fallback. `SOURCE-RIGHTS.md` stays open; revisit before any paid launch
  under P08.
- **Short research-post voice (2026-10-06, owner approved):** research captions lead with the exact line and one
  useful proof point. Keep them short and natural. Do not append boilerplate such as “history does not predict the
  next game,” repeat “not an official play” in the caption, or add a generic “save this” request. The graphic keeps
  a compact positive research-category label so it remains distinct from an official play. This is a copy/layout
  change inside the existing research category; it adds no post, play, tag, price, market or selection rule.
- **Matchup-trend context (2026-10-06, owner approved):** game pages may combine a fresh exact main-line player
  trend with the opponent's allowed-by-position/stat rank and the stored projected score. This is visible research,
  not a required input to the official-play formula and never creates, removes or upgrades a play. In CFB, a player
  whose team is projected to lose by at least 14 points carries a game-script caution and ranks below otherwise
  comparable matchup research because normal usage may not hold. Do not hide the line or pretend the caution proves
  an over or under. The existing optional Matchup research post may feature the strongest defense-supported main
  lines under the existing one-research-post cap, four-hour quote freshness and five-game history minimum; it adds
  no post slot, alternate line, paid call or Playbook tag.
- **Season and postseason record lifecycle (2026-10-06, owner approved):** every official published record keeps
  provider season and stage metadata. The default Record view is each selected sport's current season and current
  stage; the first postseason play starts a separate playoff view, and the first play of a new season starts a new
  regular-season view. Older regular seasons and playoffs remain browsable and are never rewritten. Personal/social
  tickets remain outside the official record. New-sport trials and collection coverage may be grouped by season and
  stage, but must stay labeled separately from official plays and prediction wins. The hosted build must reconcile
  the public pick IDs and settlements against the append-only research history before deployment.
- **Fresh POTD comparison (2026-10-05, owner approved):** the first POTD designation must compare every open
  official single for that Eastern game date against a matching fresh current-board market from the same run.
  Rank those official singles by the calibrated edge at the current quote, not the older saved publication price.
  An official play with no matching fresh board market receives no POTD label yet. A current market that was not
  admitted as an official play cannot become POTD, create an extra pick, bypass the daily card cap or weaken any
  price, availability, overlap, calibration, performance or news gate. Once named, POTD remains fixed unless the
  pre-post check pulls it; the existing replacement rule then uses the best remaining fresh official single.
- **Product implementation approval (2026-10-05; navigation superseded 2026-10-06):** implement the approved
  product plan in small, verified releases. The live main navigation is now **Today / Research / Games / Record / More**.
  Games includes Upcoming,
  Live and Final; `#scores` remains an alias into the Live view, not a competing main tab. Preserve `#board`,
  `#stats`, trends, player/game deep links, sport context and back navigation. Each sport retains its own Today;
  unsupported capabilities are explicit. Today puts compact actual published selections first (POTD then an
  active Climb), followed by official results and optional research. An unposted Climb is a small status, not the
  hero. Model accuracy remains separate under Record. This contract supersedes all older Board/Players/Scoreboard
  and Scores-main-tab instructions below. `docs/PRODUCT-IMPLEMENTATION.md` tracks evidence and unfinished gates.
- **Evaluation windows, not quotas (2026-10-05):** schedules promise checks and useful status, never a guaranteed
  pick, parlay or ladder step. Card sizes and post counts are ceilings. A qualified/no-play/held state is distinct
  from a delivery failure. Existing price, sample, calibration, availability, overlap, record, cadence and budget
  checks remain; never lower them to fill a slot. The Climb may advance/restart after settlement on a later
  qualifying scan, including the same day, but only one real rung is open at a time.
- **Creative testing within approved releases (2026-10-05):** rotate tested original graphic and short-copy
  variants within existing categories/caps; exact wording and facts still pass the guards. Green means a hit or
  support for the selected side (including an under); red means miss/against that side; gray means unknown/inactive.
  Pair colors with numbers/text/icons. Keep the chef/name and navy/mint/cyan foundation; no avatar replacement or
  brown/tan/amber house palette. Preserve samples, book, price and timing; do not regenerate old public attachments.
  **Not approved by this implementation:** alternate/milestone social research, new-sport pick promotion, public
  X live-progress, automated replies, broader social frequency, account/billing activation or creator outreach.
  Social trend research remains fresh **main lines only**, at least five games, in its existing optional slot.
  X live-progress still needs the separate pilot-review/release checkpoint.
- **Business readiness and source rights (2026-10-05):** safe product polish continues free. Record provider and
  asset permissions in `docs/SOURCE-RIGHTS.md`; public accessibility is not a commercial license. ESPN/portrait,
  nflverse upstream and SharpAPI use boundaries require review before expansion/monetization. Do not add feeds,
  increase limits, contact counterparties or activate payments through this approval. `docs/SUBSCRIPTION-PLAN.md`
  sets measurable reliability/usability/cohort gates; four weeks cannot be declared complete in one release.
  Browser-local Saved and opt-in feedback remain private; no new tracking or automatic message subscriptions.
  Future paid payloads require server-side entitlement checks, not hidden public JSON. Public results remain free.
- **Personal tools and visual refresh (2026-10-05):** changing the sport stays in the current section; each sport
  has its own Today view. Unsupported research stays honest and never substitutes NFL data. This supersedes the
  older non-football selector redirect to Scores. Saved players/games/lines and original-vs-latest same-book quotes
  live only in browser storage. Daily Digest is an on-demand website page, not a Discord subscription or new post.
  Feedback is manually copied/sent, with optional local section counts; no external analytics added. Start Here
  links quick plays versus research. Discord guide edits require confirmation; no new bot or channel is installed.
  Straight-play and research artwork now uses full portraits, large exact selections, restrained wordmarks and
  room for wrapped text. Keep the chef identity; no public avatar replacement. Every historical count/window stays
  visible, never market a mixed-hit sheet as 100%. Existing post selection, frequency, budgets and release gates
  are unchanged. Do not recreate already-published attachments merely to change their design.
- **Website-first new sports (2026-10-05; navigation superseded above):** Scores keeps its route alias, and the
  header selector exposes all nine leagues. NFL/CFB Games and Charts retain their football research; other sports
  show their own supported capability within the selected section, never silently redirect or show NFL data.
  Show saved NBA/CBB pregame trial projections and trial
  totals W-L-P separately from official plays; zero settled trials means pending, not a proven record. MLB/NHL
  line/final collection counts are not prediction wins. No new model or edge is invented to fill a page.
  Keep new-sport research on the website first. Optional multi-sport schedule social posts are paused by default
  (`KEENROUDY_SPORTS_SOCIAL=0`); a later owner decision is needed to resume. New-sport picks still require their
  documented trial/release gates. Existing football posts, public results and budgets do not change.
- **Casual live-update voice (2026-10-05):** the owner wants occasional natural cheering, e.g. "9 to go. Come on!"
  alongside the exact player/line and live clock. Drop redundant "Posted play" labels on straight updates.
  Keep quieter factual updates too; never repeat the casual style consecutively. This exception permits the
  exclamation in live-progress copy, not guarantees, invented urgency or premature wins. All pilot gates stay.
- **Local live-progress Discord pilot (2026-10-05, owner approved occasional midgame updates):** the existing
  five-minute observer can nominate already-public player overs and full-game total overs for a short text-only
  "what's left" update. The local 27B model selects an exact candidate and wording style; code supplies every
  number. Require two recent observations with game-clock movement, no stat regression, then re-fetch the chosen
  game before sending. Two updates per Eastern date, 45 minutes apart, one per ticket, ten minutes clear of ordinary
  Discord releases. No Playbook, mentions, replies, new picks or early "cashed" claims. Max three attempted pilot
  messages, then pause and notify the owner for review; ambiguous delivery pauses without retrying. No cloud
  fallback or metered odds calls. `KEENROUDY_LIVE_PROGRESS=0` disables delivery; the shadow kill switch disables both.
  X remains off pending three reviewed clean Discord trials and the separate release checkpoint. Scores and stats
  are supplied by the feed, never inferred by the local model. See `docs/LIVE-PROGRESS.md` for rollout evidence.
- **Local homepage editor (2026-10-05, owner requested more local liveliness):** after official social scheduling,
  each normal Mac desk run may use the local 27B model to select up to three exact supplied research notes for
  Today's compact Worth a look section. Fresh main-line season trends, observed red-zone usage and confirmed
  multi-sport fixtures only; no free-form facts, picks, live calls, forecast changes or new social posts. One
  180-second call at most, no calls within an hour, unchanged facts reuse the selection. No cloud fallback.
  Site notes expire at kickoff or their source cutoff; research stays below official plays. Failures never block
  official scheduling. `KEENROUDY_LOCAL_EDITOR=0` disables future selection; `--no-llm` skips it too.
  This is local editorial work, not autonomous website code editing or deployment.
  Sports requests ask Ollama to retain the model for 12 hours between checks (evictable, not pinned).
  `KEENROUDY_LLM_KEEP_ALIVE=15m` restores the former memory-saving behavior; no shared server setting changes.
- **Overnight polish and multi-sport release (2026-10-05; navigation superseded above):** Games includes live scores and
  Today links to all seven additional leagues. Browser score refresh preserves open sections and scroll, checks
  yesterday for midnight games, backs off failures, and never advances a successful timestamp on an error.
  Supplied DraftKings pregame lines may appear in Scores with retrieval time, never as verified in-play odds;
  hide them at kickoff or after a failed refresh. MLB/NHL team results use stored finals with coverage labeled.
  One optional factual multi-sport schedule card is due 5:50 PM ET, selected from fresh, confirmed evening/late
  fixtures at the 5:30 desk run. No picks, odds, Playbook mention or quota increase. It is lowest priority under
  the existing daily cap, mirrors only after X, and uses a frozen source snapshot plus eight-day image retention.
- **Late-slate capacity (2026-10-05):** add the daily 9 PM desk run to the existing schedule. On weekend slates
  with an evening game, reserve the fifth straight-card place until 4 PM. The five-play and three-of-kind caps
  remain unchanged. Reserve the final daily Odds API capture for after 4 PM when evening games exist; no credit,
  cadence, monthly or daily limit increases. The existing four dedicated Climb scans remain unchanged.
- **Local weekly brief (2026-10-05):** Monday's private review now selects exact evidence excerpts with the local
  27B model, at most one 180-second call. No invented summary figures and no automatic cloud fallback. Save the
  full deterministic packet regardless. `review.py --codex` is an explicit cloud-review option; verified live
  web and settlement research still use Codex. Sports local-model calls serialize without a retry queue.
- **Futures paper infrastructure (2026-10-05):** `scripts/futures_store.py` validates and appends exact sourced
  paper quotes, movements and settlements with an integrity ledger. No watches were invented or imported, and no
  official future or auto-feed collection is enabled. Special settlement cases stay pending for evidence.

- **Visual Player Charts replace the directory (2026-10-04):** the main Stats tab is a matchup-first player
  cheat sheet, not a season-leader directory. Show compact game-by-game bar charts for every stored player stat,
  with current main line, current projection, recent hit count/average, position, slate-date, sample-window and
  player-search filters. Group the next slate by matchup and team; tap through to the full player page. Build a
  compact payload from existing upcoming role forecasts, stored logs and captured lines so college remains fast on
  mobile and adds no feed cost. Keep the full player directory as a secondary Search tab. Unknown values stay
  unknown, historical games remain regular-season only, and this research view does not create official plays.
- **Lifetime Climb dollars (2026-10-04):** track the 80/20 Climb in dollars across every published rung. Show settled
  stakes, actual returns, settled net and any currently live stake separately; a live wager does not become a win or
  loss before settlement. Each past rung keeps the cumulative net immediately after that result, so the public can
  follow the total over time. A winning return includes the stake, a push or void returns its stake, and a loss
  returns zero. This accounting is derived from the append-only rung ledger and never changes the official record.
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
  70/80/90/100% minimum-hit filters, stat/type/history-window filters and player research links. Open on fresh
  main lines across all upcoming games; let readers switch among This Season, Last 10 and Last 5. Show exact hits/games,
  regular-season recorded appearances only; unknown stats suppress the row rather than inflate its rate.
  Main and alternate lines require captured prices no older than four hours; unpriced statistical milestones
  are explicitly separate and are never sportsbook offers or picks. Use existing stores, with no new requests.
  At least three recorded games on-site; at least five and a fresh public-book quote for social research.
  X trend boards use fresh main lines only, include the exact line and full-season count, carry Kook'n branding,
  never tag Playbook and remain research rather than official plays. Season trends get first consideration on even-numbered dates in the existing optional research slot,
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
- **Transparent Board (2026-10-02):** official plays first; future plays grouped separately. The October 5
  five-destination navigation supersedes the older labels; old hashes remain valid. The headline separates all published W-L from
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
- **The daily card** (2026-09-28, ceilings clarified October 2/5): up to five straight plays on Saturday and Sunday, a mix of game lines and player props
  (three of a kind at most); up to one on other days (`gates.card_cap`, ordered by `run.rank_card`). An NFL-day post
  can be research, status or a receipt; it does not require a pick. Evaluate fun tickets on weekend slates only
  within the latest main-line-first/alternate-frequency and no-stacking rules; no guaranteed parlay. Pick of the Day is
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
  in different games. A qualifying rung must complete its approved delivery; alternates are allowed, not a quota.
  A rung pulled before its X post still counts, win or lose; while ungraded it blocks the
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
  to win straight up. Show that moneyline-style W-L-P record and hit rate by league, model, season and week in
  **Record → Model**, not on Today. The October 5 product contract supersedes the older Today placement, not the
  underlying grading. It is model accuracy, never an official play or a profit claim; do not calculate units without
  a real captured moneyline price.
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
  Single-play days get no filler. No automated replies, likes, follows or unfollows; the only automated trend post is
  the approved evidence-first main-line board in the existing one-research-post daily slot. No bought or
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
- **The site**: the projection-card look everywhere (logos, photos, tiles), using the October 5 navigation and
  ordering above. Today leads with official plays and a compact official-results strip. Full model accuracy is
  under **Record → Model**, not on Today, with graded-game count and last graded kickoff. The separately
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
the GitHub runs, `line_timing.py`), has the local model select a brief from that evidence read-only, saves it to
`~/Library/Logs/KeenRoudy/review-<date>.md` (the facts in `review-packet-<date>.md`) and sends its opening to the
owner's phone. It changes nothing. When the owner asks you to act on a review, read that file, then fix what it names
the way this file says. To run it by hand: `~/.config/keenroudy/run.sh py scripts/review.py` (`--no-codex` for the
packet only, `--no-push` to skip the phone, `--codex` for an explicitly requested cloud review).

## When something breaks

- **"STOPPED: ... fails validation"**: a report broke a rule in `scripts/refresh.py validate_report`; the report is
  kept in `~/.config/keenroudy/failed/`. Fix the code that wrote it, test, deploy. Never edit the report to pass.
- **A run left files uncommitted** (`data/odds`, `data/prop-odds`): commit them as captures and push under the lock.
- **"git fetch raced another git client"**: another app refreshed the repo; the run retries by itself.
- **A post did not go out**: `run.sh py scripts/buffer_post.py reconcile` shows the error; the phone gets an alert.
- **The local model is down** (`curl -s localhost:11434/api/version`): the desk falls back to templates and rules.
- **The web researcher fails**: `codex login status`; the desk keeps running without it.
