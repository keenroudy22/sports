# Posts and graphics: everything that goes to X and how it looks

The desk posts to X as **@keenkooks** through **Buffer** (free plan), never by clicking around X. Every post is text
plus, for plays and house posts, an image card. This page is the complete spec: each post's text, its card, when it
goes out, and the code that makes it. Examples of the cards are in `docs/examples/`. What the accounts we follow post
and what gets saved is in `docs/X-NOTES.md`.

## October 6 approved redesign direction

The owner approved the casino-felt identity for the website and future card cutover: felt night `#07120D`, felt
`#0E2219`, chalk `#F2F7F4`, dim `#A9C0B3`, Kook'n green `#20C774`, chip-red fills `#F2414E` and red text
`#FF6B75`. Brown, tan and amber remain banned. Green means a hit or support, red means a miss and gray means unknown;
every use also carries a symbol or word. Brand green alone never implies that an open play won.

“Best bets” is the public name for the existing official-play set. It changes no gates, caps, prices, grading or
record. Public copy retires “Best lines”, “official card”, “plate”, “Served at” and “desk”. Keep captions short and
human: the exact play and price first, one strongest reason, one clear action. Do not explain the model or repeat
generic disclaimers in the caption; the page and card retain the required 21+ and entertainment-only wording.

Player photos and team logos stay, with team-color badges as fallback. Do not redraw a published attachment. The
felt website is live. Social templates remain separately gated under P21; until that quiet-window cutover, the
current renderers remain the production contract. Existing post categories, caps, filenames, dimensions,
Discord size limit, Buffer-only delivery and X/Discord schedule do not change.

Creative learning compares felt and legacy only within the same existing post category. Every newly scheduled
post records `cardTheme` in `data/x-posted.json`; older rows without the field count as `legacy`. The Tuesday
learning report and Monday owner review show each category/theme separately, mark fewer than eight settled posts
as a small sample, and never move selection gates, post frequency or theme automatically. A human owner decision
is still required for a later creative cutover.

## October 5 effective creative policy (superseded where stated above)

The owner approved tested original layout/color/short-copy variants within already-approved post categories and
their existing caps. This is not approval for a new category, extra post volume or broader automation. Exact
selection, price/book, historical counts/windows and result facts remain source-bound and pass the existing guards.
Green means hit/support for the selected side, including an under; red means miss/against that side; gray means
unknown/inactive. Pair color with text or symbols. The October 6 felt palette supersedes the navy/mint/cyan identity
for new releases; no public avatar change is implied. Brown/tan/amber remain banned and existing posted attachments
remain untouched.

Evaluation/release windows are checks, not quotas: qualified, no-play, held, queued and delivered are distinct
states. A caption bug gets a bounded factual fallback, never a lower evidence threshold. Rotate a small stable set
of readable templates rather than changing the brand every day. Keep one clear action per post and preserve the
Playbook-only-on-new-X-plays rule.

**Separate release checkpoints remain:** social trend sheets use fresh main lines and at least five games only;
alternate/milestone social sheets are not enabled. The live-progress Discord pilot remains bounded; public X
progress stays off. New sports stay website-first. No new feed, paid service, metrics collector or public frequency
increase is authorized by this creative approval. See AGENTS.md and `PRODUCT-IMPLEMENTATION.md`.

The free Kook'n Sports Discord mirrors this feed. Confirmed official plays arrive about 10–15 minutes before X;
other posts wait until Buffer confirms X delivery. A five-minute local job sends the same wager text and card once,
but strips the X-only `@Playbook` mention. This also applies to previously queued, unsent Discord mirrors. The card is uploaded as
a Discord attachment instead of a temporary external embed; recent receipt URLs remain live for eight days as a
delivery fallback. A Discord failure retries
and alerts ntfy; it never changes, advances or replaces the X post.

NFL and college player cards both use the athlete's ESPN portrait when available, with the existing artwork
fallback if unavailable. Preview a POTD with `python3 scripts/pick_card.py <id> --featured --svg --out <path>`.
This does not update attachments already posted. The Board shows confirmed delivery separately from a scheduled
post and from expiry of the original price; it never labels a due time as proof of delivery.

