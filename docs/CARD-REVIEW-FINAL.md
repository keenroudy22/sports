# Felt card review, final (round 12) (Claude, Oct 7, ~6:20 AM ET)

Commit 2e47b238, renders from 05:36.

**Overall: ready-with-nits.**

Ready for the owner to approve the cutover, with a few nits left. I re-checked every reported failure myself. None is a blocker or a major problem on inputs the desk can actually produce today.

What I checked (code archived from 2e47b238 to scratchpad/fin11; the only code change is single_line_ratio .41 → .43 at felt_cards.py:276):

1. **Tests.** The card suites (felt_cards, pick_card, research_art, sheet, receipts, ladder) ran 92 tests: all OK, 1 skipped (the live-render test). The 23 felt tests passed, including the headless-Chrome measurement test, which really ran. That test now covers UNDER 2.5 RECEPTIONS and OVER 22.5 COMPLETIONS with a two-line CFB name and a photo.

2. **Selection widths.** I measured 3,956 selection lines independently in headless Chrome with the embedded Barlow Condensed font. The set covered:
   - all nine market phrasings, including the older "passing attempts" and "rushing attempts";
   - OVER and UNDER at every whole and half line from 0 to 50;
   - yardage lines from 100.5 to 399.5;
   - game totals from 20 to 99.5.

   Only one line crosses x=1016: UNDER 44 COMPLETIONS at 1018.8. No book posts that line, and it sits 2.8px into the 64px margin, so nothing is cut off. The tightest realistic lines are UNDER 24 COMPLETIONS at 1013.8 and UNDER 34 at 1013.5, so .43 leaves about 2px to spare.

3. **Straight spreads.** These are confirmed latent only. run.candidates() turns only "total points" game markets and player props into plays (run.py:630-639), and gates.lean_is_total rejects any other model lean. The last straight spread play was a Sep 19 favorite. Spreads still go into Climb and longshot tickets, but those cards use their own layout.

4. **Brand chip vs photo ring.** Confirmed by pixel sampling of best-bet-player-prop.png. At x=930 the green chip ends at row 113, felt shows only on rows 114-115, and the green ring starts at row 116. At phone size the two look joined. It is cosmetic and no text is affected.

5. **Research ring headroom.** The verifier's measurement leaves only 5.9px between Kamaehu Kopa-Kaawalauole and the ring. It passes today, and the same real-width fix in item 1 below would cover it.

6. **Lifetime $42 on the push/void review cards.** This is only in the review renderer: render_felt_review.py lines 137-140 hard-code it. Production (feed.py:232/244) computes the amount from ladder.saved_through.

7. **Earlier fixes.** Both verifiers confirm they still hold, and I spot-checked four PNGs:
   - receipt: 2-3, SEASON 35-34, FUN 0-3, CLIMB STEP 1 ✗, every miss shown;
   - climb-loss: Willis ✗ in red, Wilson ✓, $0 this Climb, $42 all Climbs;
   - research: ring clear, 8 hit / 2 missed;
   - 13-game Oct 11 sheet: all 13 tiles inside the card with no overflow.

   The two verifiers checked the rest of these fixes in detail:
   - season strip at least 14px below the ticket;
   - no text pixels inside the photo ring for the four long CFB names;
   - Climb NOW/AGAIN clear of the flag pole;
   - long CFB matchups inside 1016;
   - text contrast meets AA;
   - naming, 21+ line and one-record rules.

No must-fix items remain.

## Must fix

## Follow-ups (not blocking)
- Replace the character-count width estimate with the embedded TTF's real cmap/hmtx advances plus letter spacing, and check every returned line against x=1016. This is the durable fix already noted in docs/LESSONS.md. It removes the roughly 2px squeeze on 'UNDER NN COMPLETIONS' (UNDER 44 reaches 1018.8 and UNDER 40 reaches 1015.4). It keeps the 37 realistic selections that now wrap needlessly on one line, such as OVER 22.5 COMPLETIONS. It also widens the 5.9px research-title clearance from the photo ring.
- Fix and test straight spreads before they can return as plays. With the current estimate, wide single-word school names overflow. Examples: 'CHARLESTON SOUTHERN' reaches about 1096 at 120px, 'WESTERN KENTUCKY +13.5' about 1089, and 'MASSACHUSETTS +21.5' about 1028. Add a browser test that uses the longest stored school names.
- Brand chip vs photo ring: only 2px of felt separates them (rows 114-115 at x=930), so on every photo card the green chip and green ring look joined at phone size. Move the photo center down about 8-10px (or the chip up), then rerun the ring-ink and season-strip tests.
- render_felt_review.py hard-codes _allClimbsBanked=42 on the hypothetical Climb #1 Step 2 push/void cards, which show THIS CLIMB $19. Derive the value from the fixture's own state so the review images agree with each other. Production already uses ladder.saved_through.
- Pre-existing cosmetics, unchanged since round 10:
- climb-open places 'ALL CLIMBS' at a fixed x=442, leaving about an 85px gap, with the '·' attached to the second phrase.
- receipt-six-best-bets: '+1 BEST BET ✓' sits about 4px under the last row.
- Minus signs are mixed: an ASCII hyphen for the line and U+2212 for the price on the sheet, and '-107 DK' on research.
- The research rank '32nd of 235' counts FCS teams in the denominator.
- The felt_cards docstring sets a 40px minimum text size, but the accepted dense Save-this sheet uses 15-23px. Update the docstring to say so.
