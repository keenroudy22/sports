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

## Remaining work — not deployed by this release

1. Finish the shared line-read payload and market-grouped favorites, including explicit missing-price / unsupported
   team-total states. Add per-field usage completeness and clearer current-season/current-role player comparisons.
2. Extend integrity coverage to complete append-only store revisions; add component-level health/fallback status
   and actionable-transition alerts. Complete the accounting split across receipts and the detailed scoreboard.
3. Model evaluation harness: game/week-separated holdouts; college FBS/FCS schedule labels, blowout sensitivity,
   roster/current-role weighting and opponent-adjusted efficiency candidates. Test new versions in shadow before
   promotion; do not hand-tune to McKenzie, Hawkins, UConn or NC State or overwrite current forecasts.
4. Live tracked-game worker in shadow only: shared free source fetch per game, bounded cadence, explicit source
   age, deduplication, corrections and final reconciliation. Then one Discord game, then three clean pilots before
   an X milestone release. No LLM or paid-odds call per tick. None of this is currently enabled.
5. Human-reviewed mentions workflow; new graphic families and editorial experiment; age-matched engagement
   metrics. No automated likes, follows, unsolicited replies, trend-chasing or engagement purchases. X's automation
   rules require prior written approval for an AI reply bot: https://help.x.com/en/rules-and-policies/x-automation
6. Central quota ledger / fail-closed service guard and local-model benchmark. Existing free limits remain in
   force; do not infer that the new governor exists. NBA/CBB remain paper-only; other sports retain existing
   factual coverage/capture status. Public market promotion needs prospective evidence and owner sign-off.

## Verification and deployment

Run both full test suites, build from stored data, rehearse with `--dry-run --no-llm` and researcher explicitly
disabled, inspect the responsive pages, then deploy under the desk's run lock. Verify GitHub publication and the
live 375px site. Never manually run a publishing desk job to test a release.