## The voice (the owner's rules)

New sports stay website-first (Oct 5). The optional multi-sport schedule post is paused by default
(`KEENROUDY_SPORTS_SOCIAL=0`). Scores, saved trial projections and separately labeled research records can
appear on-site; new-sport picks still need validated trial results and their release approval before social posting.
Existing football releases and results continue unchanged.

The Oct 5 owner-approved live-progress pilot is a text-only Discord exception to the ordinary X-first mirror.
Examples (fictional previews, never sent): `Receiver over 49.5 receiving yards` / `41 so far. 9 more
receiving yards to reach 50.` / `8:12 - 4th · Live stats`; or the owner's requested casual version:
`Receiver over 49.5 receiving yards` / `9 to go. Come on!` / `41/50 receiving yards · 8:12 - 4th`.
The local model chooses plain or casual; casual cannot repeat on consecutive updates. This narrow live-copy
exception permits `Come on!`, not guarantees, pressure to bet, or unverified wins.
A ticket always says `Ticket leg`, never implies the whole ticket won, and a confirmed losing
leg suppresses its remaining updates. At most two/day, 45 minutes apart, one/ticket, three pilot attempts total.
No images, Playbook tag, unsolicited mentions or replies, and no X delivery in this pilot. Early crossings and
finals remain with the observer/ordinary settlement receipts rather than another celebration. See `LIVE-PROGRESS.md`.

Weekend Climb check-ins are approved text-only house posts. At/after the 11:45 AM Saturday/Sunday run, report
the bank, next stake and unscheduled/open state unless a same-day ticket is already open. The date-specific key
prevents duplicates, and the normal queue limits apply. These are updates, not promises that a ticket will post.

