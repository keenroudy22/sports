'use strict';
/* Lazily loaded player charts and basketball prop research. app.js supplies the shared, already-tested view helpers. */
(function (root, factory) {
  root.KRPlayer = factory;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (ctx) {
  const { C, P, state, esc, head, section, empty, seg, teamDirectory, maybe, get, defenseRows, teamMark,
    when, whenShort, bookLabel, ago, lineData, saved, oddsText, rate, receipt, isNum } = ctx;
  const { GAMES, HEADSHOT, MARK, STAT_UNITS, clock, defGames, defenseVerdict, disc, filtersFold,
    hasValue, lineVM, logoImg, minus, nameSize, odd, onBoard, panelVars, pctOne, teamPanel, ticketWhen,
    toneFor, watchButton, HOUSE, holdOf, heldWords, opponentTrendText } = ctx;
  const PLAYER_CSS = `/* Player page (lazy with app-player.js; kept out of the first-load shell). */
.kt-sheet { margin: 18px 0 0; }
.kt-sheet .kt-order { margin: 0; }
.kt-sheet .kt-paper { padding-top: 16px; }
.kt-k { margin: 0 4px; font: 700 13px/1 var(--font-display); letter-spacing: .14em; text-transform: uppercase; color: var(--ink-soft); }
.kt-betrow { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.kt-betrow .kt-bet { flex-wrap: nowrap; }
.kt-betrow .kt-stamp { position: static; flex: none; transform: rotate(-6deg); margin: 6px 2px 0 0; }
.kt-prices { margin: 8px 4px 0; font: 500 13.5px/1.35 var(--font-body); color: var(--ink-soft); }
.kt-prices b { color: var(--ticket-ink); font: 700 18px/1 var(--font-display); letter-spacing: .02em; }
.kt-held { margin: 10px 4px 0; font: 500 14.5px/1.42 var(--font-body); color: var(--ticket-ink); }
.kt-chart { margin: 16px 4px 0; }
.kt-chart .kt-bars { grid-auto-columns: 1fr; gap: 10px; height: 118px; margin: 0; }
.kt-chart .kt-bars .line { right: -4px; }
.kt-chart .kt-bars .line span { top: -19px; padding: 0 4px; background: var(--paper-top); font: 700 13px/1.2 var(--font-display); }
.kt-x { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 10px; margin-top: 6px; text-align: center; font: 500 12px/1.3 var(--font-body); color: var(--ink-soft); }
.kt-x em { display: block; font: 700 20px/1 var(--font-display); font-style: normal; margin-bottom: 3px; }
.kt-x b { display: block; color: var(--ticket-ink); font: 700 13px/1.2 var(--font-display); letter-spacing: .04em; }
.kt-cap { margin: 10px 4px 0; font: 500 13px/1.35 var(--font-body); color: var(--ink-soft); }
.kt-cap b { color: var(--ticket-ink); }
.kt-hero { --panel-top: 0px; --panel-h: 190px; --ph-w: 196px; --ph-h: 254px; position: relative; margin: 44px 0 0; }
.kt-hero .kt-photo { right: 0; }
.kt-hero .kt-panel { box-shadow: 0 14px 18px rgba(0, 0, 0, .45); }
.kt-hero .kt-name { font-size: var(--name-size, 56px); margin-top: 8px; }
.kt-kick { position: relative; z-index: 2; font: 700 13px/1 var(--font-display); letter-spacing: .14em; text-transform: uppercase; color: rgba(242, 247, 244, .86); }
.kt-kick a { color: inherit; }
.kt-tabs { display: flex; gap: 18px; margin: 16px 0 0; overflow-x: auto; scrollbar-width: none; border-bottom: 1px solid var(--line);
  -webkit-mask: linear-gradient(90deg, #000 calc(100% - 28px), #0000); mask: linear-gradient(90deg, #000 calc(100% - 28px), #0000); }
.kt-tabs::after { content: ''; flex: none; width: 10px; }
.kt-tabs button { flex: none; display: flex; align-items: center; min-height: var(--tap); padding: 0; border: 0; border-bottom: 3px solid transparent; margin-bottom: -1px; background: none; cursor: pointer;
  color: var(--dim); font: 700 15px/1 var(--font-display); letter-spacing: .08em; text-transform: uppercase; }
.kt-tabs button[aria-pressed="true"] { color: var(--chalk); border-bottom-color: var(--chalk); }
.kt-big { display: flex; align-items: flex-end; gap: 16px; padding-top: 22px; }
.kt-big p { font: 500 13px/1.2 var(--font-body); color: var(--dim); }
.kt-big p b { display: block; margin-bottom: 2px; font: 700 44px/.9 var(--font-display); color: var(--chalk); letter-spacing: .01em; }
.kt-big .rest { padding-bottom: 1px; font-size: 14px; color: var(--chalk); }
.kt-matchup { margin-top: 16px; padding-top: 14px; border-top: 1px dashed rgba(169, 192, 179, .28); font: 500 14px/1.45 var(--font-body); color: var(--dim); }
.kt-matchup b { color: var(--chalk); font-weight: 600; }
.kt-log { width: 100%; margin-top: 12px; border-collapse: collapse; font-variant-numeric: tabular-nums; }
.kt-log th, .kt-log td { padding: 10px 0; border-bottom: 1px dashed rgba(169, 192, 179, .28); text-align: right; vertical-align: baseline; }
.kt-log thead th { padding: 0 0 7px; font: 700 12px/1 var(--font-display); letter-spacing: .12em; text-transform: uppercase; color: var(--dim); border-bottom: 1px solid var(--line); }
.kt-log thead th:first-child, .kt-log tbody th { text-align: left; }
.kt-log tbody th { font: 500 13px/1.3 var(--font-body); color: var(--dim); }
.kt-log tbody th a { display: inline-flex; align-items: center; min-height: var(--tap); }
.kt-log tbody th b { font: 700 17px/1.1 var(--font-display); letter-spacing: .03em; text-transform: uppercase; color: var(--chalk); margin-right: 4px; }
.kt-log tbody th span { display: block; font-size: 12px; }
.kt-log td { width: 56px; font: 500 13px/1 var(--font-body); color: var(--dim); }
.kt-log td.y { width: 52px; font: 700 22px/1 var(--font-display); color: var(--chalk); }
.kt-log.basketball-log { max-width: 720px; }
.basketball-log th, .basketball-log td { padding-inline: 0 8px; }
.basketball-log th:last-child, .basketball-log td:last-child { padding-inline-end: 0; }
.basketball-log td.log-result { width: 72px; }
.basketball-log .log-result.hit { color: var(--kookd); }
.basketball-log .log-result.miss { color: var(--burnt-text); }
.kt-kick a { padding: 14px 8px; margin: 0 -8px; }
@media (min-width: 760px) { .kt-hero, .kt-sheet { max-width: 560px; } }
@media (max-width: 359px) { .kt-hero { --ph-w: 150px; --ph-h: 194px; } .kt-sheet .kt-order { margin: 0; } .kt-betrow { flex-wrap: wrap; } }
`;
  const PLAYER_CHART_CSS = `
/* Player research is a chart-first betting dashboard, not another paper ticket. */
.player-board { max-width: 720px; margin: 18px 0 0; padding: 16px; border: 1px solid #284936; border-radius: 16px; background: linear-gradient(145deg, rgba(24,49,35,.96), rgba(10,24,17,.98)); box-shadow: 0 12px 30px rgba(0,0,0,.22); }
.player-board-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.player-board-head .eyebrow { color: var(--kookd); }
.player-board-head h2 { margin-top: 4px; font: 700 25px/1.05 var(--font-body); letter-spacing: -.02em; }
.player-board-mode { flex: none; padding: 5px 8px; border-radius: 999px; background: rgba(32,199,116,.1); color: #70e9aa; font: 700 11px/1 var(--font-body); text-transform: uppercase; letter-spacing: .05em; }
.player-line-entry { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px 12px; align-items: end; margin: 0 0 12px; padding: 12px; border: 1px solid rgba(32,199,116,.22); border-radius: 12px; background: rgba(32,199,116,.045); }
.player-line-entry label { color: var(--dim); font: 700 11px/1 var(--font-body); text-transform: uppercase; letter-spacing: .05em; }
.player-line-entry input { margin-top: 6px; min-height: 42px; }
.player-line-entry .seg { margin: 0; }
.player-line-entry p { grid-column: 1 / -1; margin: 0; }
.player-board .kt-player-numbers { margin: 0; }
.player-board .kt-player-numbers > span { border-color: rgba(169,192,179,.18); background: rgba(5,15,10,.42); }
.player-board .kt-player-numbers > span:nth-child(2) { border-color: rgba(32,199,116,.35); background: rgba(32,199,116,.07); }
.player-board .kt-prices, .player-board .kt-held, .player-board .kt-cap { color: var(--dim); }
.player-board .kt-prices b, .player-board .kt-cap b, .player-board .kt-held { color: var(--chalk); }
.player-board .kt-chance { color: var(--dim); }
.player-board .kt-chance b { color: var(--chalk); }
.player-board .kt-chart { margin: 18px 0 0; padding: 14px 10px 10px; border: 1px solid rgba(169,192,179,.15); border-radius: 12px; background: rgba(5,15,10,.42); }
.player-board .kt-chart .kt-bars,
.player-board .kt-chart .kt-x { width: 100%; grid-auto-columns: minmax(0,1fr); gap: 6px; }
.player-board .kt-chart .kt-bars { height: 138px; border-bottom-color: rgba(242,247,244,.7); }
.player-board .kt-chart .kt-bars .line { border-top-color: var(--chalk); }
.player-board .kt-chart .kt-bars .line span { top: -20px; background: #0b1c14; color: var(--chalk); }
.player-board .kt-x { color: var(--dim); }
.player-board .kt-x b { color: var(--chalk); }
.player-chart-legend { display: flex; flex-wrap: wrap; gap: 10px 16px; margin: 12px 0 0; color: var(--dim); font-size: 12px; }
.player-chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
.player-chart-legend i { width: 8px; height: 8px; border-radius: 50%; background: #6f8278; }
.player-chart-legend .hit i { background: var(--kookd); }
.player-chart-legend .miss i { background: var(--burnt); }
.player-board .kt-stubrow { margin: 12px 0 0; min-height: 0; }
.player-board .kt-season { color: var(--dim); }
.line-lab { max-width: 720px; margin: 12px 0 0; padding: 15px 16px 13px; border: 1px solid rgba(169,192,179,.22); border-radius: 16px; background: rgba(5,15,10,.5); }
.line-lab-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.line-lab-head h2 { margin-top: 3px; font: 700 22px/1.05 var(--font-body); letter-spacing: -.02em; }
.line-lab-head p:last-child { margin-top: 4px; color: var(--dim); font: 500 13px/1.35 var(--font-body); }
.line-lab-direction { flex: none; padding: 6px 9px; border-radius: 999px; background: var(--chalk); color: #07110b; font: 700 12px/1 var(--font-body); text-transform: uppercase; letter-spacing: .05em; }
.line-lab-table { width: 100%; margin-top: 12px; border-collapse: collapse; table-layout: fixed; font-variant-numeric: tabular-nums; }
.line-lab-table th, .line-lab-table td { padding: 9px 6px; border-top: 1px solid rgba(169,192,179,.14); text-align: center; }
.line-lab-table thead th { padding-top: 0; border: 0; color: var(--dim); font: 700 11px/1 var(--font-body); text-transform: uppercase; letter-spacing: .06em; }
.line-lab-table th:first-child, .line-lab-table td:first-child { width: 34%; padding-left: 0; text-align: left; }
.line-lab-table tbody th { color: var(--chalk); font: 700 18px/1 var(--font-display); }
.line-lab-table tbody td { color: var(--chalk); font: 700 15px/1 var(--font-body); }
.line-lab-table tbody td span { display: block; margin-top: 3px; color: var(--dim); font: 500 11px/1 var(--font-body); }
.line-lab-table tr.book { background: rgba(32,199,116,.08); }
.line-lab-table tr.book th { color: #70e9aa; }
.line-lab-tag { display: inline-block; margin-left: 5px; color: var(--kookd); font: 700 9px/1 var(--font-body); text-transform: uppercase; letter-spacing: .07em; vertical-align: 2px; }
.line-lab-note { margin-top: 9px; color: var(--dim); font: 500 12px/1.4 var(--font-body); }
.player-insights { max-width: 720px; display: grid; gap: 12px; margin-top: 12px; }
.player-insight { min-width: 0; padding: 15px 16px; border: 1px solid rgba(169,192,179,.2); border-radius: 16px; background: rgba(5,15,10,.46); }
.player-insight.wide { grid-column: 1 / -1; }
.player-insight-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.player-insight-head h2 { margin-top: 3px; font: 700 20px/1.05 var(--font-body); letter-spacing: -.02em; }
.player-insight-head span { flex: none; color: var(--dim); font: 700 10px/1 var(--font-body); letter-spacing: .06em; text-transform: uppercase; }
.player-window-row, .player-compare-row { display: grid; grid-template-columns: 58px minmax(0,1fr) auto; align-items: center; gap: 9px; margin-top: 9px; font-variant-numeric: tabular-nums; }
.player-window-row:first-of-type, .player-compare-row:first-of-type { margin-top: 0; }
.player-window-row > span, .player-compare-row > span { color: var(--dim); font: 700 11px/1 var(--font-body); text-transform: uppercase; letter-spacing: .04em; }
.player-window-row > b, .player-compare-row > b { color: var(--chalk); font: 700 13px/1 var(--font-body); white-space: nowrap; }
.player-window-track, .player-compare-track { position: relative; height: 9px; overflow: hidden; border-radius: 999px; background: rgba(169,192,179,.12); }
.player-window-track i, .player-compare-track i { display: block; height: 100%; min-width: 2px; border-radius: inherit; background: var(--void); }
.player-window-row.hit .player-window-track i { background: var(--kookd); }
.player-window-row.miss .player-window-track i { background: var(--burnt); }
.player-compare-row.book .player-compare-track i { background: var(--chalk); }
.player-compare-row.kookn .player-compare-track i { background: #70e9aa; }
.player-role-bars { height: 94px; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(22px,1fr); align-items: end; gap: 6px; padding: 8px 4px 0; border-bottom: 1px solid rgba(242,247,244,.55); }
.player-role-bar { min-width: 0; display: grid; align-items: end; height: 100%; }
.player-role-bar i { display: block; min-height: 2px; border-radius: 4px 4px 0 0; background: #879b90; }
.player-role-labels { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(22px,1fr); gap: 6px; margin-top: 6px; text-align: center; }
.player-role-labels span { min-width: 0; color: var(--dim); font: 600 9px/1.15 var(--font-body); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.player-insight-note { margin-top: 10px; color: var(--dim); font: 500 12px/1.4 var(--font-body); }
.player-insight-note b { color: var(--chalk); font-weight: 600; }
@media (min-width: 680px) { .player-insights { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 520px) {
  .player-board { padding: 14px; }
  .player-board-head h2 { font-size: 22px; }
  .player-line-entry { grid-template-columns: 1fr; }
  .player-line-entry p { grid-column: 1; }
  .player-board .kt-chart { margin-left: -4px; margin-right: -4px; padding-left: 8px; padding-right: 8px; }
  /* Bars and their opponent/date labels must use the same fluid columns.
     The old 52px label minimum escaped 320–430px cards and looked cut off. */
  .player-board .kt-chart .kt-bars,
  .player-board .kt-chart .kt-x { width: 100%; grid-auto-columns: minmax(0,1fr); gap: 4px; }
  .player-board .kt-chart .kt-x { overflow: visible; font-size: 9px; line-height: 1.15; }
  .player-board .kt-chart .kt-x span { min-width: 0; overflow: visible; overflow-wrap: anywhere; }
  .player-board .kt-chart .kt-x em { font-size: 16px; }
  .player-board .kt-chart .kt-x b { font-size: 10px; line-height: 1.05; letter-spacing: 0; }
  .line-lab, .player-insight { padding: 14px 12px 12px; }
  .line-lab-head h2 { font-size: 20px; }
  .line-lab-table th, .line-lab-table td { padding-left: 3px; padding-right: 3px; }
  .line-lab-table th:first-child, .line-lab-table td:first-child { width: 31%; }
  .player-window-row, .player-compare-row { grid-template-columns: 50px minmax(0,1fr) auto; gap: 7px; }
}
/* Matchup-grouped basketball milestones. One compact row answers what hit, how often,
   how large the role was, and whether Kook'n has a current comparison. */
.milestone-intro { max-width: 920px; display: grid; gap: 10px; margin: 0 0 16px; padding: 14px 16px; border: 1px solid rgba(32,199,116,.3); border-radius: 14px; background: rgba(32,199,116,.055); }
.milestone-intro p { margin: 0; }
.milestone-games { max-width: 920px; display: grid; gap: 14px; }
.milestone-game { overflow: hidden; border: 1px solid rgba(169,192,179,.22); border-radius: 16px; background: rgba(5,15,10,.48); }
.milestone-game-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 13px 15px; background: rgba(24,49,35,.72); cursor: pointer; list-style: none; }
.milestone-game-head::-webkit-details-marker { display: none; }
.milestone-game-head::after { content: '+'; flex: none; color: var(--kookd); font: 800 20px/1 var(--font-body); }
.milestone-game[open] .milestone-game-head { border-bottom: 1px solid rgba(169,192,179,.18); }
.milestone-game[open] .milestone-game-head::after { content: '−'; }
.milestone-game-head h2 { font: 700 19px/1.1 var(--font-body); letter-spacing: -.01em; }
.milestone-game-head span { margin-left: auto; color: var(--dim); font: 600 12px/1.2 var(--font-body); }
.milestone-team { padding: 12px 14px 4px; }
.milestone-team + .milestone-team { border-top: 1px solid rgba(169,192,179,.16); }
.milestone-team h3 { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; font: 700 15px/1.2 var(--font-body); }
.milestone-row { display: grid; grid-template-columns: minmax(180px,1.35fr) repeat(3,minmax(54px,.48fr)) minmax(145px,.9fr); align-items: center; gap: 8px; min-height: 58px; padding: 9px 0; border-top: 1px solid rgba(169,192,179,.12); font-variant-numeric: tabular-nums; }
.milestone-row:first-of-type { border-top: 0; }
.milestone-player { min-width: 0; color: var(--chalk); text-decoration: none; }
.milestone-player b { display: block; overflow: hidden; font: 700 15px/1.15 var(--font-body); text-overflow: ellipsis; white-space: nowrap; }
.milestone-player span { display: block; margin-top: 3px; color: var(--dim); font: 500 11px/1.25 var(--font-body); }
.milestone-player b .milestone-mark { display: inline; color: #70e9aa; font: 800 17px/1 var(--font-body); }
.milestone-rate { text-align: center; }
.milestone-rate small { display: block; color: var(--dim); font: 700 9px/1 var(--font-body); letter-spacing: .06em; text-transform: uppercase; }
.milestone-rate b { display: block; margin-top: 4px; color: var(--chalk); font: 700 13px/1 var(--font-body); }
.milestone-compare { min-width: 0; text-align: right; }
.milestone-compare b, .milestone-compare span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.milestone-compare b { color: var(--chalk); font: 700 12px/1.2 var(--font-body); }
.milestone-compare span { margin-top: 4px; color: var(--dim); font: 500 10px/1.2 var(--font-body); }
.milestone-foot { max-width: 920px; margin-top: 14px; }
@media (max-width: 620px) {
  .milestone-game-head { align-items: flex-start; padding: 12px; }
  .milestone-game-head h2 { font-size: 17px; }
  .milestone-team { padding: 10px 11px 3px; }
  .milestone-row { grid-template-columns: minmax(0,1fr) repeat(3,47px); gap: 5px; padding: 10px 0; }
  .milestone-player b { font-size: 14px; white-space: normal; }
  .milestone-mark { font-size: 15px; }
  .milestone-compare { grid-column: 1 / -1; display: flex; justify-content: space-between; gap: 8px; padding: 0 0 2px; text-align: left; }
  .milestone-compare span { margin: 0; text-align: right; white-space: normal; }
}
`;
  if (typeof document !== 'undefined' && document.head && document.createElement && !(document.getElementById && document.getElementById('kr-player-css'))) {
    const style = document.createElement('style'); style.id = 'kr-player-css'; style.textContent = PLAYER_CSS + PLAYER_CHART_CSS; document.head.appendChild(style);
  }
  const views = {};

  const LOG_COLS = { QB: ['cmp', 'att', 'passYds', 'passTD', 'int', 'car', 'rushYds', 'rushTD'],
    RB: ['car', 'rushYds', 'anyTD', 'targets', 'rec', 'recYds', 'rzCar'], FB: ['car', 'rushYds', 'anyTD', 'targets', 'rec', 'recYds', 'rzCar'],
    WR: ['targets', 'rec', 'recYds', 'anyTD', 'recLong', 'rzTgt'], TE: ['targets', 'rec', 'recYds', 'anyTD', 'recLong', 'rzTgt'], PK: ['fgm', 'fga', 'xpm', 'kPts'] };
  const PROJ_KEY = { rec: 'receptions', car: 'carries' };
  /* The mock's short tab words, so five tabs fit at 375 px; the full name stays the accessible label. */
  const TAB_SHORT = { cmp: 'Comp', att: 'Att', rec: 'Rec', car: 'Car', targets: 'Tgt' };
  const PLAYER_LABEL = { ...C.LABEL, q1_passYds: '1Q pass yds', q1_cmp: '1Q completions', q1_att: '1Q attempts', q1_rushYds: '1Q rush yds', q1_car: '1Q carries', q1_recYds: '1Q rec yds', q1_rec: '1Q receptions' };
  const meanOf = list => { const values = list.filter(isNum); return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null; };
  const playerWindowChart = ({ values, line, dir, format, scopeLabel = 'Season' }) => {
    const windows = [['L5', values.slice(-5)], ['L10', values.slice(-10)], [scopeLabel, values]];
    const averages = windows.map(([, rows]) => meanOf(rows));
    const maxAverage = Math.max(1, ...averages.filter(isNum));
    const rows = windows.map(([label, sample], index) => {
      const clean = sample.filter(isNum), average = averages[index];
      if (!clean.length) return `<div class="player-window-row"><span>${esc(label)}</span><div class="player-window-track"><i style="width:0"></i></div><b>–</b></div>`;
      if (line != null) {
        const hits = clean.filter(value => dir === 'under' ? value < line : value > line).length, pct = Math.round(100 * hits / clean.length);
        return `<div class="player-window-row ${pct >= 60 ? 'hit' : pct <= 40 ? 'miss' : ''}"><span>${esc(label)}</span><div class="player-window-track" aria-hidden="true"><i style="width:${pct}%"></i></div><b>${pct}% · ${hits}/${clean.length}</b></div>`;
      }
      const width = Math.max(2, Math.min(100, 100 * average / maxAverage));
      return `<div class="player-window-row"><span>${esc(label)}</span><div class="player-window-track" aria-hidden="true"><i style="width:${width.toFixed(1)}%"></i></div><b>${esc(format(average))} avg</b></div>`;
    }).join('');
    return `<section class="player-insight" aria-labelledby="player-windows"><div class="player-insight-head"><div><p class="eyebrow">Recent form</p><h2 id="player-windows">Trend windows</h2></div><span>${line == null ? 'Averages' : esc(dir)}</span></div>${rows}<p class="player-insight-note">${line == null ? 'Recorded-game averages for each window.' : `Results against ${esc(format(line))}. Historical hit rates, not probabilities.`}</p></section>`;
  };
  const playerRoleChart = ({ title, entries, format, note }) => {
    const clean = entries.filter(entry => isNum(entry.value)), top = Math.max(1, ...clean.map(entry => entry.value));
    if (!clean.length) return '';
    const last3 = meanOf(clean.slice(-3).map(entry => entry.value)), all = meanOf(clean.map(entry => entry.value));
    return `<section class="player-insight" aria-labelledby="player-role"><div class="player-insight-head"><div><p class="eyebrow">Workload</p><h2 id="player-role">${esc(title)}</h2></div><span>Last ${clean.length}</span></div><div class="player-role-bars" role="img" aria-label="${esc(`${title}: ${clean.map(entry => format(entry.value)).join(', ')}`)}">${clean.map(entry => `<span class="player-role-bar" title="${esc(`${entry.label}: ${format(entry.value)}`)}"><i style="height:${Math.max(2, 86 * entry.value / top).toFixed(1)}px"></i></span>`).join('')}</div><div class="player-role-labels" aria-hidden="true">${clean.map(entry => `<span>${esc(entry.short || entry.label)}</span>`).join('')}</div><p class="player-insight-note"><b>Last 3: ${esc(format(last3))}</b> · shown average ${esc(format(all))}.${note ? ` ${esc(note)}` : ''}</p></section>`;
  };
  const playerComparisonChart = ({ items, format }) => {
    const clean = items.filter(item => isNum(item.value));
    if (clean.length < 2) return '';
    const top = Math.max(1, ...clean.map(item => Math.max(0, item.value)));
    return `<section class="player-insight wide" aria-labelledby="player-compare"><div class="player-insight-head"><div><p class="eyebrow">Same scale</p><h2 id="player-compare">Prop comparison</h2></div><span>${clean.length} numbers</span></div>${clean.map(item => `<div class="player-compare-row ${esc(item.kind || '')}"><span>${esc(item.label)}</span><div class="player-compare-track" aria-hidden="true"><i style="width:${Math.max(2, Math.min(100, 100 * Math.max(0, item.value) / top)).toFixed(1)}%"></i></div><b>${esc(format(item.value))}</b></div>`).join('')}<p class="player-insight-note">Book and Kook’n numbers are current only when labeled above. Recent averages and opponent allowance are historical context.</p></section>`;
  };
  const chartWindows = (rows, window) => {
    if (!rows.length) return [];
    if (window !== 'last20') return [rows.slice(-10)];
    return rows.length <= 10 ? [rows] : [rows.slice(0, -10), rows.slice(-10)];
  };
  const chartWindowLabel = (start, count, total) =>
    `Games ${start + 1}–${start + count} of ${total}`;
  const basketballPlayer = async route => {
    const league = route.league === 'CBB' ? 'CBB' : 'NBA';
    const profile = await C.chartPlayer(get, league, route.id);
    const matchupBack = new RegExp(`^${league}-[0-9]+$`).test(route.game || '') ? route.game : null;
    const back = `<a class="kt-back" href="${matchupBack ? `#game/${esc(matchupBack)}` : `#research/players?sport=${league}`}">‹ ${matchupBack ? 'Matchup' : `${league} player research`}</a>`;
    if (!profile) return head('', 'Player not found', `No stored ${league} games for this player.`, back);
    const { data, season: baseSeason, team: [teamId, teamAbbr] } = profile;
    const basketball = await get(league === 'NBA' ? 'app/nba.json' : 'app/cbb.json').catch(() => ({ games: [] }));
    const belongs = game => Object.values(game.teams || {}).some(team => String(team.id) === String(teamId));
    const now = Date.now();
    const upcoming = game => (!game.status || game.status === 'scheduled') && Date.parse(game.kickoff) > now;
    const linkedGame = matchupBack && ((basketball.games || []).find(game => game.id === matchupBack)
      || (await maybe('sports.json'))?.leagues?.[league]?.games?.find(game => game.id === matchupBack));
    const matchup = matchupBack ? (linkedGame && belongs(linkedGame) ? linkedGame : null)
      : (basketball.games || []).filter(game => upcoming(game) && belongs(game))
        .sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0];
    const next = matchup && upcoming(matchup) ? matchup : null;
    const props = league === 'NBA' && next ? await C.nbaMatchupProps(get, basketball, next.id) : { rows: [] };
    const cutoff = linkedGame?.kickoff && C.dayOf(linkedGame.kickoff);
    // Matchup links show the pregame sample. Stored box rows carry Eastern dates.
    const rows = (data.rows || []).filter(row => !cutoff || row[1] < cutoff);
    const keys = profile.keys || [];
    const value = (row, stat) => { const i = keys.indexOf(stat); return i < 0 ? null : row[9 + i]; };
    const available = C.POSITION_STATS.G.filter(stat => stat === route.stat || rows.some(row => isNum(value(row, stat))));
    const pkey = `${league}:${route.id}`, carries = route.stat || route.season || route.sample || route.line;
    if (state.player.key !== pkey || (carries && state.player.hash !== location.hash)) {
      state.player.key = pkey; state.player.hash = location.hash; state.player.stat = route.stat || null;
      state.player.season = route.season || 'current';
      state.player.window = ['all', 'last5', 'last10', 'last20'].includes(route.sample) ? route.sample : 'last10';
      state.player.line = route.line || '';
      state.player.direction = route.direction === 'under' ? 'under' : 'over';
    }
    const stat = available.includes(state.player.stat) ? state.player.stat : available.includes('pts') ? 'pts' : available[0];
    const season = Number(baseSeason), scope = state.player.season;
    const seasons = [...new Set(rows.filter(row => row[4] === 2).map(row => Number(row[2])))].sort((a, b) => b - a);
    const regular = rows.filter(row => row[4] === 2 && (scope === 'all' || Number(row[2]) === Number(scope === 'current' ? season : scope)))
      .sort((a, b) => String(a[1]).localeCompare(String(b[1])));
    const limit = state.player.window === 'all' ? regular.length : Number(state.player.window.replace('last', ''));
    const recent = regular.slice(-limit), values = recent.map(row => value(row, stat)).filter(isNum);
    const last5 = regular.slice(-5).map(row => value(row, stat)).filter(isNum);
    const last10 = regular.slice(-10).map(row => value(row, stat)).filter(isNum);
    const side = matchup && Object.entries(matchup.teams).find(([, team]) => String(team.id) === String(teamId));
    const opponent = matchup && matchup.teams[side?.[0] === 'home' ? 'away' : 'home'];
    const typedLine = state.player.line !== '' && isNum(Number(state.player.line)) && Number(state.player.line) >= 0 ? Number(state.player.line) : null;
    const selectedSide = state.player.direction === 'under' ? 'under' : 'over';
    const linkedBook = typedLine != null && route.stat === stat && Number(route.line) === typedLine ? bookLabel(route.book) : null;
    const posted = (basketball.trial?.plays || []).filter(play => (!route.game || String(play.gameId || `${league}-${play.eventId}`) === route.game) && !play.result && String(play.athleteId) === String(route.id)
      && (typedLine == null || (play.line === typedLine && String(play.direction || 'over').toLowerCase() === selectedSide))
      && (!linkedBook || bookLabel(play.book) === linkedBook)
      && play.stat === stat && Date.parse(play.kickoff) > Date.now()).sort((a, b) => String(b.publishedAt).localeCompare(String(a.publishedAt)))[0];
    const eventId = next?.providerId || String(next?.id || '').replace(/^(NBA|CBB)-/, '');
    const gameRows = next ? (props.rows || []).filter(row => String(row.athleteId) === String(route.id)
      && String(row.eventId) === String(eventId) && Date.parse(row.kickoff) > Date.now()) : [];
    const gameComparisons = gameRows.filter(row => row.stat === stat).sort((a, b) => String(b.sourceAt).localeCompare(String(a.sourceAt)));
    const bookComparisons = linkedBook ? gameComparisons.filter(row => bookLabel(row.book) === linkedBook) : gameComparisons;
    const comparison = bookComparisons.find(row => typedLine == null || row.line === typedLine)
      || (!linkedBook ? gameComparisons[0] : null);
    const dir = typedLine != null ? selectedSide : String(posted?.direction || comparison?.side || 'over').toLowerCase() === 'under' ? 'under' : 'over';
    const quoteRow = bookComparisons.find(row => isNum(row.line) && isNum(row[dir]) && Math.abs(row[dir]) >= 100
      && (typedLine == null || row.line === typedLine));
    const capturedLine = isNum(posted?.line) ? posted.line : quoteRow?.line ?? null;
    const line = typedLine ?? capturedLine;
    const lineLabel = capturedLine != null ? 'Book line' : 'Chart line';
    const quoteStatus = quoteRow && C.quoteStatus({ state: 'open', ...quoteRow, observedAt: quoteRow.sourceAt, odds: quoteRow[dir] }, next?.kickoff);
    const projectionInfo = data.projection || null;
    const hold = linkedGame && !next ? 'Pregame projection is unavailable for this matchup.'
      : comparison?.hold || gameRows.find(C.basketballAvailabilityHold)?.hold
        || (linkedBook && !comparison ? 'The exact matchup quote and projection are unavailable.' : null);
    const projection = hold ? null : comparison ? comparison.projection?.value : projectionInfo?.values?.[stat];
    const hits = list => line == null ? { hits: null, games: list.length } : { hits: list.filter(v => dir === 'over' ? v > line : v < line).length, games: list.length };
    const h5 = hits(last5);
    const team = side ? side[1] : { id: teamId, abbreviation: teamAbbr, name: comparison?.teamName || teamAbbr };
    const photoLeague = league === 'NBA' ? 'nba' : 'mens-college-basketball';
    const photo = `https://a.espncdn.com/i/headshots/${photoLeague}/players/full/${encodeURIComponent(route.id)}.png`;
    const metric = PLAYER_LABEL[stat] || 'Player stats';
    const average = list => list.length ? list.reduce((sum, number) => sum + number, 0) / list.length : null;
    const fmt = number => number == null ? '–' : C.statValue(number, stat, Number.isInteger(number) ? 0 : 1);
    const quote = posted ? `<b>Kook’n play:</b> ${esc(dir)} ${esc(line)} at ${esc(oddsText(posted.odds))} ${esc(bookLabel(posted.book))} · ${esc(C.stakeOf(posted))}u`
      : quoteRow ? `<b>${esc(dir === 'over' ? 'Over' : 'Under')} ${esc(line)} ${esc(oddsText(quoteRow[dir]))}</b> at ${esc(bookLabel(quoteRow.book))} · ${quoteStatus.current ? `checked ${esc(ago(quoteRow.sourceAt))}` : 'earlier quote · recheck price'}` : '';
    const windows = chartWindows(recent, state.player.window);
    const top = Math.max(1, line || 0, ...windows.flat().map(row => value(row, stat)).filter(isNum));
    const multiplePanels = windows.length > 1;
    const result = number => C.thresholdResult(number, line, dir);
    const chart = windows.flat().some(row => isNum(value(row, stat))) ? windows.map((shown, i) => {
      const shownValues = shown.map(row => value(row, stat));
      const label = multiplePanels ? chartWindowLabel(i ? windows[0].length : 0, shown.length, recent.length)
        : recent.length > shown.length ? `Last ${shown.length} of ${recent.length} games` : '';
      return `<figure class="kt-chart" role="img" aria-label="${esc(`${metric}: ${shownValues.map(v => isNum(v) ? v : 'not recorded').join(', ')}${line != null ? ` against ${line}` : ''}`)}"><div class="kt-bars" aria-hidden="true">${shownValues.map(v => `<div class="col"><div class="bar ${result(v)}" style="height:${(Math.max(2, 132 * Math.max(0, v || 0) / top)).toFixed(1)}px"></div></div>`).join('')}${line != null ? `<div class="line" style="bottom:${(132 * line / top).toFixed(1)}px"><span>${esc(line)}</span></div>` : ''}</div><div class="kt-x" aria-hidden="true">${shown.map((row, i) => `<span><em class="${result(shownValues[i])}">${esc(fmt(shownValues[i]))}</em><b>${row[7] ? 'vs' : '@'} ${esc(row[8] || row[6])}</b>${esc(new Date(`${row[1]}T12:00:00Z`).toLocaleDateString('en-US', {month:'short', day:'numeric', timeZone:'UTC'}))}</span>`).join('')}</div><figcaption class="kt-cap">${label ? `${esc(label)}. ` : ''}${line == null ? 'Recorded game results.' : `<b>${shownValues.filter(v => result(v) === 'hit').length} of ${shownValues.filter(isNum).length} ${esc(dir)} ${esc(line)} in the games shown.</b> History, not a probability.`}</figcaption></figure>`;
    }).join('') : '<p class="small muted">No recorded values for this stat in the selected games.</p>';
    const seasonStatValues = regular.map(row => value(row, stat)).filter(isNum);
    const nbaWindow = playerWindowChart({ values: seasonStatValues, line, dir, format: fmt, scopeLabel: scope === 'all' ? 'All' : 'Season' });
    const minuteEntries = regular.slice(-8).map(row => ({ value: value(row, 'min'), label: `${row[7] ? 'vs' : '@'} ${row[8] || row[6]}`, short: row[8] || row[6] }));
    const minuteTrend = stat === 'min' ? '' : playerRoleChart({ title: 'Minutes trend', entries: minuteEntries,
      format: number => C.statValue(number, 'min', Number.isInteger(number) ? 0 : 1), note: 'Minutes show whether the recent role is holding.' });
    const nbaComparison = playerComparisonChart({ items: [
      { label: capturedLine != null ? 'Book' : 'Chart line', value: line, kind: 'book' }, { label: 'Kook’n', value: isNum(projection) ? Number(projection) : null, kind: 'kookn' },
      { label: 'L5 avg', value: average(last5) }, { label: 'L10 avg', value: average(last10) }, { label: scope === 'all' ? 'All avg' : 'Season', value: average(seasonStatValues) }
    ], format: fmt });
    const nbaInsights = `<div class="player-insights">${nbaWindow}${minuteTrend}${nbaComparison}</div>`;
    const thresholds = line == null ? [] : [...new Set([-2, -1, 0, 1, 2].map(step => Math.max(0, line + step)))];
    const ladder = thresholds.length ? `<section class="line-lab" aria-labelledby="nba-ladder"><div class="line-lab-head"><div><p class="eyebrow">What-if research</p><h2 id="nba-ladder">Line ladder</h2><p>How often did ${esc(data.name)} ${dir === 'over' ? 'clear' : 'stay below'} nearby numbers?</p></div><span class="line-lab-direction">${esc(dir)}</span></div><table class="line-lab-table"><thead><tr><th>Line</th><th>L5</th><th>L10</th><th>Season</th></tr></thead><tbody>${thresholds.map(threshold => { const count = list => ({hits:list.filter(v => dir === 'over' ? v > threshold : v < threshold).length,games:list.length}); const a=count(last5),b=count(last10),c=count(regular.map(row => value(row,stat)).filter(isNum)); const cell=x=>`<td>${x.games ? Math.round(100*x.hits/x.games)+'%' : '–'}<span>${x.hits}/${x.games}</span></td>`; return `<tr${threshold===line?' class="book"':''}><th>${esc(threshold)}${threshold===line?`<span class="line-lab-tag">${capturedLine != null ? 'Book' : 'Chart'}</span>`:''}</th>${cell(a)}${cell(b)}${cell(c)}</tr>`; }).join('')}</tbody></table><p class="line-lab-note">${isNum(projection) ? `Kook’n projects ${esc(fmt(projection))}. ` : ''}Historical thresholds—not offered alternate prices or probabilities.</p></section>` : '';
    const hero = `<div class="page-head" style="display:flex;gap:14px;align-items:center;margin-top:28px"><span class="ava xl" style="--tc:#15301F" aria-hidden="true"><img src="${esc(photo)}" alt=""></span><div><p class="eyebrow">${teamMark(team, 'sm', league)} ${esc(team.name || team.displayName || team.abbreviation || teamAbbr)} · ${esc(data.pos || '')}</p><h1>${esc(data.name)}</h1><p class="sub">${opponent ? `${side[0] === 'home' ? 'vs' : 'at'} ${esc(opponent.name || opponent.displayName || opponent.abbreviation)} · ${esc(whenShort(matchup.kickoff))}` : `${esc(regular.length)} regular-season games recorded`}</p></div></div>`;
    const tabs = `<nav class="kt-tabs" aria-label="Stat">${available.map(key => `<button type="button" data-set="pstat:${esc(key)}" aria-pressed="${key === stat}">${esc({pts:'PTS',reb:'REB',ast:'AST',fg3m:'3PM',pra:'PRA',pa:'P+A',pr:'P+R',ra:'R+A',min:'MIN'}[key] || PLAYER_LABEL[key] || key)}</button>`).join('')}</nav>`;
    const seasonSelect = `<label class="sr" for="psea">Season</label><select id="psea" class="select" data-select="playerSeason"><option value="current"${scope === 'current' ? ' selected' : ''}>This season · ${esc(season)}</option>${seasons.filter(x => x !== season).map(x => `<option value="${x}"${String(x) === String(scope) ? ' selected' : ''}>${x}</option>`).join('')}<option value="all"${scope === 'all' ? ' selected' : ''}>All seasons</option></select>`;
    /* A displayed gap is always Kook'n minus the book. Direction belongs in the price and hit-rate rows;
       flipping the sign for unders made the same two numbers disagree between matchup and player pages. */
    const projectionGap = isNum(projection) && isNum(line) ? projection - line : null;
    const lineEntry = capturedLine == null ? `<div class="player-line-entry"><label>Set chart line<input class="search" type="number" inputmode="decimal" min="0" step="0.5" value="${esc(state.player.line || '')}" placeholder="e.g. 14.5" data-input="playerLine"></label>${seg('pdir', [['over','Over'],['under','Under']], dir)}<p class="small muted">Choose a number to compare with past games.</p></div>` : '';
    const range = !hold && isNum(comparison?.projection?.low) && isNum(comparison?.projection?.high)
      ? `<p class="kt-prices"><b>Kook’n range:</b> ${esc(fmt(comparison.projection.low))}–${esc(fmt(comparison.projection.high))}</p>` : '';
    const estimateNote = hold ? `<p class="kt-prices"><b>Projection held:</b> ${esc(hold)}</p>` : !comparison && projectionInfo?.status ? `<p class="kt-prices"><b>${projectionInfo.status === 'ready' ? 'Kook’n baseline' : projectionInfo.status === 'early' ? 'Early Kook’n baseline' : 'Projection held'}:</b> ${projectionInfo.status === 'held' ? esc(projectionInfo.reason || 'Not enough stable role evidence') : `${esc(projectionInfo.games)} current-season games · ${esc(projectionInfo.minutes)} projected minutes · ${esc(projectionInfo.method)}.`} ${projectionInfo.status === 'early' && projectionInfo.reason ? esc(projectionInfo.reason) + '.' : ''}</p>` : '';
    const projectedMinutes = hold ? null : comparison?.projection?.minutes ?? projectionInfo?.minutes;
    const roleMinutes = comparison?.currentRole?.minutes;
    const boxPath = league === 'NBA' ? 'nba' : 'mens-college-basketball';
    const resultWords = { hit: 'Hit', miss: 'Miss', push: 'Push', unknown: '—' };
    const logRows = recent.slice().reverse().map(row => {
      const total = value(row, stat), outcome = result(total);
      const date = new Date(`${row[1]}T12:00:00Z`).toLocaleDateString('en-US', {month:'short', day:'numeric', timeZone:'UTC'});
      return `<tr><th scope="row"><a class="plain-link" href="https://www.espn.com/${boxPath}/boxscore/_/gameId/${esc(row[0])}" target="_blank" rel="noopener"><b>${row[7] ? 'vs' : 'at'} ${esc(row[8] || row[6])}</b></a><span>${esc(date)}</span></th>
        <td class="y">${esc(fmt(total))}</td>${stat === 'min' ? '' : `<td>${esc(value(row, 'min') ?? '—')}</td>`}${line == null ? '' : `<td class="log-result ${outcome}">${resultWords[outcome]}</td>`}</tr>`;
    }).join('');
    const gameLog = logRows ? `<table class="kt-log basketball-log"><thead><tr><th scope="col">Game</th><th scope="col">${esc(metric)}</th>${stat === 'min' ? '' : '<th scope="col">Min</th>'}${line == null ? '' : `<th scope="col">${esc(dir === 'under' ? 'U' : 'O')} ${esc(line)}</th>`}</tr></thead><tbody>${logRows}</tbody></table>`
      : '<p class="small muted">No games in this window.</p>';
    return `${back}${hero}${tabs}${filtersFold('player', `${scope === 'all' ? 'All seasons' : season + ' season'} · ${recent.length} games · ${esc(metric)}`, `${seasonSelect}${seg('pwin', [['last5','Last 5'],['last10','Last 10'],['last20','Last 20'],['all','All games']], state.player.window)}`)}<section class="player-board" aria-labelledby="nba-stat"><div class="player-board-head"><div><p class="eyebrow">${capturedLine != null ? posted ? 'Posted line' : quoteStatus?.current ? 'Current line' : 'Earlier line' : line != null ? 'Chart line' : 'Season snapshot'}</p><h2 id="nba-stat">${esc(metric)}</h2></div><span class="player-board-mode">${capturedLine != null ? 'Kook vs Book' : 'Player history'}</span></div>${lineEntry}<div class="kt-number-grid kt-player-numbers"><span><small>${lineLabel}</small><b class="num">${esc(line == null ? '–' : line)}</b></span><span><small>Kook’n projection</small><b class="num">${esc(isNum(projection) ? fmt(projection) : 'Held')}</b></span><span><small>Kook’n − line</small><b class="num">${projectionGap == null ? '–' : `${projectionGap > 0 ? '+' : ''}${esc(fmt(projectionGap))}`}</b></span><span><small>Last 5 average</small><b class="num">${esc(fmt(average(last5)))}</b></span><span><small>Last 5 hits</small><b class="num">${line == null ? '–' : `${h5.hits}/${h5.games}`}</b></span></div>${quote ? `<p class="kt-prices">${quote}</p>` : ''}${estimateNote}${range}${isNum(projectedMinutes) && comparison ? `<p class="kt-prices"><b>Kook’n minutes:</b> ${esc(C.fixed(projectedMinutes))}</p>` : ''}${roleMinutes?.length ? `<p class="kt-prices"><b>Recent workload:</b> ${roleMinutes.map(m => esc(m)).join(' / ')} minutes</p>` : ''}<div class="player-chart-legend"><span class="hit"><i></i>Cleared line</span><span class="miss"><i></i>Missed line</span><span><i></i>Push or unknown</span></div>${chart}</section>${nbaInsights}${ladder}<section class="kt-page-sec"><div class="kt-sec-head"><h2 class="kt-tape">Game log</h2><span class="kt-kind">Official box scores</span></div>${gameLog}<p class="small muted" style="margin-top:8px">Last 5, Last 10 and the full season use recorded regular-season appearances. A one-minute appearance counts as an appearance; minutes are shown so role changes stay visible. Kook’n minus the book is not a probability or proof that a price is valuable.</p></section>`;
  };
  views.player = async route => {
    const league = route.league;
    if (state.league !== league) state.league = league;
    if (league === 'NBA' || league === 'CBB') return basketballPlayer(route);
    const back = `<a class="kt-back" href="#research/players?pl=${esc(league)}">‹ Research</a>`;
    const profile = await C.chartPlayer(get, league, route.id);
    if (!profile) return head('', 'Player not found', 'No stored games for this player in this league.', back);
    const [teams, today, lines] = await Promise.all([teamDirectory(league), get('app/today.json'), lineData(league)]);
    const { data, keys, season: baseSeason, team: [teamId, teamAbbr] } = profile;
    const { rows, pos } = data;
    const quarterByGame = new Map((data.firstQuarter || []).map(r => [String(r.eventId), r.stats || {}]));
    const read = (row, stat) => stat.startsWith('q1_') ? quarterByGame.get(String(row[0]))?.[stat.slice(3)] : C.observedStat(row, keys, stat);
    /* A new player starts fresh, unless the link carried a stat, season or sample. */
    const pkey = `${league}:${route.id}`;
    const carries = route.stat || route.season || route.sample || route.line || route.direction;
    if (state.player.key !== pkey || (carries && state.player.hash !== location.hash)) {
      state.player.key = pkey;
      state.player.hash = location.hash;
      state.player.stat = route.stat || null;
      state.player.season = route.season || 'current';
      state.player.window = ['all', 'last5', 'last10', 'last20'].includes(route.sample) ? route.sample : 'all';
      state.player.line = route.line || '';
      state.player.direction = route.direction === 'under' ? 'under' : 'over';
    }
    const options = [...new Set([...(C.POSITION_STATS[pos] || C.POSITION_STATS.WR), 'snapPct'])].filter(stat => rows.some(r => isNum(read(r, stat))));
    const quarterKeys = league === 'NFL' ? ['passYds','cmp','att','rushYds','car','recYds','rec'].filter(k => (data.firstQuarter || []).some(r => isNum(r.stats?.[k])) && (k === 'passYds' || k === 'cmp' || k === 'att' ? rows.some(r => isNum(C.observedCell(r, keys, k))) : (C.POSITION_STATS[pos] || []).includes(k))) .map(k => `q1_${k}`) : [];
    options.push(...quarterKeys);
    if (state.player.stat && PLAYER_LABEL[state.player.stat] && !options.includes(state.player.stat)) options.push(state.player.stat);
    const stat = options.includes(state.player.stat) ? state.player.stat : options[0] || (C.POSITION_STATS[pos] || C.POSITION_STATS.WR)[0];
    const isQuarter = stat.startsWith('q1_');
    const team = ((teams || {}).teams || {})[teamId] || { name: teamAbbr };
    const abbr = id => (((teams || {}).teams || {})[id] || {}).abbr || id;
    const now = Date.now();
    const next = (today.games || []).filter(g => (!route.game || g.id === route.game) && g.league === league && !g.completed && Date.parse(g.kickoff) > now && [g.home.id, g.away.id].includes(String(teamId)))
      .sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0];
    const side = next ? (String(next.home.id) === String(teamId) ? 'home' : 'away') : null;
    const nextDetail = next ? await maybe(`app/games/${next.id}.json`) : null;

    /* Season and sample: Last 5/10/20 always count inside the chosen season. */
    const currentSeason = (next && next.season) || baseSeason || ((teams || {}).defense || {}).season;
    const seasons = [...new Set(rows.filter(r => r[4] === 2).map(r => Number(r[2])))].sort((a, b) => b - a);
    if (!['current', 'all'].includes(state.player.season) && !seasons.includes(Number(state.player.season))) state.player.season = 'current';
    const scope = state.player.season, win = state.player.window;
    const scopeLabel = scope === 'all' ? 'All seasons' : `${scope === 'current' ? currentSeason : scope} season`;
    const recent = C.playerHistory(rows, currentSeason, scope, win);
    const thisSeason = C.playerHistory(rows, currentSeason);
    const values = recent.map(r => read(r, stat));

    /* The line: the board's priced quote first, else the captured reference line from the game feed. */
    const pricedRows = !isQuarter && next && lines ? (lines.lines || []).filter(r => String(r.athleteId) === String(route.id) && r.gameId === next.id && C.marketKey(r) === stat) : [];
    const linkedLine = !isQuarter && state.player.line !== '' && isNum(Number(state.player.line)) && Number(state.player.line) >= 0 ? Number(state.player.line) : null;
    const linkedBook = linkedLine != null && route.stat === stat && Number(route.line) === linkedLine
      && (!route.direction || route.direction === state.player.direction) ? bookLabel(route.book) : null;
    const sameBook = row => !linkedBook || linkedBook === bookLabel(row.displayBook || row.book);
    const matchesLink = r => linkedLine == null || (Number(r.line) === linkedLine && String(r.direction || 'over').toLowerCase() === state.player.direction && sameBook(r));
    const priced = pricedRows.filter(r => matchesLink(r) && !r.roleSuspect && !r.priceSuspect).map(r => lineVM(r, now)).filter(vm => onBoard(vm, now) && (vm.age.kind === 'fresh' || vm.age.kind === 'aging')).sort((a, b) => (b.edge ?? -99) - (a.edge ?? -99))[0] || null;
    const latest = pricedRows.slice().sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))[0];
    const captured = !isQuarter && (((nextDetail || {}).props || {}).lines || {})[route.id];
    const refLine = captured && isNum((captured[stat] || [])[0]) ? captured[stat][0] : null;
    const capturedReference = refLine != null ? { line: refLine, state: 'reference', book: nextDetail?.props?.provider || null, observedAt: nextDetail?.props?.capturedAt || null } : null;
    const quote = priced?.src || (linkedLine != null
      ? pricedRows.filter(r => matchesLink(r) && !r.priceSuspect).sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))[0]
        || (refLine === linkedLine && sameBook(capturedReference) ? capturedReference : { line: linkedLine, state: 'reference' })
      : latest || capturedReference);
    const line = quote && isNum(Number(quote.line)) ? Number(quote.line) : null;
    const lineStatus = quote ? C.quoteStatus(quote, next?.kickoff, now) : null;
    const lineLabel = quote?.book ? 'Book line' : 'Chart line';
    /* The side a priced row is graded on; with no priced row the line reads as an over, never a held row's side. */
    const dir = linkedLine != null ? state.player.direction : String((priced ? priced.src : {}).direction || 'over').toLowerCase() === 'under' ? 'under' : 'over';
    const h = line != null ? C.hits(values, line) : null;

    const opp = next ? (side === 'home' ? next.away : next.home) : null;
    const group = C.POS_GROUP[pos];
    const dRows = teams ? defenseRows(teams, league) : {};
    const allow = !isQuarter && opp && group && teams ? C.rankOf(dRows, opp.id, group, stat) : null;
    const tone = allow ? toneFor(allow.rank, allow.of, stat) : 'neutral';
    const verdict = allow && line != null ? defenseVerdict(C.rankTone(allow.rank, allow.of), dir, defGames(dRows, opp.id, group, stat)) : null;
    const vs = opp ? C.splits(recent, keys, stat, opp.id, (row, k, s2) => read(row, s2)).vs : null;
    const proj = side && nextDetail && nextDetail.forecast ? ((((nextDetail.forecast.players || {})[side] || {}).players || []).find(p => String(p.id) === String(route.id)) || null) : null;
    const availability = side && nextDetail ? ((((nextDetail.teams || {})[side] || {}).injuries || [])
      .find(player => String(player.id || '') === String(route.id) || String(player.name || '') === String(data.name)) || null) : null;
    const availabilityHeld = Boolean(availability && /out|doubtful|suspension|reserve/i.test(availability.status || ''));
    const projectionField = PROJ_KEY[stat] || stat;
    const projectionReview = Boolean(proj && (proj.underReview || []).includes(projectionField));
    const projV = proj && !projectionReview ? proj[projectionField] : null;
    const summary = C.summarize(values);
    const split = C.splits(recent, keys, stat, null, (row, k, s2) => read(row, s2));
    const valueText = v => C.statValue(v, stat, Number.isInteger(v) ? 0 : 1);
    const rangeText = v => C.statValue(stat === 'snapPct' ? v : Math.round(v), stat);
    const word = (PLAYER_LABEL[stat] || stat).toLowerCase();
    const seasonSummary = C.summarize(thisSeason.map(r => read(r, stat)));
    const last5Summary = C.summarize(recent.slice(-5).map(r => read(r, stat)));
    const seasonValues = thisSeason.map(r => read(r, stat)).filter(isNum);
    const seasonHigh = seasonValues.length ? Math.max(...seasonValues) : null;

    const seasonSelect = `<label class="sr" for="psea">Season</label><select id="psea" class="select" data-select="playerSeason"><option value="current"${scope === 'current' ? ' selected' : ''}>This season · ${esc(currentSeason ?? '')}</option>${seasons.filter(x => x !== Number(currentSeason)).map(x => `<option value="${x}"${String(x) === String(scope) ? ' selected' : ''}>${x}</option>`).join('')}<option value="all"${scope === 'all' ? ' selected' : ''}>All seasons</option></select>`;
    const showing = `${scopeLabel} · ${recent.length} game${recent.length === 1 ? '' : 's'}${win === 'all' ? '' : ` · last ${win.replace('last', '')}`} · ${PLAYER_LABEL[stat] || stat}`;
    const cols = [...(LOG_COLS[pos] || LOG_COLS.WR), ...(keys.includes('snapPct') && rows.some(r => C.observedCell(r, keys, 'snapPct') != null) ? ['snapPct'] : [])];
    const log = recent.slice().sort((a, b) => String(b[1]).localeCompare(String(a[1])));
    const where = r => r[7] === 0 ? '@' : r[7] === -1 ? 'vs (neutral)' : 'vs';
    const shareHref = `#player/${league}/${encodeURIComponent(route.id)}?stat=${encodeURIComponent(stat)}${scope !== 'current' ? `&season=${encodeURIComponent(scope)}` : ''}${win !== 'all' ? `&sample=${win}` : ''}`;

    /* The player page in the Kitchen Ticket look: the team panel with the two-pass photo, text stat tabs, Tonight's
       line on paper, one big figure, the matchup sentence and the game log in chalk on the felt. Unavailable
       (decision 9): no projection, chance or edge anywhere; only the real recent volumes the build saved. */
    const heldRow = pricedRows.find(r => r.roleSuspect || r.priceSuspect) || null;
    const held = availabilityHeld || projectionReview || Boolean(heldRow);
    const opponentTrend = (data.upcomingTrends || []).find(row => row.gameId === next?.id && row.stat === stat
      && (line == null || Number(row.line) === Number(line)) && row.direction === dir);
    /* The same words as the play page and the Today ticket (app.js heldWords), from the same hold rule. */
    const heldText = availabilityHeld
      ? `${data.name} is listed ${availability.status}. Kook’n projection and edge are held unless the official status changes.`
      : held ? `No grade from me tonight. ${heldWords(holdOf(pricedRows) || { kind: 'role' })}` : '';
    const g = next ? GAMES.get(next.id) || next : null, mine = g ? g[side] : null;
    const colours = mine ? teamPanel(mine.color, mine.alt) : team.color ? teamPanel(team.color) : HOUSE;
    const photo = HEADSHOT[league] ? HEADSHOT[league](route.id) : null, img = photo ? `<img src="${esc(photo)}" alt="">` : '';
    const spread = next && next.market && isNum(Number(next.market.spread)) && next.market.spread !== null ? (side === 'home' ? 1 : -1) * Number(next.market.spread) : null;
    const hero = `<section class="kt-hero kt-order" style="${panelVars(colours)}" aria-label="${esc(`${data.name}, ${team.name || teamAbbr || ''} ${pos || ''}`)}">
      <div class="kt-panel">${photo ? `<div class="kt-ph" aria-hidden="true">${img}</div>` : ''}<span class="kt-logo" aria-hidden="true">${logoImg({ ...team, id: teamId }, league)}</span>
      <p class="kt-kick"><a href="#team/${esc(league)}/${esc(teamId)}">${esc(team.abbr || team.name || teamAbbr || '')}</a> ${esc(pos || '')} · ${thisSeason.length} game${thisSeason.length === 1 ? '' : 's'}</p>
      <h1 class="kt-name" style="--name-size:${nameSize(data.name, 56)}px">${esc(data.name)}</h1>
      <p class="kt-meta">${next ? `<span class="kt-discs">${disc(mine || team, league)}${disc(opp, league)}</span><span><b>${side === 'home' ? 'vs' : 'at'} ${esc(opp.name)}</b>${esc(ticketWhen(next.kickoff))}${spread != null ? `, ${esc(team.abbr || '')} ${esc(minus(`${spread > 0 ? '+' : ''}${spread}`))}` : ''}</span>` : '<span>No game scheduled in the window</span>'}</p></div>
      ${photo ? `<div class="kt-ph kt-photo" aria-hidden="true">${img}</div>` : ''}</section>`;
    const tabs = `<nav class="kt-tabs" aria-label="Stat">${options.filter(k => !k.startsWith('q1_')).map(k => `<button type="button" data-set="pstat:${esc(k)}" aria-pressed="${k === stat}"${TAB_SHORT[k] ? ` aria-label="${esc(PLAYER_LABEL[k] || k)}"` : ''}>${esc(TAB_SHORT[k] || PLAYER_LABEL[k] || k)}</button>`).join('')}</nav>${quarterKeys.length ? `<nav class="kt-tabs kt-quarter-tabs" aria-label="First-quarter stat">${quarterKeys.map(k => `<button type="button" data-set="pstat:${esc(k)}" aria-pressed="${k === stat}">${esc(PLAYER_LABEL[k])}</button>`).join('')}</nav>` : ''}`;
    /* Best price per side at the shown line, never from a row whose price failed the sanity check. */
    const sides = ['over', 'under'].map(d => pricedRows.filter(r => sameBook(r) && !r.priceSuspect && Number(r.line) === line && String(r.direction).toLowerCase() === d && C.quoteStatus(r, next?.kickoff, now).current)
      .sort((a, b) => b.odds - a.odds)[0]).map((r, i) => r && { dir: i ? 'under' : 'over', odds: r.odds, book: bookLabel(r.book), observedAt: r.observedAt });
    /* Unavailable, one side's price alone would read as a lean: print both sides at one price, else the line only. */
    const quoteBook = bookLabel((quote || {}).book) || (sides.find(Boolean) || {}).book;
    const pricesText = sides[0] && sides[1] && sides[0].odds === sides[1].odds && sides[0].book === sides[1].book ? `Both sides <b class="num">${esc(odd(sides[0].odds))}</b> at ${esc(sides[0].book)}.`
      : held ? (line != null ? `Main line <b class="num">${esc(valueText(line))}</b>${quoteBook ? ` at ${esc(quoteBook)}` : ''}.` : '')
      : sides.filter(Boolean).map(x => `${x.dir === 'over' ? 'Over' : 'Under'} <b class="num">${esc(odd(x.odds))}</b> at ${esc(x.book)}`).join(', ') + (sides.some(Boolean) ? '.' : '');
    const projectionValue = Array.isArray(projV) && isNum(projV[0]) ? projV[0] : null;
    const projectionDelta = projectionValue != null && line != null ? projectionValue - line : null;
    const projectionLabel = held ? 'Held' : projectionValue == null ? 'Not posted' : valueText(projectionValue);
    const edgeLabel = held || projectionDelta == null ? '–' : `${projectionDelta > 0 ? '+' : ''}${C.fixed(projectionDelta)}`;
    const projectionAgrees = projectionDelta == null || (dir === 'under' ? projectionDelta < 0 : projectionDelta > 0);
    const priceComparison = priced && priced.calibrated && priced.chance != null && priced.needs != null
      ? `<p class="kt-prices">${esc(dir === 'over' ? 'Over' : 'Under')} ${esc(valueText(line))} ${esc(odd(priced.odds))} at ${esc(priced.book)} · checked ${esc(ago(priced.src.observedAt))}</p><p class="kt-lead kt-chance" style="margin-top:8px"><span>Kook’n chance<b class="num">${pctOne(priced.chance)}</b></span><i></i><span>Break-even win rate<b class="num">${pctOne(priced.needs)}</b></span></p>${hasValue(priced) ? '<p class="kt-prices">✓ clears my price</p>' : ''}`
      : priced && projectionDelta != null
        ? `<p class="kt-prices"><b>${projectionAgrees ? 'Direction only.' : 'No Kook’n lean at this line.'}</b> ${projectionAgrees ? `The projection points ${esc(dir)}, but this price did not clear the model checks.` : `The projection is ${projectionDelta < 0 ? 'below' : 'above'} the ${esc(dir)} line.`}</p>`
        : '';
    const hitLabel = h && h.n ? `${h[dir]}/${h.n}` : '–';
    const unitFor = STAT_UNITS[isQuarter ? stat.slice(3) : stat] || [String(PLAYER_LABEL[stat] || stat).toUpperCase()];
    const windows = chartWindows(recent, win);
    const top = Math.max(1, line || 0, ...windows.flat().map(row => read(row, stat)).filter(isNum));
    const multiplePanels = windows.length > 1;
    const res = v => C.thresholdResult(v, line, dir);
    const md = r => new Date(`${r[1]}T12:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
    const chart = windows.length ? windows.map((shown, i) => {
      const sv = shown.map(row => read(row, stat));
      const label = multiplePanels ? chartWindowLabel(i ? windows[0].length : 0, shown.length, recent.length)
        : recent.length > shown.length ? `Last ${shown.length} of ${recent.length} games shown.` : '';
      const hits = sv.filter(v => res(v) === 'hit').length;
      const sample = sv.filter(isNum).length;
      return `<figure class="kt-chart" role="img" aria-label="${esc(`${PLAYER_LABEL[stat] || stat}: ${sv.map(v => isNum(v) ? v : 'not recorded').join(', ')}${line != null ? ` against the ${line} line` : ''}.`)}">
      <div class="kt-bars" aria-hidden="true">${sv.map(v => `<div class="col"><div class="bar ${res(v)}" style="height:${(isNum(v) ? Math.max(2, 112 * Math.max(0, v) / top) : 2).toFixed(1)}px"></div></div>`).join('')}${line != null ? `<div class="line" style="bottom:${(112 * line / top).toFixed(1)}px"><span>${esc(line)}</span></div>` : ''}</div>
      <div class="kt-x" aria-hidden="true">${shown.map((r, i) => `<span><em class="${res(sv[i])}">${isNum(sv[i]) ? esc(valueText(sv[i])) : '–'}</em><b>${r[7] === 0 ? '@' : ''}${esc(abbr(r[6]))}</b>${res(sv[i]) === 'hit' ? '✓ ' : res(sv[i]) === 'miss' ? '✗ ' : ''}${esc(md(r))}</span>`).join('')}</div>
      <figcaption class="kt-cap">${sample && line != null ? `<b>${hits} of ${sample} ${dir} ${esc(valueText(line))}.</b> ` : ''}${esc(label)}</figcaption></figure>`;
    }).join('') : '<p class="kt-cap">No stored games in this selection.</p>';
    const bettingNumbers = `<span><small>${lineLabel}</small><b class="num">${esc(valueText(line))}</b></span><span><small>Kook’n projection</small><b class="num">${esc(projectionLabel)}</b></span><span><small>Projection vs line</small><b class="num">${esc(edgeLabel)}</b></span><span><small>Recent hits</small><b class="num">${esc(hitLabel)}</b></span>`;
    const historyNumbers = `<span><small>Season average</small><b class="num">${seasonSummary ? esc(valueText(seasonSummary.avg)) : '–'}</b></span><span><small>Last 5 average</small><b class="num">${last5Summary ? esc(valueText(last5Summary.avg)) : '–'}</b></span><span><small>Season high</small><b class="num">${seasonHigh == null ? '–' : esc(valueText(seasonHigh))}</b></span><span><small>Games recorded</small><b class="num">${esc(seasonValues.length)}</b></span>`;
    const boardTitle = isQuarter ? `${PLAYER_LABEL[stat]} trend` : PLAYER_LABEL[stat] || stat;
    const boardEyebrow = isQuarter ? `${PLAYER_LABEL[stat]} · history` : line != null ? (held ? 'Unavailable · reference line' : lineStatus && lineStatus.current ? 'Current line' : 'Reference line') : 'Season snapshot';
    const sheet = `<section class="player-board" aria-labelledby="line-h"><div class="player-board-head"><div><p class="eyebrow">${esc(boardEyebrow)}</p><h2 id="line-h">${esc(boardTitle)}</h2></div><span class="player-board-mode">${line != null ? 'Book vs Kook’n' : 'Trend view'}</span></div>
      <div class="kt-number-grid kt-player-numbers">${line != null ? bettingNumbers : historyNumbers}</div>
      ${held ? `<span class="kt-stamp hold kt-player-hold" role="img" aria-label="Unavailable">${MARK.hold}UNAVAILABLE</span>` : ''}
      ${pricesText ? `<p class="kt-prices">${pricesText}</p>` : ''}
      ${!isQuarter && line == null ? `<p class="kt-prices"><b>Historical stats are available.</b> No current book line has been captured for ${next ? 'this matchup' : 'an upcoming game'} yet, so there is no line-based Kook’n projection to compare.</p>` : ''}
      ${held ? `<p class="kt-held">${esc(heldText)}</p>`
        : `${priceComparison}
          ${Array.isArray(projV) && isNum(projV[1]) && isNum(projV[2]) ? `<p class="kt-prices">Projected range ${esc(rangeText(projV[1]))}–${esc(rangeText(projV[2]))}.</p>` : ''}`}
      ${line != null ? '<div class="player-chart-legend" aria-label="Chart legend"><span class="hit"><i></i>Cleared line</span><span class="miss"><i></i>Missed line</span><span><i></i>Push or unknown</span></div>' : ''}
      ${chart}<div class="kt-stubrow"><p class="kt-season" style="font-size:13px">${esc(!isQuarter && lineStatus ? `${held && quote?.observedAt ? 'Reference line checked' : lineStatus.label}${quote && quote.observedAt ? ` · ${clock(quote.observedAt)}` : ''}` : showing)}</p></div></section>`;
    const insightRows = C.playerHistory(rows, currentSeason, scope, 'all');
    const insightValues = insightRows.map(row => read(row, stat)).filter(isNum);
    const insightScope = scope === 'all' ? 'All' : scope === 'current' ? 'Season' : String(scope);
    const footballWindow = playerWindowChart({ values: insightValues, line, dir, format: valueText, scopeLabel: insightScope });
    const receivingStat = /^(?:rec|recYds|targets|recTD|recLong)$/;
    const roleKey = isQuarter
      ? /(?:passYds|cmp|att)$/.test(stat) ? 'q1_att' : /rushYds|car$/.test(stat) ? 'q1_car' : /recYds|rec$/.test(stat) ? 'q1_rec' : null
      : pos === 'QB' ? (/^(?:passYds|cmp|att|passTD|int)$/.test(stat) ? 'att' : 'car')
        : ['RB', 'FB'].includes(pos) ? (receivingStat.test(stat) ? 'targets' : 'car')
          : ['WR', 'TE'].includes(pos) ? 'targets' : pos === 'PK' ? 'fga' : 'snapPct';
    const roleTitles = { att: 'Attempts trend', car: 'Carries trend', targets: 'Targets trend', fga: 'Field-goal attempts', snapPct: 'Snap share trend',
      q1_att: '1Q attempts trend', q1_car: '1Q carries trend', q1_rec: '1Q receptions trend' };
    const roleFormat = number => roleKey === 'snapPct' ? `${Math.round(100 * number)}%` : C.statValue(number, roleKey, Number.isInteger(number) ? 0 : 1);
    const roleEntries = roleKey ? insightRows.slice(-8).map(row => ({ value: read(row, roleKey), label: `${row[7] === 0 ? '@' : 'vs'} ${abbr(row[6])}`, short: abbr(row[6]) })) : [];
    const footballRole = roleKey && roleKey !== stat ? playerRoleChart({ title: roleTitles[roleKey], entries: roleEntries, format: roleFormat,
      note: isQuarter ? 'First-quarter workload only.' : 'Recent opportunity helps separate role changes from box-score noise.' }) : '';
    const footballComparison = playerComparisonChart({ items: [
      { label: quote?.book ? 'Book' : 'Chart line', value: line, kind: 'book' }, { label: 'Kook’n', value: held ? null : projectionValue, kind: 'kookn' },
      { label: 'L5 avg', value: meanOf(insightValues.slice(-5)) }, { label: 'L10 avg', value: meanOf(insightValues.slice(-10)) },
      { label: scope === 'all' ? 'All avg' : scope === 'current' ? 'Season' : String(scope), value: meanOf(insightValues) },
      { label: 'Opp vs pos', value: !isQuarter && allow ? allow.value : null }
    ], format: valueText });
    const footballInsights = `<div class="player-insights">${footballWindow}${footballRole}${footballComparison}</div>`;
    /* GameGrid-inspired what-if research, using only Kook'n's stored results. Alternate rows are not represented
       as available book markets: only the exact captured quote gets the Book label. */
    const ladderRows = C.playerHistory(rows, currentSeason, scope, 'all');
    const ladderValues = ladderRows.map(r => read(r, stat)).filter(isNum);
    const ladderStep = /passYds/.test(stat) ? 25 : /(?:rushYds|recYds)/.test(stat) ? 10 : /Long/.test(stat) ? 5
      : /(?:cmp|att)/.test(stat) ? 2 : 1;
    const ladderMiddle = line != null ? line : !held && projectionValue != null ? Math.max(.5, Math.round(projectionValue) - .5)
      : summary && isNum(summary.median) ? Math.max(.5, Math.floor(summary.median) + .5) : null;
    const ladderLines = ladderMiddle == null ? [] : [...new Set([-2, -1, 0, 1, 2].map(n => Math.max(.5, ladderMiddle + n * ladderStep)))].sort((a, b) => a - b);
    const ladderWindow = (list, threshold) => { const sample = list.filter(isNum), counts = C.hits(sample, threshold), hits = counts[dir];
      return { hits, games: counts.n, pct: counts.n ? Math.round(100 * hits / counts.n) : null }; };
    const ladderCell = x => `<td>${x.pct == null ? '–' : `${x.pct}%`}<span>${x.games ? `${x.hits}/${x.games}` : 'no games'}</span></td>`;
    const scopeHead = scope === 'current' ? 'Season' : scope === 'all' ? 'All' : String(scope);
    const lineLab = ladderLines.length && ladderValues.length ? `<section class="line-lab" aria-labelledby="line-lab-h"><div class="line-lab-head"><div><p class="eyebrow">What-if research</p><h2 id="line-lab-h">Line ladder</h2><p>How often did ${esc(data.name)} ${dir === 'under' ? 'stay below' : 'clear'} nearby numbers?</p></div><span class="line-lab-direction">${esc(dir)}</span></div>
      <table class="line-lab-table"><thead><tr><th scope="col">Line</th><th scope="col">L5</th><th scope="col">L10</th><th scope="col">${esc(scopeHead)}</th></tr></thead><tbody>${ladderLines.map(threshold => { const isBook = line != null && Number(threshold) === Number(line);
        return `<tr${isBook ? ' class="book"' : ''}><th scope="row">${esc(valueText(threshold))}${isBook ? '<span class="line-lab-tag">Book</span>' : ''}</th>${ladderCell(ladderWindow(ladderValues.slice(-5), threshold))}${ladderCell(ladderWindow(ladderValues.slice(-10), threshold))}${ladderCell(ladderWindow(ladderValues, threshold))}</tr>`; }).join('')}</tbody></table>
      <p class="line-lab-note">${projectionValue != null && !held ? `Kook’n projects ${esc(valueText(projectionValue))}. ` : ''}History at hypothetical thresholds—not offered lines, prices, or betting probabilities.</p></section>` : '';
    const tds = recent.reduce((n, r) => n + (read(r, 'passTD') || 0), 0), ints = recent.reduce((n, r) => n + (read(r, 'int') || 0), 0), any = recent.reduce((n, r) => n + (read(r, 'anyTD') || 0), 0);
    const big = summary ? `<div class="kt-big"><p><b class="num">${esc(valueText(summary.avg))}</b>${esc(word)} a game</p><p class="rest">Median ${esc(valueText(summary.median))}.${!isQuarter && pos === 'QB' ? ` ${tds} TD, ${ints} INT.` : !isQuarter && any ? ` ${any} TD.` : ''}</p></div>` : '';
    const matchup = allow ? `<p class="kt-matchup"><b>${esc(opp.abbr || opp.name)} allows ${esc(valueText(allow.value))} ${esc(word)} a game</b> to ${esc(group)}s, over ${esc(defGames(dRows, opp.id, group, stat))} games: ${allow.rank} of ${allow.of}${league === 'CFB' ? ' FBS defenses' : ''}, 1 allows the least.${verdict && !held ? ` That ${verdict === 'supports' ? 'supports' : 'works against'} the ${dir}.` : ''}${vs && vs.summary ? ` He averaged ${esc(valueText(vs.summary.avg))} in ${vs.summary.n} meeting${vs.summary.n === 1 ? '' : 's'} with them.` : ''}</p>` : '';
    const LOG_VIEW = { QB: [['C/A', r => `${read(r, 'cmp') ?? '–'}/${read(r, 'att') ?? '–'}`], ['TD-INT', r => `${read(r, 'passTD') ?? '–'}-${read(r, 'int') ?? '–'}`]],
      RB: [['Car', r => read(r, 'car')], ['Rec', r => read(r, 'rec')]], WR: [['Tgt', r => read(r, 'targets')], ['Rec', r => read(r, 'rec')]], PK: [['FG', r => `${read(r, 'fgm') ?? '–'}/${read(r, 'fga') ?? '–'}`], ['XP', r => read(r, 'xpm')]] };
    const quarterView = pos === 'QB' ? [['C/A', r => `${read(r,'q1_cmp') ?? '–'}/${read(r,'q1_att') ?? '–'}`]] : [['Car', r => read(r,'q1_car')], ['Rec', r => read(r,'q1_rec')]];
    const view = (isQuarter ? quarterView : LOG_VIEW[pos] || LOG_VIEW[pos === 'FB' ? 'RB' : 'WR']).filter(([label]) => !(label === 'Rec' && stat === 'rec') && !(label === 'Car' && stat === 'car'));
    const chalkLog = log.length ? `<table class="kt-log"><thead><tr><th scope="col">Game</th>${view.map(([label]) => `<th scope="col">${esc(label)}</th>`).join('')}<th scope="col">${esc(unitFor[unitFor.length - 1])}</th></tr></thead><tbody>${log.map(r => { const v = read(r, stat);
      return `<tr><th scope="row"><a class="plain-link" href="#game/${esc(league)}-${esc(r[0])}"><b>${r[7] === 0 ? 'at' : 'vs'} ${esc(abbr(r[6]))}</b></a><span>${esc(md(r))}${r[4] === 3 ? ', postseason' : ''}</span></th>${view.map(([, f]) => `<td>${esc(f(r) ?? '–')}</td>`).join('')}<td class="y">${v == null ? '–' : esc(valueText(v))}</td></tr>`; }).join('')}</tbody></table>` : '<p class="kt-cap">No games to show.</p>';
    const q1GameIds = new Set(recent.map(r => String(r[0])));
    const q1Rows = league === 'NFL' ? (data.firstQuarter || []).filter(r => r.seasonType === 2 &&
      q1GameIds.has(String(r.eventId)) && (scope === 'all' || Number(r.season) === Number(scope === 'current' ? currentSeason : scope)))
      .sort((a, b) => String(a.date).localeCompare(String(b.date))) : [];
    const q1ByGame = new Map(q1Rows.map(r => [String(r.eventId), r]));
    const q1Shown = recent.map(r => q1ByGame.get(String(r[0])) || { eventId: r[0], date: r[1], opp: r[6], stats: {}, source: `https://www.espn.com/nfl/game/_/gameId/${r[0]}` })
      .sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const q1Cols = pos === 'QB' ? [['cmp','passYds','Passing','completions'],['car','rushYds','Rushing','carries']] : [['car', 'rushYds', 'Rushing', 'carries'], ['rec', 'recYds', 'Receiving', 'catches']];
    const q1Sample = k => q1Shown.filter(r => isNum(r.stats?.[k])).length;
    const q1Average = k => { const v = q1Shown.map(r => r.stats?.[k]).filter(isNum);
      return v.length ? C.fixed(v.reduce((a, b) => a + b, 0) / v.length) : '–'; };
    const q1Games = n => `${n} game${n === 1 ? '' : 's'}`;
    const q1 = league === 'NFL' ? `<section class="kt-quarter" id="first-quarter" aria-labelledby="q1-heading">
      <div class="kt-sec-head"><h2 class="kt-tape" id="q1-heading">First quarter</h2><span class="kt-kind">${esc(scopeLabel)}</span></div>
      <p class="kt-quarter-coverage">${q1Rows.length ? `${q1Rows.length} of ${recent.length} selected games available` : 'No first-quarter games available yet'}<span>Game stats · not projections</span></p>
      ${q1Shown.length ? `<div class="kt-quarter-summary">${q1Cols.map(([count, yards, label, unit]) => `<div><span class="kt-quarter-label">${label} · 1Q average</span><p><b class="num">${esc(q1Average(yards))}</b> yards</p><small>${esc(q1Average(count))} ${unit} per game${count === 'cmp' ? ` · ${esc(q1Average('att'))} attempts` : ''}</small><span class="kt-quarter-sample">Yards: ${q1Games(q1Sample(yards))} · ${unit}: ${q1Games(q1Sample(count))}</span></div>`).join('')}</div>
      <table class="kt-log kt-quarter-log"><thead><tr><th scope="col">Game</th>${q1Cols.map(([, , label]) => `<th scope="col">${label === 'Passing' ? 'Pass' : label === 'Rushing' ? 'Rush' : 'Rec'} yards</th>`).join('')}</tr></thead><tbody>
      ${q1Shown.slice().reverse().map(r => `<tr><th scope="row"><a class="plain-link" href="${esc(r.source)}" target="_blank" rel="noopener"><b>${esc(abbr(r.opp))} ↗</b></a><span>${esc(new Date(r.date + 'T16:00:00Z').toLocaleDateString('en-US', {month:'short', day:'numeric', timeZone:'UTC'}))}</span></th>${q1Cols.map(([count, yards, , unit]) => `<td><b>${isNum(r.stats?.[yards]) ? esc(r.stats[yards]) : '–'}</b><span>${isNum(r.stats?.[count]) ? esc(r.stats[count]) : '–'} ${count === 'cmp' ? `/${isNum(r.stats?.att) ? esc(r.stats.att) : '–'} comp/att` : r.stats?.[count] === 1 ? (unit === 'carries' ? 'carry' : 'catch') : unit}</span></td>`).join('')}</tr>`).join('')}
      </tbody></table>` : '<p class="kt-cap">Verified rushing and receiving stats will appear here as games are added.</p>'}
      <details class="plain-fold kt-quarter-source"><summary>Coverage &amp; sources</summary><p class="small muted">First quarter only. Passing, rushing and receiving. nflverse and ESPN play-by-play checked against full-game player and team totals. Missing stats show a dash, never zero. Averages use only available games for each stat; season and game filters apply. These are not projections or betting probabilities.${q1Rows.length ? ` Latest source check ${esc(clock(q1Rows[q1Rows.length - 1].checkedAt))}.` : ''}</p></details></section>` : '';

    return `<a class="kt-back" href="#research/players?pl=${esc(league)}">‹ Research</a>${hero}${tabs}${sheet}${footballInsights}${lineLab}
      ${filtersFold('player', showing, `${seasonSelect}${seg('pwin', [['all', 'All games'], ['last5', 'Last 5'], ['last10', 'Last 10'], ['last20', 'Last 20']], win)}`)}
      ${!recent.length ? `<p class="btn-row">${seasons.filter(x => x !== Number(currentSeason)).slice(0, 1).map(x => `<button type="button" class="btn small" data-set="pseason:${x}">Show ${x}</button>`).join('')}<button type="button" class="btn small" data-set="pseason:all">All seasons</button></p>` : ''}
      <details class="plain-fold kt-player-detail" data-box="player-context"><summary>Why this number</summary>${big}${matchup}${opponentTrend && opponentTrendText(opponentTrend) ? `<p class="kt-matchup ${opponentTrend.opponentAdjustment?.against ? 'red' : ''}">${esc(opponentTrendText(opponentTrend))}</p>` : ''}</details>
      <div class="btn-row" style="margin-top:14px">${watchButton({ type: 'player', key: `player:${league}:${route.id}`, title: data.name, league, href: `#player/${league}/${route.id}` })}<a class="btn small" href="${esc(shareHref)}" data-copy-link>Copy link</a></div>
      <section class="kt-page-sec"><div class="kt-sec-head"><h2 class="kt-tape">Game log</h2><span class="kt-kind">${esc(scope === 'current' ? 'Regular season' : scopeLabel)}</span></div>${chalkLog}
      <details class="plain-fold" data-box="player-every"><summary>${isQuarter ? 'Every full-game stat' : 'Every stat'}</summary>${log.length ? `<div class="table-wrap"><table class="t"><thead><tr><th>Game</th>${cols.map(k => `<th class="n">${esc(PLAYER_LABEL[k] || k)}</th>`).join('')}</tr></thead><tbody>${log.map(r =>
        `<tr><td><a href="#game/${esc(league)}-${esc(r[0])}">${esc(r[1])}</a><br><span class="tiny muted">${esc(where(r))} ${esc(abbr(r[6]))}${r[4] === 3 ? ' · postseason' : ''}</span></td>${cols.map(k => { const v = C.observedStat(r, keys, k); return `<td class="n">${v == null ? '<span class="muted">–</span>' : k === 'snapPct' ? Math.round(100 * v) + '%' : esc(v)}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div><p class="small muted" style="margin-top:6px">A dash means not recorded, never zero.</p>` : ''}</details>
      <details class="plain-fold" data-box="player-splits"><summary>Splits</summary><div class="kpis"><div class="kpi"><small>Home</small><b class="num">${esc(split.home ? valueText(split.home.avg) : '–')}</b><span>${split.home ? split.home.n : 0} game${split.home && split.home.n === 1 ? '' : 's'}</span></div><div class="kpi"><small>Away</small><b class="num">${esc(split.away ? valueText(split.away.avg) : '–')}</b><span>${split.away ? split.away.n : 0} game${split.away && split.away.n === 1 ? '' : 's'}</span></div>${split.neutral ? `<div class="kpi"><small>Neutral site</small><b class="num">${esc(valueText(split.neutral.avg))}</b><span>${split.neutral.n} game${split.neutral.n === 1 ? '' : 's'}</span></div>` : ''}</div></details></section>${q1}`;
  };

  views.basketballMilestones = async route => {
    const league = route.league === 'CBB' || state.league === 'CBB' ? 'CBB' : 'NBA';
    const [index, basketball, props] = await Promise.all([
      get(`app/players/${league}.json`),
      get(league === 'NBA' ? 'app/nba.json' : 'app/cbb.json'),
      league === 'NBA' ? maybe('app/nba-props.json') : Promise.resolve(null)
    ]);
    const future = (basketball.games || []).filter(game => (!game.status || game.status === 'scheduled') && Date.parse(game.kickoff) > Date.now())
      .sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    const slateDay = future.length ? C.dayOf(future[0].kickoff) : null;
    const slate = future.filter(game => !slateDay || C.dayOf(game.kickoff) === slateDay);
    if (!slate.length) return empty(`No ${league} matchups are on the current board`, 'The threshold board appears when the next scheduled slate and current-season player histories are available.', 'research');
    const teamIds = new Set(slate.flatMap(game => Object.values(game.teams || {}).map(team => String(team.id))));
    const slateAt = Date.parse(slate[0].kickoff), activeAfter = new Date(slateAt - 21 * 86400000).toISOString().slice(0, 10);
    const eligible = (index.players || []).filter(entry => teamIds.has(String(entry[3])) && Number(entry[6]) >= 5 && String(entry[5] || '') >= activeAfter);
    const shardIds = [...new Set(eligible.map(entry => C.shardOf(entry[0], index.shards)))];
    const shards = await Promise.all(shardIds.map(id => get(`app/players/${league}/${id}.json`)));
    const shardById = new Map(shardIds.map((id, i) => [id, shards[i]]));
    const entryById = new Map(eligible.map(entry => [String(entry[0]), entry]));
    const STAT = {
      pts: { label: 'PTS', word: 'points', steps: [5, 10, 15, 20, 25, 30] },
      reb: { label: 'REB', word: 'rebounds', steps: [2, 4, 6, 8, 10, 12] },
      ast: { label: 'AST', word: 'assists', steps: [2, 4, 6, 8, 10, 12] },
      fg3m: { label: '3PM', word: 'threes', steps: [1, 2, 3, 4, 5] }
    };
    const priced = (props?.rows || []).filter(row => Date.parse(row.kickoff) > Date.now());
    const prices = new Map(priced.map(row => [`${row.eventId}|${row.athleteId}|${row.stat}`, row]));
    const availabilityHolds = new Set(priced.filter(C.basketballAvailabilityHold).map(row => `${row.eventId}|${row.athleteId}`));
    const count = (values, threshold) => ({ hits: values.filter(value => isNum(value) && value >= threshold).length, games: values.filter(isNum).length });
    const cell = (label, result) => `<span class="milestone-rate"><small>${label}</small><b>${result.hits}/${result.games}</b></span>`;
    const playerRows = new Map();
    for (const entry of eligible) {
      const id = String(entry[0]), shard = shardById.get(C.shardOf(id, index.shards)), data = shard?.players?.[id];
      if (!data) continue;
      const rows = (data.rows || []).filter(row => Number(row[2]) === Number(index.season) && Number(row[4]) === 2)
        .sort((a, b) => String(a[1]).localeCompare(String(b[1])));
      if (rows.length < 5) continue;
      /* Basketball rows carry an opponent abbreviation after the shared eight-field
         prefix, so their stat payload starts at 9 (the player page uses the same schema). */
      const value = (row, stat) => { const i = (shard.keys || []).indexOf(stat); return i < 0 || !isNum(row[9 + i]) ? null : Number(row[9 + i]); };
      const recentMinutes = rows.slice(-5).map(row => value(row, 'min')).filter(isNum);
      const minuteAvg = recentMinutes.length ? recentMinutes.reduce((sum, number) => sum + number, 0) / recentMinutes.length : null;
      const projectedMinutes = isNum(data.projection?.minutes) ? Number(data.projection.minutes) : null;
      if (Math.max(minuteAvg || 0, projectedMinutes || 0) < 12) continue;
      const candidates = [];
      for (const [stat, meta] of Object.entries(STAT)) {
        const season = rows.map(row => value(row, stat)).filter(isNum);
        if (season.length < 5) continue;
        const threshold = meta.steps.filter(step => count(season, step).hits / season.length >= .9).pop();
        if (threshold == null) continue;
        const seasonResult = count(season, threshold), l10 = count(season.slice(-10), threshold), l5 = count(season.slice(-5), threshold);
        candidates.push({ id, entry, data, stat, meta, threshold, season: seasonResult, l10, l5, minuteAvg, projectedMinutes,
          projection: isNum(data.projection?.values?.[stat]) ? Number(data.projection.values[stat]) : null });
      }
      candidates.sort((a, b) => (b.threshold / b.meta.steps[b.meta.steps.length - 1]) - (a.threshold / a.meta.steps[a.meta.steps.length - 1])
        || b.season.hits / b.season.games - a.season.hits / a.season.games);
      playerRows.set(id, candidates.slice(0, 2));
    }
    const teamRows = teamId => eligible.filter(entry => String(entry[3]) === String(teamId)).flatMap(entry => playerRows.get(String(entry[0])) || [])
      .sort((a, b) => (b.projectedMinutes || b.minuteAvg || 0) - (a.projectedMinutes || a.minuteAvg || 0)
        || String(a.entry[1]).localeCompare(String(b.entry[1]))).slice(0, 14);
    let firstRendered = true;
    const renderedGames = slate.map(game => {
      const sides = ['away', 'home'].map(side => ({ side, team: game.teams?.[side], rows: teamRows(game.teams?.[side]?.id) }));
      if (!sides.some(side => side.rows.length)) return '';
      const teamBlock = ({ team, rows }) => `<section class="milestone-team"><h3>${teamMark(team, 'sm', league)} ${esc(team?.name || team?.abbreviation || 'Team')}</h3>${rows.length ? rows.map(item => {
        const playerKey = `${game.providerId || String(game.id || '').replace(/^\w+-/, '')}|${item.id}`;
        const price = prices.get(`${playerKey}|${item.stat}`);
        const held = price?.hold || availabilityHolds.has(playerKey);
        const projection = held ? null : price ? price.projection?.value : item.projection;
        const chartLine = item.threshold - .5;
        const odds = isNum(price?.over) ? oddsText(price.over) : null;
        const fresh = price && Date.now() - Date.parse(price.sourceAt) >= 0 && Date.now() - Date.parse(price.sourceAt) <= 4 * 3600000;
        const comparison = price ? `<b>${price.line === chartLine ? 'Book' : 'Book main line'} ${esc(price.line)} ${odds ? `· ${esc(odds)}` : ''}${isNum(projection) ? ` · Kook’n ${esc(C.statValue(projection, item.stat))}` : held ? ' · Projection held' : ''}</b><span>${price.line !== chartLine ? 'Milestone price not verified · ' : ''}${fresh ? `Checked ${esc(ago(price.sourceAt))}` : 'Earlier quote · recheck price'}</span>`
          : `<b>${isNum(projection) ? `Kook’n ${esc(C.statValue(projection, item.stat))}` : held ? 'Projection held' : 'No current comparison'}</b><span>Milestone price not verified</span>`;
        const href = esc(C.playerLineHref({ league, athleteId: item.id, stat: item.stat, line: chartLine, direction: 'over',
          book: price?.line === chartLine && odds ? bookLabel(price.book) : null, gameId: game.id }));
        const role = `${item.entry[2] || ''}${isNum(item.minuteAvg) ? ` · L5 ${item.minuteAvg.toFixed(1)} MIN` : ''}`;
        return `<div class="milestone-row"><a class="milestone-player" href="${href}"><b>${esc(item.entry[1])} <span class="milestone-mark">${esc(item.threshold)}+ ${esc(item.meta.label)}</span></b><span>${esc(role)} · tap for game chart</span></a>${cell('L5', item.l5)}${cell('L10', item.l10)}${cell('Season', item.season)}<span class="milestone-compare">${comparison}</span></div>`;
      }).join('') : '<p class="small muted" style="padding:8px 0 12px">No 90% milestone cleared the role and sample checks.</p>'}</section>`;
      const open = firstRendered; firstRendered = false;
      return `<details class="milestone-game"${open ? ' open' : ''}><summary class="milestone-game-head"><h2>${esc(game.teams?.away?.shortName || game.teams?.away?.name || 'Away')} at ${esc(game.teams?.home?.shortName || game.teams?.home?.name || 'Home')}</h2><span>${esc(whenShort(game.kickoff))}</span></summary>${sides.map(teamBlock).join('')}</details>`;
    }).filter(Boolean);
    if (!renderedGames.length) return empty(`No ${league} 90% thresholds passed the checks`, 'Players need at least five current-season games and a recent role of 12 or more minutes. The board will fill in as the sample grows.', 'research');
    return `<div class="milestone-intro"><p><b>Historical hit rate · not a probability.</b> Each row shows the highest common threshold that landed in at least 90% of this season’s recorded games.</p><p class="small muted">A 10+ milestone is charted against 9.5 so an exact 10 counts correctly. Book lines are separate current comparisons—not prices for the milestone. Verify every line, price, injury and role in your sportsbook.</p></div><div class="milestone-games">${renderedGames.join('')}</div><div class="card on-felt milestone-foot"><p class="small"><b>How to use this:</b> Tap any threshold for the player’s recent-game bar chart, exact line, game log, minutes trend and Kook’n projection. Trivial low-minute results are filtered out; a player still appearing here does not make the next game certain.</p></div>`;
  };

  views.basketballPlayers = async route => {
    const league = route.league === 'CBB' || state.league === 'CBB' ? 'CBB' : 'NBA';
    const query = String(state.players.q || '').trim().toLowerCase();
    const [index, props, schedule] = await Promise.all([
      get(`app/players/${league}.json`),
      league === 'NBA' ? maybe('app/nba-props.json') : null,
      league === 'NBA' && query ? maybe('app/nba.json') : null,
    ]);
    const players = (index.players || []).filter(entry => C.researchMatches(query, entry[1], entry[4], entry[2]));
    const statName = key => ({ pts:'Points', reb:'Rebounds', ast:'Assists', fg3m:'Threes', pra:'Pts + reb + ast', pa:'Pts + assists', pr:'Pts + rebounds', ra:'Rebounds + assists' }[key] || key);
    const search = `<div class="toolbar prop-toolbar"><div class="grow"><label class="sr" for="bpq">Find a player or team</label><input id="bpq" class="search" type="search" placeholder="Find ${league} players or teams" value="${esc(state.players.q)}" data-input="pq" autocomplete="off" maxlength="160"></div></div>`;
    const now = Date.now();
    const complete = await C.nbaUpcomingProps(get, schedule, now);
    const available = (complete ?? props?.rows ?? []).filter(row => Date.parse(row.kickoff) > now);
    const playerGameKey = row => `${row.eventId}|${row.athleteId}`;
    const holds = new Set(available.filter(C.basketballAvailabilityHold).map(playerGameKey));
    const common = new Set(['pts','reb','ast','fg3m','pra','pa','pr','ra']);
    const comparisons = available.filter(row => common.has(row.stat) && isNum(row.line)
      && C.researchMatches(query, row.name, row.teamAbbr, row.teamName, statName(row.stat))).map(row => {
      const held = Boolean(row.hold || holds.has(playerGameKey(row)));
      const projection = held ? null : row.projection?.value;
      const direction = row.side === 'under' ? 'under' : 'over';
      const quote = C.quoteStatus({ ...row, observedAt: row.sourceAt, odds: row[direction], state: 'open' }, row.kickoff, now);
      const gap = isNum(projection) ? projection - row.line : null;
      return { row, held, projection, gap, direction, quote, lean: Boolean(row.favorite && !held && quote.current && gap != null) };
    }).sort((a, b) => Number(b.lean) - Number(a.lean) || Number(b.quote.current) - Number(a.quote.current)
      || Number(b.gap != null) - Number(a.gap != null) || Math.abs(b.gap ?? 0) - Math.abs(a.gap ?? 0)
      || String(a.row.kickoff).localeCompare(String(b.row.kickoff))).slice(0, 18);
    const photo = (id, label) => `<span class="ava sm" aria-hidden="true"><img src="https://a.espncdn.com/i/headshots/${league === 'NBA' ? 'nba' : 'mens-college-basketball'}/players/full/${encodeURIComponent(id)}.png" loading="lazy" alt=""><em>${esc(label || '')}</em></span>`;
    const board = comparisons.map(({ row, held, projection, gap, direction, quote, lean }) => {
      const odds = row[direction];
      const price = [isNum(odds) ? `${direction === 'under' ? 'Under' : 'Over'} ${oddsText(odds)}` : 'Odds unavailable', bookLabel(row.book)].filter(Boolean).join(' · ');
      const checked = quote.current ? `Checked ${ago(row.sourceAt)}` : quote.label;
      const history = held ? '' : C.nbaPropHistory(row, direction);
      const href = esc(C.playerLineHref({ league, athleteId: row.athleteId, stat: row.stat, line: row.line, direction,
        book: bookLabel(row.book), gameId: row.eventId ? `NBA-${row.eventId}` : null }));
      return `<a class="receipt plain-link" style="grid-template-columns:42px minmax(0,1fr) auto" href="${href}">${photo(row.athleteId, row.teamAbbr)}<div><b>${esc(row.name)} · ${esc(statName(row.stat))}</b><span>${esc(row.teamAbbr || '')} · ${esc(whenShort(row.kickoff))}</span><span>${esc(price)} · ${esc(checked)}</span>${history ? `<span>History · ${esc(history)}</span>` : ''}${held ? `<span>${esc(row.hold || 'Availability review')}</span>` : ''}${lean ? '<span class="green">Research lean</span>' : ''}</div><div class="n"><b class="num">${esc(row.line)}</b><span>${quote.current ? 'Book' : 'Saved line'}</span><b class="num">${isNum(projection) ? esc(C.statValue(projection, row.stat)) : 'Held'}</b><span>${gap == null ? 'Kook’n' : `${gap > 0 ? '+' : ''}${C.fixed(gap)} vs line`}</span></div></a>`;
    }).join('');
    const directory = players.slice().sort((a, b) => String(b[5]).localeCompare(String(a[5]))
      || String(a[1]).localeCompare(String(b[1]))).slice(0, 24);
    const browse = directory.map(entry => {
      const baseline = league === 'CBB' ? entry[7] : null;
      const values = baseline?.values;
      return `<a class="receipt plain-link" style="grid-template-columns:42px minmax(0,1fr) auto" href="#player/${league}/${esc(entry[0])}?stat=pts">${photo(entry[0], entry[4])}<div><b>${esc(entry[1])}</b><span>${esc(entry[4] || league)} · ${esc(entry[2] || 'Position unavailable')}</span><span>${esc(entry[6])} recorded game${entry[6] === 1 ? '' : 's'} · through ${esc(entry[5] || '–')}</span></div><div class="n">${values ? `<b>${baseline.status === 'early' ? 'Early Kook’n' : 'Kook’n'}</b>${['pts','reb','ast'].filter(stat => isNum(values[stat])).map(stat => `<span>${esc(C.statValue(values[stat], stat))} ${stat.toUpperCase()}</span>`).join('')}` : '<b>Game log</b><span>L5/L10 · minutes</span>'}</div></a>`;
    }).join('');
    const directoryBody = browse ? `<div class="receipts">${browse}</div>${players.length > directory.length ? `<p class="small muted">Showing ${directory.length} of ${players.length}. Search to narrow the list.</p>` : ''}`
      : '<p class="small muted">No recorded player matches this search.</p>';
    const playerDirectory = board && !query ? `<details class="more-box"><summary>Player directory · ${players.length}</summary>${directoryBody}</details>`
      : `<section class="kt-sec"><h2>Player directory</h2>${directoryBody}</section>`;
    return `${search}<section class="kt-sec"><div class="kt-sec-head"><h2 class="kt-head">${league} prop finder</h2></div>${board ? `<div class="receipts">${board}</div>` : league === 'NBA' && !query ? '<p class="small muted">No captured comparisons for upcoming games. Browse recorded player games below.</p>' : ''}</section>${playerDirectory}`;
  };

  return views;
});
