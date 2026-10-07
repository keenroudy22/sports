# Benchmark: paid tools, pick brands and X accounts (Oct 6, 2026)

THE PAID FIELD
- **Prop tools.** Props.cash costs $19.99/mo or $199.99/yr (4.8 on iOS). Outlier runs $19.99 to $129.99/mo (4.9 on iOS). Linemate is free, with a $9.99 to $19.99/mo upgrade. BettingPros is $29.99/mo and PropFinder $14.99/mo. What they sell: hit rates for several windows in one row, a way to try any line, alternate-line ladders, with/without-teammate splits, one-tap preset searches and fast search.
- **Odds and value tools.** OddsJam runs about $199 to $499/mo (about 2.5 on Trustpilot). Unabated runs about $99 to $799/mo, Pikkit Pro $29.99/mo, Action PRO $24.99/mo and BetQL $4.99 to $49.99/mo. What they sell: the market's price with the bookmaker's cut removed, line history, closing-line value measured by price, each book's cut, and bet tracking.
- **Pick brands** (Action, Dimers, Pickswise, Covers, VSiN). They sell faces, star ratings and short hot-streak windows. Their reviews complain about records that don't match, bets that can be deleted, surprise renewals and numbers that contradict each other.

WHERE KOOK'N ALREADY WINS, FOR FREE
- A calibrated chance next to the break-even the price needs, plus a fair price and edge.
- An append-only, hash-checked public record that keeps every loss.
- Minimum game counts, and charts with dates and opponents.
- No sportsbook ads, and no paid early access to Discord.

WHERE IT LOSES TODAY
- The calibrated chance disappears in the views people scan most (Matchup edges, Trends, Matchups).
- Best bets read as stale.
- Hit-rate history shows one window at a time.
- Search dead-ends.
- Line history and per-book prices are already in the game files but never drawn.
- Proof of when each play was posted is invisible.
- Generated text carries the site's strongest AI tells.

The ten ship items fix exactly these, all from stored data, with no new feed, account or paid call.

DO NOT COPY
Sportsbook bonus walls, referral links, one-click bet slips, star ratings or letter grades, "most bet on" feeds, 1-of-1 "100%" trends, hand-picked hot-streak windows, paid early access, AI personas, and push alerts that would need a new channel.

NOT FEASIBLE FOR FREE
Public betting and money splits need licensed data. Contests and cross-device sync need accounts. Our stored line movement is the free stand-in for splits.

PAYLOAD BUDGET
- The shell (index.html, app.css and app.js, gzipped) is 92,818 B against a 94,208 B cap, so only 1,390 B are left.
- Live today.json is about 270 KB of its 320 KB limit, and lines.json is about 451 KB of 768 KB.
- So: build joins into the data files (lines.json has the most room), and pair every UI change with deletions. P2-02, P2-03, P2-08 and the voice cuts all shrink app.js.
- Before items 6 to 8, move Record, More and the team page into a lazily loaded app-more.js. That frees about 18 to 22 KB.

NEXT AFTER THE TOP 10, IN ORDER
1. A "since your last visit" line, plus private browser-only grading of Saved lines, labeled "Your saved lines, not the Kook'n record".
2. A "Books say X% (cut removed)" marker on tickets, a counterpoint when we disagree with the books by a lot, and renaming "Fair" to "Our fair price".
3. Closing-line value measured by price, run in shadow (R7).
4. Splits for with and without a teammate.
5. A More › Calculators page: odds converter, cut removed, hold, expected value and closing-line value.
6. A "Get alerts" page comparing Discord, RSS and X.
7. Combined hit history for My ticket.

DROPPED
Posting-time jitter, line-move notes written by the model, alerts on saved filters, and game-situation splits until the items above ship.

KEEPING THE BENCHMARK
Save this comparison as docs/BENCHMARK.md. Include the feature and price matrix, the do-not-copy list, and a 375 px checklist: rows per screen, taps to reach L10, and taps to try a custom line. Queue the ten ship items as P29 to P38 in docs/product-status.json, each with an owner, a next action and an observable completion check.

