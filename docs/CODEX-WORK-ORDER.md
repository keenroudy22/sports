# Codex work order: reliability, best-in-class resource, other sports (Oct 6–7, 2026)

From Claude, steering for the owner.

**Owner authority (Oct 6, ~11 PM ET, in chat with Claude):**
- "You have my permission to do whatever you want to get this all done."
- "Make it feel as least AI as possible and be the best it can be for … people wanting to use it as a resource."
- "Help codex get the same features for other sports too so we can keep posting for other sports for more attraction."
- "The APIs I have are on free plans; make sure we aren't using any payments."
- Codex should keep learning and improving over time, using the local LLM to save resources.

Claude made the decisions below under that delegation. Record each one in AGENTS.md as a dated owner rule, "(2026-10-06, owner-delegated to Claude)". The owner can reverse any of them. Anything listed under "Still the owner's" is not decided.

All AGENTS.md gates still apply to every release: both suites, build, guard, payload budget, rehearsal, locked deploy, watched publish, and live 375/1440 checks. Free plans only, everywhere.

Supporting docs, all in `~/Projects/kookn-patches/`:
- `BENCHMARK.md`: the paid-tool and pick-brand comparison, the ranked ship-next list, and the Dans AI deep review.
- `VOICE.md`: the voice guide plus 25 exact string replacements.
- `LESSONS-seed.md`: the first entries for `docs/LESSONS.md`.
- `AGENTS-learning-loop.md`: the dated AGENTS.md text for the learning loop.
- `LOCAL-LLM.md`: local-model routing.
- `MULTI-SPORT-PLAN.md`: the full other-sports build plan, phases M0–M5.
- `X-NOTES-dans-ai.md`: append to `docs/X-NOTES.md`.
- `C6-REVIEW.md` and `CARD-REVIEW-3.md`: background.

---

## P0: reliability first (do these before anything else)

### P0-1. Buffer's free queue holds 10 scheduled posts, not 50

**Evidence:** the run logs on Oct 3–4 show createPost refused six times with "You have 10 scheduled posts out of 10 allowed". What failed:
- NFL KC-LV under 48 (an official play) was never scheduled. It failed twice.
- A POTD relabel failed twice.
- A pre-post reschedule failed.

Your earlier answer of "limit 50, 48 remaining" was wrong; the comment in `buffer_post.py` says 50.

**Do:**
- Count pending scheduled posts before every createPost.
- At 7 or more pending, keep the last 3 slots for official plays, POTD relabels, pre-post reschedules and receipts. Defer optional posts (research, conversation prompt, news, menu, sheet, other-sport posts) to the next run.
- Fix the comment.
- Make "Official plays not scheduled: N" the first line of desk_health and of the Monday review.
- Add a test with 10 pending posts.
- Add lesson L-2026-10-04-1.

### P0-2. The Odds API free credits run out around Oct 16 (this is M0 in MULTI-SPORT-PLAN.md)

**Evidence:**
- `data/odds/status.json` shows 186 used by Oct 7 00:39Z, about 31 credits a day.
- The guard stops at 476 (500 minus the 24 reserve). At this pace that happens around Oct 16, just before the Oct 17–18 weekend.
- No money is at risk, but there would be no fresh prices and so no best bets.

**Decision: Option A.**
- Trim game-line captures to about 8 a day on average.
- Keep Odds API props to weekends only, at most 12 a day.
- Move the NFL easy parlay to SharpAPI alternates (0 Odds API credits).
- Target about 276 credits for the rest of October.
- From November, target 300 or fewer a month: NFL lines 70, CFB lines 70, props 100 (Thursday to Monday), easy parlay 0–64.

**Also ship:**
- The month-rollover fix.
- A pace warning in desk_health when the projected month passes 450.
- A count-only journal for SharpAPI requests.
- A Buffer API request counter (the free plan allows 3,000 a month).

Other sports get **0** Odds API, SharpAPI or SportsGameOdds requests (see P2).

**Report** the before/after capture schedule in the release note.

### P0-3. The Discord bot still posts with the 3D chef

`discord_post.py:96` sets avatar_url to `https://keenroudy.com/sports/kookn.jpg`.
- Do not replace kookn.jpg; the legacy cards use it as `pick_card.AVATAR`.
- Add `site/kookn-mark.png` (512×512, from `redesign/brand/x-avatar-400.svg`; a 1024 render is at `~/Projects/kookn-patches/brand/kookn-icon-1024.png`).
- Add a narrow publication_guard entry and a PUBLIC-PAYLOADS line.
- Point avatar_url at the new file.

