# Owner-approved X style: "their energy, plus the whole record" (2026-10-07)

> **Updated Oct 7, later the same day:** where POSTING-PLAYBOOK.md v3 differs from this file, the playbook wins. That covers captions keeping the "I have it at 47." shape, Final/Leftovers replacing Leftovers-only, no dashes, Prep List thresholds, Discord routing, and the chef as the existing clay chef.

On Oct 7 the owner approved this direction in Claude's chat ("Yes to the twist").
- Record it as a dated owner rule.
- Build it after P0, together with P1-11 (the Dans AI borrowings).
- Where it conflicts with VOICE.md's DON'T list or the "no '!'" line in POSTS.md, this wins, but only within the limits below.
- Evidence:
  - `docs/X-NOTES.md` (Cody Brown);
  - `X-NOTES-dans-ai.md`;
  - `X-NOTES-harry.md`;
  - `X-STYLE-RESEARCH.json` (avatar survey plus our own post numbers).
- The short version: Cody, Dan and Harry win on a person's voice, named series and win moments. They show only wins and sell a paid trial. Kook'n is free and shows every miss, and that is the personality.

## 1. Named kitchen series

These are labels inside existing categories. There is no new post type, slot, cap, frequency or selection change.

| Series | Category it renames | Example opening |
|---|---|---|
| Hot Plate | POTD | `🍳 Hot Plate (POTD): Roman Wilson over 19.5 rec yds (-104, FanDuel)` |
| Chef's Special | Weekend lotto/longshot | `🎰 Chef's Special: +2194 college lotto (FanDuel)` |
| The 80/20 Climb | Climb steps (unchanged name) | Steps end with `Still climbing? ❤️` |
| Prep List | Every-game list (P1-11 item 1) | `📋 Prep List: hit in every game this season` (main lines, N/N only, 5+ games) |
| Burnt | Misses, in receipts and results | `Burnt 🔥 Kincaid over 3.5 rec, finished 2. Missed by 1.5.` |
| Leftovers | 9 AM receipt | `Leftovers from Sunday: 3-2` then every play, wins and misses with equal weight |

Keep "POTD" visible so people still recognize it.

## 2. The cook's voice

- **"I" replaces "we" in automated captions** ("I have it at 54%").
- **No invented personal moments.** Never write that the owner is at a game, watching or feeling something about a play. Only the owner's own hand posts do that.
- **One "!" is allowed on:**
  - cashed posts;
  - a Climb step that cashed;
  - the wins line of a receipt.

  Never on a pick, never on two posts in a row. Extend `x_post.guard` narrowly and add tests.
- **Cashed posts may open with one short reaction** from an approved rotating list: `Cooked.`, `Plated.`, `Out of the oven.`, `That one's done.` Never repeat the previous reaction.
- **Still banned:**
  - guarantees: "lock", "free money", "easy", "can't lose", "this goes 15-0";
  - like-to-unlock, holding a pick hostage, "last chance", "turn on notifications".

## 3. Win moments and payouts

- **Cashed posts get a felt win card** (green ✓) inside the existing cashed category.
  - Claude reviews the sample render before the first post (P21 gate).
  - Receipts keep misses at equal weight as red ✗ "Burnt" rows.
- **Payout lines:** fun tickets, Chef's Special, longshots and Climb steps may show `$10 → $230`.
  - Compute it only from the captured price at publication.
  - Label it as the payout at the posted price.
  - Never show a payout on a straight play: still no units or dollars for straight plays on X.

## 4. Face and avatar

- The owner chose a cartoon of themself in a chef hat for the X avatar. Claude is producing it with the owner. The owner sets it, or Claude uploads it once while the owner is present.
- P0-3 (the Discord bot avatar): ship the ticket mark now. Switch to the cartoon once it exists.

## 5. Process

1. Render samples of every changed caption and card. Claude reviews them before the first live post.
2. Add tests in `tests/test_voice.py` and the x_post guard tests: the allowed "!" placement, the banned phrases, payout only on tickets and Climb, and no invented personal moments.
3. Judge it after 4 weeks on likes and replies per view and on follows, not on views. Report it in the Monday review.

## Not approved

- Paid or VIP pitches, giveaways, affiliate links and blurred picks.
- Wins-only posting.
- Same-player escalators (no-stacking rule).
- Automated live sweats on X (the pilot gate is unchanged).
- More posts per day, or a new slot.