- **Short and human, straight to the point** (2026-09-26: "Not so AI looking. And straight to the point on the
  tweets"). A play is one line with its price and book, then our number in a few words. No labels ("TEAM PROP"), no
  slogans ("Graded in public"). From Oct 4, one short saved supporting sentence follows our number when available.
  It comes from structured history or verified supporting facts; arbitrary prose is never mined for a reason.
  The site keeps the complete reasoning and counterarguments. Under the character limit, keep the reason ahead
  of the optional engagement ask; never truncate a wager to fit it.
- **Every number comes from the pick.** `x_post.guard` refuses a post whose numbers are not in the pick's own fields
  (rounded projections and ladder dollars are allowed as the post writes them). No em or en dashes, no "!", no
  marketing words ("lock", "guaranteed"), no advice ("bet this"), no model names. A post that fails its check is held
  and named in the log and on the phone, never posted.
- **No straight-play units on X.** Money and full record units live on the site. Receipts may identify a fun parlay
  as its smaller 0.25u stake so it cannot be mistaken for a full-unit straight play.
- **Every play and fun parlay ends on the ask** `❤️ if you're tailing` (a ladder rung: `❤️ if you're climbing`), then
  `@Playbook` (Action Network's betslip bot, which replies with the bet pre-loaded) and the league tag `#CFB` / `#NFL`.
  The Playbook tag is only for **new plays on X**, including new parlay/Climb tickets. It is absent from Discord,
  results, recaps, research, menus and other updates. Previously published posts are not rewritten.
- **No links in play posts** (X shows linked posts to fewer people); the card carries keenroudy.com/sports. Cashed
  posts carry the original post's X link, which makes them quote it.

## Each post

| Post | When (Eastern) | Text shape | Card | Code |
|---|---|---|---|---|
| **Play** | Around noon; two hours before an earlier kickoff; never before 9 AM; ten minutes apart | `Iowa/Michigan over 38.5 (-105, ESPN BET)` / `I have it at 47.` / ask / tags | the play card | `x_post.draft`, `pick_card.svg` |
| **Pick of the Day** | First in the noon batch | `🍳 Hot Plate (POTD): ...` then as a play | the play card labelled `HOT PLATE (POTD)` (`cards/<id>-potd.png`) | `featured.py` |
| **Player prop** | As a play | `Jordan Love under 2.5 carries (-111, DraftKings)` / `I have it at 1.2.` | the player's ESPN headshot on the card | `pick_card.artwork` |
| **Side** | As a play | `Duke -10 vs Stanford (-110, FanDuel)` / `I have Duke by 14.` | the side's logo | |
| **Lotto / longshot** | After the plays | `🎰 +2506 Chef's Special: 5-leg college lotto (FanDuel)` / `$10 → $260 at the posted +2506` / legs / `❤️ if you're tailing` | parlay card with the legs | `x_post.parlay_head` |
| **Easy props** (alternate lines) | Evaluate weekend slates, within the current once-per-league/seven-day alternate exception; never a quota | `🎰 +450 Chef's Special: 3-leg NFL easy props (FanDuel)` then the posted-price example and legs | parlay card | `easy_parlay.py` |
| **80/20 Climb step** | On a qualifying scan; one open rung, with same-day advancement/restart allowed after settlement | `🪜 $75 → $117 · 80/20 Climb, step 2 (-178, FanDuel)` / `Step 1 cashed. $19 banked on the way to $1,000.` / legs / `Still climbing? ❤️` | a tall winding route with the real bank, ride, rung and labeled future checkpoints | `ladder.py`, `pick_card.ladder_svg` |
| **Conversation prompt / teaser** | Once on a multi-play card, after the first play | A short slate question, or—when it is already ready—`The 80/20 Climb is back later today. Step 2 is already cooked. 🪜` with its real ride and bank, then the league tag | none; intentionally text-only | `buffer_post.conversation_text` |
| **Injury angle** | After verified top-player news, at most two a day | `🚨 ESPN lists A.J. Brown OUT for PHI at CHI.` / a teammate's real post-news line, price and book / the opponent's allowed-by-position stat / `Board lean, not a posted play. Take it or pass? #NFL` | none; timeliness and the question are the point | `news_posts.candidates` |
| **Morning receipt** | 9 AM the day after a game day | `Saturday: 5-3` then `✅ Iowa/Michigan over 38.5` per play; a fun ticket adds `0.25u · 2/3 legs hit · missed by one leg` when the stored settlement supports it; a raw losing player prop waits for its injury/return review until 12 hours after kickoff, then uses the official stats if no different official book settlement is known; a verified injury adds `injured in-game · checked before grading`; `Today: 3 plays.`, tags | the tall navy/mint report card (W/L per play, finals, parlay sweat, the chef) | `receipts.day_receipt`, `with_menu`, `pick_card.receipt_svg` |
| **Week's receipt** | Wednesday 9 AM | `The week (Sep 23 to Sep 29): 12-9` then the record by kind; fun parlays show their smaller stake | receipt report card | `receipts.week_receipt` |
| **Save this projection sheet** | 10 AM college Saturday and NFL Sunday | full NFL slate or 16 college games / exact line, odds and book / up to four price-qualified mint rings / save ask / tag | 1080x1350 compact projection grid | `sheet.py` |
| **Research card** | At most one per football slate, targeted for 10:30 AM | Fresh outright Underdog Watch first; otherwise a priced underdog cover, defense-supported exact-line Matchup Trend, or End-zone Work. CFB players projected to trail by 14+ are ranked down and carry game-script context. The category label distinguishes research; the caption stays to the exact line, one proof point and price without a stock disclaimer or generic save ask | Compact 1200x675 navy/mint/cyan card with large lines and one team/player hero | `research_posts.py` |

Confirmed official plays, the Pick of the Day and fun/challenge tickets use the same copy and card in Discord about
10-15 minutes before their X time. Receipts, injury angles and conversation prompts mirror after X. Public promotion
says "plays hit Discord first," never "guaranteed bets" or anything that implies a win.
| **Cashed** | As an ordinary win settles (9 AM to 12:30 AM, within three hours); a Climb win remains eligible 24 hours and an overnight result targets 9:05 AM | `✅ Cashed: Iowa/Michigan over 38.5 (-105, ESPN BET)` (or `✅ POTD cashed: ...`, `✅ +2506 5-leg lotto cashed (ESPN BET)`, `✅ 80/20 Climb step 2 cashed: $75 → $146` / `$48 banked. $117 rides step 3.`) then the tag and the original post's link | ordinary wins quote the original without a new image; a Climb win adds the dedicated 1080x1350 advancement/completion card | `receipts.cashed`, `pick_card.ladder_result_svg` |
| **Menu** (alone) | 8:45 AM on a game day with no receipt | `Today: 6 plays` then `Iowa/Michigan 3:30 PM` per game | `site/img/kitchen-menu.png` | `receipts.menu` |
| **The book** | 6 PM on a day with nothing else; the daily-presence fallback, never a forced play | `Season through Sep 28: 23-22` then by kind | `site/img/kitchen-book.png` | `receipts.book` |

An injury angle only exists after a newer projection removed the player and redistributed their role, and after a
book price was captured following the news. It never counts as a play; a qualifying official play posts separately.

Limits: twenty posts a day at most, counting what is queued (`buffer_post.MAX_PER_DAY`); ten minutes between any two
posts (`buffer_post.free_slot`). The card must be live on the site before a post is scheduled; a play whose card is
not live waits for the next run (nothing goes out bare).

## The cards (graphics)

### October 5 visual refresh

New straight-play assets use `pick_card.modern_svg`: full player portraits or team logos, the exact selection
as the largest element, and separate book/price and projection blocks. Mint/cyan accents rotate deterministically
through the existing themes. Kook’n and the chef remain the brand; the wordmark leads data-heavy graphics.
Parlay and ladder templates retain their specialized layouts. Existing published attachments stay untouched.

Research assets use `research_art.svg`: compact landscape header, clean rows, exact sample counts and expanding row heights
for longer fields. Use only selected verified evidence, not statistics transcribed from inspiration screenshots.
Keep historical trends distinct from official plays; do not call a mixed-rate sheet “100%.” This changes artwork,
not candidate selection, automatic release times, X/Discord limits, injury checks or data budgets.

**Lines-first ticket design (owner approved 2026-10-02):** longshots, lottos and easy
props use `pick_card.ticket_svg`: 1080 px wide with height that grows for every complete leg. Each full-width
panel leads with the player/team, an 80 px wager line, and the market. Unknown market wording stays intact;
never truncate a leg or hide it behind “more.” Each player leg uses its real ESPN cutout large on the right side
without a circular portrait badge when available; game
legs use the relevant team logo or both matchup logos. Three deterministic navy/mint/cyan treatments rotate by
ticket ID, so a published card never changes on rerender. A small chef badge and price/book in the header replace
the oversized mascot. The ladder and straight-play renderers stay separate. Existing Discord/X attachments are not replaced.

Drawn as SVG and rendered to PNG by headless Chrome (`pick_card.render`). New straight cards and Climb cards use
1080x1350; tickets and research may grow vertically to keep full rows legible. Older house templates retain their
own dimensions. The hosted build draws needed assets on deploy (`scripts/feed.py`) into `site/data/cards/`,
served at `https://keenroudy.com/sports/data/cards/<name>.png`: `<pick id>.png`, `<pick id>-potd.png`,
`receipt-day-<date>.png`, `receipt-week-<date>.png`, `sheet-<league>-<date>.png`,
`research-<family>-<date>.png`, `ladder-result-<pick id>.png`.

The **Climb ticket and result cards** share one persistent path. Each completed step gets a green checkmark, the
current or next step is outlined, anonymous future checkpoints lead to the $1,000 flag, and no future return or
step count is promised. The result leads with `STEP N CASHED` or `CLIMB COMPLETE`, keeps each actual leg in a
full-width row, and shows only the bank and next stake needed to understand the climb. Schedule explanations and
generic motivational copy stay in the post, not on the graphic. The small chef stays in the header; no image enters
the headline, leg or accounting zones. A completed run shows the clean $50 start for the next climb.

Legacy frame reference (`docs/examples/`); the newer specialized templates above supersede it for new assets:
- top left the **KOOK'N** wordmark and pan icon; top right the precise label (`PLAYER PROP`, `GAME TOTAL`,
  `GAME SPREAD`, `LONGSHOT`, `LOTTO TICKET`, `EASY PROPS`, `PICK OF THE DAY · GAME TOTAL`, `80/20 CLIMB · STEP 2`,
  `RECEIPTS`);
- the matchup and kickoff (a parlay: how many games and the day); `TODAY'S PLATE` (`THE CLIMB: $50 TO $1,000` on a
  rung, `YESTERDAY'S PLATES` on a receipt); the play big; `Served at` the price and book; `We project ...`;
- at the foot `Graded in public, win or lose. keenroudy.com/sports` and `Entertainment only. Not advice.`;
- on the right, the plate: an NFL player's ESPN headshot for a player prop, both teams' logos for a total ("AT"
  between them), the side's logo for a spread, and the chef (`site/kookn-chef.png`, cut out of the profile picture
  `site/kookn.jpg`) for parlays, receipts and house cards.

