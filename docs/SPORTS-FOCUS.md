# Owner decision, 2026-10-07: three sports, all year

The owner asked for focus: football, basketball and soccer, covering every month. Claude recommended it as the realistic plan, and the owner told Claude to give it to Codex.
- Record it as a dated owner rule.
- It replaces the **Order** line and the NHL-first milestones in `MULTI-SPORT-PLAN.md` and work order P2.
- Everything else in that plan still applies: free ESPN data only, zero Odds API, SharpAPI or SportsGameOdds requests outside football, exact-milestone price matching, append-only stores, guard entries per file family, `leagues.OFFICIAL == {'NFL','CFB'}`, and the P11 gate for best bets.

## The three sports

| Sport | Leagues | Season | Role |
|---|---|---|---|
| Football | NFL, college football | Aug to Feb | The only sport with best bets, the Climb and fun tickets (unchanged) |
| Basketball | NBA, then men's college basketball, then WNBA in summer | NBA Oct 20 to June; college Nov to April (March Madness); WNBA May to Sept | Research and posts; trial projections stay silent until a P11 packet |
| Soccer | Premier League and Champions League, then MLS in summer | EPL Aug to May (UCL Tue/Wed nights); MLS late Feb to Nov | Research and posts; mostly team level (form, goals, totals, both teams to score) unless ESPN shows priced player boards |

- **Every month is covered.** July is the thin month (WNBA and MLS only), so post less then rather than adding a sport.
- **Champions League** plays Tuesday and Wednesday nights, exactly where our X feed is quietest (1–2 posts).

## Build order

1. **Finish P0 and P1 first.** That includes the X twist.
2. **NBA, ready by opening night (Tue Oct 20).**
   - Build the M1/M2 machinery (sport_box, prop boards, player charts, Today, slate card) for **NBA first** instead of NHL.
   - Trend boards on X start once players have 5 current-season games, around Oct 28 to Nov 1.
   - Until then, website charts may use the labeled last-season window.
3. **Soccer from the next Premier League weekend you can do well (aim for Oct 24–25, not Oct 17).**
   - Start with EPL slate cards and team trends, then add Champions League midweek.
   - First save one EPL fixture that proves ESPN's priced board, as the plan already says. If player props aren't there, keep to team markets and say so.
4. **College basketball** for the season opener in early November. Same machinery as NBA, with the existing CBB paper trial.
5. **Summer:** WNBA and MLS reuse the basketball and soccer code.

## NHL and MLB

- **No new build work.** Keep what already exists (scores, market_lab line captures, the `#lab` status) exactly as it is, so nothing breaks and no history is lost.
- Remove NHL from the M1/M2 milestones, `RESEARCH_LEAGUES`, `SPORT_PAGES` and the prop-board priority list.
- Don't build NHL or MLB player pages, trend boards or posts.
- Revisit MLB before Opening Day 2027, only if July looks too quiet.

## Posting

- Use the existing P2 caps (3 a day Monday to Friday, 2 on Saturday and Sunday, 1 per league). These posts are dropped first under the Buffer 10-slot and daily caps.
- League name first.
- Research label, no @Playbook, never in the record.
- Claude reviews the first sample card of each new category before its first post.

## Why this is the realistic plan

- **Half the work.** Last night's four live regressions came from big multi-surface releases. Seven leagues at once would multiply that.
- **The free plans hold.** Only ESPN is used outside football, and Buffer's 10-slot queue stays reserved for best bets first.
- **The biggest audiences.** Basketball (NBA, March Madness) and soccer are where betting X accounts get the most attention outside football. Harry runs NFL plus soccer, and Cody and Dan rotate NBA in.
- **The record stays clean.** Backtests show no basketball or soccer edge at the close, so those sports bring attention through research and stay out of the record until a trial earns it.
