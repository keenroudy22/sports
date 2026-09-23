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

The schedule runs in dry-run mode until the sports GitHub login exists and publishing is turned on
by editing the job's `ProgramArguments` and reloading it (the plist says how). Live publishing is meant
to be turned on one kind at a time with `--publish-kinds`.

## The local model

Ollama serves the model at `http://localhost:11434`; `KEENROUDY_LLM_MODEL` in the env file names the
tag. The model is asked for prose and judgment only. Every rewrite passes `llm.check_style` (no em or en
dashes, plain words, short sentences, no model or version names, no marketing, no advice) and
`llm.numbers_ok` (every number in the text appears in the pick's fields, the desk output or the facts),
or the template stands. A judgment counts only when it points at a fact by id; unsure means hold.
With Ollama down the run publishes on templates and holds on a quarterback rule of thumb.

## X

Only researched favorites go to X. Drafts land in `~/.config/keenroudy/x-drafts/` and post only with
`--confirm`; the autonomous path needs both `KEENROUDY_X_AUTONOMOUS=1` and `--i-understand` and stays
off until the owner asks. Every post is logged in `data/x-posted.json` with its id and a hash of its text,
and X's own duplicate refusal is the backstop. A post links to `https://keenroudy.com/sports/#pick/<id>`,
which opens that pick's card with its reasoning.
