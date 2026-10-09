# Kook'n voice

## Current authority (owner, 2026-10-09)

`docs/KOOKN-PLAN.md` supersedes every older example below where they differ. Public captions use only the exact
shapes and word banks in `data/voice/pools.json`; code fills their fields and the local model may select a template
ID but may not write public copy. `scripts/voice.py` holds the full caption/Discord kill list and every send path
must fail closed when it finds a banned word, private publishing detail, bare athlete ID, duplicated token or banned
punctuation. Results name the role stat that explains the outcome. New public copy says “catches,” not
“receptions,” and never explains the automation behind the post.

Every writer, person or model, reads this before touching a user-visible word.

WHO IS TALKING
One sharp friend who bets. Sends you the bet, the price and one good reason, then stops. Owns a miss in one line. Never sells, never lectures, never explains how the system works.

DO
1. Lead with the bet: player or team, line, price, book. Then our number. Then one reason, only if it's a good one. Example: "Roman Wilson over 19.5 rec yds (-104, FanDuel). We have it at 43."
2. Say numbers the way people say them: "We make it 58%. The price needs 52%." "We're 7 points off the market."
3. Add one caveat, and only when it changes the read: "Only 3 games of history." "College injury news is thin."
4. Give misses the same room as hits, with no speech after: "Falcons/Saints under 48 missed. Final: Falcons 45, Saints 24."
5. Use the shorthand bettors use: rec yds, ML, dog, cashed, sweat, off the card, counts at -110, good to -115, line moved.
6. Give every recurring automated line 2 to 4 approved variants. Pick one by date and log it as copyVariant.
7. Use at most one kitchen nod per post.
8. Say each required thing once, where it belongs. The page footer carries 21+, entertainment only and the helpline. Every card carries "21+ · Entertainment only". The Record page explains grading.

DON'T
- Repeat a disclaimer in the section note, the row and the footer. Use at most one "not a best bet" per screen, and only where research sits next to picks.
- Talk about our own honesty: "honest", "NO HIDING", "We never force a play", "An empty list beats a forced one", "That keeps the chance honest". The record proves it; saying it reads like an ad.
- Explain the plumbing: captured, reference line, Provider-listed, "No football data is substituted", hosted refreshes, desk runs, "the owner", "a person settles", Illustrative.
- Stack hedges ("a window, not a promise" plus "never guaranteed"). Pick one.
- Use model-speak in the main views: raw curve, shrunk, calibrated, uncalibrated, middle estimate, "record against the close". The "How we got X%" fold explains the method once, in plain words.
- Use AI or SaaS words: insights, leverage, robust, seamless, comprehensive, unlock, elevate, delve, crucial, empower, game-changer, dive in, "not just X but Y", "Here's".
- Use em or en dashes as punctuation. Records like 35–35 and minus signs are fine.
- Use "!", except the approved live-progress "Come on!".
- Use rhythmic triplets or mirrored slogans ("5 LEGS. ONE TICKET.").
- Chain 4 or more middle dots. Write a sentence or cut the weakest item.
- Imitate the owner's hand-posted hype (YESSIR, THE MODEL COOKED) in automated text.
- Invent a person. Write "Notes", not "Analyst notes". Never draft first-person history for the owner.

SWAPS
middle estimate -> our average / we project X on average
captured, reference line -> seen / line (no price yet)
Closed to new entries -> off the card
graded at X, the price we posted -> counts at X
Old price · check your book -> Good to X · latest we saw Y
release window -> usually drops around
Provider-listed injuries -> ESPN's injury list
paper trial -> testing, no picks yet
official play / official card -> best bet
Ladder (public) -> 80/20 Climb
plate, Served at, desk -> delete