## Ship next (from the comparison)

### 1. Stop Buffer's 10-post queue from blocking best bets
In scripts/buffer_post.py, count pending scheduled posts before every createPost. A post is pending when its x-posted.json entry has a bufferPostId, no sentAt, no cancelledAt and a future dueAt. Once 7 or more are pending, keep the last 3 places for official plays, POTD relabels, pre-post reschedules and receipts, and push optional posts (research, conversation prompt, news, menu, sheet) to the next run. Correct the comment that says 'Buffer allows 50'. Put 'Official plays not scheduled: N' as the first line of desk_health and of the Monday review. Add a test to tests/test_buffer_post.py with a fixture of 10 pending posts.

Why: On Oct 3–4 Buffer refused createPost 6 times with 'Scheduled posts limit reached… 10 out of 10 allowed'. The NFL KC-LV under 48 failed to schedule twice, a POTD relabel failed twice and a pre-post reschedule failed. A missed official post breaks the 'every play goes out' promise that paid pick services are judged on. This stays inside the existing rule that optional posts give way before queue limits. No new service is needed and the Discord lead and daily caps do not change. It works on the free static setup.

Effort: small

### 2. Research cards show our price check, not just history
(a) Game page 'Matchup edges' (app.js ~1585, where signals = 1 + trend + defense): count the Model signal only when the exact line's calibrated grade clears our bar. build_site.py copies grade chance, needs, edge and view onto modelReads as additive fields. Every card shows 'Our chance 52% · 53% needed'. Cards that fail move into a fold labeled 'History only · no edge at this price' and never show 'N of 3 signals'. (b) Build UX P2-09 on Trends and Players › Matchups: match lines.json on officialKey plus line and show one line per card, either 'At this price: 52% vs 53% needed · no edge' or '+4.3 · clears our bar'. That line replaces the three tiles (P2-08), so app.js gets smaller. (c) The player number is a mean, so label it 'Our average' and write 'We project 41.1 on average' (this reverses P2-08's 'middle'). Stop using ▲/▼ against the line as a direction signal. (d) When our average differs from the player's recent average by more than 30%, add one code-built sentence that names the driver, e.g. 'Projected for 24 attempts. His last four: 50, 36, 43, 11. Wide range, low certainty.' Keep those rows out of Today's 'Research worth a look' and show at most one row per game there. Add pinned tests: TB at DAL Hurst over 21.5 (−1.3) cannot show a Model signal, and the JJ Kohl row shows the gap sentence.

Why: On the live TB at DAL page (375 px), Hurst, Godwin and Irving overs show '3 of 3 signals' while our own board grades them below break-even. Their history was built with Baker Mayfield, who is now OUT. props.cash ($19.99/mo) and Outlier ($19.99–129.99/mo) sell 'hit rate vs implied odds'. Kook'n's calibrated chance is better than that, yet it is missing from the views people scan most. JJ Kohl's 167.1 estimate against a 266.3 average with a 58% chance looks like a bug to anyone used to a projection-gap column. This is display only: no gate, pick or record changes. It is a build-time join with almost no change to shell size.

Effort: small

### 3. Tickets show a 'Good to' price and the latest quote instead of 'Old price'
build_site.py parses each open pick's cutoff string (pricing.py's own format) into additive cutoffOdds and cutoffLine fields in today.json. The published text stays unchanged. On the ticket face and the pick page, replace 'Old price (quoted 5 days ago) · check your book' with 'Good to −117 at 49.5'. Below it, use pickChange() (already in app.js ~2133 for Saved) to show 'Latest we saw: over 46.5 −111 DraftKings · 33 min ago · inside our limit', or '· past our limit'. Always show the quote's age. A quote older than 4 hours never becomes an Open badge, and grading stays at the posted price. Today heading after the slate: 'Next best bet · Wed 7:30 PM', with the subhead '6 open best bets through Mon, Oct 12'. 'Already posted' becomes 'Also on the card'. Add node tests for the after-slate heading and the inside/past-limit states. Budget about 1 KB of shell, offset by the copy cuts.

