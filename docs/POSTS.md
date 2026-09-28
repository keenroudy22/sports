# Posts and graphics: everything that goes to X and how it looks

The desk posts to X as **@keenkooks** through **Buffer** (free plan), never by clicking around X. Every post is text
plus, for plays and house posts, an image card. This page is the complete spec: each post's text, its card, when it
goes out, and the code that makes it. Examples of the cards are in `docs/examples/`. What the accounts we follow post
and what gets saved is in `docs/X-NOTES.md`.

## The voice (the owner's rules)

- **Short and human, straight to the point** (2026-09-26: "Not so AI looking. And straight to the point on the
  tweets"). A play is one line with its price and book, then our number in a few words. No labels ("TEAM PROP"), no
  slogans ("Graded in public") and no reason sentences in the tweet; the site keeps the reasons.
- **Every number comes from the pick.** `x_post.guard` refuses a post whose numbers are not in the pick's own fields
  (rounded projections and ladder dollars are allowed as the post writes them). No em or en dashes, no "!", no
  marketing words ("lock", "guaranteed"), no advice ("bet this"), no model names. A post that fails its check is held
  and named in the log and on the phone, never posted.
- **No units on X, ever.** Money and units live on the site only.
- **Every play and fun parlay ends on the ask** `❤️ if you're tailing` (a ladder rung: `❤️ if you're climbing`), then
  `@Playbook` (Action Network's betslip bot, which replies with the bet pre-loaded) and the league tag `#CFB` / `#NFL`.
- **No links in play posts** (X shows linked posts to fewer people); the card carries keenroudy.com/sports. Cashed
  posts carry the original post's X link, which makes them quote it.

## Each post

| Post | When (Eastern) | Text shape | Card | Code |
|---|---|---|---|---|
| **Play** | Around noon; two hours before an earlier kickoff; never before 9 AM; ten minutes apart | `Iowa/Michigan over 38.5 (-105, ESPN BET)` / `We have it at 47.` / ask / tags | the play card | `x_post.draft`, `pick_card.svg` |
| **Pick of the Day** | First in the noon batch | `POTD: ...` then as a play | the play card labelled `PICK OF THE DAY` (`cards/<id>-potd.png`) | `featured.py` |
| **Player prop** | As a play | `Jordan Love under 2.5 carries (-111, DraftKings)` / `We have it at 1.2.` | the player's ESPN headshot on the plate | `pick_card.artwork` |
| **Side** | As a play | `Duke -10 vs Stanford (-110, FanDuel)` / `We have Duke by 14.` | the side's logo | |
| **Lotto / longshot** | After the plays | `🎰 +2506 COLLEGE LOTTO (ESPN BET)` (from +1000; `🎯 +583 NFL LONGSHOT` under it) then one leg a line; fun tickets may mix feed-priced alternates such as `Drake London 40+ rec yds` | parlay card with the legs | `x_post.parlay_head` |
| **Easy props** (alternate lines) | Sat (college) and Sun (NFL) | `🍀 +450 NFL EASY PROPS (FanDuel)` then legs like `Drake London 40+ rec yds` | parlay card | `easy_parlay.py` |
| **80/20 ladder step** | With the plays, one a day when two clean games exist | `🪜 KOOK'N 80/20 LADDER · STEP 2` / `$75 → $146 (+95, FanDuel)` / `$19 banked · win banks $29, $117 rides` / legs / `❤️ if you're climbing` | a tall winding route with the real bank, ride, rung and unpriced future checkpoints | `ladder.py`, `pick_card.ladder_svg` |
| **Conversation prompt** | Once on a multi-play card, after the first play | `First play is out. Who wants the next one? 👀` or one of the short rotating slate questions, then the league tag | none; intentionally text-only | `buffer_post.conversation_text` |
| **Morning receipt** | 9 AM the day after a game day | `Saturday: 5-3` then `✅ Iowa/Michigan over 38.5` per play, `Today: 3 plays.`, tags | the receipt card (W/L per play, the chef) | `receipts.day_receipt`, `with_menu`, `pick_card.receipt_svg` |
| **Week's receipt** | Wednesday 9 AM | `The week (Sep 23 to Sep 29): 12-9` then the record by kind | receipt card | `receipts.week_receipt` |
| **Save this watchlist** | 10 AM college Saturday and NFL Sunday | `📌 4 NFL games where our numbers disagree most with the market.` / save ask / tag | 1080x1350 grid with four large model/market tiles | `sheet.py` |
| **Cashed** | As a win settles (9 AM to 12:30 AM, within three hours) | `✅ Cashed: Iowa/Michigan over 38.5 (-105, ESPN BET)` (or `✅ POTD cashed: ...`, `✅ +2506 5-leg lotto cashed (ESPN BET)`, `✅ 80/20 ladder step 2 cashed: $75 → $146` / `$48 banked. $117 rides step 3.`) then the tag and the original post's link | none (it quotes the original) | `receipts.cashed` |
| **Menu** (alone) | 8:45 AM on a game day with no receipt | `Today: 6 plays` then `Iowa/Michigan 3:30 PM` per game | `site/img/kitchen-menu.png` | `receipts.menu` |
| **The book** | 6 PM on a day with nothing else | `Season through Sep 28: 23-22` then by kind | `site/img/kitchen-book.png` | `receipts.book` |

Limits: twenty posts a day at most, counting what is queued (`buffer_post.MAX_PER_DAY`); ten minutes between any two
posts (`buffer_post.free_slot`). The card must be live on the site before a post is scheduled; a play whose card is
not live waits for the next run (nothing goes out bare).

## The cards (graphics)

Drawn as SVG by `scripts/pick_card.py` and rendered to PNG by headless Chrome (`pick_card.render`), 1200x675, except
the sheet (1080x1350). The hosted build draws them on every deploy (`scripts/feed.py`) into `site/data/cards/`,
served at `https://keenroudy.com/sports/data/cards/<name>.png`: `<pick id>.png`, `<pick id>-potd.png`,
`receipt-day-<date>.png`, `receipt-week-<date>.png`, `sheet-<league>-<date>.png`.

One frame for every card (`docs/examples/`):
- top left the **KOOK'N** wordmark and pan icon; top right the precise label (`PLAYER PROP`, `GAME TOTAL`,
  `GAME SPREAD`, `LONGSHOT`, `LOTTO TICKET`, `EASY PROPS`, `PICK OF THE DAY · GAME TOTAL`, `80/20 LADDER · STEP 2`,
  `RECEIPTS`);
- the matchup and kickoff (a parlay: how many games and the day); `TODAY'S PLATE` (`THE CLIMB: $50 TO $1,000` on a
  rung, `YESTERDAY'S PLATES` on a receipt); the play big; `Served at` the price and book; `We project ...`;
- at the foot `Graded in public, win or lose. keenroudy.com/sports` and `Entertainment only. Not advice.`;
- on the right, the plate: an NFL player's ESPN headshot for a player prop, both teams' logos for a total ("AT"
  between them), the side's logo for a spread, and the chef (`site/kookn-chef.png`, cut out of the profile picture
  `site/kookn.jpg`) for parlays, receipts and house cards.

Colours: the side the play is on, from the slate (ESPN) or `data/team-colors-cfb.json`, with a near-black primary
using its alternate; the kitchen's own brown and orange (`pick_card.HOUSE`: `#2a1c14`, `#3d2a1d`, `#f28c28`) for the
ladder, receipts and house cards. Cream `#f6f1e6` and ink `#141414` for text. Images are ESPN's (headshots
`https://a.espncdn.com/i/headshots/nfl/players/full/<id>.png`, logos `.../teamlogos/nfl/500/<abbr>.png` and
`.../teamlogos/ncaa/500/<id>.png`), fetched when the card is drawn and embedded; a failed fetch falls back to the
chef. `KEENROUDY_CARD_ART=0` turns photos and logos off. No units on any card.

The **Save this watchlist** (`scripts/sheet.py`): a header (`SAVE THIS`, `WEEK 3 NFL WATCHLIST`, the date), two columns
of game cards (logos, our projected score to a tenth, win chances as bars in the teams' colours, and large model/market
spread and total comparisons, orange where our number leans clearly), and the foot. Both sports show the four games
where our number and the line differ most; the complete slate stays on the site.

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
