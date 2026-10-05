'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../site/core.js');

test('shared plot renders under hits, ties, unknowns and snap percentages on one scrollable scale', () => {
  const source=fs.readFileSync('site/app.js','utf8');
  const body=source.match(/const historyPlot = \([^\n]+\) => \{([\s\S]*?)\n  \};/)[1];
  const render=new Function('C','esc','rows','values','line','direction','compact','key',body);
  const rows=[{label:'A'},{label:'B'},{label:'C'},{label:'D'}];
  const html=render(C,C.esc,rows,[0,.8,1,null],.8,'under',false,'snapPct');
  assert.match(html,/under 80%; green hit/);
  assert.match(html,/plot-hit plot-zero-value/);
  assert.match(html,/plot-push/);
  assert.match(html,/plot-miss/);
  assert.match(html,/plot-unknown/);
  assert.match(html,/>80%<\/b>/);
  assert.match(html,/history-chart-canvas/);
  const css=fs.readFileSync('site/app.css','utf8');
  assert.match(css,/\.history-chart \{[^}]*overflow-x:auto/);
  assert.doesNotMatch(css,/\.full-chart \.plot-value \{ font-size:8px/);
});

test('Climb and parlay week labels stay distinct and do not mix dollar and unit summaries', () => {
  const source=fs.readFileSync('site/app.js','utf8');
  const body=source.match(/const settledWeeks = \([^\n]+\) => \{([\s\S]*?)\n  \};/)[1];
  const render=new Function('C','esc','played','wl','unitText','settledRow','settled','clv','searching','weekLabel','scope',body);
  const row={kind:'parlays',parlayType:'ladder',result:'win',odds:-200,riskUnits:.25,kickoff:'2026-10-04T17:00Z'};
  const run=(scope,rows)=>render(C,C.esc,t=>t.wins+t.losses+t.pushes,t=>`${t.wins}–${t.losses}`,n=>n+'u',()=>'',rows,new Map(),false,w=>w,scope);
  assert.match(run('ladder',[row]),/1–0 · 1 ladder step/);
  assert.doesNotMatch(run('ladder',[row]),/fun parlay|[0-9]u/);
  assert.match(run('parlays',[{...row,parlayType:'longshot'}]),/1 fun parlay/);
});

test('research scope, side labels and primary Tools destinations are unambiguous', () => {
  const source=fs.readFileSync('site/app.js','utf8');
  assert.match(source,/up to last 5 this season/);
  assert.match(source,/Last 10 this season/);
  assert.match(source,/const hitSummary/);
  assert.match(source,/h\[side\]/);
  const tools=source.slice(source.indexOf('async function viewMore()'),source.indexOf('async function viewSchedule()'));
  assert.equal((tools.match(/href="#arbs"/g)||[]).length,1);
  assert.equal((tools.match(/href="#lab"/g)||[]).length,1);
  assert.doesNotMatch(tools,/personalLinks\(/);
});

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

test('Today puts published plays and official results before optional research and model detail', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const today = source.slice(source.indexOf('async function viewToday()'), source.indexOf('const modelCard ='));
  assert.ok(today.indexOf('card.map(playCard)') < today.indexOf('officialStrip(picks)'));
  assert.ok(today.indexOf('officialStrip(picks)') < today.indexOf('research-heading'));
  assert.ok(today.indexOf('card.map(playCard)') < today.indexOf('inactive-ladder'));
  assert.doesNotMatch(today, /transparent-record/);
  assert.equal((today.match(/scorecardCard\(/g) || []).length, 0, 'the model scorecard belongs under Model results');
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

test('Scores preserves its old routes under Games with a nine-league header selector', () => {
  assert.deepEqual(C.parseRoute('#scores'), {view:'scores',league:'ALL'});
  for(const league of ['NFL','CFB','NBA','WNBA','CBB','MLB','NHL','EPL','MLS'])
    assert.deepEqual(C.parseRoute('#scores/'+league), {view:'scores',league});
  const source=fs.readFileSync('site/app.js','utf8');
  assert.match(source, /scores:'games'/);
  assert.match(source, /gamesTabs\('scores'\)/);
  assert.match(source, /data-sport-select aria-label="Choose a sport"/);
  assert.match(source, /const SCORE_LEAGUES = \['NFL', 'CFB', 'NBA', 'WNBA', 'CBB', 'MLB', 'NHL', 'EPL', 'MLS'\]/);
  assert.match(source, /event\.target\.matches\('\[data-sport-select\]'\)/);
  const tabs=source.match(/const TABS = (.*);/)[1];
  assert.equal((tabs.match(/\['/g) || []).length,5);
  assert.match(tabs,/\['more', 'Tools'\]/);
});

test('sport research distinguishes collected games, trial records and missing projections', () => {
  const source=fs.readFileSync('site/app.js','utf8');
  const body=source.match(/const sportResearch = \(league, history, trials\) => \{([\s\S]*?)\n  \};/)[1];
  const render=new Function('esc','whenShort','league','history','trials',body);
  const html=render(C.esc,C.whenShort,'MLB',{leagues:{MLB:{gamesQuoted:13,gamesGraded:11}}},null);
  assert.match(html,/13<\/b> games with saved lines/);
  assert.match(html,/not prediction wins/);
  assert.doesNotMatch(html,/trial totals record/);
  const pending=render(C.esc,C.whenShort,'NBA',null,{leagues:{NBA:{recorded:0,record:{win:0,loss:0,push:0},upcoming:[]}}});
  assert.match(pending,/Pending/);assert.doesNotMatch(pending,/>0–0/);
  const trial=render(C.esc,C.whenShort,'NBA',null,{leagues:{NBA:{recorded:12,record:{win:5,loss:3,push:1},upcoming:[]}}});
  assert.match(trial,/5–3–1/);assert.match(trial,/Not official plays/);
  assert.match(render(C.esc,C.whenShort,'MLS',null,null),/No model record or projections yet/);
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
