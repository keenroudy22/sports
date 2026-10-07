# Kook'n autopilot: fully automated, improving every week (owner request, 2026-10-07)

The owner: "make sure Codex is in place and the LLM, and that this is fully automated while growing and improving over time, to avoid becoming stale."
- The owner does no hand posting and wants no routine involvement.
- Their only touchpoints are occasional yes/no phone pings, batched to at most one a week unless something is urgent.

This file says what runs by itself, what Codex adds as scheduled work, and the rules that keep it fresh without breaking the record or the free plans.

## 1. Already automatic (verified by Claude, Oct 7 9 AM)

- **launchd jobs, all loaded:** run, ladder, precheck, discord, heartbeat, review. Today's heartbeat exit 1 was its expected alert (the trend file near budget), now fixed by the P0 split.
- **Local model:**
  - Ollama 0.35 starts at login (`brew services`).
  - `qwen3.8:27b` is loaded with a 12-hour keep-alive. `qwen3:8b` and `qwen3:32b` are also present.
  - Runs log "local models: judgment qwen3.8:27b … verified templates kept".
- **Cloud researcher:** `codex` CLI 0.158, logged in with ChatGPT.
- **Learning:**
  - Weekly calibration shrinks overconfident player chances (NFL k 0.12, CFB k 0.23).
  - Segment pauses: plays it blocked this way went 6–36, about 30u saved.
  - Rule-by-rule refusal stats are kept.
  - Monday review at 9:30 AM, built by the local 27B model.

## 2. Codex scheduled tasks (create these in the Codex app's Scheduled tab, like the 11:45 PM felt check)

| Task | When (ET) | What it does | Done when |
|---|---|---|---|
| **Desk health & fix** | Daily 7:45 AM | Read `ALERT.txt`, yesterday's and today's run logs, the last 10 hosted runs, `data/x-posted.json` delivery state and Claude's `~/Projects/kookn-patches/AUDIT-INBOX.md`. Fix real bugs and regressions only, with a test, deployed by the AGENTS.md script under the run lock. Verify live at 375 and 1440 px. | A 3-line entry in `~/Library/Logs/KeenRoudy/codex-status.md`. A phone ping **only** if something is broken and unfixed, or needs the owner. |
| **Weekly improve** | Monday 10:30 AM (after the 9:30 review) | Read `review-<date>.md`, `docs/product-status.json`, `docs/LESSONS.md` and the social scorecard (section 3). Ship the next 1–2 approved queued items, plus any anti-stale changes section 3 allows. Each is its own small verified release. | Status entry. One batched owner ask (yes/no with before/after numbers) if anything owner-gated is ready. |
| **Season switch** | 1st and 15th of each month, 8 AM | Using SPORTS-FOCUS.md and ESPN schedules, prepare the next season's machinery about 2 weeks ahead and switch leagues on or off as seasons start and end. Dates: NBA Oct 20; college basketball early Nov; MLS late Feb; WNBA May; EPL Aug; UCL Sep; football preseason Aug. | Status entry. The `#lab` capability states match reality. |
| **Felt cutover** | Daily 11:45 PM (already created) | As set. Remove it after a clean cutover. | |

**Rules for every scheduled task:**
- Use AGENTS.md deploys only, under the lock.
- Never decide an owner-gated item: new categories, record counting, best bets in a new sport, paid services.
- Never weaken a guard to make something pass.
- Stay on free plans only.
- Never touch MGL.
- If unsure, write the question into the weekly owner ask instead of guessing.

## 3. Anti-stale content engine (desk code, automatic, inside approved categories)

All of this is "tested copy and layout variants within an already approved category and its existing caps", which AGENTS.md already allows.

1. **Variant library per series.** Hot Plate, plays, Chef's Special, Climb, Cooked, Final/Leftovers, Prep List and teaser each get 4–6 caption templates and 2–3 card layouts. Code fills every number. Templates live in a tracked JSON file with tests.
2. **The local model writes new variants every week:**
   - The 27B model proposes 2 new caption templates per series from VOICE.md, CODEX-TWIST.md and the series' top performers.
   - Templates have placeholders only and never numbers.
   - Each must pass `x_post.guard`, the voice lint, the banned-phrase list and the length limits.
   - Passing templates enter rotation at no more than a 15% share.
3. **Rotation learns:**
   - Pick variants by likes, reposts and replies per view (Thompson sampling or similar).
   - Keep at least 10% exploration.
   - After 8 posts, a variant below its series median is retired; one above it gains share.
   - Never judge one before 8 posts.
4. **Freshness rules:**
   - No caption opening repeats within 7 days.
   - No player in the Prep List 3 days running.
   - Prep List stat categories rotate.
   - The same card layout never runs more than 3 posts in a row.
5. **Timing tests:** optional posts (Prep List, teaser, Early Look) may test ±30 minutes inside existing caps and spacing. Keep the winner after 8 posts per arm.
6. **Series scorecard in the Monday review:**
   - per series: posts, views, likes, reposts and replies per view, and follower change;
   - optional research series under the floor for 4 straight weeks pause automatically, with a note.
   - Official plays, receipts, Final posts and the Climb are never paused by engagement.
7. **What the local model is for:**
   - template proposals;
   - choosing the one supporting reason from structured evidence;
   - the homepage editor and the weekly brief (both existing);
   - tagging lessons.
   - It never writes a number, a pick or a live post. If Ollama is down, the desk uses the existing templates, and the heartbeat alerts after 2 failed runs.

## 4. The model keeps improving, without gaming the record

- Weekly calibration and segment pauses stay automatic (they already are).
- Shadow proposals (R0–R7) are measured weekly. Promoting one still needs the owner's yes. Batch them into the weekly ask with before/after numbers so it's one tap.
- New sports run silent trials. A sport earns best bets only through its P11 packet, which is also a weekly-ask item.

## 5. Two-agent check (keep it: it caught 4 live regressions on Oct 6–7)

- Claude runs a **read-only daily audit at about 7:15 AM** (Claude desktop scheduled task `kookn-daily-audit`): live payloads and site, new commits since the last audit, post delivery, card files, run-log refusals and errors.
- Findings go to `~/Projects/kookn-patches/AUDIT-INBOX.md` under a dated heading, each with an ID, severity, evidence and the expected fix.
- Codex's 7:45 task reads that file, fixes or answers each item, and marks it in `codex-status.md` with the item ID.
- Claude never edits the repos or deploys. Codex never edits the inbox, apart from appending "seen <ID>" lines.

## 6. Owner touchpoints (the whole list)

- One weekly yes/no phone ask, only when something is waiting: promotions, new-sport best bets, anything new or public.
- An urgent ping only for broken-and-unfixed delivery or record problems.
- Pinning the Start here post once.
- Nothing else.
