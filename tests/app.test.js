'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../site/core.js');

test('game research is independent of posted plays and shows exact comparisons with cautions', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const body = source.match(/const modelReadsSection = \(card, detail\) => \{([\s\S]*?)\n  \};/)[1];
  const render = new Function('C', 'esc', 'ago', 'whenShort', 'section', 'card', 'detail', body);
  const html = render(C, C.esc, C.ago, C.whenShort, (title, text) => title + text,
    { league: 'NFL', state: 'pre', kickoff: '2099-10-05T00:20:00Z' },
    { favoriteLines: [], picks: [], modelReads: [{ title: 'Player over 25.5 receiving yards', athleteId: '1',
      comparison: 'We project 35 vs 25.5', performanceCaution: true, warnings: ['Higher bar'],
      observedAt: new Date().toISOString(), snapshotAt: new Date().toISOString(), odds: -110, book: 'FanDuel',
      history: { season: { hits: 3, games: 4 } } }] });
  assert.match(html, /Player over 25.5/);
  assert.match(html, /We project 35 vs 25.5/);
  assert.match(html, /3\/4 this season/);
  assert.match(html, /Higher bar/);
  assert.match(html, /#player\/NFL\/1/);
  assert.match(source, /C.filterTrends\(detail.seasonTrends/);
  assert.doesNotMatch(source, /No qualifying streak sheet/);
});

test('a qualifying Upset Watch renders percentages without relying on another view’s local helpers', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const body = source.match(/const upsetRow = \(game, rank = null\) => \{([\s\S]*?)\n  \};/)[1];
  const render = new Function('C', 'esc', 'odds', 'whenShort', 'ago', 'game', 'rank', body);
  const html = render(C, C.esc, C.odds, C.whenShort, C.ago, {
    id: 'NFL-test', league: 'NFL', kickoff: '2026-10-04T17:00:00Z',
    upsetWatch: {team: 'Underdog', odds: 160, opponentOdds: -192, book: 'DraftKings',
      modelChance: .6, marketChanceNoVig: .369, observedAt: '2026-10-02T16:00:00Z',
      reasons: ['Our score has Underdog 27.0, Favorite 23.0 — Underdog by 4.0'],
      warnings: ['Raw model estimate, not a calibrated value bet']}
  }, 1);
  assert.match(html, /Our chance 60%/);
  assert.match(html, /market 37%/);
  assert.match(html, /not a calibrated value bet/);
  assert.match(html, />Why</);
  assert.match(html, /Underdog by 4.0/);
  assert.match(html, /Top upset signal/);
  assert.match(html, /#game\/NFL-test/);
});

test('Underdog Watch stays visible and separates outright winners from spread covers', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /const underdogWatch = \(games, board\) =>/);
  assert.match(source, /Outright upset candidates/);
  assert.match(source, /Underdog spread value/);
  assert.match(source, /Covering does not mean winning outright/);
  assert.match(source, /Top upset signal/);
  assert.match(source, /\$\{underdogWatch\(now, board\)\}/,
    'the Today page renders the permanent section without a qualifying-candidate conditional');
});

test('confidence labels rank calibrated chances without calling them locks', () => {
  const rows = C.rankConfidence([
    { id: 'value', title: 'B', grade: { calibrated: true, tier: 'strong', chance: .55, edge: 8 } },
    { id: 'chance', title: 'A', grade: { calibrated: true, tier: 'lean', chance: .59, edge: 3 } },
    { id: 'thin', title: 'C', grade: { calibrated: true, tier: 'lean', chance: .70, edge: 4, thin: true } },
    { id: 'unpriced', title: 'D', state: 'unpriced', grade: { calibrated: true, tier: 'lean', chance: .80, edge: 5 } },
  ]);
  assert.equal(rows.find(row => row.id === 'chance').confidenceRank, 1);
  assert.equal(rows.find(row => row.id === 'value').confidenceRank, 2);
  assert.equal(rows.find(row => row.id === 'thin').confidenceRank, undefined);
  assert.equal(rows.find(row => row.id === 'unpriced').confidenceRank, undefined);
  assert.equal(rows.slice(0, 2).sort(C.byConfidence)[0].id, 'chance');
  assert.equal([rows[0], rows[2]].sort(C.byConfidence)[0].id, 'value',
    'a qualifying value read sorts ahead of a higher raw chance that failed the thin-data gate');
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /Highest confidence/);
  const board = source.slice(source.indexOf('async function viewBoard(route)'), source.indexOf('async function viewTicket()'));
  assert.doesNotMatch(board, /lock\b/i);
});

test('Today keeps the season scorecard above secondary lines and removes the duplicate record block', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const today = source.slice(source.indexOf('async function viewToday()'), source.indexOf('const modelCard ='));
  assert.ok(today.indexOf('scorecardCard(scoreboard') < today.indexOf('research-heading'));
  assert.doesNotMatch(today, /transparent-record/);
  assert.equal((today.match(/scorecardCard\(/g) || []).length, 1, 'Today renders one prominent scorecard');
});