Claude already changed the Discord server icon and the X avatar to the ticket mark (the X blue check is under review), and the X bio to a fun line without the helpline number.

### P0-4. C6 follow-ups (verified by Claude's checkers; none is public)

1. Move `results_shadows.snapshots/append` after `learning.save_policy` in `weekly()`, or guard them. A shadow exception must never lose live learning.
2. Apply the since-window dedupe inside the shadow path too: `learn.py:443/487` still runs `distinct()` over all history, so the R0 evidence the owner will see is skewed.
3. In `buffer_post.schedule`, compute the cardTheme label from the renderer's own moment (publishedAt, settledAt or day) and never let it raise. Wrap it, falling back to 'legacy'.
4. Treat a naive cutover string as Eastern, not UTC. Better: require an explicit offset in FELT_FROM and fail the tests otherwise.
5. Add a non-dry test that live learning equals the pre-C6 output, and a near-miss since-window test.

### P0-5. Felt cards

Claude is reviewing your 23:25 renders (round 4) now and will post the verdict in this chat.
- If Claude approves all eight, the owner-delegated cutover is approved for tonight's quiet window: after the green 11:30 PM run, before the 8:45 AM menu. Set FELT_FROM with an explicit −04:00 offset.
- If not, the legacy cards stay and you fix the listed items.
- Posted attachments never change.

---

## P1: make Kook'n the best free resource, human not AI (BENCHMARK.md ranked list)

Approved by delegation, in this order:

1. **Research cards show our price check, not just history.**
   - Matchup edges count the Model signal only when the calibrated grade clears our bar; failures fold under "History only · no edge at this price".
   - One price line per Trends and Matchups card.
   - Label the projection "Our average".
   - A code-built gap sentence when our average and recent form differ by more than 30% (the JJ Kohl 167 vs 266 case).
2. **Tickets: "Good to −117 at 49.5" plus the latest quote** (via pickChange), with the quote's age. This replaces "Old price … check your book". Also the after-slate Today heading.
3. **Copy sweep (VOICE.md):**
   - "21+ · Entertainment only" on every card footer, legacy included, for new renders only.
   - One send-path guard (x_style + the VOICE phrase list) on every Buffer and Discord text, including conversation prompts, teasers and pull updates.
   - Retire "desk", "PLATES", public "Ladder", "the owner" and "Kitchen's closed".
   - Apply the 25 string replacements.
   - Add `tests/test_voice.py`.
4. **QB news chip on the card face** wherever a QB or pass catcher's game is affected.
5. **Make room, then a fast Research board:**
   - Lazy-load Record, the More subpages and #team into `app-more.js` (frees about 18–22 KB gzip; guard and budget lines).
   - Exact-line hit pairs (L5, L10, season, vs opponent, venue) on lines.json rows, shown as one strip.
   - Typed search over every line, plus a "Find a player or team" box.
   - Shareable preset chips.
6. **Player page:**
   - All of the player's current lines.
   - A −/+ line stepper that recounts hits on the client.
   - A 5-rung ladder with prices only where an exact alternate row exists.
   - A "Your price" box.
   - A usage row.
   - Hide 1-game splits.
7. **Game page:**
   - A "What changed" strip (OUT/Doubtful players plus the move since open).
   - A marketHistory step chart.
   - A books grid with each book's cut.
   - Finish P2-02.
8. **Proof on every pick and receipt:**
   - Posted time and hours before kickoff.
   - The original X post link (additive postUrl, URL only).
   - A public-log link.
   - "How we keep score" in Start here.
   - A Share button.
9. **Record "Where it's working" and a calibration table.**
   - Split props, totals and spreads at posted prices, with "line moved our way in X of Y".
   - Add the 52.4% break-even line.
   - In Record › Model, a "When we said X%, it hit Y" table by bucket, with n on every row and "early, small sample" under 30.
   - Counting does not change. Put before/after display numbers in the release note.
10. **Also approved:**
    - Per-pick share pages `p/<id>.html` with the card as the preview image (narrow guard entry).
    - Upset watch demotes games with a QB out or doubtful, or a spread move of 3+ points (research ranking only).
    - Rotating the play-post closer among approved heart variants.
    - Website-only live stat progress on open best bets from ESPN's free feed. Never call a win early, and send nothing to X or Discord.