Why: On live Today, 4 of 6 best bets are grayed 'Old price … check your book', even though lines.json already holds newer quotes for the same markets. The first thing a visitor sees looks expired. Action Network shows 'would play to' and the current best price. The owner dislikes 'Price expired', and the Oct 2 rule already allows a current captured quote next to the preserved original. Free and static.

Effort: small

### 4. P0 copy sweep: 21+ on every card, one guard on every outgoing text, no robot tells
(a) Compliance: the legacy pick_card.py footers (~609, 680, 773, 853, 924, 1028) go to '21+ · Entertainment only'. research_art.py:88 'DATA + CONTEXT' goes to '21+ · Entertainment only'. The sheet footer gets 21+. Only new renders change; posted attachments are never redrawn. (b) One send-path guard: every Buffer and Discord text, including conversation prompts, fun teasers, the Climb teaser and the Discord pull update, passes x_post.x_style plus the VOICE.md phrase list before it is scheduled. A failing optional prompt is skipped and logged. (c) Retired words: remove 'desk' from the Climb check-in, 'PLATES' from the receipt card, public 'Ladder' (use 80/20 Climb), 'the owner' from site copy and 'Kitchen's closed' from RSS titles (GUIDs kept). (d) Future generated text: rewrite the percentile sentence so it has no ordinal, drop the 'Nth of 1' role rank when fewer than 3 teammates are projected, use FBS-only defense tables for CFB in run.py to match the site's 'of 136', drop 'Confidence N of 10', dedupe cautions by sentence, and remove the judge's 'which is a concrete reason the over is likely wrong' from pull notes. (e) Display-time fixes for stored text: receipt rows read 'had 1' instead of 'Final: Marvin Harrison Jr.: 1 receptions', and 'both legs hit' instead of 'all 2 legs won'. whyLines() never promotes a fact whose direction is not 'for' on a modelLean pick; build_site carries the direction. (f) tests/test_voice.py (stdlib) plus a node twin fail on em/en dashes used as punctuation, the VOICE.md banned list, 'Confidence \d+ of 10', 'Nth of 1' role ranks, ordinal bugs such as '82th', and any card SVG without '21+'. Keep the code-parsed markers exactly as they are: 'before its post went out', ' ET: ', '. Published cutoff', '. Stays in the record', and the Model lean, Prop lean, Researched pick, Role:, Defense: and Last N games: prefixes.

Why: AGENTS.md requires 21+ on every card. FELT_FROM is None, so the legacy renderers posting today have no 21+. An em-dash prompt reached X on Oct 3 through an unguarded path. Strings like '82th percentile', 'Nth of 1 NMSU WRs', '1 receptions' and 'Confidence 3 of 10' (badges were retired Oct 6), plus a why bullet arguing for more points on an under (Bills/Rams), are the strongest 'made by AI' signals and undercut the honest record. Pickswise sells 'human expert' copy for exactly this reason. Published records stay untouched. The cuts also shrink app.js.

Effort: medium

### 5. QB news on the card itself
build_site.py joins data/app/research.json injuries and each game's nextUp into a per-team QB status. It adds an additive qbNews field to Upset watch rows, the game hero's 'Unusual gap' badge, Matchup edges, Trends rows and Players › Matchups cards for that team's QB and pass catchers. The chip goes on the card face, never in a fold: 'QB news: Lamar Jackson questionable · line moved 8 since open · our team number doesn't see injuries'. Pinned tests: the Ravens +142 upset card and the TB at DAL hero both show the chip.

Why: Live: the top upset signal (Ravens +142, 53% vs 40%) sits on an 8-point line move with Lamar Questionable, and the only warning is inside a closed fold. TB at DAL carries an 'Unusual gap' badge with Mayfield OUT. Trends shows Hurst 4/4, all with the injured QB. Linemate and Outlier sell injury-aware views. Kook'n already has the data but shows it about 2,000 px down the page. This is a display-only build-time join. Demoting or excluding these games changes the ranking, so that part is an owner question.

