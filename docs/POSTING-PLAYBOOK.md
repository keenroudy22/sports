# Superseded where it differs by `docs/KOOKN-PLAN.md` (owner, 2026-10-09)

# Kook'n posting playbook, v3 (2026-10-07)

**October 8 owner timing override (item 38):** Every new official play, ticket, Comfort Food
and Climb rung targets 9:30 AM Eastern on game day, Hot Plate first and ten minutes apart.
Discord is 10–15 minutes ahead. A kickoff before 10:30 AM keeps an 8:30 AM target;
late-admitted plays take the next safe slot at least 15 minutes after admission and
before kickoff. The 9:00 receipt leads the normal batch, then plays, then Prep List
and other research. This replaces every noon/two-hours-before/6 PM play time below;
the older example schedule is retained as historical context only.

**Authority:**
- The owner asked for "exactly what post it should do and when and how to get engagement".
- Then: "You tell me", "Do whatever you need to do", "get it all done".
- They approved the twist (CODEX-TWIST.md) and the three-sport focus (SPORTS-FOCUS.md).
- Claude made every call below on that delegation. Record section 0 as dated owner rules ("owner-delegated to Claude, 2026-10-07"). The owner can veto any line.

**Evidence:**
- docs/X-NOTES.md (Cody Brown), X-NOTES-dans-ai.md, X-NOTES-harry.md, X-STYLE-RESEARCH.json.
- Two adversarial reviews on Oct 7: engagement, and rules/feasibility against the code and the post log.

**The owner does no hand posting.** Everything below is automated. The face of the account is the touched-up clay chef, live as the X avatar since Oct 7.

## 0. Decisions made for the owner (record each in AGENTS.md)