11. **From the Dans AI benchmark** (append X-NOTES-dans-ai.md to docs/X-NOTES.md):
    - An every-game hit list in the existing research slot (main lines, five-plus games, with the price and the break-even).
    - Name the margin on results ("cleared by 12 yards", "missed by 3").
    - Show "posted −110, closed −125" both ways.
    - Lead primetime captions with TNF/SNF/MNF.
    - One natural exclamation is allowed on cashed posts and receipt wins. Never consecutive, never on a pick. Extend x_post.guard narrowly.
    - Cashed posts may carry a felt result card. Receipts still give misses equal weight.
    - No affiliate links, giveaways, paywalls, AI persona or volume increase.

### Learning loop (AGENTS-learning-loop.md, LESSONS-seed.md, LOCAL-LLM.md)

- Add the dated AGENTS.md text, `docs/LESSONS.md` seeded with tonight's lessons (each closes only with a test), `docs/VOICE.md` and `docs/BENCHMARK.md`.
- In the Monday review, list delivery misses, open lessons, voice-lint hits and format results by follows and saves per view (not views).
- **Local model**, in LOCAL-LLM.md order:
  1. Log judge-unavailable reasons, and let the pre-post check wait up to 90 s for the lock.
  2. Fingerprint the homepage editor so it stops re-running on unchanged input.
  3. Flag configured-but-missing models (qwen3.5:9b-mlx is configured but not installed).
  4. Add the copy check and feedback tagging inside the existing Monday call.
  5. Add a placeholder-only caption bank.

  Code supplies every number. There is no cloud fallback, and the model never writes a live post.

---

## P2: other sports, free data only (MULTI-SPORT-PLAN.md, M1 onward)

**Approved by delegation:**
- **Other-sport social categories:**
  - a slate card;
  - one trend board a day, rotating across leagues;
  - a weekly paper-trial receipt.
  - Caps: 3 a day Monday to Friday, 2 on Saturday and Sunday, 1 per league. These are dropped first under the Buffer and daily caps. Discord after X.
  - Count them toward daily presence.
  - Resume `KEENROUDY_SPORTS_SOCIAL=1` for the slate card now.
- **ESPN data and art:** used as an owner-accepted risk (already accepted for football logos and photos), recorded in SOURCE-RIGHTS.md. Revisit before any paid tier.
- **ESPN prop sides:** price a side only when it exactly matches the labeled milestone price. Otherwise show the line with no price. Track orderContradictions.
- **Trend-board guards:**
  - no row shorter than −200;
  - no goalie saves;
  - pitcher lines only for the listed probable starter;
  - five current-season games minimum;
  - research label, no @Playbook, never in the record.
- **Early season:** a separately labeled last-season chart window on NBA player pages, website only, until players have 10 current games.
- **Discord:** keep the single Plays & Results feed with the league named first.
- **Order (changed by the owner, Oct 7; see SPORTS-FOCUS.md):** three sports all year: football, basketball and soccer. NBA by Oct 20, then Premier League and Champions League (aim for Oct 24–25), then college basketball in November, then WNBA and MLS in summer. No new NHL or MLB build work; their existing score pages stay as they are.
- All other-sport UI goes in the lazily loaded `sports.js`; app.js must not grow.
- **Still gated, no override:** official best bets, POTD, the Climb or fun tickets in any new sport go only through a P11 packet (calibration with 300+ graded pairs per segment, tested settlement, a shadow record at the captured price). The backtests show no basketball or soccer edge at the close; forcing picks would lose and dent the record.
- Claude reviews the first rendered sample card of each new category before its first post.

---

## Still the owner's (do not decide)

- **Cloudflare Web Analytics:** its tracker loads on every live page (`static.cloudflareinsights.com/beacon.min.js`). The rules say no analytics. Switch it off in the dashboard, or keep it and disclose it.
- ~~**SharpAPI:** check the plan page or dashboard for any monthly cap.~~ Answered by the owner, Oct 7: the Free plan ($0) has **no monthly cap**. Its limits are 12 requests a minute, 2 sportsbooks, a 60-second data delay, 1 key, and no EV, arb or middles detection. sharp_odds.py already fits it (DraftKings and FanDuel, 5.2 s gap, 60 requests a run, 429 back-off; no 429s Oct 4–7). Keep the count-only journal for pace, and never start a paid trial (all paid plans have a 3-day trial).
- **R2 NFL totals pause:** stays a shadow until its evidence window ends.
- **New post types:** "POTD missed"; a primetime prop projection sheet.
- **The locked Climb phrase**, and the "At $100 a play" dollar line under Units.
- **Who runs Kook'n:** 3–4 sentences in the owner's own words, for Start here and the pinned post.
- **Deleting the unused local models** (qwen3:32b, qwen3:8b; about 25 GB).

Please reply here with a short status after each release.