RULES THAT HOLD COPY IN PLACE
- Every number comes from a code field, never from a model.
- Code parses some stored text, so keep these markers exactly: "before its post went out", " ET: ", ". Published cutoff", ". Stays in the record". Also keep the Model lean, Prop lean, Researched pick, Role:, Defense: and "Last N games:" prefixes, which x_post.LEAD_INS and the app.js WHY regexes depend on.
- Published records are append-only. Change the templates for future picks, and fix old text only at display time.
- The owner's October 7 decision replaces the older Climb waiting phrase: say `not posted yet` until a rung is actually posted. Keep the heart `if you're tailing` closer and the verified injury-angle closer.
- tests/test_voice.py enforces this list. Whenever the owner reacts to a word or post, add a dated line here and extend the test.

## String replacements to apply

- **scripts/buffer_post.py:53 (CONVERSATION; went out on X 2026-10-03)**
  - old: `One play down. Props, sides or totals—what are you looking at?`
  - new: `One down. Props, sides or totals for you today?`
- **scripts/receipts.py:553-554 (weekend Climb check-in X post)**
  - old: `\nTicket scans: 10 AM, 1:30 PM, 4 PM and 8 PM ET, plus the regular desk runs. + \nDiscord gets a qualifying ticket first; X follows about 10-15 minutes later. No forced step.`
  - new: `\nWe look for one at 10, 1:30, 4 and 8 ET. If it qualifies, Discord sees it first.`
- **scripts/receipts.py:247 and :274 (receipt card label)**
  - old: `YESTERDAY’S PLATES / THIS WEEK’S PLATES`
  - new: `YESTERDAY / LAST 7 DAYS`
- **scripts/pick_card.py:609, 680, 773, 853, 1028 and 924 (legacy card footers, new renders only)**
  - old: `Entertainment only. Not advice.  (and at 924: Entertainment only. Not advice. Verify current prices.)`
  - new: `21+ · Entertainment only  (and at 924: 21+ · Entertainment only · Prices move)`
- **scripts/research_art.py:88 (research card footer)**
  - old: `DATA + CONTEXT`
  - new: `21+ · Entertainment only`
- **scripts/market_read.py:~133 (game-page market read, shows '82th', '1th')**
  - old: `Our {word} gap of {abs(g['gap']):g} points is at the {g['percentile']}th percentile of the model's gaps; gaps this large went {w}-{l} against the close in {g['n']} graded games.`
  - new: `Our {word} is {abs(g['gap']):g} points off, bigger than {g['percentile']}% of our past gaps. Gaps this size went {w}-{l} against the close in {g['n']} games.`
- **scripts/run.py:1182 (prop defense rank; CFB table must be FBS-only)**
  - old: `{row['rank']} of {len(table)} this season (1 is stingiest).`
  - new: `{ordinal(row['rank'])}-stingiest of {len(table)} this season.`
- **scripts/run.py:1184 (still matches app.js /against this side/)**
  - old: `The opponent's positional allowance points against this side. It covers the whole position group, not just this player.`
  - new: `The defense leans against this side (that's the whole position group, not just him).`
- **scripts/run.py:1329-1332 (model-lean why, future picks only)**
  - old: `Model lean, published on our number alone. Our total is {proj} against {line}: the {side} reads {chance}% after the raw {raw}% is shrunk by the model's record against the close, {edge:+.1f} points clear of the {be}% that {odds} needs.`
  - new: `Model lean, our number only. We have the total at {proj}; the book is at {line}. That makes the {side} {chance}%, and {odds} needs {be}%.`
- **scripts/run.py:1341-1342 (model-lean risk; also drop 'Confidence {c} of 10.' at :1300)**
  - old: `It rests on the model alone, and the closing line beats our number on average, so a gap this size is more often our error than the market's. {sparse}Confidence {c} of 10.`
  - new: `It's our number against the market's, and the closing line usually beats ours, so a gap this big often means we're missing something. {sparse}`
- **scripts/receipts.py result_detail (display-time only; stored settlements unchanged)**
  - old: `· Final: Marvin Harrison Jr.: 1 receptions  /  · Final: all 2 legs won`
  - new: `· had 1  /  · both legs hit`