1. **The 8:45 AM menu post is retired,** and so is the "Today: N plays." line merged into the morning receipt. Teasers and conversation prompts are **off on X** until 1,000 followers. All of them got 0 likes or replies, and they promise plays the pre-post check can still pull.
2. **The weekend Save this projection sheet is off X.** It stays on the site.
3. **The Saturday/Sunday Climb check-in post is folded into the morning post** as one line when no rung is open.
4. **Discord:**
   - Plays & Results gets posted plays only.
   - #wins-and-bad-beats gets wins and bad beats (section 2).
   - Losses go on X only in the end-of-slate Final, or the 9 AM Leftovers (owner's own rule, Oct 7).
5. **Play captions keep the Sep 26 shape** ("I have it at 47.") plus one supporting reason that carries a code-supplied number. Chance and break-even stay on the card.
6. **"I" replaces "we".** "Hot Plate (POTD)" is allowed as the POTD series name, an exception to the Oct 6 retirement of "plate"; "plate" stays banned everywhere else. "Still climbing? ❤️" replaces "❤️ if you're climbing" for new rungs.
7. **The Prep List** (section 7) is the first-choice research post on every football game day, using trend thresholds rather than strict every-game, per the owner ("every game will get stale... trends is good"). If fewer than 3 rows qualify, the existing research chain (Underdog Watch, spread dog, Matchup, End-zone) takes the slot. Its save ask `Save it for kickoff 📌` is approved.
8. **TNF and MNF get a one-game Prep List,** deciding the previously open "primetime prop sheet" question.
9. **Early Look:** a new research post on Tuesday only, 10:45 AM (section 5).
10. **Night games post at 6:00 PM:** kickoffs at 7 PM ET or later, including SNF, TNF, MNF and late CFB. The 5:30 run schedules them with fresher prices.
11. **International morning NFL games** (Oct 11 PHI@JAX, Oct 18 HOU@JAX, Oct 25 PIT@NO, Nov 8 CIN@ATL; 9:30 AM ET) post at **8:30 AM**, the only exception to "never before 9 AM". The 6:45 run schedules them.
12. **Win cards** (Cooked) join the cashed category. **Payout lines** go on fun tickets and the Climb only.
13. **Other sports:** at most **one** other-sport Prep List a day, rotating. Details in section 5.
14. **The pinned "Start here" post** goes out once through Buffer; the owner taps Pin. Its first line uses the owner's own words ("me and myself").
15. **Volume targets** (section 1).

## 1. Volume: fewer, better

Our own data: Oct 4 had 15 posts and got 0 likes and 0 reposts; Oct 2 had 6 posts and got 7 likes and 5 reposts.

| Day type | Typical | Ceiling |
|---|---:|---:|
| College Saturday / NFL Sunday | 8 | 12, with at most 9 queued before 1 PM |
| TNF / MNF day | 3–4 | 5 |
| Quiet weekday | 2 | 3 |
| Other sports | 1 across all leagues | 1 |

`MAX_PER_DAY = 20` stays as a safety limit, not a target.

**Buffer API budget:** the free plan allows 3,000 requests a month. Check the counter weekly and keep the projected month under 2,700. If it's tight, drop other-sport posts first.

## 2. Discord routing

**Plays & Results:**
- Hot Plate, best bets, Chef's Special and other fun tickets, and Climb steps.
- Same words and card, about 10–15 minutes before X.
- Nothing else.

**#wins-and-bad-beats:**
- Every win, using the Cooked card and caption.
- Every bad beat:
  - a player prop that missed by 1 catch, carry or attempt, by 5.5 yards or less (10.5 or less for passing yards), or by 1.5 or less in NBA counting stats;
  - a game total or spread lost by 1.5 points or less;
  - a ticket or Climb step that lost exactly one leg, where that leg is itself a bad beat.
- Caption: `Bad beat 😩 Smith over 49.5 rec yds. Had 47, missed by 2.5.`
- This needs `DISCORD_WINS_WEBHOOK_URL`, which the owner adds to the env file. Until then, skip quietly and note it once in the status log.

**Unchanged:** Arb Radar and the live-progress pilot.

## 3. Rules every post follows

1. **Line 1 is the most concrete thing a stranger can read:**
   - the odds on a ticket (`🎰 +2194 Chef's Special`);
   - the dollar path on the Climb;
   - the W-L on a Final;
   - the bet itself on a play or result.

   The series name rides in the same line, never alone ahead of the number.
2. **One ask per post.**
   - Plays and tickets: `❤️ if you're tailing`, then `@Playbook` and the league tag (existing rule).
   - Climb steps: `Still climbing? ❤️`, then `@Playbook` and the tag.
   - Prep List: `Save it for kickoff 📌`.
3. **Code supplies every number:**
   - The guards allow only pick fields.
   - Margins are `|result − line|` from the settled `actual`, exact to the half point.
   - Tickets and the Climb get no leg margins, only `2/3 legs hit · missed by one leg`.
   - A push or void gets no margin.
   - Example numbers in tests come from fixtures run through the real code.
4. **No em or en dashes.** Use ` · ` (the guard refuses `[–—]`).
5. **"I", never an invented personal moment.**
6. **One "!" at most,** on a win only (Cooked, a Climb step that cashed, a winning Final). Never on a pick, never on two posts in a row.
7. **No honesty talk** ("even the burnt ones", "all shown"). The Final shows the misses; it doesn't brag about showing them.
8. **Felt cards:** one dominant headline, rows at least 40 px at 1080 wide. 21+ and entertainment-only stay in the card footer.

## 4. Card time, and the queue

- **T, the card time:**
  - noon, or 2 hours before an earlier kickoff (college noon kickoffs post at 10:00 AM, NFL 1 PM games at 11:00 AM);
  - never before 9 AM, except international mornings at 8:30;
  - night games at 6:00 PM;
  - ten minutes apart.
- **The Hot Plate goes first in the batch of the day's first card time.** Set the POTD's target to the earliest play target of the day. A POTD on a night game goes at 6:00 PM as `🍳 SNF Hot Plate (POTD): ...`.
- **Fix: a play may never be admitted to the record without a reachable X window.**
  - Enforce this at admission (gates and `featured.todays_plays`).
  - If plan() drops one, log `<id> has no X window` and count it under "Official plays not scheduled".
- **Queue (Buffer free: 10 scheduled):**
  - With 7 or more queued, sort the run's plans essentials-first before admitting any.
  - No run fills the 10th place; it stays free for relabels and reschedules.
  - Essentials are plays, tickets and Climb rungs, receipts (Final, Leftovers, weekly), cashed and Climb results.
  - Weekend 6:45 runs schedule no other-sport post.
  - A deferred play counts as "not scheduled" only once it misses its target.
  - Drop order under shared caps: other-sport, Prep List or research, news.

## 5. Day templates (Eastern)

### College Saturday / NFL Sunday (about 8 posts)

| When | Post | Caption | Card |
|---|---|---|---|
| 9:00, or the first run after everything has settled | **Leftovers** (only if the last slate's Final didn't go out) | `Leftovers: Friday went 1-1` / `✅ NMSU/FIU over 52.5 · cleared by 8.5` / `❌ Smith over 49.5 rec yds · had 46, missed by 3.5` / `Prep List: 4 of 6 hit.` (if one posted) / `🪜 Climb: $94 rides step 3, $42 banked.` (if no rung is open) / `#CFB` | Felt receipt, ✓ and ✗ rows of equal size |
| 9:30 (slides behind plays due earlier; skipped if it can't post 45 minutes before its first row's kickoff) | **Prep List** | `📋 Prep List: Saturday` / `Kaytron Allen over 74.5 rush yds (-115, DraftKings) · over in 6 of 6` / `5 more on the card. Save it for kickoff 📌` / `#CFB` | Prep List card |
| T | **Hot Plate (POTD)** | `🍳 Hot Plate (POTD): Georgia/Alabama over 52.5 (-110, FanDuel)` / `I have it at 58.5.` / `Both offenses are top 10 in plays per game.` / `❤️ if you're tailing` / `@Playbook #CFB` | Play card |
| T+10… | **Best bets** | `Kaytron Allen over 74.5 rush yds (-115, DraftKings)` / `I have it at 88.` / `He's cleared 74.5 in 5 of 6, and Iowa allows the 4th-most rush yds in the Big Ten.` / `❤️ if you're tailing` / `@Playbook #CFB` | Play card |
| after the plays | **Chef's Special** (if one qualifies) | `🎰 +2194 Chef's Special: 4-leg college lotto (FanDuel)` / `$10 → $229 at the posted +2194` / legs / `❤️ if you're tailing` / `@Playbook #CFB` | Lines-first ticket |
| scans | **Climb step** (if one qualifies) | `🪜 $94 → $149 · 80/20 Climb, step 3 (-170, FanDuel)` / `Step 2 cashed. $42 banked on the way to $1,000.` / legs / `Still climbing? ❤️` / `@Playbook #NFL` | Climb route |
| 6:00 PM | Night-game plays | `Saturday night:` or `SNF:` prefix, only when the play's game is that window | Play card |
| first settlement pass after each final | **Cooked** (wins only; 2 or more wins in one pass make one post) | `{reaction} ✅ Georgia/Alabama over 52.5 (-110, FanDuel) · cleared by 10.5` / `The line closed 54.5, 2 points our way.` (or `against us`, from the stored close) / link to the original / `#CFB`. Reaction rotates (`Cooked.`, `Served.`, `Out of the oven.`, `That one's done.`), never the previous one. No `Plated.`: "plate" is allowed only in Hot Plate (POTD). The first Cooked of the day adds `Discord had it first.` only when the log confirms Discord delivery. | Win card |
| last game final, before 12:30 AM | **Final** | `Final: Saturday went 3-2` / every play `✅` or `❌` with its margin / `#CFB` | Felt receipt |
| news | Injury angle (at most 2, existing rule) | unchanged | none |

**Final fitting rule:** if the text is too long, drop the margin text from every row before dropping any row, and never drop a ❌ row while a ✅ row remains.

### TNF / MNF day (3–4 posts)

| When | Post |
|---|---|
| 9:00 | Leftovers (if due) |
| 9:30 | `📋 TNF Prep List: Chiefs at Raiders` (one game, same rules, up to 6 rows) |
| 6:00 PM | `🍳 TNF Hot Plate (POTD): ...`, or the night game's best bet |
| about 12:00 AM | Cooked (thanks to the settle-only pass), then the Final if before 12:30 AM, otherwise 9 AM Leftovers |

### Quiet weekday (2 posts)

| When | Post |
|---|---|
| Tuesday 10:45 AM | **Early Look:** `👀 Early Look: weekend lines where my number and the price disagree` / `Iowa/Michigan under 41.5 (-110, FanDuel)` / `3 more on the card. #CFB`. Up to 4 main lines, ranked by the Board's calibrated value at a public-book price no older than 4 hours, no Hard Rock. Thin, stale or uncalibrated rows get no rank. The card shows "my chance vs needs" and a RESEARCH label. No @Playbook. It counts as the day's one research post. |
| Wednesday 9:00 AM | **Weekly receipt:** `The week: 12-9` / `Player props 6-2 · Game lines 1-5` / `Fun tickets 0-5 · Climb 1-2` / `Closest burn: Smith over 49.5 rec yds · had 49` / `After posting, the line moved our way on 13 of 21, against us on 8.` / `#CFB #NFL`. **Keep the breakdown by bet type, always.** It drew the account's first real outside reply on Oct 7 ("Breaking the week out by bet type is useful. Props vs game lines vs parlays usually tell very different stories."). If the text runs long, drop the line-move line before the breakdown. The felt weekly card already shows it. |
| any day | A best bet only if one qualifies. The book at 6 PM only if nothing else posted. |

### Other sports (one Prep List a day at most, rotating)

| League | When | Precondition |
|---|---|---|
| NBA | 6:10 PM on NBA nights, scheduled by the 5:30 run, from about Oct 28 | An ESPN NBA box-score store exists (per-player minutes and starter, free summary endpoint), ESPN prop sides are priced exactly, and players have 5 current games. Before that: the existing 5:50 PM slate card on opening night (Oct 20) only, with one trial projection labeled testing. |
| EPL | Friday 6:10 PM, the weekend list | Team markets only (goals, totals, both teams to score), from stored ESPN results and only for markets ESPN prices. No player rows until a lineup capture exists. |
| UCL | Tuesday or Wednesday 12:15 PM, only when no NBA list goes that day | Only once a UCL results store exists. |

## 6. Results speed

Add a **settle-only pass** to the existing 30-minute precheck job:
- free ESPN finals only, under the run lock, no metered calls;
- the existing 3-hour Cooked freshness and 12:30–9:00 AM quiet hours.

Wins then post within about 30–45 minutes of the final, including primetime wins just before midnight. The postgame injury check for raw prop losses is unchanged; a loss still under review moves the Final to 9 AM Leftovers.

## 7. Prep List rules (the owner: "no bench guys with tiny lines")

**Hit rate:**
- 5–9 games: at least 80%.
- 10 or more games: at least 8 of the last 10 and at least 70% for the season.
- Say "every game" only when every row is N/N.

**Price check on each row:** the card shows the calibrated grade from `lines-<league>.json` as `My price check: clears` or `History only · no edge at this price`. Rank by hits/games, then games.

**Role:**
- NFL and college WR/TE: at least 5 targets a game over the last 3 (box-score `pbpTgt`).
- RB: at least 12 carries a game over the last 3.
- QB: the usual starter (`starters.py`), not listed doubtful or worse.
- NFL snap share at least 60% when nflverse has it.
- Questionable, doubtful or out players never appear (`seasonTrends.injuryStatus`).
- College cards carry `College injury news is thin.`

**Lines:**
- No 0.5 lines.
- Floors: receptions ≥ 2.5, receiving yards ≥ 29.5, rushing yards ≥ 39.5, passing yards ≥ 189.5.
- NBA (later): points ≥ 11.5, rebounds ≥ 4.5, assists ≥ 3.5, threes ≥ 1.5, and at least 26 minutes a game over the last 10 and 20 in each of the last 5.

**Price and exclusions:**
- Main line only, a book in `research_posts.PUBLIC_BOOKS`, captured price no older than 4 hours, never shorter than −200.
- One row per player, at most 6 rows.
- No player 3 days running; rotate stat types.
- Drop any player whose game and stat has an open best bet that day, on either side.

**Fewer than 3 rows:** fall back to the existing research chain.

**Card:** 1080 wide, height grows per row, felt, header `RESEARCH · PREP LIST · SATURDAY`, rows at least 40 px, footer 24 px.

**Data:** all fields already exist (box-score store or player charts, nflverse, `seasonTrends.history`, `research-context.json`, `lines-<league>.json`). No new requests.

## 8. Cards

| Card | Spec |
|---|---|
| Win (Cooked) | A new card family:<br>• big green ✓, the line and price, the final and margin, the line-move line, and the season strip;<br>• payout only on tickets and the Climb;<br>• the season strip comes from `receipts.season_as_of(...)` via `record_scope.text`, with Climb results excluded, plus a test that it equals record.json at that moment;<br>• a PUBLIC-PAYLOADS line, a hosted render in feed.py and 8-day retention. |
| Final / Leftovers | ✓ and ✗ rows of equal size with margins, and the season strip. |
| Prep List | Section 7. |
| Pinned | An evergreen series card: what posts and when. |

Claude reviews sample renders of the Win, Final, Prep List and pinned cards before their first posts. Leave every `site/img/kitchen-*` file in place; queued posts and the 8-day Discord retry still use them.

## 9. Pinned "Start here" (once, through Buffer; the owner taps Pin)

```
Kook'n is me, myself and a model. Free CFB and NFL best bets, every one graded in public, wins and misses.
🍳 Hot Plate (POTD) on game days
🪜 The $50 → $1,000 Climb
📋 Prep List before kickoff
Discord gets every best bet 10 to 15 min before X: <invite link>
21+. For fun.
```

## 10. Guards and tests (Codex)

**Guards:**
- **Tickets only:** allow `payout10 = round(10 × decimal(odds))`. A straight play with any `$` is refused.
- **Results:** allow the stored final stat, the margin and the closing line.
- **Voice list:** add `Hot Plate (POTD)` to the allow-list; ban `[–—]`.

**Tests:**
- A Saturday with 5 plays, 1 ticket and 1 rung schedules at most 9 posts before 1 PM, defers nothing official and keeps the 10th place free.
- Cashed and Climb results are essential.
- No menu post, teaser, conversation prompt or weekend sheet on X.
- No loss on X outside a Final or Leftovers.
- Discord Plays & Results gets play kinds only; #wins-and-bad-beats gets wins and bad beats by the margin rules.
- Every margin on a .5 line ends in .5; ticket results have no leg margins.
- Fitting a Final drops margins before rows, and never drops ❌ while a ✅ remains.
- Prep List: role, floors, −200, freshness, PUBLIC_BOOKS, open-bet exclusion, 3-row fallback, no player 3 days running.
- International 9:30 AM games post at 8:30. A play with no X window is never admitted.
- Night games go at 6:00 PM with the right prefix.
- The settle-only pass makes no metered calls.
- Every template in this file passes `receipts.guard` or `x_post.guard`.

## 11. Measuring

- **Engagement per view** = (likes + reposts + real replies) ÷ views, where real replies are comments minus 1 on @Playbook-tagged posts.
- Saves, profile visits and follows come from the owner's Monday X read when available. The Prep List is judged on saves.
- Judge a series at 8 posts or 4 weeks, whichever is later. Judge Chef's Special and the Climb at 8 posts or season's end.
- The Monday review gets a series scorecard (AUTOPILOT.md section 3).
