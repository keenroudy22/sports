# X playbook for @keenkooks

Inside the existing rules:
- Buffer only, no automated replies, likes or follows.
- At most 20 posts a day, 10 minutes apart.
- One hashtag and one call to action per post; `@Playbook` only on new plays.
- No units on straight plays.
- Plays are never chosen for engagement. Packaging and timing can change; which plays exist cannot.

## Where it stands (2026-10-06)

- **Audience:** 77 followers after 621 posts (since Feb 2024).
- **Last 7 days:** 7.4K impressions, 1.1% engagement, 29 profile visits, net follows about flat.
- **Median impressions by format** (Buffer 48-hour metrics, `data/x-posted.json`, 58 measured posts):

  | Format | Median impressions |
  |---|---|
  | Tickets / longshots | 485 |
  | Climb steps | 180 |
  | Straight plays | 136 |
  | Research cards | 88 |
  | Cashed posts | 63 |
  | Receipts | 61 |
  | Morning menu | 58 |
  | Sheets | 40 |

  Only straights and receipts have reached the 8-post minimum.
- **What the bigger accounts do** (`docs/X-NOTES.md`): lottos lead; "save this" sheets get saves; multi-day
  challenges bring people back; a teaser before the drop; receipts; one clear ask.

The account already has the formats. What's missing is legibility, proof, rhythm and community work.

## 1. Profile

- **Banner:** `redesign/brand/png/x-banner-1500x500.png`. Felt background, the ticket mark, KOOK'N SPORTS, "Every
  play graded in public". The content sits clear of the avatar and of mobile cropping.
- **Bio** (live since 2026-10-06, 152/160):
  > Free CFB + NFL best bets with the price, the book and our chance. Graded in public, win or lose. Discord first. Entertainment only. 21+ · 1-800-MY-RESET
- **Pinned post:** a monthly "Start here" card that shows the season record, what you get (best bets, research
  board, Climb) and the Discord link in the reply. Re-pin after a big hit only if it's still the honest picture.
- **Avatar:** the owner's call. The ticket mark (`png/x-avatar-400.png`) reads at small sizes. The 3D chef has
  personality. A reasonable test is the ticket mark for 4 weeks while watching profile-visit rate.

## 2. Cards (templates in `cards.py`, samples in `samples/`)

- **Size and type:** 1080×1350. One hook line first. Nothing that has to be read is smaller than 40px.
- **Play card:** the selection large and green, price + book, "We make it 54%. Price needs 51%." with a meter, fair
  price, edge, and the season record strip.
- **Receipt:** big W–L for the day, green ✓ / red ✗ tickets, and "the misses stay on the record".
- **Fun ticket:** odds-first hook, legs as rows, "tracked apart from best bets".
- **Climb:** "$50 → $79", the legs, and the $50 → $1,000 progress bar. Facts only.
- **Research:** a hit-rate bar chart against the line, "4 of 4 this season · price needs 54%", and "history, not a
  probability".
- **Art:** player photo on props, team logos on game lines (team-color chips if an image is missing).

## 3. Daily rhythm (ceilings, not quotas)

| Day | Sequence (ET) | Ceiling |
|---|---|---|
| CFB Saturday / NFL Sunday | 9:00 receipt (+ menu only if plays are approved) · 10:00 Save-this sheet · 10:30 one research card · plays at noon or kickoff−2h, POTD first · tickets · Climb step · at most 1 injury angle · cashed posts only for POTD, tickets and Climb (other wins roll into the next morning's receipt) | 12 (was up to 17) |
| Mon / Thu NFL nights | receipt · 1 play · at most 1 injury angle · cashed POTD | 5 |
| Tue / Wed / Fri | receipt (weekly recap on Wednesday) · a qualified CFB weeknight play · the 6 PM season-record card only as a fallback | 3 |

Why fewer posts: at 77 followers, ten posts with about zero likes each teach the algorithm the account is low
engagement. Fewer, stronger cards get more reach per post.

## 4. Captions (keep the `x_post.draft` shapes)

- Line 1 is the hook: the play and price, or `+582 NFL LONGSHOT`, or `MONDAY 0-1`.
- Line 2 is the one reason (from `data/x-reasons.json`), or `Season: 35-35` on receipts.
- One ask: `❤️ if you're tailing`, or for sheets, `Bookmark this for Saturday`.
- One tag (`#CFB` or `#NFL`); `@Playbook` only on new plays. No links in the post; the link goes in the reply.
- No em or en dashes, no "!", no "lock" or "guaranteed".

## 5. The owner's 25 minutes a day (by hand, never automated)

- **9:15:** five genuinely useful replies on bigger betting accounts' threads, with a number or angle and no links.
- **12:30:** answer every reply on your own posts.
- **During games:** two or three live reactions of your own ("9 to go. Come on.").
- **Evening:** quote-post a follower's winning slip, with their permission.

## 6. Measurement

- **Weekly, per format:** n, median impressions, engagement rate. Extend `review.post_metrics` (L193) and
  `review.packet` (L304).
- **Profile visits and follows per 1,000 impressions:** Buffer doesn't provide these. The owner downloads X's
  analytics CSV by hand into `~/.config/keenroudy/x-analytics/`, matched by tweet ID. This is a new metrics input, so
  the owner decides.
- **Rules:** keep a format that beats the 4-week average on profile visits or follows. Rewrite it after 8 attempts
  below average. Under 8 posts is "insufficient", per GROWTH.md.
- **Targets (GROWTH.md):** 25K weekly impressions → 1% profile visits → 10% of those follow.
