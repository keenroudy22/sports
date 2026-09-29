# Moving the desk to GPT: the exact steps

Written 2026-09-28, when the owner moved the desk's AI work from Claude to OpenAI's GPT.

## What changes and what does not

**Nothing about the desk itself moves.** It runs on its own and never needed an AI chat to run:
- the Mac runs the desk on its schedule (launchd: 6:45, 8:30, 11:45 AM, 5:30 and 11:30 PM Eastern, plus Sunday
  2:45 PM and Sunday, Monday and Thursday 6:50 PM), the pre-post check every 30 minutes, and the 7:15 AM heartbeat;
- GitHub runs the captures, forecasts, site build and deploy (`.github/workflows/publish.yml`);
- Buffer posts to X; ntfy sends the phone alerts; Ollama on the Mac (Qwen, not Claude) writes and weighs. The 8B local
  model handles guarded rewrites, while the 32B model is reserved for judging verified facts.

**Four things change:**

| Was | Now |
|---|---|
| You asked Claude (this app) to change, fix and deploy the desk | You ask **Codex**, OpenAI's coding agent (part of ChatGPT). It reads `AGENTS.md` in the repo, which has everything it needs. |
| The desk's news check read the web through the `claude` command | It reads the web through the `codex` command (`KEENROUDY_RESEARCHER=codex`) |
| A Claude scheduled task reviewed the weekend on Monday | You ask Codex on Monday (prompt below) |
| Claude kept notes about your preferences | They are written into `AGENTS.md` and `DESK.md`, where Codex reads them |

What you need: a ChatGPT plan that includes Codex (Plus or Pro). No API key, no new bill.

## Step 1: install Codex on the Mac Studio

Already done for you on 2026-09-28 (`npm install -g @openai/codex`). To check, open Terminal and run:

```
codex --version
```

If it says "command not found", run `npm install -g @openai/codex` and check again.

## Step 2: sign in with your ChatGPT account (you do this; it needs your password)

```
codex login
```

Pick **Sign in with ChatGPT**; a browser window opens; sign in and approve. Then check:

```
codex login status
```

It should say you are logged in. The desk never sees your password or a key; Codex keeps its own sign-in.

## Step 3: switch the desk's news check to GPT

One command changes one line in the desk's settings file (it prints nothing):

```
sed -i '' 's/^KEENROUDY_RESEARCHER=.*/KEENROUDY_RESEARCHER=codex/' ~/.config/keenroudy/env
```

Check it took (prints the setting's name and value, which is not a secret):

```
grep '^KEENROUDY_RESEARCHER=' ~/.config/keenroudy/env
```

Test it on a real game (it takes a minute or two and prints the facts it verified):

```
cd ~/Projects/sports && ~/.config/keenroudy/run.sh py scripts/researcher.py NFL-401872963 --market total --side over
```

Use any upcoming game id from the site's game pages (the part after `#game/`). If Codex is not signed in, the desk
keeps running and simply works without the news check. Leave the setting empty to turn the news check off; unknown
or retired provider names do not trigger a fallback.

The routine news check pins `gpt-6-sol` at low reasoning instead of inheriting the interactive Codex model. The
Monday review pins it at medium reasoning. These defaults save plan usage without moving live-news verification to
an offline model. Their optional overrides are listed in `deployment/mac/env.example`.

## Step 4: work with Codex instead of Claude

Open Terminal and start Codex in the desk's working copy:

```
cd ~/Projects/sports-dev
codex
```

(Or open the same folder in the ChatGPT desktop app's Codex.) The first time, send it:

> Read AGENTS.md and DESK.md. Then run `~/.config/keenroudy/run.sh doctor` and tell me in plain words how the desk is
> doing: the last runs, what posted on X, and anything that failed.

From then on, talk to it the way you talked to Claude ("why no NFL post yesterday", "add a ladder post", "make the
tweets shorter"). `AGENTS.md` tells it how to change the code and deploy safely: test, rehearse, take the desk's run
lock, push as keenroudy22, and watch the site deploy. When it asks to run a command, it is asking for your approval;
approve the ones in `AGENTS.md`'s deploy steps.

## Step 5: the Monday review (automatic)

A Mac job runs every Monday at 9:30 AM Eastern (`com.keenroudy.sports.review`, installed 2026-09-28): it gathers the
week from the desk's records, has GPT (Codex, read-only) write the review, saves it to
`~/Library/Logs/KeenRoudy/review-<date>.md`, and sends the opening to your phone through the usual alerts. It changes
nothing. To act on it, tell Codex:

> Read this week's review in ~/Library/Logs/KeenRoudy/ and fix what it names, the way AGENTS.md says.

To run it any time: `~/.config/keenroudy/run.sh py scripts/review.py`.

## Step 6: the Claude pieces are off

- The Claude scheduled task "KeenRoudy weekend check-in" was a one-time review for 2026-09-28; it is disabled and its
  stuck run stopped. No Claude routine is scheduled for the desk.
- Nothing on the Mac depends on Claude now: the news check runs only on Codex (Step 3), the review runs on Codex
  (Step 5), and `run.sh doctor` checks only the tools the desk uses. The Claude app can go.

## Graphics and posts

Codex knows every post's words and card from `docs/POSTS.md` (examples in `docs/examples/`), which `AGENTS.md` points
it to. Ask it to preview before changing a post: it can draw any card and draft any tweet without posting.

## What Codex must never do (the short list; `AGENTS.md` has the rest)

- Touch anything of MyGolfLinks (MGL), or push as anyone but `keenroudy22`.
- Edit published picks or the record's ledgers by hand, or invent a price.
- Put a key or password anywhere, or type your passwords.
- Click around X in a browser, or delete a post that already went out.
- Deploy in the middle of a desk run (it takes the run lock).

## Where everything is (for Codex and for you)

- Repo: `keenroudy22/sports` on GitHub; the desk's clone `~/Projects/sports`; the working copy `~/Projects/sports-dev`.
- Settings and secrets: `~/.config/keenroudy/env` (names only in `deployment/mac/env.example`); GitHub secrets
  `ODDS_API_KEY` and `SHARP_API`.
- The Mac's own setup, copied into the repo: `deployment/mac/` (`run.sh` and the three launchd jobs).
- Logs: `~/Library/Logs/KeenRoudy/`. The operating guide and its history: `DESK.md`.