Effort: small

### 6. Make room, then make the Research board answer fast
Step 1 (prerequisite): move Record, the More subpages (start, saved, ticket, arbs, schedule, status, feedback, responsible) and #team into app-more.js, loaded on first navigation. Keep receipt() and the pure model functions in app.js for Today and the tests. That frees about 18–22 KB gzip; today there are only 1,390 B left (92,818 of 94,208 B). It needs a narrow publication_guard entry, a payload_budget line and a PUBLIC-PAYLOADS.md line. Step 2: add exact-line hit pairs to each lines.json row (l5, l10, season, vsOpp, lastSeason, venue) using favorite_hit_rates() and the boxscore stores. Live lines.json has about 335 KB of headroom. The collapsed row shows one strip, 'L5 3/5 · L10 7/10 · 2026 9/12 · vs FIU –'. Under 3 games it is gray and marked 'small', never shown as 100%. The metadata shrinks to chips ('QB · CFB · Wed 7:30') and the meter caption to '58% vs 53% needed', so about 4 rows fit per phone screen. Step 3: typed search covers every current line ('2 Lamb lines · none clears our bar'). A 'Find a player or team' box at the top of Research opens the player page from a lazily loaded slim name index. Step 4: shareable preset chips: 'Clears our bar and hit 7 of last 10', 'Soft matchup and hitting', 'Unders that keep hitting (5+ games)', 'More work with a starter out'. Add game, market, side and book filters plus 'hide heavy favorites' inside filtersFold. Edge stays the default sort.

Why: props.cash puts L5/L10/L20/season/H2H in one row. Outlier filters by game, prop, book, side and hit rate. Linemate's cheat-sheet presets are its biggest free hook. On Kook'n, collapsed rows show no history, only about 3 rows fit per screen, and searching 'Lamb' on the default view says nothing matches. Kook'n can beat all three because every preset carries the price check, which none of them do. Uses stored data only, with no new requests and nothing behind a paywall.

Effort: medium

### 7. Player page: every line for the player, and any line you want to try
Under the Next card on #player, add a compact table of all of that player's current lines from lines.json: stat, line/side, best price and book, our chance vs needed (only when calibrated and fresh), L10 and ✓. Tapping a row switches the stat chip and the chart. Add a − / + stepper in 0.5 steps that moves the chart's dashed line and recounts L5/L10/L20/All on the client. Below it, a 5-rung ladder around the main line shows hits. Price, chance and break-even appear only where an exact alternate row exists; otherwise the rung says 'no price', and an unpriced line never gets a chance. Add a 'Your price' box: enter your book's odds for the same line and see break-even next to our chance (pure math, no invented price). Under the main chart, add a thin usage row (attempts, targets or carries) and tag games below 50% of his median with a gray 'partial game?'. Hide splits that rest on 1 game.

Why: Outlier's Custom Line Builder, props.cash's adjustable line, Linemate's stepper and its '100% Alternate Lines' sheet are core paid or free hooks. Kook'n counts hits against one line only, a QB page takes up to 10 chip taps to scan, and nothing explains JJ Kohl's 11-attempt game. Everything comes from stored player shards. It respects the Season Trends rule that unpriced milestones are history, never offers or picks.

Effort: medium

