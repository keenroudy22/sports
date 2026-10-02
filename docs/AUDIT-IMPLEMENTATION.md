# October 2 audit implementation

Owner approved implementation on October 2, 2026. This is the release checklist, not a claim that every phase
of the audit is finished. Free service ceilings and the append-only public record remain mandatory.

## First release: safeguards and the picks-first Board

- Hard refusal of paused / negative calibrated value / missing prop calibration / stale new straight plays.
  A favorite or researched label is not a bypass. Daily card sizes are maximums.
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
- Three original preview families (Matchup Menu, End-zone Work, Week of Football), generated from real site
  data. Navy/mint/cyan/violet. Preview only: nothing queued or advertised as coming.

## Remaining staged work — not enabled by the second release

1. Broader line-payload consolidation and per-component operational alerting beyond the current heartbeat checks.
   Source-age labels already exist, but are not a complete per-provider health monitor.
2. Prospective model shadow evaluation and independently validated FBS/FCS membership labels. The evaluation
   report explicitly labels its prior-season coverage heuristic; it is not official membership data.
3. Validated priced team totals, touchdown probabilities and alternate-line streak sheets need evidence not
   currently available; do not hand-tune to named players or overwrite current forecasts.
4. Live tracked-game worker in shadow only: shared free source fetch per game, bounded cadence, explicit source
   age, deduplication, corrections and final reconciliation. Then one Discord game, then three clean pilots before
   an X milestone release. No LLM or paid-odds call per tick. None of this is currently enabled.
5. New graphics' public-release checkpoint and measured editorial experiment. The manual mentions workflow is
   documented in GROWTH.md; there is no automatic inbox/reply worker. Age-matched analytics remain an operational
   collection step, not an implemented new analytics feed. No automated likes, follows, unsolicited replies,
   trend-chasing or engagement purchases. X's automation
   rules require prior written approval for an AI reply bot: https://help.x.com/en/rules-and-policies/x-automation
6. Cross-service quota reporting beyond the new shared Odds API guard. NBA/CBB remain paper-only; other sports retain existing
   factual coverage/capture status. Public market promotion needs prospective evidence and owner sign-off.

## Verification and deployment

Run both full test suites, build from stored data, rehearse with `--dry-run --no-llm` and researcher explicitly
disabled, inspect the responsive pages, then deploy under the desk's run lock. Verify GitHub publication and the
live 375px site. Never manually run a publishing desk job to test a release.
