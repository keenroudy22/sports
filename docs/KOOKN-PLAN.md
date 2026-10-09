# The Kook'n plan (October 9, 2026)

> **The plan on one page**
> 1. Every football game day gets a play. TNF, SNF and MNF always get a play on that game itself.
> 2. A play needs two things: our number disagrees with the book's, and we can name the reason why.
> 3. When the gap is big and the reason isn't obvious, we go and look it up (injuries, QB, news). If we still can't find it, we skip it and say so.
> 4. Plays are ranked by what has actually been winning, not by the biggest gap.
> 5. Totals can still be the most common pick. If they keep losing, the system cuts them back by itself.
> 6. Fun lanes, each with its own record line: Upset pick, Gut call, Chef's Special, Safer combo and the Climb. The Best bets headline stays the same.
> 7. Plays post the morning of the game, every game day (your rule), about 20 minutes apart. Night games get a second news check before kickoff.
> 8. Captions: the play, my number, one real reason. No disclaimers and no jargon. Four rotating shapes, so posts don't read like a bot.
> 9. Results name the stat that explains them ("0 catches on 6 targets"), and misses get as much space as wins.
> 10. On the site, every play and every big gap shows "why my number differs".
> 11. Learning moves both ways: it tightens what loses and loosens back what wins, slowly enough not to chase luck.
> 12. NBA plays start Oct 20, soccer Oct 24-25, college hoops in early November. You approve this once, then it runs on its own with a monthly check-in.

**This is the one plan.** Wherever they disagree, it replaces the older rules for plays, posts, engagement, research and
learning: the "owner's current rules" in AGENTS.md, POSTING-PLAYBOOK v3, DIRECTION-RULES, NO-FORCED-PLAYS-SPEC and
OWNER-DECISIONS items 1-38. Codex records it as your dated rule. The build details are in `KOOKN-PLAN-CODEX.md`.

These rules don't change: the record is append-only; no invented prices, stats or sources; free plans only; X goes
through Buffer only, with no automated replies, likes or follows; MGL stays separate; secrets stay out of the repo;
21+ and entertainment only.

---

## 1. What Kook'n is

Kook'n is one person's sports kitchen with a cartoon chef as the face: a few fun plays a day with real reasons,
research anyone can use in ten seconds, and every result on the record. Grow a following free now; maybe a paid
resource later.

**The twist** is the thing Cody, Dan and Harry don't do: **every play says why the chef disagrees with the book.** You
put it like this: "when the model doesn't align with the market there is likely a reason and we need to know the
reason." Kook'n finds that reason, names it and shows it. Every result goes on the record, misses included, and the
80/20 Climb is the running story.

**The voice** is a person. Short, first person, one real reason. No disclaimers, no jargon, and nothing public
mentions schedules or automation.

---

## 2. Plays

### 2.1 Why it went quiet

The current math squeezes the model's number almost all the way back to 50%, then asks for a 4-point edge on top.
An NFL prop at -110 would need the model to be 99% sure. NFL spreads can never qualify, NFL totals are paused, and
the one weekday place was locked to the NFL game. That's why TNF was empty. Totals filled the weekend for a separate
reason: they were published days early, before player props even had prices.

### 2.2 What the numbers say

Against the book's own fair price:
- **The model does not beat the market on average.** When it says 61%, its side has hit about 52%.
- **The best spot:** NFL props at normal prices (-160 to +150) with a moderate gap went 179-144 (55%, +10.7u).
  Outside that sweet spot, NFL props lost about 21u. The season's overall NFL prop profit leans on 4 long-odds hits.
- **College player props have lost** (-22u this season), and **NFL totals went 3-13.**
- **Big gaps lost more often when we didn't know why.** So now every big gap gets investigated. If we find the
  reason, it can be a play (upsets included). If we can't, we skip it and say so on the site.

**Expect roughly a coin flip at first.** The plan doesn't pretend the model is sharp. It takes reasoned shots, shows
the reason, keeps the record and learns which reasons pay.

### 2.3 How a play gets chosen

