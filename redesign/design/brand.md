# Kook'n brand guide

## Name and voice

- **Name:** "Kook'n" (wordmark KOOK'N, with SPORTS under it). "Best bets" = the daily official plays.
- **Voice:** a sharp friend at the sportsbook counter. Plain words, short sentences, the number first, honest about
  misses.
- **Never:** "lock", "guaranteed", "can't lose", "risk-free", "!". Never advice. Never imply that a historical hit
  rate is a probability.
- **Always:** the price and the book, our chance against what the price needs, and "graded in public, win or lose".
  21+ and 1-800-MY-RESET in footers.

## Logo

- **Mark:** a winning ticket. Chalk ticket, felt-night "K", a small tilted chef hat on the top-left corner, and a
  green stub with a white ✓ behind a perforation. Files: `brand/kookn-mark.svg` (on felt) and
  `kookn-mark-clear.svg`.
- **Wordmark:** KOOK'N in chalk, drawn as paths so it needs no font, with a green flame apostrophe and SPORTS
  letterspaced in green. Files: `kookn-wordmark.svg`, plus `kookn-wordmark-light-bg.svg` for light backgrounds.
- **Lockups:** `kookn-lockup-horizontal.svg` and `kookn-lockup-stacked.svg`, with PNG exports in `brand/png/`.
- **Clear space:** at least the height of the chef hat on all sides. Minimum size: 24 px tall for the mark, 96 px
  wide for the wordmark.
- **Never:** recolor the stub red (red means a miss), outline it, stretch it, or put it on a busy photo.
- **The 3D chef** stays as a personality character (empty states, Discord, celebrations), not the logo.

## Color: casino felt

| Token | Hex | Use |
|---|---|---|
| `--felt-night` | #07120D | page |
| `--felt` | #0E2219 | cards |
| `--felt-raised` | #15301F | hover, raised controls |
| `--line` / `--line-strong` | #21412F / #3D7356 | dividers / input borders |
| `--chalk` | #F2F7F4 | text (15.4:1 on felt) |
| `--dim` | #A9C0B3 | secondary text (8.6:1) |
| `--kookd` | #20C774 | brand + hit (7.5:1); dark ink #062B1C on green fills |
| `--burnt` | #F2414E | miss fills and icons only (4.47:1 fails for small text) |
| `--burnt-text` | #FF6B75 | red text (6.0:1) |
| ticket paper / ink | #F2F7F4 / #07120D | best-bet tickets |

Why this palette:
- props.cash (#0F0F0F + #27DA8E) and Outlier (#0E0E0E + #5DFFB1) both sit in green-on-black. The deep felt base
  reads as a betting table and is ours.
- Green and red keep their meaning: hit and miss, always with ✓ / ✗ and a word.
- Brown, tan and amber stay banned.

## Type

- **Display:** Barlow Condensed 600/700, for headlines, numbers on tickets and card hooks.
- **Body:** DM Sans 400–700.
- **Site floors:** body 16 px, meta 14 px, labels 13 px.
- **Card floors** (1080 wide): hero 96, hook 64, numbers 56, rows 40, labels 30, footer 26.
- **Production cards:** embed the OFL fonts as base64, because CI renders on Ubuntu.

## Results

| State | Look | Words |
|---|---|---|
| Hit | green ticket stub, ✓ | "Hit" (optional flavor: "Kook'd") |
| Miss | red ticket stub, ✗ | "Miss" (optional flavor: "Burnt") |
| Push / void | gray stub, – | "Push" / "Void" |
| Open best bet | green stub with our chance | "54% our chance" |
| Posted price is old (quote past its freshness limit) | gray stub with our chance | "Old price" / "Posted price may be gone", plus "still graded at −110 (DraftKings)". Never "Price expired". |
| Closed to new entries, pulled, withdrawn, in play | gray stub | "Closed to new entries" / "Pulled before posting" / "Withdrawn" / "In play", with the desk's entry note. No pitch, no meter. |
