# October 2 audit implementation

Owner approved implementation on October 2, 2026. This is the release checklist, not a claim that every phase
of the audit is finished. Free service ceilings and the append-only public record remain mandatory.

**Current work:** the October 5 product plan and effective navigation supersede older layout descriptions here.
See `PRODUCT-IMPLEMENTATION.md` for its staged release tracker, `SOURCE-RIGHTS.md` for unresolved commercial
permissions, and AGENTS.md for the effective operating rules. Earlier release descriptions below are history.

## Third release: confidence order and explained upsets

- Every fresh, calibrated value read can be compared by confidence without hiding the separate value ordering.
  Confidence is the calibrated chance to win; value is how far that chance clears the price. The current view labels
  only its top five confidence reads and offers an explicit confidence sort. No thin, stale, unpriced or
  uncalibrated row is ranked, and no rank is called a lock. Performance cautions use a higher value threshold.
- Upset Watch ranks fresh outright candidates by the raw winner disagreement and exposes the reasons behind the
  signal: projected score, model-versus-spread gap and only the offense/defense rating drivers stored in that exact
  forecast. Large line movement and college schedule/role uncertainty are shown as warnings.
- The existing optional Underdog Watch graphic uses the same projected score and spread gap. This does not promote
  moneyline wagering, change model weights, add a feed call or turn the watch into an official play.

## First release: safeguards and the picks-first Board

- Hard refusal of negative calibrated value / missing prop calibration / stale new straight plays. The October 4
  policy replaced performance-only pauses with higher thresholds. A favorite or researched label is not a bypass.
  Daily card sizes are maximums.
- Shared learned prop arithmetic for quote shopping, gates, generated explanations and priced Board rows.
  Raw candidate screening remains recorded separately. New reports freeze probability inputs; old reports stand.
- Combined fun-ticket prices are explicitly estimated in new data; freshness uses the oldest leg.
- Complete research reports compared against the trusted pre-push Git revision in CI, supplementing the original
  field ledger. No ledger replacement and no historical report edits.
- Board leads with today's official plays; future plays and overdue settlements are separate disclosures.
  Five navigation items; old links preserved. Expired quotes remain expired. Game favorites precede model tiles.
- Projection gap distinguished from price edge; large college spread disagreements flagged without retuning.
- Headline accounting split, with all outcomes retained. At verification time: combined legacy straight record
  29–28, 1 void, −0.69u. Captured-price subset 15–17, −2.86u before 1u promotional stake credit; historical assumed
  subset 14–11, 1 void, +1.17u at assumed prices. The split is presentation, not a regrade. Detailed legacy
  totals remain available and explicitly explain their assumptions.
- Midnight/mint/cyan styling, clearer small-screen tiles and favorite-line spacing. No new services or polling.

## Second release: research clarity and reliability

- Market-grouped game favorites reuse the existing shared priced-line payload. Explicit unsupported ML value,
  team-total and alternate-streak states prevent empty data from looking like a recommendation.
- Per-field role-usage completeness and observed denominators; missing red-zone data remains unknown.
- Upset Watch uses two same-book moneylines from existing free ESPN captures, fresh quote/forecast checks and a
  raw-model warning. No automatic ML play. Missing coverage gives no watch.
- Matchup Menu requires fresh priced favorites, five historical games and an 80% historical hit rate; it never
  truncates a window to manufacture 100%. End-zone research reports opportunities, not probabilities, with
  explicit role-forecast age and incomplete CFB injury coverage.
- Complete append-only JSONL and market-capture preservation against the trusted base; no ledger replacement.
- Component source-age/fallback labels; existing heartbeat failure-change/recovery notifications.
- Captured/assumed/promo accounting on detailed record and future receipts. No regrading.
- Offline college model variants and game/week-blocked comparisons saved in `audit-evaluation-2026-10-02.json`.
  Blowout downweighting worsened margin error in both seasons; other variants show no convincing overall gain.
  Keep released weights. This is retrospective comparative evidence, not a fresh untouched holdout.
- Shared fail-closed Odds API gate across main odds, props and NFL alternates. Verify 500-credit allowance and
  reserve before metered calls; no quota increase. SportsGameOdds retains its existing independent guard.
- Local synthetic evidence benchmark: Qwen 27B passed 4/4; Ollama 8B timed out on 3/4 (45-second cap). Tiny test,
  not a quality guarantee or a test of the optional MLX runtime. Keep current routing and template-first prose.
- Original research families generated from real site data in navy/mint/cyan/violet. On October 2 the owner approved
  one optional public research card per slate. Outright and spread underdogs are kept separate; Matchup Menu and
  End-zone Work are evidence-only fallbacks. The generic Week of Football preview remains unqueued.

## Remaining staged work — not enabled by the second release

1. Broader line-payload consolidation and per-component operational alerting beyond the current heartbeat checks.
   Source-age labels already exist, but are not a complete per-provider health monitor.
2. Prospective model shadow evaluation and independently validated FBS/FCS membership labels. The evaluation
   report explicitly labels its prior-season coverage heuristic; it is not official membership data.
3. Validated priced team totals, touchdown probabilities and alternate-line streak sheets need evidence not
   currently available; do not hand-tune to named players or overwrite current forecasts.
4. The live tracked-game worker began in shadow: one shared free ESPN source fetch per game, four-minute
   minimum cadence, eight-game cap, source age, transition deduplication, corrections and final reconciliation.
   October 5 approved a bounded Discord progress pilot with the local model selecting exact supplied facts.
   See `LIVE-PROGRESS.md` for current attempt limits and evidence. X remains off until its separate release decision;
   this product implementation does not activate it. No paid-odds call per tick.
5. Measure the newly released research graphic experiment. The manual mentions workflow is
   documented in GROWTH.md; there is no automatic inbox/reply worker. Age-matched analytics remain an operational
   collection step, not an implemented new analytics feed. No automated likes, follows, unsolicited replies,
   trend-chasing or engagement purchases. X's automation
   rules require prior written approval for an AI reply bot: https://help.x.com/en/rules-and-policies/x-automation
6. Cross-service quota reporting beyond the new shared Odds API guard. NBA/CBB remain paper-only; other sports retain existing
   factual coverage/capture status. Public market promotion needs prospective evidence and owner sign-off.
7. Season futures now have the tested append-only paper quote/settlement ledger in `scripts/futures_store.py`.
   Exact source collection and sport-specific preseason models are still needed. The Lab labels the tracker ready, but there are
   no official futures selections until an exact free-source price, settlement rules, evidence and owner approval
   all exist.

## Verification and deployment

Run both full test suites with their actual exit statuses, build from stored data, use the isolated offline
`scripts/rehearse.py --slot HHMM` helper, inspect responsive pages, then deploy under the desk's run lock. The plain
`run.py --dry-run` path is not itself offline. Verify GitHub publication and the
live 375px site. Never manually run a publishing desk job to test a release.