Colours: the side the play is on, from the slate (ESPN) or `data/team-colors-cfb.json`, with a near-black primary
using its alternate; the kitchen's own navy and mint (`pick_card.HOUSE`: `#08131d`, `#10313a`, `#5eeaa4`) for the
ladder, receipts and house cards. Cream `#f6f1e6` and ink `#141414` for text. Images are ESPN's (headshots
`https://a.espncdn.com/i/headshots/nfl/players/full/<id>.png`, logos `.../teamlogos/nfl/500/<abbr>.png` and
`.../teamlogos/ncaa/500/<id>.png`), fetched when the card is drawn and embedded; a failed fetch falls back to the
chef. `KEENROUDY_CARD_ART=0` turns photos and logos off. No straight-play units on cards; a receipt may show a fun
ticket's 0.25u stake.

The **Save this projection sheet** (`scripts/sheet.py`): a header (`SAVE THIS`, `WEEK 3 NFL PROJECTIONS`, the date), two
columns of compact game cards (logos, our projected score to a tenth, win chances as bars in the teams' colours, and
spread and total comparisons with the exact captured line, odds and book), and the foot. NFL shows the full slate;
college shows the 16 largest projection gaps. A numbered mint ring marks up to four markets where our calibrated
chance clears that real price by the Board's value threshold and names the actual wager (`OVER 45.5`, `MINN +3.5`);
the selected market line and price are mint instead of the model projection. Missing, stale, thin and pass
prices do not get a ring. Rings are watches, not official plays. Moneyline does not
appear until both sides carry real book prices to compare with the projected win chance. The complete college slate
stays on the site.