- **scripts/receipts.py:~509-511 (Climb loss post)**
  - old: `{bank} stays banked. Climb {n} restarts at {start}. + That’s why we bank 20%: one miss can’t take it back.`
  - new: `{bank} stays banked. Climb {n} starts at {start}.  (print the bank clause only when banked > 0; drop the moral line)`
- **site/app.js:~832-833 (Today hero, empty state)**
  - old: `Free daily picks with the price, the book and our honest chance. / ${esc(reason)}. We never force a play. ${esc(nextWindow)} That's a window, not a promise. <a href="#research">See the research board →</a> · <a href="#schedule">Release schedule</a>`
  - new: `Free picks, each with the price and the chance we give it. / ${esc(reason)}. ${esc(nextWindow)} <a href="#research">Browse the research →</a>`
- **site/app.js:~852 (Today research empty state)**
  - old: `No current, priced research line clears our value bar. The board stays empty instead of filling space.`
  - new: `Nothing on the board is worth the current price. Check back closer to kickoff.`
- **site/app.js:~135 (How we got X%)**
  - old: `Our raw model runs hot in this market, so we discount it heavily. That keeps the chance honest.`
  - new: `Our model runs hot in this market, so we cut it down hard.`
- **site/app.js:~159-169 (ticket status, 3 places)**
  - old: `Closed to new entries`
  - new: `Off the card`
- **site/app.js:~1114, 1567, 1807 (estimate labels; the number is a mean)**
  - old: `Our middle estimate for this game: ${…}. We shrink it before showing a chance. / Our middle estimate is ${…} against the ${…} line. / Our middle estimate`
  - new: `We project ${…} on average for this game. / We project ${…} on average; the line is ${…}. / Our average`
- **site/app.js:~981 and ~1713 (injury notes)**
  - old: `Provider-listed injuries and status changes, newest first. / Provider-listed injuries. Verify the latest availability before relying on a projection.`
  - new: `ESPN's injury list and status changes, newest first. / ESPN's injury list. Check the latest before you lean on a projection.`
- **site/app.js:~2048 (Record › Model)**
  - old: `Honest read: the line was the closer forecast in ${closer} of ${markets.length} markets. That is why we shrink our raw numbers before showing a chance.`
  - new: `The book's line beat our projection in ${closer} of ${markets.length} markets. That's why we cut our raw numbers down before showing a chance.`
- **site/app.js (5 places: Research, Games, Record notes for other sports)**
  - old: `No football data is substituted.`
  - new: `(delete the sentence; keep the link that follows)`
- **site/app.js:~1321 (Research › News)**
  - old: `Analyst notes`
  - new: `Notes`
- **site/core.js:484 (college gap caution; has an em dash)**
  - old: `Large model / market gap. College schedule strength, blowouts and changing roles can distort this estimate—not an automatic edge.`
  - new: `We're 7+ points off the market here. In college that often means our number is missing something: weak schedules, blowouts, depth changes.`
- **site/core.js:836 (delivery label on every ticket)**
  - old: `On the website · social delivery not yet confirmed`
  - new: `On the site · X not confirmed yet`
- **site/index.html:42 (global footer; bump asset versions)**
  - old: `<b>For entertainment only.</b> Nothing here is betting advice or a guarantee. 21+ where legal. Gambling problem? Call <b>1-800-MY-RESET</b> (1-800-697-3738) or 1-800-522-4700. Every best bet is graded at the price and book we posted. Fun tickets and the 80/20 Climb are tracked separately. Times are Eastern.`
  - new: `<b>21+ where legal. For entertainment only.</b> Not betting advice, and nothing here is guaranteed. Gambling problem? Call <b>1-800-MY-RESET</b> (1-800-697-3738) or 1-800-522-4700. Times are Eastern.`
- **scripts/research_posts.py:102, 104, 111 (research captions, the growth slot)**
  - old: `Model {m}% | market {k}%`
  - new: `We give them {m}%. The price says {k}%.`