### 8. Game page: what changed first, then the line history
Under the hero, add a one-line 'What changed' strip listing OUT/Doubtful players at QB, RB, WR and TE and the move since open, e.g. 'Baker Mayfield OUT · spread TB +3.5 → +8.5 · total 52.5 → 47.5'. Draw marketHistory (already in every games/*.json and never read by app.js) as a small inline SVG step chart for spread and total, with a kickoff marker and the caption 'captured snapshots, not every tick'. Render marketRead.books as a grid: book, spread, total, price, the book's cut %, best price highlighted, capture time. Hard Rock is labeled comparison only, and anything older than 4 hours is never shown as current. Finish P2-02: merge 'Model vs market' into the hero, fold the injury report under Next up and add jump chips. Page order: What changed, Lines we like, Matchup edges (with the price check), then the rest.

Why: TB at DAL is 7,419 px tall at 375 px, and the QB-out note starts at y≈3,094. Action Network's free odds page leads with open/now and the best price, and Unabated and OddsJam Platinum ($499) sell line history and hold. Kook'n already ships the data and never draws it. Shell bytes stay about level because P2-02 deletes a duplicate section. No new feed calls.

Effort: medium

### 9. Proof on every receipt and pick
On the pick page and each receipt row, show 'Posted Tue 11:45 AM ET · 31h before kickoff · Original post on X ↗ · In the public log ↗'. The build adds an additive postUrl field (x.com/keenkooks/status/<tweetId>) to pick entries in today.json and record.json from data/x-posted.json. It carries the URL only, never Buffer IDs, metrics or the log file. The public-log link opens the GitHub history of the research file that first published the play. Add a narrow publication_guard field entry, fixtures and a PUBLIC-PAYLOADS.md line. Add a 'How we keep score' paragraph to Start here that links the repo and the integrity test. Add a Share button (navigator.share, with copy-link as the fallback) on tickets and the pick page.

Why: The main trust signals at Betstamp, Pikkit, Juice Reel and Action Network are timestamps and 'verified bets'. Their reviews complain about deletable bets and records that don't match. Kook'n's append-only, hash-checked public record is stronger than any of theirs, yet the site never shows it: 69 of 81 logged posts have tweet IDs and none is linked. This links posts that are already public and does not change what counts.

Effort: small

### 10. A Record page that explains itself (needs your yes)
Under the Record KPIs, add a 'Where it's working' strip on the posted-price basis only, the same basis as the units line. One row each for player props, game totals and spreads: W–L, units, and 'line moved our way in X of Y'. Add one plain sentence: 'At about −110 you need 52.4% to profit.' In Record › Model, add a 'When we said X%, it hit Y' table with buckets 50–55, 55–60, 60–65 and 65%+, n on every row, and 'early, small sample' under 30. Add a table by edge size (0–2, 2–5, 5+ points). Counting does not change. Splits are recomputed with C.recordBreakdown captured rows, and a test checks that the strip totals equal the headline captured totals. The release note gives the owner the before and after display numbers.

Why: CBS Inside the Lines prints splits that include its losing markets, and tout-spotting guides treat an unsplit W-L as the first red flag. Today the 35–35 headline sits next to −4.11u on a different 21–24 base, and the real story (props doing well, game totals 8–13, −5.40u) is buried in a collapsed box. No paid tool publishes whether its stated chances come true; BetQL stars and Action letter grades are opaque. This changes how the record is presented, so it waits for the owner's yes.

Effort: small · needs owner

---

## Deep review: Dans AI, Oct 6

The owner named Dan's AI as a second account to study for attraction. The real account is **@DanGambleAI** (display
name Dan's AI Sports Picks): 333.8K followers, 95 following, about 17.9K posts, joined June 2023. Several lookalike
accounts copy the name. Two read-only passes on Oct 6 covered 54 original posts from Oct 3 evening to Oct 6 evening,
a few older posts, the Articles tab and outside reviews. Sources: an X tab (nothing liked, followed or clicked), the
public fxtwitter embed mirror, Discord's public invite count, the App Store listing, Casino.org, BetPredictionSite and
OddsPlays. Metrics were read at different post ages, some long posts were cut off at Show more, and save counts were
not visible on every post. This is a creative benchmark, not proof of what works for a 77-follower account.

The most useful fact: this file recorded 332K on Sep 26, so he gained only about 1.8K followers in ten days while
nearly every post drew 50K or more views. Big reach is not fast follower growth, even for him. Judge Kook'n
experiments on profile visits and follows, as `GROWTH.md` already says, not on views.

### The operating loop

It is the same loop as Cody Brown, packed into one game night. Monday Oct 5 (MNF), Eastern:

| Time | Post |
|---|---|
| 8:30 | Menu teaser quoting last week's MNF win |
| 9:03 | Single-game 100% hit-rate list |
| 9:49 | One tight end's receiving-yards alt ladder (30+/40+/50+) with five ✅ matchup reasons |
| 10:34 | Discord game-night giveaway promo |
| 11:46 | Dropping-soon teaser |
| 12:11 | +631 same-game parlay drop |
| 2:01 | Pick of the Day with line-movement proof |
| 3:34 | +2200 longshot special |
| 4:35 | Paid-app challenge step, slip blurred |
| 5:45 | Discord promo video |
| 6:31 | Prop projection sheets |
| 7:21 | One-hour-to-go hub linking every bet |
| 8:23 to 11:00 | Five short live-sweat lines, a POTD cash post and a meme clip |
| 11:12 | Question about a real moment from the game |
| 11:20 | Instant cash post (now pinned) |
| Tue 8:31 | ✅ recap of last night's wins |

Volume: about 22 posts on Sunday, 21 on Monday and 10 on Tuesday with no NFL game, roughly 18 a day. About half of
the game-night posts are one-line live sweats. No hashtags and no @Playbook; he uses FanDuel load links instead.

### What each format earns

Every post gets a floor of about 50K to 60K views, even a one-line comment that the game should be good. Views mostly
measure his account size. Likes and saves per view are what separate the formats.

| Format | Example (Eastern) | Views | Likes | Saves |
|---|---|---:|---:|---:|
| Every-game list, text in the caption over one plain photo | TNF props, Oct 6 6:31 PM (saves mostly within an hour) | 74K | 704 | 497 |
| Every-game list, one game | MNF list, Oct 5 9:03 AM | 124K | 510 | 254 |
| Every-game sheet, whole week | Grouped by game, Oct 2 10:47 AM | 452K | 308 | 498 |
| Lotto built from the list | 13 legs, +4021, mostly −260 to −650 alternates, Oct 3 7:04 PM | 393K | 869 | 648 |
| Ticket drop | +631 MNF SGP, slip on a player photo, Oct 5 12:11 PM | 220K | 429 | 276 |
| Alt ladder with ✅ reasons | Oct 5 9:49 AM | 163K | 211 | 88 |
| Narrative ticket, other sport | MLB playoff pitching matchup into a +486 SGP, Oct 6 11:40 AM (28 replies) | 138K | 154 | 56 |
| POTD with line-move proof | Oct 5 2:01 PM | 84K | 212 | 55 |
| Prop projection sheet | SNF, line vs projection, Oct 4 7:11 PM | 110K | 104 | 41 |
| Instant cash post | +631 cash, pinned, Oct 5 11:20 PM (45 replies) | 110K | 490 | 6 |
| Instant cash post | MLB, Oct 6 7:42 PM (43 replies) | 58K | 436 | n/a |
| Morning ✅ recap, wins only | Oct 6 8:31 AM | 103K | 160 | 2 |
| Real-moment question | Post-game touchdown question, Oct 5 11:12 PM (21 replies) | 133K | 118 | n/a |
| Teaser that holds a pick for likes | Oct 4 1:29 PM | 72K | 214 | 1 |
| Live-sweat line | Oct 4 and 5, about a dozen | 55K to 60K | 29 to 54 | n/a |
| Link hub | Oct 5 7:21 PM | 86K | 33 | 8 |
| Giveaway / Discord promo | Oct 5 10:34 AM | 98K | 33 | 3 |
| Blurred, paywalled pick | Oct 4 8:48 AM | 87K | 26 | n/a |
| Paid-app recap pitch | Oct 6 3:42 PM | 51K | 19 | 1 |
| NBA future with a short why | Rookie of the Year +330, Oct 6 4:47 PM (10 replies) | 51K | 59 | 19 |

What the table says:

1. **Lists of exact thresholds earn the saves.** The best like and save rates in the sample (about 1% likes and 0.7%
   saves on the TNF list) came from a plain text list in the caption. The photo was decoration.
2. **Tickets earn reach and tail intent.** Odds and payout sit above the fold.
3. **Instant cash posts earn likes and replies, not saves.** They are community, not reference.
4. **Holding a pick for likes earns likes and no saves.** It is a conversation trick, not value.
5. **Promotion, paywalls and link hubs were the weakest posts in the sample,** even with 333K followers. (Cody's
   all-bets index did well; Dan's hub did not.)

### Visual system

- **Tickets:** the real FanDuel slip on a large cut-out player photo, a huge headline banner, stake and payout visible,
  a load-the-link footer. Most picks attach a second sportsbook ad image.
- **Lists:** often no designed graphic at all. The list is the caption.
- **Projection sheets:** team sheets labeled as AI prop projections, line against projection in green and red, a
  player cutout.
- **One win template reused every time:** neon green, a giant bang headline, checked legs, stake and return.
- **AI-generated scenes of the invented Dan character next to real athletes** (handing a player a Hall of Fame jacket,
  surfing with an MLB star, a GTA-style scene, Big Ben). The pick cards themselves use real photos.

### Voice and the "AI" label

- "AI" is the name and the costume, not the writing. The avatar and banner are AI-generated pictures of an invented
  person. Casino.org says the name comes from the ChatGPT "DAN" prompt and the operator is anonymous. His NBA articles
  (2024, and an Apr 2026 champion model) leaned on AI much harder than his current X posts.
- The model barely appears on X: a robot-emoji algorithm line on projection sheets. Probabilities, edges and the
  0 to 100 prop grade stay inside the paid app.
- The captions sound like a person watching the game: first person, groans at a missed catch, relief when a leg
  lands, leg-by-leg progress such as 7 of 10 receiving yards, an occasional typo (an MNF special labeled TNF).
- Trust effect: the label and persona help discovery and attract impostors, but outside reviewers call the
  forecasting weak and the promotion aggressive, and one sums it up as a fun freebie. The voice, not the AI, is what
  makes the account feel human.

### Records and receipts

- Only wins get graphics: settled slips with green checks, the win template, a quote of the original post and a
  morning ✅ list. Losses appear only in text, and gently (one rollover loss was called "Bank Builder still stings",
  @DanGambleAI, Sep 14).
- No W-L, no units and no record page. Claims are selective streaks: a 73% NFL hit rate, 3/3 ladders, 6.5 units in
  April. GameScript tells buyers to check the cappers' social media; a paying App Store reviewer asked for per-capper
  tracking. BetPredictionSite says he once posted Super Bowl picks for both teams.
- Line movement is used as proof of paid early access: the paid app had the pick at −110 at 9 AM, now −160.

Kook'n's complete, append-only record is the one thing this account cannot show.

### Other sports

- The lead sport and bio rotate with the season. Summer Instagram pushed MLB, WNBA and soccer; the X bio now says NFL
  and CFB, yet no college football appeared in this window.
- A new sport enters through one big story or one season-long future. MLB came in through a playoff pitching matchup
  told as a head-to-head story (the most replies of his Tuesday posts). NBA came in two weeks before tip-off with a
  Rookie of the Year future and a short why, quoting a summer-league clip. He quotes league and team accounts for video
  instead of uploading clips.
- No NHL from Dan on X or in search. The Oct 6 read above found one NHL goal-scorer card (Splash Bets, 6K views). NHL
  looks thin among the accounts we follow.

### CTAs and the funnel

- One call to action per post: tail, heart if you tailed, or who's with me. Most picks end with a 21+ line.
- Money comes from FanDuel one-tap tail links on almost every pick (boosts and promo tokens become content) and from
  GameScript, a paid capper-plus-AI app: a $1 trial, then about $100 a month on the App Store, with a $1,000 tier
  reported. Blurred slips and an app-only $10 to $10,000 rollover challenge push the trial.
- The free Discord is GameScript's own server (about 96K members) with game-night live channels and giveaways
  (GTA VI copies, NFL jerseys).

### The Kook'n adaptation

Copy what makes people save, reply and trust. Skip what sells. Kook'n already has the skeleton of this loop: the 9 AM
receipt, the 10 AM sheet, the 10:30 research card, noon plays and cashed posts as wins settle.

**Borrow, inside current rules** (every wording or card change still gets an owner preview, per `POSTS.md`):

1. **An every-game list in the existing research slot.** Season Trends at its strictest: fresh main lines that hit in
   every game this season, each with N/N, price, book and what that price needs to break even. Five-game minimum, main
   lines only, one research post per date, even-date priority unchanged. It will be shorter than Dan's because it
   refuses milestones, and that is the point. Use the every-game headline only when every row is N/N.
2. **Concrete reasons on the play card.** Up to three ✅ facts from stored evidence (allowed-by-position rank, role,
   exact-line history) plus one visible counterpoint, as the site's Why this play does. The caption keeps one reason.
   A card change goes through the P21 social-template gate.
3. **Specific results.** Name the margin from the stored settlement (`cleared by 12 yards`, `missed by 3`). Losses
   keep equal weight in the morning receipt.
4. **Honest line movement.** Kook'n saves the original and closing quotes. `Posted −110, closed −125` on a result is
   Dan's early-access boast made truthful, but only if moves against us are shown the same way. Needs guard support.
5. **Lead with the window.** Primetime posts start with TNF, SNF or MNF (or the college slot) so the reader knows what
   the post is at a glance.
6. **Keep the clean ticket hierarchy.** One dominant player, odds as the headline, full-width legs, no sportsbook
   branding. The lines-first ticket already does this.
7. **Make the record the pinned promise.** Dan pins his biggest win and cannot show a W-L. The pinned Start here post
   (P27, the owner's call) can lead with free plays and every result public, wins and losses.
8. **One-tap tailing without affiliates.** @Playbook does what his FanDuel load links do, free and without a referral.
   Keep it on new plays only.

**Avoid:**

- 100% hit-rate claims on three or four games, low milestones and 13-leg lottos stacked from −260 to −650 alternates.
- Holding a pick until it gets likes, dropping-soon teasers with nothing ready, and link hubs.
- Paywalled or blurred picks, early-access boasts, sportsbook ad images, affiliate tail links and promo-token parlays.
- Giveaways.
- AI-generated pictures of a persona with real athletes, "AI" in the name, robot-emoji model talk.
- Win-only graphics, softened losses, streak claims without a W-L, picks on both sides.
- An all-in rollover challenge. The 80/20 Climb is the safer story.
- Same-player alt ladders (30+/40+/50+), which break the no-stacking rule.
- POTD captions that do not name the pick.
- 18 to 22 posts a day, desk-automated live sweats on X, uploaded game clips and memes.

**Needs the owner's yes first** (this review approves none of it):

- Listing several lines in a research caption, or bringing back a save ask. Both conflict with the Oct 6 short
  research voice, even though Dan's best list was a caption list.
- A result card for ordinary wins (a new public file family under P21). If yes, the receipt must still give losses
  equal weight.
- Exclamation marks or a casual reaction line in cashed posts or receipts. The guard bans "!" outside the Discord live
  pilot.
- A post-game question about a real moment. The conversation slot is before the plays. The owner can always post one
  by hand.
- X live progress. It still needs three clean Discord pilots and its own release checkpoint.
- Payout lines such as $10 pays $412 on fun tickets.
- A primetime player-projection sheet, which would be a new research family.
- NBA or NHL on social: resuming `KEENROUDY_SPORTS_SOCIAL`, an NBA opening-week research post, or any public future.
- Showing heavy favorites on trend lists (R5, still in shadow).
- Affiliate links, giveaways, a paid tier or more posts per day. Recommendation: no.

**Other sports, Kook'n's way.** NBA tips off around Oct 20. Keep it website-first: trial projections on the NBA Today
view, graded apart from best bets. If the owner wants NBA on social, Dan's pattern points to one opening-week marquee
game told as a factual story (projection, exact line and price, labeled as a trial) rather than daily picks. NHL has a
market lab and no model, so it stays scores and collected lines. The thin NHL coverage among these accounts is a
reason to build and trial an NHL model, not to post NHL picks early.