## Previewing before anything posts

From `~/Projects/sports-dev` (nothing here posts):
- a play's card: `python3 scripts/pick_card.py <pick id>` (writes `~/.config/keenroudy/x-drafts/<id>.png`; `--out
  PATH` elsewhere; `--svg` prints the SVG);
- a play's tweet: `python3 scripts/x_post.py draft <pick id>`;
- what the next run would post, with times: `~/.config/keenroudy/run.sh py scripts/buffer_post.py plan`;
- the sheet: `python3 scripts/sheet.py --league NFL --day 2026-10-04 --out /tmp/sheet.png`;
- the ladder: `~/.config/keenroudy/run.sh py scripts/ladder.py`.

Any change to a post's look or words: update the tests (`tests/test_x_post.py`, `tests/test_pick_card.py`,
`tests/test_receipts.py`), render the cards and look at them, and show the owner before it goes live. New post
types need the owner's yes.

## The site's look

The site (`site/`) uses the same projection-card look as the Games page everywhere: team logos or player photos on
every play and line, stat tiles (price, line, we project, edge), a lotto look for big parlays, the ladder strip and
card, chance bars, form dots. Tabs: Today, Board, Games, Stats, Record, More. Check every change at 375 px wide (no
sideways scroll, no console errors) and bump the asset versions in `site/index.html` (`app.css?v=`, `core.js?v=`,
`app.js?v=`) so phones load the new files.

Each upcoming game detail page also has **Kook'n favorite lines** near the top: every fresh, priced main line the
calibrated Board likes, ranked by edge against the price with line vs projection, book, chance and break-even shown.
Player lines also show exact-line last-ten and season hit rates when the stored game log supports them, labeled as
history rather than a prediction. Readers may choose alternates at their book, but alternates do not replace the main
value line in this list. The reads stay separate from official plays, and the section may honestly be empty when no
price qualifies.