1. **Gap.** Our chance minus the book's fair chance at that exact line, taken from that book's own two prices.
2. **Reason.** Code checks stored data for a reason: an injury or role change, a QB change, weather, the line moving
   our way, the matchup, a usage trend, pace, or a hit streak. Reasons that argue *against* our side are saved too,
   and a hard one (player questionable, bad weather for a passing over, a college blowout spread on a starter's over)
   blocks the play. A reason only counts if it actually supports our side, so the Bills/Rams mistake can't happen again.
3. **Dig deeper.** When the gap is large, or a top candidate has no fresh-news reason, the web researcher looks up
   the news (injury, QB, suspension, role, weather, travel, motivation): up to 8 lookups a day, free, inside the
   ChatGPT plan. A sourced finding counts as a reason, for or against.
4. **Honesty checks** (unchanged in spirit): a fresh price on both sides at the exact line, no broken prices, no role
   or QB holds, the same player not on two tickets, injury-clear, and Indiana books for college. A price that only
   one book offers is allowed on game day if it's fresh and normal-looking.
5. **Ranking.** Plays with real news behind them rank highest. Spots that have actually been winning rank higher.
   Markets that keep losing count for less. The size of the gap only breaks ties.

College player props have lost money this year, so they only get through where a specific kind has been winning on
its own record (right now that's college rushing unders).

### 2.4 The daily rule: never dark on a game day

You said both "it doesn't have to make a play just because" and "not posting a bet for TNF is crazy." Both can be
true: never post a broken play, and never go dark on a game day.

On every football game day:
1. **Best bets**, up to the cap. The top one is the **🍳 Hot Plate (POTD)**. Caps: 5 on Saturday and Sunday, 2 on
   every other day (up from 1).
2. If no best bet qualifies: a **👨‍🍳 Gut call** at half a unit. It's the top candidate with a smaller gap and at
   least one real reason, and it passes every honesty check.
3. If that fails: a **🛡️ Safer combo**, two strong favorites (each about 70%+) from different games, at -200 to +120.
4. If that fails too, on a non-primetime day only: a short "no play from me" post naming the closest line.

**Primetime guarantee.** TNF, SNF and MNF games always get a play on that game: a best bet if one qualifies,
otherwise a Gut call on that game. A Safer combo may pair that game's favorite with another game the same night.
Primetime never gets a pass post. The only way it goes dark is if no price on the game passes the honesty checks,
which means a data outage, and you'd get an alert.

### 2.5 Market mix

You said: "I see more totals than anything and I am okay with that but it shouldn't be everything." So there's no
fixed market order. Totals can still be the most common pick. If they keep losing, the system cuts them back by
itself. The only fence: totals stay under 40% of the week's best bets (at most 2 on a weekend day, 1 on a weekday),
and a total needs a real reason (weather, pace, injury, QB or line move), not just a hit streak. NFL totals stay
paused until their own results earn them back.

Spreads and moneylines get a real path onto the card. College spreads come first, when our margin is at least 6
points off the book. NFL spreads and moneylines run quietly in the background and join automatically after 30
graded at or above break-even. No two plays go on the same game.

### 2.6 The fun lanes (each with its own record line)

| Lane | What it is | When | Stake |
|---|---|---|---|
| **🐕 Upset pick** | College underdog our number has winning outright, spread 6.5 or less (about +120 to +220), with a reason. NFL upsets run quietly in the background until they earn it. | Any college day, at most 1 | 1u |
| **👨‍🍳 Gut call** | The fallback above. On weekends the local model may also pick one from the researched shortlist. | At most 1 a day | 0.5u |
| **🛡️ Safer combo** | Two strong favorites (above). Replaces the old easy parlay. | Only when there's no best bet | 1u |
| **🎰 Chef's Special** | Fun ticket, 3-4 legs, +300 to +800, one book, different games. College and NFL can mix. No same-game parlays, because free data can't honestly price legs that move together. | Any football day with 3+ games; NBA days once live | 0.25u |
| **🪜 80/20 Climb** | Unchanged: $50 to $1,000, bank 20%, one rung at a time, never forced. | Its own checks | $ ledger |
| **NBA / Soccer / CBB** | Same rules, own line, 1 play a day per sport. Joins the Best bets headline after 30 graded at or above break-even. | From their start dates | 1u |

**The record.** The "Best bets" headline is the same set as today: before **35-36 (1 void), −5.11u at posted prices (21-25 with a recorded price)**; after
**the same**. Each lane gets its own W-L/units line, plus an "All plays" line. No past result changes.
The new lanes start at 0-0.

**Every ticket is explained.** Each leg of a Chef's Special, Safer combo or Climb rung carries its own one-line why
on the site.

---

## 3. Posts

### 3.1 When things post (Eastern)

| | Saturday / Sunday | TNF / MNF days | Weekday college nights | No football |
|---|---|---|---|---|
| 9:00 | Results from the day before | Results, if any | Results, if any | Weekly notes, a results post, or one other-sport post |
| 9:15 | 📌 Prep List | | | |
| 9:30-10:50 | 🍳 Hot Plate, then best bets, Upset pick, Gut call (noon kickoffs first) | | | |
| ~11:10 | 🪜 Climb rung, if one | One-game Prep List | Prep List (Tue, 3+ games) | |
| ~11:30 | 🎰 Chef's Special | | | |
| 9:30 AM | (see above) | **The primetime play**, then a 2nd play and the Special, the morning of the game | The night's plays, the morning of the game | |
| ~5:30 PM | News re-check on night-game plays | News re-check | News re-check | |
| As wins land | Cooked win posts (at most 4, none 12:30-9 AM) | same | same | |
| End of slate | Final if settled by 11:30 PM, otherwise Results at 9:00 next day | same | same | |

Weekly: **Wednesday 7 PM** TNF early look (Wednesday's research post). **Friday 7 PM** Saturday early look (new;
Friday's research post). **Tuesday 11:00** Weekly notes (replaces the Wednesday receipt).

- Posts go out about 20 minutes apart. Times shift a few minutes each day so they don't look scheduled.
- Discord Plays & Results gets each play 10-15 minutes before X, as now.
- Volume: weekend typically 9 posts (ceiling 12), TNF/MNF 3-4 (ceiling 6), quiet weekdays 2-3 (ceiling 4). At the
  ceiling, other sports drop first, then the Prep List, then extra Cooked posts, then the Special. Plays, results
  and the Climb never drop.
- Every play posts the morning of its game (owner, Oct 8: "Posts need to go out the morning of games"). Night-game
  plays get a second news check around 5:30 PM. If a hard news pull happens after a play posts, Discord gets an update and the
  Final notes it. The play stays on the record.
- Other sports: up to 2 posts on a light football weekday, 1 on weekends. Never on Discord.

### 3.2 What captions look like

The play, my number, one reason. `@Playbook` only on new plays and tickets, and one league tag. These examples show
the shape only; real posts fill every number from stored data.

```
Kaytron Allen over 74.5 rush yds (-115, DraftKings)
I'm at 88. He's cleared 74.5 in 5 of his last 6.
❤️ if you're tailing
@Playbook #CFB
```
```
🐕 Upset pick: Toledo to win (+150, DraftKings)
Book has them losing. I've got Toledo by 2.
Why I'm higher than the book: Bowling Green is down to its backup QB.
❤️ if you're riding with me
@Playbook #CFB
```
```
Saturday: 3-2.
✅ Allen over 74.5 rush yds · 112 yds on 21 carries
✅ Iowa/Washington over 41.5 · went 31-20
❌ TK King over 49.5 rec yds · 0 catches on 6 targets
❌ Tuten under 1.5 catches · had 2 (left hurt)
#CFB
```

- **Four caption shapes rotate**: play first, reason first, "Book says 49.5. I say 68." first, or play plus reason
  only. The same shape never runs twice in a row.
- **"My number" lines rotate** too: "I'm at 47." / "I've got 47 total points." / "My number's 47." / "I have it at 47."
- **The ask rotates and isn't on every post**: "❤️ if you're tailing" / "❤️ if you're on it" / "❤️ if you're riding
  with me" / nothing. It's always on the Hot Plate, Special, Upset and Climb, and on at most every other best bet.
- **Win posts react to what actually happened**: "Not close." for a blowout, "Sweated that one." for a close call,
  "Took till the 4th." for a late finish, and a plain "Cashed." most of the time. One kitchen word a day at most. One
  "!" only on a blowout or a Climb win.
- **Prep List**: "Last list went 4 of 6. Today's:" then up to 4 rows like `Nacua over 5.5 catches -120 FD · 9/10`.
  A bad list is stated plainly, with no excuse.
- **Labels**: only three are branded: Hot Plate, Chef's Special and the Climb. Everything else uses plain words:
  Upset pick, Gut call, Safer combo, Results, Weekly notes.

### 3.3 The kill list (never in a caption or Discord post)

- **Disclaimers:** "not an official play", "not a TD pick", "Usage, not a TD pick or official play.", "Research
  only", "Check current prices", "History does not predict…", "Full details on the graphic". The card already shows
  what kind of post it is.
- **Jargon:** vig, implied, break-even, EV, CLV, calibrated, "selection", "captured", "the desk", "next run", "scan
  time", "our edge". Normal football words like "run game" and "edge rusher" are fine.
- **Plumbing:** player ID numbers (like the "Final: 4869443" leak), doubled words ("Stateate"), "From Claude", times
  of runs, anything that hints at automation.
- **Money talk and morals:** "$0 banked", "That's why we bank 20%", "One miss can't take it back".
- **Hype and filler:** lock, guaranteed, free money, hammer, smash, "Plated.", questions fishing for replies, honesty
  slogans, "We have it at" (it's "I"), em dashes, and the usual AI words (delve, unlock, elevate, game-changer, and
  so on).

If a caption trips the list, the system picks a different approved wording. It never drops the play.

### 3.4 Never the same twice

Every caption comes from an approved word bank written in this plan. Code picks from it by rotation, so nothing
repeats back to back and no line shows up in more than about 40% of a week's posts. The local model may only choose
among approved wordings. It never writes public text. Wordings that keep getting fewer views (20+ posts, 30% under
the series' usual) retire and get swapped for a reviewed spare.

---

## 4. Graphics

- Every image uses the approved Kitchen Ticket design for its post type, with a player photo on every player prop
  (a team-color badge if there's no photo).
- Old felt, navy or research-art cards can't post. If the image isn't a Kitchen Ticket render, the post is held and
  you get an alert. "Old-style image posted" becomes a health-check alarm.
- The card shows the same number as the caption ("MY NUMBER 68 · LINE 49.5") and the same WHY line.
- **Every approved design is in `design/APPROVED-GRAPHICS/`**, with a README that maps each post type to its design.
  New lanes get a chip on an existing design: Upset pick and Gut call use the best-bet ticket with an UPSET PICK or
  GUT CALL chip; Safer combo uses the Chef's Special ticket with a SAFER COMBO chip; every research post (End-zone
  Work, Season Trends, Upset Watch, early looks) uses the research list card; the Climb route card goes on rung posts
  and the site.
- An automated render check replaces the "Claude reviews the first render" step. It checks text in bounds, the
  photo present, the exact footer and no kill-list words. A failure holds that one post and alerts you.

---

## 5. Growth

**Now (Oct 9):** 79 followers, 3 Discord members, about 0.4 likes and reposts per 100 views. Reach comes from people
who don't follow us yet. Fun tickets (median 447 views), named-player Hot Plates (227) and the Climb get looked at.
Questions, menus, sheets and flat "✅ Cashed:" posts get almost nothing.

- **The series:** Hot Plate (daily anchor), Upset and Gut calls (the fun risk), Chef's Special (the reach engine),
  the Climb (the story), results with the real stat, and the Prep List and early looks (the saveable lists).
- **Discord funnel:** "Discord gets plays first" goes in the bio and pinned post, not in plays.
- **Bio (you set it):** "Free football plays every game day 🧑‍🍳 Research on every game at the link. Discord gets
  plays first. 21+"
- **Pinned post** (Buffer posts it once, you tap Pin): "Start here 👇 / 🍳 Hot Plate: my top play each game day /
  🪜 80/20 Climb: $50 to $1,000, 20% banked every win / 📌 Prep List: lines that keep clearing / Every game's research
  and every result is on the site. Discord gets plays first. 21+"
- No questions, menus or projection sheets on X. They stay on the site.
- If you ever feel like it, replying in big accounts' threads is the one thing automation can't do. Nothing below
  depends on it.

**30-day targets (by Nov 9)**, reported every Monday:

| Measure | Now | Target |
|---|---|---|
| Followers | 79 | 200 |
| Discord members | 3 | 25 |
| Median views per play post | ~180 | 250 |
| Likes + reposts per 100 views | 0.4 | 0.8 |
| Primetime NFL games with a play on that game | TNF Oct 8: none | 100% |
| Football game days with a play, Gut call or Safer combo | | 95%+ |
| Posted plays with a named reason | about 1 in 4 | 100% |
| Kill-list phrases in posts | several | 0 |

---

## 6. Research on the site

| Page | What a bettor gets in 10 seconds |
|---|---|
| **Today** | The Hot Plate and the day's plays as tickets: price, book, my number, WHY and the hit strip. Then the Climb, last game day's W-L and the Prep List, with nothing hidden behind a fold. |
| **Play page** | "The book has 49.5. I'm at 68. Why: {reasons, with source and time}. Against: {reasons}." Then, plainly: "This price needs to win 50.5% of the time. When my number's been this far off on NFL receiving yards, it's been right 55% of the time (169 games checked)." Tickets show a why for every leg. |
| **Research board** | Every fresh main line with the gap and reason chips, plus a "has a reason" filter. |
| **Game page** | **"Why my number differs"** for every big gap: the reasons found, or the exact checks that came back empty ("Checked injuries, QB, weather, line move, news: nothing found. Passing."). This replaces the generic red caution. Model leans and next-man-up injuries stay. |
| **Games / college navigator** | Projected scores, mismatch badges, close games first, team ranks, and the garbage-time flag on props when the spread is 21+. |
| **Player page** | Game-by-game bars at the current line, role trend, QB-change note and matchup rank. |
| **Record** | The calendar (units by day and month), lane lines, Vegas vs reality, and how the model does in each market. |
| **Climb** | The route graphic with every real step and the plan (Record › Climb), linked from Today's Climb stub. |
| **Start here** | How a play gets chosen in plain words (my number vs the book, plus the reason), what each lane means, and that every result stays on the record. |

---

**The website is updated with each release** so every rule in this plan shows up on the site the day it goes live: lanes and their record lines, reasons on every play, the Climb route, Weekly notes, and Start here.

## 7. Learning and improving

**Measured every week** across every candidate we looked at, not only the ones posted: wins, units and closing-line
movement by lane, market, gap size, reason type and price. For posts: views, likes and reposts at 24 hours and 7 days
by series and wording, plus the follower and Discord counts.

**What adjusts on its own (both ways, inside fences):**
- Markets that keep losing count for less, and markets that keep winning count for more, a little at a time.
- A reason type that keeps losing stops counting as a reason, and comes back if it recovers.
- The gap needed in a losing market rises, and falls back when it recovers.
- Pauses and cap changes need two weeks in a row of the same signal, so one bad weekend doesn't flip the system.
- NFL spreads, moneylines and upsets join on their own after 30 quiet results at or above break-even.
- Projection fixes, like the QB-change and current-team role errors behind the JJ Kohl and TK King misses, ship on
  their own once they test more accurate on past games.

**What it never does on its own:** add a sport, market, lane or post slot; raise a cap; weaken an honesty check;
change how the record counts; or touch a published play.

**You see it in three places.** A one-line phone ping when something moves (say "undo KEY" to reverse it). **Weekly
notes** on X every Tuesday ("7-7 week. Props carried it (6-2). Game lines didn't (1-5). Climb made it to step 2.").
And a **monthly review on the 1st**: the record by lane, which reasons paid, growth against the targets, and at most
three proposals for you in one message.

---

## 8. What you approve by approving this plan

1. The daily rule and the primetime guarantee (best bet, then Gut call at 0.5u, then Safer combo; a pass post only on
   non-primetime days).
2. Weekday cap from 1 to 2.
3. Lane record lines, with the Best bets headline unchanged (35-36, 1 void, −5.11u at posted prices, before and after).
4. Two-way learning inside the fences, including NFL sides and upsets joining on their own and automatic projection
   fixes.
5. The caption changes: rotating shapes, number lines and asks, Prep List as a list, and plain labels (Chef's Upset
   becomes Upset pick, Chef's Call becomes Gut call, Comfort Food becomes Safer combo, Kitchen Notes becomes Weekly
   notes).
6. Chef's Special on any football day with 3+ games.
7. Other sports as public plays (NBA Oct 20, soccer Oct 24-25, college hoops early November), priced only from ESPN's
   free DraftKings lines, each on its own record line.
8. Automated render checks in place of Claude reviews.
9. The bio and pinned post text.
10. The Friday 7 PM Saturday early look.

Codex builds it in three releases, each released as soon as it passes every test (under the run lock, never mid-run): (1) play selection and the primetime
guarantee, (2) captions and variety, (3) everything else.

## Addendum, Oct 9: trends must account for who they played (owner)

Owner: "Remember to check things like def vs position and who those players have played against for trends as that can make a big difference in CFB."

- Every player trend, hit strip and Prep List row shows the opponent's defense-vs-position rank for tonight (yards and catches allowed to that position, FBS rank) and **splits the player's history by opponent quality**: games vs FBS defenses ranked in the top half vs bottom half vs FCS, with FCS games labeled and never counted as proof on their own.
- A college prop's trend counts as a reason only when it holds against comparable defenses (tonight's opponent's rank band) or when tonight's defense is weaker than the ones he's already beaten. A streak built on FCS or bottom-10 defenses against a top-30 defense tonight is a counter-reason, shown on the play page.
- Captions may use it as the one reason: "Washington gives up the 9th-most WR yards. He's cleared 64.5 in 4 of 5 against FBS."