test('official plays render as a compact collapsed list with details on demand', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const card = source.slice(source.indexOf('const playCard = p =>'), source.indexOf('/* The one record'));
  const css = fs.readFileSync('site/app.css', 'utf8');
  assert.doesNotMatch(card, /matchMedia|\$\{open\}/, 'play cards never auto-expand by viewport');
  assert.match(card, /<details data-persist="pick-/);
  assert.match(card, /View details/);
  assert.match(css, /\.plays \{ display: grid; grid-template-columns: 1fr;/);
  assert.match(css, /\.play-compact-meta \{ display: block !important;/);
});

test('board navigation highlights the selected line view and offers a fast favorites view', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /href="#board\/favorites" \$\{active === 'favorites' \? 'aria-current="page"'/);
  assert.match(source, /href="#board\/props" \$\{active === 'props' \? 'aria-current="page"'/);
  assert.match(source, /boardTabs\(favorites \? 'favorites' : props \? 'props' : 'lines'\)/);
  assert.match(source, /No best line right now/);
});

test('Trends opens on upcoming main lines and supports season, Last 10 and Last 5 windows', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /trendKind: 'main', trendWindow: 'season'.*trendDay: 'all'/);
  assert.match(source, /C\.trendWindow\(C\.bestTrendPrices\(data\.rows \|\| \[\]\), state\.trendWindow\)/);
  assert.match(source, /\['season','This season'\],\['last10','Last 10'\],\['last5','Last 5'\]/);
  assert.match(source, /\['main','Main lines'\],\['alternate','Alternates'\],\['milestone','Milestones'\]/);
  assert.doesNotMatch(source.slice(source.indexOf('async function viewTrends'), source.indexOf('async function viewMore')), /trendMin/);
});

test('game pages put favorites before secondary model reads and do not publish model methodology', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const game = source.slice(source.indexOf('async function viewGame(route)'), source.indexOf('const finalSection'));
  assert.ok(game.indexOf('favoriteLinesSection') < game.indexOf('modelReadsSection'));
  assert.doesNotMatch(game, /Why the model says this|Forecast history/);
  assert.doesNotMatch(source, /How we calculated it/);
});

test('Games shows compact current model offense and defense ranks for both teams', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /OFF <b>#\$\{rank\.offense\}<\/b>/);
  assert.match(source, /DEF <b>#\$\{rank\.defense\}<\/b>/);
  assert.match(source, /No\. 1 is strongest/);
  const games = source.slice(source.indexOf('async function viewGames()'), source.indexOf('/* ---------- one game ---------- */'));
  assert.match(games, /projGrid\(rows, true\)/, 'ranks are enabled on the Games tab');
});

test('the default stats view is a visual all-stat player chart board with search kept secondary', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const css = fs.readFileSync('site/app.css', 'utf8');
  const stats = source.slice(source.indexOf('async function viewStats(route)'), source.indexOf('async function playerSearch(league)'));
  assert.match(source, /\['stats', 'Charts'\]/);
  assert.match(stats, /route\.tab \|\| 'charts'/);
  assert.match(stats, /Player charts/);
  assert.match(stats, /\['search', 'Search'\]/);
  assert.match(source, /const CHART_STATS = \['passYds'.*'snapPct'\]/s);
  assert.match(source, /app\/player-charts\/\$\{league\}\.json/);
  assert.match(source, /\['last5', 'Last 5'\], \['last10', 'Last 10'\], \['season', 'Season'\]/);
  assert.match(source, /\['PK', 'K'\]/);
  assert.match(css, /\.player-chart-card/);
  assert.match(css, /\.mini-chart/);
  assert.match(css, /@media \(max-width: 620px\)[\s\S]*\.chart-team-grid \{ grid-template-columns:1fr;/);
});

test('the Climb shows a cashed rung, the next step state and past lines in a dropdown', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /cashed · Step \$\{L\.step\} is being checked · not posted yet/);
  assert.match(source, /<details class="ladder-history"><summary>Past steps/);
  assert.match(source, /map\(l => l\.title\).*join\(' · '\)/);
  assert.match(source, /All-time ladder totals/);
  assert.match(source, /Settled stake/);
  assert.match(source, /Running \$\{esc\(signedMoney\(total\.net\)\)\}/);
});

test('the Lab tracks season futures without presenting a public play', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const lab = source.slice(source.indexOf('async function viewLab()'), source.indexOf('function viewArbs()'));
  assert.match(lab, /Season futures/);
  assert.match(lab, />Planned</);
  assert.match(lab, /Original quotes, later moves and book settlements/);
  assert.match(lab, /stay separate from the daily card/);
  assert.doesNotMatch(lab, /official futures? (?:pick|play)/i);
});

test('score pages refresh factual scores in the browser without treating odds or picks as live', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const live = source.slice(source.indexOf("const LIVE ="), source.indexOf('/* Preserve the official pick'));
  assert.match(live, /NFL: \['football', 'nfl'/);
  assert.match(live, /NBA: \['basketball', 'nba'/);
  assert.match(live, /MLB: \['baseball', 'mlb'/);
  assert.match(live, /NHL: \['hockey', 'nhl'/);
  assert.match(live, /EPL: \['soccer', 'eng\.1'/);
  const transport = fs.readFileSync('site/live.js', 'utf8');
  assert.match(transport, /ttl = 45000/);
  assert.match(transport, /cache:'no-store'/);
  assert.doesNotMatch(live, /competition\.odds|event\.odds|pickOdds/);
  assert.match(source, /refresh every minute/);
});

test('More links to the public posting schedule and keeps qualifying language', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /link\('#schedule', 'Posting schedule'/);
  const schedule = source.slice(source.indexOf('async function viewSchedule()'), source.indexOf('/* ---------- pick details'));
  assert.match(schedule, /8:45 AM/);
  assert.match(schedule, /10:30 AM/);
  assert.match(schedule, /Around noon/);
  assert.match(schedule, /10–15 minutes before X/);
  assert.match(schedule, /not promised picks/);
});
