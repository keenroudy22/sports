'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const C = require('../site/core.js');

test('saved research filters accept visible choices and reject malformed or obsolete settings', () => {
  const prefs=C.researchPreferences({trendKind:'all',trendRate:'0',chartPos:'none',chartDay:'2026-99-99',chartOpponent:'undefined',
    chartQuery:'London',boardScope:'settled',recordScope:'ladder',recordSeason:'2026',recordPhase:'playoffs',ticket:[{id:'not-a-filter'}],league:'CFB'});
  assert.deepEqual([prefs.trendKind,prefs.trendRate,prefs.chartPos,prefs.chartDay,prefs.chartOpponent],['main','80','all','next','all']);
  assert.equal(prefs.chartQuery,'London');
  assert.equal(prefs.boardScope,'settled');
  assert.equal(prefs.recordScope,'ladder');
  assert.equal(prefs.recordSeason,'2026');assert.equal(prefs.recordPhase,'playoffs');
  assert.equal(prefs.ticket,undefined);assert.equal(prefs.league,undefined);
  assert.equal(C.researchPreferences({chartDay:'2026-02-30'}).chartDay,'next');
  assert.equal(C.researchPreferences({chartDay:'2026-10-05',chartOpponent:'11'}).chartDay,'2026-10-05');
  assert.equal(C.researchPreferences({chartQuery:'x'.repeat(161)}).chartQuery,'');
  assert.equal(C.researchPreferences({recordSeason:'2206',recordPhase:'preseason'}).recordSeason,'current');
  assert.deepEqual(C.researchPreferences(null),C.RESEARCH_DEFAULTS);
});

test('published records default to each sport current season and stage while preserving archives', () => {
  const pick=(id,league,season,seasonType,result='win')=>({id,league,season,seasonType,result,odds:-110,kickoff:`${season}-10-01T00:00:00Z`});
  const rows=[pick('n25','NFL',2025,2),pick('n26r','NFL',2026,2,'loss'),pick('n26p','NFL',2026,3),
    pick('h26','NHL',2026,'post-season','loss'),pick('h27','NHL',2027,'regular-season'),
    {...pick('manual','CFB',2026,null),season:null}];
  const current=C.recordArchive(rows);
  assert.deepEqual(current.rows.map(row=>row.id),['n26p','h27','manual'],'current is evaluated per sport and playoffs start a new default slice');
  assert.deepEqual(current.seasons,[2027,2026,2025]);
  assert.deepEqual(current.currentByLeague,{NFL:2026,NHL:2027});
  assert.equal(current.unassigned,1,'missing metadata stays visible instead of silently disappearing');
  assert.deepEqual(C.recordArchive(rows,'2026','regular').rows.map(row=>row.id),['n26r']);
  assert.deepEqual(C.recordArchive(rows,'2026','playoffs').rows.map(row=>row.id),['n26p','h26']);
  assert.equal(C.recordArchive(rows,'all','all').rows.length,rows.length,'the archive retains every published row');
  assert.equal(C.recordPhaseOf({seasonType:'playoffs'}),'playoffs');
  assert.equal(C.recordPhaseOf({seasonType:null}),'regular');
});

test('a workspace reset leaves other research, Saved, sport and original ticket values untouched', () => {
  const original={league:'CFB',chartQuery:'London',chartDay:'2026-10-05',chartOpponent:'11',chartWindow:'last5',
    trendKind:'alternate',boardQuery:'yards',watchlist:[{key:'kept'}],ticket:[{odds:-110,line:25.5}]};
  const reset={...original,...C.researchReset('charts')};
  assert.equal(reset.chartQuery,'');assert.equal(reset.chartDay,'next');assert.equal(reset.chartOpponent,'all');
  assert.equal(reset.chartWindow,'season');assert.equal(reset.trendKind,'alternate');assert.equal(reset.boardQuery,'yards');
  assert.equal(reset.league,'CFB');assert.equal(reset.watchlist,original.watchlist);assert.equal(reset.ticket,original.ticket);
  assert.equal(C.researchReset('trends').trendKind,'main');assert.equal(C.researchReset('lines').boardScope,'open');
  assert.deepEqual(C.researchReset('everything'),{});
});

test('effective chart history applies venue and opponent before the sample and retains exact observations', () => {
  const rows=Array.from({length:25},(_,i)=>({date:`2026-09-${String(i+1).padStart(2,'0')}`,home:i%2,opp:String(i%3),stats:{rushYds:i-2}})).reverse();
  rows.push({date:'2026-09-30',home:1,opp:'1',stats:{rushYds:null}});
  const before=JSON.stringify(rows);
  const season=C.chartHistory(rows,'rushYds',{chartWindow:'season'});
  assert.equal(season.length,25,'Season is not silently capped at 20');
  assert.deepEqual(season.slice(0,3).map(r=>r.stats.rushYds),[-2,-1,0]);
  const subset=C.chartHistory(rows,'rushYds',{chartWindow:'last5',chartVenue:'home',chartOpponent:'1'});
  assert.ok(subset.every(r=>r.home===1&&r.opp==='1'));
  assert.equal(subset.length,4,'short matching history keeps its true count');
  assert.equal(C.chartHistory(rows,'rushYds',{chartOpponent:'999'}).length,0);
  assert.equal(C.chartHistory(rows,'missing').length,0);
  assert.equal(JSON.stringify(rows),before,'stored history is never sorted/mutated in place');
});

test('display-only observed values preserve unknown, zero and negative without changing legacy helpers', () => {
  const keys=['rushYds','snapPct'];
  const row=(day,value,snap)=>['game',day,2026,1,2,'a','b',1,value,snap];
  const rows=[row('2026-10-01',null,null),row('2026-09-20',0,0),row('2026-09-10',-3,.8)];
  assert.equal(C.cell(rows[0],keys,'rushYds'),0,'legacy counting interpretation is preserved');
  assert.equal(C.observedCell(rows[0],keys,'rushYds'),null);
  assert.equal(C.observedCell(rows[1],keys,'rushYds'),0);
  assert.equal(C.observedCell(rows[2],keys,'rushYds'),-3);
  assert.equal(C.observedCell(rows[2],keys,'unavailable'),null);
  assert.equal(C.windows(rows,keys,'rushYds').last5.n,3);
  assert.deepEqual(C.windows(rows,keys,'rushYds',[5],null,C.observedCell).last5,{n:2,avg:-1.5,median:-1.5,min:-3,max:0});
  assert.equal(C.splits(rows,keys,'rushYds','b',C.observedCell).vs.summary.n,2);
  assert.deepEqual(C.splits(rows,keys,'rushYds','b',C.observedCell).vs.games.map(r=>r.value),[null,0,-3]);
});

test('stat display renders snap fractions as percentages without changing chart units', () => {
  assert.equal(C.statValue(.8,'snapPct'),'80%');
  assert.equal(C.statValue(0,'snapPct'),'0%');
  assert.equal(C.statValue(null,'snapPct'),C.DASH);
  assert.equal(C.statValue(-3,'rushYds'),'-3.0');
  const plot=C.chartGeometry([0,.8,1],.8);
  assert.equal(plot.bars[1].point,plot.line,'only text is formatted; geometry uses the real numeric value');
});

test('historical chart bars and threshold share one coordinate system, including zero and negatives', () => {
  const g=C.chartGeometry([-10,0,10,20,null],10);
  assert.equal(g.bars[2].point,g.line);
  assert.ok(g.bars[3].point<g.line);
  assert.ok(g.bars[0].point>g.zero);
  assert.equal(g.bars[1].height,0);
  assert.equal(g.bars[1].point,g.zero);
  assert.equal(g.bars[4],null);
  for(const bar of g.bars.filter(Boolean)) {
    assert.ok(bar.top>=0 && bar.top+bar.height<=100);
    assert.equal(Math.min(bar.point,g.zero),bar.top);
  }
  assert.equal(C.chartGeometry([0,0],0).line,C.chartGeometry([0,0],0).zero);
  assert.equal(C.chartGeometry([null],null).line,null);
  assert.ok(C.chartGeometry([-3,-1],-2).line>0);
});

test('chart hit colors respect selected unders, pushes and inclusive milestones', () => {
  assert.equal(C.thresholdResult(8,10,'under'),'hit');
  assert.equal(C.thresholdResult(12,10,'under'),'miss');
  assert.equal(C.thresholdResult(10,10,'under'),'push');
  assert.equal(C.thresholdResult(10,10,'over',true),'hit');
  assert.equal(C.thresholdResult(10,10.5,'over'),'miss');
  assert.equal(C.thresholdResult(null,0,'over'),'unknown');
  assert.equal(C.thresholdResult(-1,0,'under'),'hit');
});

test('shared quote labels never call old, unknown, unpriced or started lines current', () => {
  const now=Date.parse('2026-10-05T12:00:00Z');
  const row={state:'open',odds:-110,line:5.5,observedAt:'2026-10-05T11:00:00Z',kickoff:'2026-10-05T20:00:00Z'};
  assert.equal(C.quoteStatus(row,null,now).current,true);
  for(const changed of [{observedAt:'2026-10-05T01:00:00Z'},{observedAt:'2026-10-06T00:00:00Z'},
    {observedAt:null},{odds:null},{state:'reference'},{state:'stale'},{state:'unpriced'},{state:'closed'},
    {kickoff:'2026-10-05T11:00:00Z'}]) assert.equal(C.quoteStatus({...row,...changed},null,now).current,false);
  assert.equal(C.quoteStatus(null,null,now).kind,'missing');
  assert.equal(C.quoteStatus(row,'2026-10-05T11:00:00Z',now).kind,'started');
});

test('defense ranks use per-stat observed coverage and never coerce unknown values into zeros', () => {
  const rows={a:{g:5,WR:{recYds:20},coverage:{WR:{recYds:2}}},b:{g:5,WR:{recYds:null},coverage:{WR:{recYds:0}}},c:{g:4,WR:{recYds:0}}};
  assert.deepEqual(C.rankDefenses(rows,'WR','recYds').map(r=>[r.team,r.games]),[['c',4],['a',2]]);
  assert.deepEqual(C.rankDefenses(rows,'WR','recYds',3).map(r=>r.team),['c']);
});

test('new workspace aliases preserve legacy research and trial routes', () => {
  assert.deepEqual(C.parseRoute('#charts'),{view:'stats'});
  assert.deepEqual(C.parseRoute('#tools'),{view:'more'});
  assert.deepEqual(C.parseRoute('#record/trials'),{view:'record',tab:'trials'});
  assert.deepEqual(C.parseRoute('#scores/NFL'),{view:'scores',league:'NFL'});
});

test('delivery status distinguishes sent, queued, overdue, cancelled and unknown', () => {
  const now = Date.parse('2026-10-02T16:00:00Z');
  assert.match(C.deliveryText({delivery:{discordAt:'2026-10-02T15:45:00Z',xDue:'2026-10-02T16:10:00Z'}}, now), /Discord sent.*Posted here first · X to follow/);
  assert.match(C.deliveryText({delivery:{xAt:'2026-10-02T15:50:00Z'}}, now), /X sent/);
  assert.match(C.deliveryText({delivery:{xDue:'2026-10-02T15:50:00Z'}}, now), /Posted here first · X to follow/);
  assert.equal(C.deliveryText({delivery:{cancelled:true}}, now), '');
  assert.equal(C.deliveryText({delivery:{failed:true}}, now), '');
  assert.match(C.deliveryText({}, now), /Posted here first · X to follow/);
  assert.equal(C.deliveryText({result:'win'}, now), '');
});

test('headline record separates assumed prices and promotional credits without rewriting plays', () => {
  const picks = [{ result:'win', odds:100 }, { result:'loss', odds:-110, earlyExit:true, units:0 },
    { result:'win', odds:-115, priceAssumed:true }, { result:'loss', odds:200, kind:'parlays' }];
  const frozen = JSON.stringify(picks);
  const r = C.recordBreakdown(picks);
  assert.equal(r.all.wins, 2);
  assert.equal(r.all.losses, 1);
  assert.equal(r.captured.units, 0);
  assert.equal(r.captured.wins, 1);
  assert.equal(r.assumed.wins, 1);
  assert.equal(r.credits, 1);
  assert.equal(JSON.stringify(picks), frozen);
});

test('new lanes stay out of the Best bets headline and keep their own record lines', () => {
  const picks = [
    { id:'legacy', result:'win', odds:-110 },
    { id:'best', lane:'best_bet', result:'loss', odds:-110 },
    { id:'hot', lane:'hot_plate', result:'win', odds:120 },
    { id:'gut', lane:'gut_call', result:'win', odds:100, riskUnits:.5 },
    { id:'safe', lane:'safer_combo', result:'loss', odds:-150, riskUnits:1, kind:'parlays' },
  ];
  const r = C.recordBreakdown(picks);
  assert.equal(r.all.wins, 2);
  assert.equal(r.all.losses, 1);
  assert.equal(r.lanes.gut_call.wins, 1);
  assert.equal(r.lanes.safer_combo.losses, 1);
  assert.equal(r.allPlays.wins, 3);
  assert.equal(r.allPlays.losses, 2);
});

test('official card separates Eastern dates and keeps ungraded older plays visible', () => {
  const picks = [{id:'today',kickoff:'2026-10-03T00:00:00Z'}, {id:'tomorrow',kickoff:'2026-10-03T17:00:00Z'},
    {id:'old',kickoff:'2026-10-01T22:00:00Z'}, {id:'settled',kickoff:'2026-10-03T00:00:00Z',result:'win'}];
  const r = C.cardSchedule(picks, Date.parse('2026-10-02T14:00:00Z'));
  assert.deepEqual(r.today.map(p=>p.id), ['today']);
  assert.deepEqual(r.upcoming.map(p=>p.id), ['tomorrow']);
  assert.deepEqual(r.awaiting.map(p=>p.id), ['old']);
});

test('the generic college disagreement caution is retired: specific reasons come from the build', () => {
  assert.equal(C.modelCaution, undefined);
});

test('straight play cards link to the player or matchup; tickets and incomplete props keep details', () => {
  assert.equal(C.pickResearchRoute({ kind: 'props', athleteId: '5138451', league: 'CFB', gameId: 'CFB-401858245' }), '#player/CFB/5138451');
  assert.equal(C.pickResearchRoute({ athleteId: 3122840, league: 'NFL' }), '#player/NFL/3122840');
  for (const marketType of ['total', 'spread', 'moneyline', 'team_total']) {
    assert.equal(C.pickResearchRoute({ marketType, gameId: 'NFL-123' }), '#game/NFL-123');
  }
  for (const p of [{}, { kind: 'props', gameId: 'NFL-123' }, { athleteId: '1' },
    { kind: 'parlays', gameId: 'NFL-123' }, { legs: ['leg'], gameId: 'NFL-123' },
    { parlayType: 'ladder', athleteId: '1', league: 'NFL' }]) {
    assert.equal(C.pickResearchRoute(p), null);
  }
  const route = C.pickResearchRoute({ gameId: 'NFL-123/"<&' });
  assert.equal(route, '#game/NFL-123%2F%22%3C%26');
  assert.deepEqual(C.parseRoute(route), { view: 'game', id: 'NFL-123/"<&' });
});

const KEYS = ['recYds', 'rec', 'recLong', 'snapPct'];
// [eventId, date, season, week, seasonType, team, opp, home, ...stats]
const row = (date, opp, home, recYds, rec, extra = {}) =>
  ['e' + date, date, Number(date.slice(0, 4)), 1, 2, '1', opp, home, recYds, rec, extra.recLong ?? null, extra.snapPct ?? null];

test('text helpers escape markup and format numbers without claiming precision', () => {
  assert.equal(C.esc('<b>"x" & y</b>'), '&lt;b&gt;&quot;x&quot; &amp; y&lt;/b&gt;');
  assert.equal(C.odds(150), '+150');
  assert.equal(C.odds(-110), '-110');
  assert.equal(C.odds(null), C.DASH);
  assert.equal(C.signed(2.25), '+2.3');
  assert.equal(C.signed(-3), '-3.0');
  assert.equal(C.signed(0), '0.0');
  assert.equal(C.spreadText('ATL', 2.5), 'ATL +2.5');
  assert.equal(C.spreadText('ATL', -3), 'ATL -3');
  assert.equal(C.spreadText('ATL', 0), 'ATL PK');
  assert.equal(C.modelSpread('ATL', 'CAR', 4.3), 'ATL -4.3');
  assert.equal(C.modelSpread('ATL', 'CAR', -2), 'CAR -2.0');
  assert.equal(C.modelSpread('ATL', 'CAR', 0.01), 'Even');
  assert.equal(C.ago(null), 'time not recorded', 'a missing time is not January 1970');
  assert.equal(C.when(null), '');
});

test('leans name the team and the total direction the model prefers', () => {
  const game = { home: { abbr: 'ATL' }, away: { abbr: 'CAR' }, lean: { spread: 6.8, side: 'home', total: -2.3 } };
  assert.deepEqual(C.leanText(game), { side: { team: 'ATL', points: 6.8, chance: null }, total: { direction: 'Under', points: 2.3, chance: null } });
  assert.equal(C.leanTone(0.58, false), 'lean-strong');
  assert.equal(C.leanTone(0.58, true), 'lean-mild', 'a thin sample never shows green');
  assert.equal(C.leanTone(0.55, false), 'lean-mild');
  assert.equal(C.leanTone(0.52, false), '');
  assert.equal(C.leanTone(null, false), '');
  assert.deepEqual(C.leanText({ ...game, lean: { spread: 1, side: 'home', total: 0.5 } }, 2), {});
  assert.equal(C.leanText({ home: {}, away: {} }), null);
});

test('windows count back from the newest game and report their true sample', () => {
  const rows = [row('2025-09-07', '2', 1, 50, 4), row('2025-09-14', '3', 0, 80, 6), row('2026-09-10', '4', 1, 120, 9)];
  const w = C.windows(rows, KEYS, 'recYds', [2, 5]);
  assert.equal(w.last2.n, 2);
  assert.equal(w.last2.avg, 100);
  assert.equal(w.last5.n, 3);
  assert.equal(w.season.n, 1, 'the season is the newest game’s season');
  assert.equal(w.season.avg, 120);
});

test('a listed player without a counting stat had zero, but longest and snaps stay unknown', () => {
  const r = row('2026-09-10', '4', 1, null, null);
  assert.equal(C.cell(r, KEYS, 'recYds'), 0);
  assert.equal(C.cell(r, KEYS, 'recLong'), null);
  assert.equal(C.cell(r, KEYS, 'snapPct'), null);
  assert.equal(C.cell(r, KEYS, 'notAKey'), null);
});

test('player pages expose the common scoring, volume, long-play, and red-zone stats by position', () => {
  assert.deepEqual(C.POSITION_STATS.QB,
    ['passYds', 'passTD', 'cmp', 'att', 'int', 'rushYds', 'car', 'rushTD', 'scrambles', 'sacks', 'rushLong']);
  assert.deepEqual(C.POSITION_STATS.RB,
    ['rushYds', 'car', 'anyTD', 'rushTD', 'recYds', 'rec', 'targets', 'recTD', 'rushLong', 'recLong', 'rzCar', 'i10Car', 'i5Car']);
  assert.deepEqual(C.POSITION_STATS.WR,
    ['recYds', 'rec', 'targets', 'anyTD', 'recTD', 'recLong', 'rushYds', 'car', 'rushTD', 'rzTgt', 'i10Tgt']);
  assert.deepEqual(C.POSITION_STATS.TE,
    ['recYds', 'rec', 'targets', 'anyTD', 'recTD', 'recLong', 'rzTgt', 'i10Tgt']);
  assert.equal(C.LABEL.rushTD, 'Rush TD');
  assert.equal(C.LABEL.recTD, 'Rec TD');
  assert.equal(C.LABEL.anyTD, 'Any TD');
});

test('Any TD adds observed rushing and receiving scores without turning missing history into zero', () => {
  const keys = ['rushTD', 'recTD'];
  const statRow = (rush, rec) => ['g', '2026-09-10', 2026, 1, 2, 'a', 'b', 1, rush, rec];
  assert.equal(C.observedStat(statRow(1, 2), keys, 'anyTD'), 3);
  assert.equal(C.observedStat(statRow(null, 1), keys, 'anyTD'), 1);
  assert.equal(C.observedStat(statRow(0, 0), keys, 'anyTD'), 0);
  assert.equal(C.observedStat(statRow(null, null), keys, 'anyTD'), null);
  assert.equal(C.observedStat(statRow(1, 2), keys, 'rushTD'), 1);
});

test('missing play-by-play counts stay unknown instead of becoming zeros', () => {
  assert.equal(C.cell([...Array(8), null], ['rzCar'], 'rzCar'), null);
  assert.equal(C.cell([...Array(8), 0], ['rzCar'], 'rzCar'), 0);
  assert.equal(C.cell([...Array(8), null], ['i10Tgt'], 'i10Tgt'), null);
  const role = { group: 'RB', roleUsage: { games: 4, volume: {car: null, tgt: 3}, redZone: 8 } };
  assert.equal(C.injurySleeperSignal(role, 10), null);
});

test('injury sleeper labels require an established role plus current opportunity', () => {
  const role = { group: 'RB', roleUsage: { games: 3, snapPct: .23, volume: { car: 6, tgt: 2.7 }, redZone: 1 } };
  assert.deepEqual(C.injurySleeperSignal(role, 1.7),
    { tier: 'dart', label: 'Deep sleeper', roleOpportunities: 8.7, projected: 1.7 });
  assert.deepEqual(C.injurySleeperSignal(role, 5),
    { tier: 'volume', label: 'Sleeper watch', roleOpportunities: 8.7, projected: 5 });
  assert.equal(C.injurySleeperSignal(role, 1), null, 'a depth-chart promotion alone is not enough');
  assert.equal(C.injurySleeperSignal({ group: 'WR', roleUsage: { games: 1, snapPct: .5, volume: { tgt: 8 }, redZone: 2 } }, 8), null,
    'one game is not an established role');
});

test('splits separate home, away and neutral and list head-to-head meetings', () => {
  const rows = [row('2025-09-07', '2', 1, 50, 4), row('2025-09-14', '2', 0, 80, 6), row('2026-01-04', '3', -1, 20, 1)];
  const s = C.splits(rows, KEYS, 'recYds', '2');
  assert.equal(s.home.avg, 50);
  assert.equal(s.away.avg, 80);
  assert.equal(s.neutral.avg, 20);
  assert.equal(s.vs.summary.n, 2);
  assert.deepEqual(s.vs.games.map(g => g.value), [50, 80]);
  assert.deepEqual(C.hits([50, 80, 20, 60.5], 60.5), { over: 1, under: 2, push: 1, n: 4 });
});

test('a market’s words map to the stat behind it, and a row that names its stat wins', () => {
  assert.equal(C.marketKey({ market: 'receiving yards' }), 'recYds');
  assert.equal(C.marketKey({ market: 'rushing attempts' }), 'car');
  assert.equal(C.marketKey({ market: 'pass attempts' }), 'att');
  assert.equal(C.marketKey({ title: 'Terrance Ferguson under 32.5 receiving yards' }), 'recYds');
  assert.equal(C.marketKey({ market: 'longest reception' }), null);
  assert.equal(C.marketKey({ market: 'receiving yards', stat: 'rec' }), 'rec');
  assert.equal(C.marketKey({ market: 'rec' }), 'rec');
  assert.equal(C.marketKey({ market: 'recYds' }), 'recYds');
  assert.equal(C.marketKey({ market: 'car' }), 'car');
  assert.equal(C.marketKey({ market: 'receptions' }), 'rec');
  assert.equal(C.marketKey(null), null);
});

test('a role ranks a player among teammates at his position by the volume behind the market', () => {
  const players = [{ id: '1', pos: 'TE', targets: [5.1, 2, 8] }, { id: '2', pos: 'TE', targets: [2.3, 0, 5] },
    { id: '3', pos: 'WR', targets: [9, 5, 13] }, { id: '4', pos: 'TE' }];
  assert.deepEqual(C.roleOf(players, '2', 'TE', 'recYds'), { rank: 2, of: 2, stat: 'targets', volume: 2.3 });
  assert.equal(C.roleOf(players, '3', 'TE', 'recYds'), null, 'a receiver is not ranked among tight ends');
  assert.equal(C.roleOf(players, '1', 'TE', 'recLong'), null, 'no volume stat stands behind a longest-play line');
  assert.equal(C.POS_GROUP.FB, 'RB');
});

test('defense ranks put the stingiest first, share ranks on ties and ignore missing rows', () => {
  const rows = { A: { g: 2, WR: { recYds: 150 } }, B: { g: 2, WR: { recYds: 100 } }, C: { g: 2, WR: { recYds: 150 } }, D: { g: 2, TE: { recYds: 40 } } };
  const ranked = C.rankDefenses(rows, 'WR', 'recYds');
  assert.deepEqual(ranked.map(r => [r.team, r.rank]), [['B', 1], ['A', 2], ['C', 2]]);
  assert.deepEqual(C.rankOf(rows, 'C', 'WR', 'recYds'), { rank: 2, of: 3, value: 150 });
  assert.equal(C.rankOf(rows, 'D', 'WR', 'recYds'), null);
  assert.equal(C.rankTone(30, 32), 'soft');
  assert.equal(C.rankTone(3, 32), 'tough');
  assert.equal(C.rankTone(16, 32), 'neutral');
});

const now = Date.parse('2026-09-19T12:00:00Z');
const leg = (id, odds, extra = {}) => ({ id, odds, book: 'DraftKings', gameId: 'NFL-' + id, state: 'open', kickoff: '2026-09-20T17:00:00Z', title: 'Leg ' + id, ...extra });

test('an illustrative parlay multiplies separate-game prices at one book', () => {
  const t = C.summarizeTicket([leg('1', -110), leg('2', 150)], 1, 'units', 10, now);
  assert.equal(t.available, true);
  assert.ok(Math.abs(t.decimal - (1 + 100 / 110) * 2.5) < 1e-9);
  assert.equal(t.odds, 377);
  assert.ok(Math.abs(t.dollars.profit - 37.73) < 0.01);
  assert.equal(C.american(2), 100);
  assert.equal(C.american(1.5), -200);
});

test('arb calculator splits two prices equally and does not call ordinary juice an arb', () => {
  const split = C.arbSplit(298, -195, 181.55);
  assert.equal(split.valid, true);
  assert.equal(split.arb, true);
  assert.ok(Math.abs(split.firstStake - 50) <= 0.02);
  assert.ok(Math.abs(split.secondStake - 131.55) <= 0.02);
  assert.ok(Math.abs(split.profit - 17.45) <= 0.03);
  assert.ok(Math.abs(split.roi - 9.61) <= 0.02);
  assert.equal(C.arbSplit(-110, -110, 100).arb, false);
  assert.equal(C.arbSplit(0, -110, 100).valid, false);
});

test('arb radar has a shareable route', () => {
  assert.deepEqual(C.parseRoute('#arbs'), { view: 'arbs' });
});

test('the multi-sport lab has a shareable route', () => {
  assert.deepEqual(C.parseRoute('#lab'), { view: 'lab' });
  assert.deepEqual(C.parseRoute('#scores/NHL'), { view: 'scores', league: 'NHL' });
  assert.deepEqual(C.parseRoute('#schedule'), { view: 'schedule' });
});

test('a ticket refuses what the sportsbook would price differently or not at all', () => {
  const reason = rows => C.summarizeTicket(rows, 1, 'units', 10, now).reason;
  assert.match(reason([leg('1', -110)]), /at least two/);
  assert.match(reason([leg('1', -110), leg('2', 150, { book: 'FanDuel' })]), /Mixed sportsbooks/);
  assert.match(reason([leg('1', -110), leg('2', 150, { gameId: 'NFL-1' })]), /Same-game/);
  assert.match(reason([leg('1', -110), leg('2', 150, { kickoff: '2026-09-18T17:00:00Z' })]), /current, priced/);
  assert.match(reason([leg('1', -110), leg('2', null)]), /current, priced/);
  assert.match(C.summarizeTicket([leg('1', -110), leg('2', 150)], 0, 'units', 10, now).reason, /positive stake/);
  assert.match(C.ticketText([leg('1', -110)]), /not an official ticket/);
});

test('the record counts priced picks only and withholds ROI below ten', () => {
  const picks = [
    { result: 'win', odds: 150 }, { result: 'loss', odds: -110 }, { result: 'push', odds: -110 },
    { result: 'win', odds: null }, { result: 'void', odds: -110 }, { result: null, odds: -110 }];
  const r = C.recordOf(picks);
  assert.equal(r.wins, 2);
  assert.equal(r.losses, 1);
  assert.equal(r.priced, 3, 'an unpriced win and a void never enter returns');
  assert.deepEqual([r.pricedWins, r.pricedLosses, r.unpriced], [1, 1, 1]);
  assert.ok(Math.abs(r.units - 0.5) < 1e-9);
  assert.equal(r.roi, null);
  assert.equal(r.pending, 1);
  const ten = Array.from({ length: 10 }, (_, i) => ({ result: i < 6 ? 'win' : 'loss', odds: 100 }));
  assert.equal(C.recordOf(ten).roi, 20);
});

test('the Week 1 import is listed apart and kept out of the record, its units and its ROI', () => {
  const fs = require('node:fs');
  const report = JSON.parse(fs.readFileSync('research/2026-09-14-NFL-week-1-import.json', 'utf8'));
  const five = new Set(['w1-loveland-rec', 'w1-mayfield-pass', 'w1-otton-rec', 'w1-pollard-carries', 'w1-bateman-rec']);
  /* build_site stamps the report's historicalImport flag on each of its picks, as the site sees them */
  const picks = ['props', 'riskyProps', 'gamePicks', 'parlays'].flatMap(k => report[k] || []).map(p => ({ ...p, historicalImport: report.historicalImport }));
  const all = C.recordOf(picks), favorites = C.recordOf(picks.filter(p => five.has(p.id)));
  assert.equal(picks.length, 26);
  assert.ok(picks.every(C.isUnpricedImport));
  assert.deepEqual([all.wins, all.losses, all.priced, all.units], [0, 0, 0, null], 'no price was recorded, so nothing is totalled');
  assert.deepEqual([all.imported.wins, all.imported.losses, all.imported.voids], [14, 11, 1], 'the results are still shown apart');
  assert.deepEqual([favorites.imported.wins, favorites.imported.losses], [1, 4]);
  const mixed = C.recordOf([...picks, { result: 'win', odds: -110 }, { result: 'loss', odds: -110 }]);
  assert.deepEqual([mixed.wins, mixed.losses, mixed.priced, mixed.unpriced], [1, 1, 2, 0], 'the record and its units describe the same picks');
  assert.equal(C.recordOf([{ result: 'win', odds: -110 }]).imported, null);
});

test('a pick is open only until its quote expires, its entries close or its game starts', () => {
  const now = Date.parse('2026-09-20T12:00:00Z');
  const pick = { status: 'active', expiresAt: '2026-09-20T15:30:00Z', kickoff: '2026-09-20T17:00:00Z' };
  assert.equal(C.isOpen(pick, now), true);
  assert.equal(C.isOpen({ ...pick, expiresAt: '2026-09-20T11:30:00Z' }, now), false);
  assert.equal(C.isOpen({ ...pick, kickoff: '2026-09-20T11:00:00Z' }, now), false);
  assert.equal(C.isOpen({ ...pick, status: 'expired' }, now), false);
  assert.equal(C.isOpen({ ...pick, result: 'win' }, now), false);
});

test('a pick says where it stands in words, and red is only for a loss', () => {
  const now = Date.parse('2026-09-20T12:00:00Z');
  const pick = { status: 'active', expiresAt: '2026-09-20T15:30:00Z', kickoff: '2026-09-20T17:00:00Z' };
  const word = p => C.pickState(p, now).word;
  assert.equal(word(pick), 'Open');
  assert.equal(word({ ...pick, entryNote: 'moved 2 against' }), 'Line moved');
  assert.equal(word({ ...pick, entryNote: 'Closed to new entries at 11:03 AM ET, before its post went out: the quarterback is out.' }), 'Pulled',
    'a play pulled over news before its post says so, not that the line moved');
  assert.equal(word({ ...pick, kickoff: '2026-09-20T11:00:00Z', entryNote: 'before its post went out: news' }), 'Pulled', 'even once its game is on');
  assert.equal(word({ ...pick, expiresAt: '2026-09-20T11:00:00Z' }), 'Price expired');
  assert.equal(word({ ...pick, kickoff: '2026-09-20T11:00:00Z' }), 'In play');
  assert.deepEqual(C.pickState({ ...pick, result: 'win' }, now), { word: 'Won', tone: 'win' });
  assert.deepEqual(C.pickState({ ...pick, result: 'loss' }, now), { word: 'Lost', tone: 'loss' });
  assert.equal(C.pickState({ ...pick, entryNote: 'x' }, now).tone, 'closed', 'a closed pick is grey, not red');
  assert.equal(C.isLongshot({ kind: 'riskyProps' }), true);
  assert.equal(C.isLongshot({ kind: 'parlays', parlayType: 'longshot' }), true);
  assert.equal(C.isLongshot({ kind: 'props' }), false);
});

test('a board line leads with a plain word and backs it with its numbers', () => {
  assert.deepEqual(C.gradeOf({ tier: 'strong', chance: 0.61, push: 0, needs: 0.524, edge: 8.6, thin: false }),
    { tier: 'strong', word: 'Good value', detail: '61% our chance · this price needs 52% to win often enough · 8.6 points above what this price needs' });
  assert.equal(C.gradeOf({ tier: 'lean', chance: 0.7, push: 0.03, needs: 0.5, edge: 20, thin: true }).detail,
    '70% our chance, 3% chance of a tie · this price needs 50% to win often enough · 20.0 points above what this price needs · few games so far');
  assert.deepEqual(C.gradeOf(null), { tier: 'none', word: 'No model read', detail: '' });
  assert.equal(C.gradeOf({ tier: 'lean', chance: 0.6, push: 0, needs: 0.524, edge: 7.6, calibrated: false }).detail,
    '60% our chance · this price needs 52% to win often enough · 7.6 points above what this price needs · not yet checked against results');
  assert.equal(C.gradeOf({ tier: 'lean', chance: 0.62, push: 0, needs: null, calibrated: false }).detail, '62% our chance · no price yet · not yet checked against results');
  const lines = [{ id: 'a', grade: { tier: 'pass', edge: -2 } }, { id: 'b' }, { id: 'c', grade: { tier: 'strong', edge: 6 } },
    { id: 'd', grade: { tier: 'strong', edge: 9 } }, { id: 'e', grade: { tier: 'lean', edge: 3 } }];
  assert.deepEqual(lines.sort(C.byGrade).map(l => l.id), ['d', 'c', 'e', 'a', 'b']);
  const leans = [{ id: 'thin', grade: { tier: 'lean', edge: 30, thin: true } }, { id: 'solid', grade: { tier: 'lean', edge: 3 } }];
  assert.deepEqual(leans.sort(C.byGrade).map(l => l.id), ['solid', 'thin'], 'a solid sample outranks a bigger thin one');
  assert.equal(C.gradeOf(null, 'FBS vs FCS: v2 is not reliable here').detail, 'FBS vs FCS: v2 is not reliable here');
});

test('pick types match the old results page', () => {
  assert.equal(C.category({ kind: 'gamePicks', marketType: 'total' }), 'Totals');
  assert.equal(C.category({ kind: 'gamePicks', marketType: 'spread' }), 'Spreads');
  assert.equal(C.category({ kind: 'props' }), 'Straights');
  assert.equal(C.category({ kind: 'riskyProps' }), 'Risky lines');
  assert.equal(C.category({ kind: 'parlays', parlayType: 'longshot' }), 'Longshots');
  assert.equal(C.category({ kind: 'parlays' }), 'Parlays');
});

test('old links land on the matching new pages', () => {
  const cases = {
    '': { view: 'today' }, '#sports': { view: 'today' }, '#home': { view: 'today' },
    '#record': { view: 'record' }, '#scores': { view: 'scores', league: 'ALL' }, '#props': { view: 'board' }, '#parlays': { view: 'ticket' },
    '#players': { view: 'stats' }, '#research': { view: 'research' }, '#game/NFL-401872932': { view: 'game', id: 'NFL-401872932' },
    '#player/NFL/4430878': { view: 'player', league: 'NFL', id: '4430878' }, '#player/cfb/5': { view: 'player', league: 'CFB', id: '5' },
    '#sport/MLB': { view: 'scores', league: 'MLB' }, '#stats': { view: 'stats', tab: 'charts' },
    '#stats/defense': { view: 'stats', tab: 'defense' },
    '#board/props': { view: 'board', tab: 'props' }, '#board/favorites': { view: 'board', tab: 'favorites' },
    '#team/CFB/2390': { view: 'team', league: 'CFB', id: '2390' }, '#nonsense': { view: 'today' },
    '#pick/CFB-2026-W3-duke-minus-10-vs-stan-dk': { view: 'today', pick: 'CFB-2026-W3-duke-minus-10-vs-stan-dk' },
    '#pick': { view: 'today' },
  };
  for (const [hash, expected] of Object.entries(cases)) assert.deepEqual(C.parseRoute(hash), expected, hash);
  assert.equal(C.shardOf('4430878', 32), 4430878 % 32);
});

test('parlays stay out of the straight-pick units and carry their own stake', () => {
  const picks = [
    { kind: 'gamePicks', odds: -110, result: 'win' },
    { kind: 'gamePicks', odds: -110, result: 'loss' },
    { kind: 'parlays', parlayType: 'longshot', odds: 360, result: 'win', riskUnits: 0.25 },
  ];
  const r = C.recordOf(picks, 2);
  assert.deepEqual([r.wins, r.losses], [1, 1], 'the parlay win is not in the straight record');
  assert.ok(Math.abs(r.units + 0.0909) < 0.001, 'units come from the two straight picks alone');
  assert.equal(r.parlays.staked, 0.25);
  assert.ok(Math.abs(r.parlays.units - 0.9) < 1e-9, '+360 on a quarter unit returns 0.9u');
  assert.ok(Math.abs(C.summaryOf(picks, 2).units - 0.809) < 0.001, 'summaryOf counts everything given to it');
  assert.equal(C.stakeOf({}), 1, 'a pick with no recorded stake is one unit');
});

test('a priced line on a thin sample says too early, not no value', () => {
  const thin = C.gradeOf({ tier: 'pass', chance: 0.81, needs: 0.44, edge: 37, thin: true, calibrated: false });
  assert.equal(thin.word, 'Too early to tell');
  const flat = C.gradeOf({ tier: 'pass', chance: 0.5, needs: 0.52, edge: -2, thin: true });
  assert.equal(flat.word, 'No value');
  const solid = C.gradeOf({ tier: 'lean', chance: 0.62, needs: 0.52, edge: 10, thin: false });
  assert.equal(solid.word, 'Some value');
});

test('a performance caution explains the higher bar without erasing a qualifying line', () => {
  const cautious = C.gradeOf({ tier: 'strong', chance: 0.58, needs: 0.52, edge: 6,
    performanceCaution: true, performanceNeed: 5 });
  assert.deepEqual([cautious.tier, cautious.word], ['strong', 'Good value']);
  assert.match(cautious.detail, /need at least 5 points above what this price needs/);
  const shrunk = C.gradeOf({ tier: 'lean', view: 'pass', chance: 0.52, needs: 0.53, edge: -1 });
  assert.deepEqual([shrunk.tier, shrunk.word], ['pass', 'No value']);
  assert.equal(C.tierOf({ tier: 'lean' }), 'lean');
  assert.equal(C.tierOf(null), 'none');
  const rows = [{ grade: { tier: 'strong', performanceCaution: true } }, { grade: { tier: 'lean' } }];
  assert.equal(rows.sort(C.byGrade)[0].grade.tier, 'strong');
});

test('an early exit credit is a loss on the record and zero in units', () => {
  const credited = { kind: 'props', odds: -113, result: 'loss', earlyExit: true };
  const picks = [credited, { kind: 'props', odds: -110, result: 'win' }];
  const r = C.recordOf(picks, 2);
  assert.equal(r.earlyExits, 1);
  assert.deepEqual([r.wins, r.losses], [1, 1], 'the credited pick still lost');
  assert.equal(C.unitsFor(credited), 0, 'the stake came back');
  assert.ok(Math.abs(r.units - 0.909) < 0.001, 'only the winner moves the units');
  assert.equal(C.unitsFor({ ...credited, earlyExit: false }), -1, 'without the credit it is a full unit');
});

test('one record: the straight plays in wins and losses and units, the side records apart', () => {
  const now = Date.parse('2026-09-26T13:00:00Z');                          // Saturday 9 AM ET
  const play = (id, result, odds, kickoff, extra = {}) => ({ id, result, odds, kickoff, kind: 'gamePicks', ...extra });
  const picks = [
    play('thu', 'win', -111, '2026-09-25T00:15:00Z', { featured: true, posted: true }),        // Thursday night (Eastern)
    play('fri', 'loss', -105, '2026-09-25T23:00:00Z', { featured: true, entryNote: 'before its post went out' }), // pulled: never posted
    play('fri2', 'win', 100, '2026-09-26T00:00:00Z'),                                           // Friday 8 PM ET
    play('old', 'loss', -110, '2026-09-19T17:00:00Z', { posted: true }),                       // last week
    play('open', null, -110, '2026-09-26T19:30:00Z'),
    { id: 'ls', kind: 'parlays', parlayType: 'longshot', legs: [{}, {}, {}], result: 'loss', odds: 583, riskUnits: 0.25, kickoff: '2026-09-25T20:00:00Z' },
    { id: 'w1', historicalImport: true, result: 'win', odds: null, kickoff: '2026-09-07T17:00:00Z' },
  ];
  const r = C.theRecord(picks, now);
  assert.deepEqual([r.season.wins, r.season.losses, r.season.pending], [2, 2, 1], 'every published straight play, pulled or not');
  assert.equal(Math.round(100 * r.season.units) / 100, -0.1, 'one unit a play at the published price: +0.90 - 1 + 1 - 1');
  assert.deepEqual([r.week.wins, r.week.losses], [2, 1], 'this football week, Tuesday to Monday');
  assert.equal(r.lastDay.day, '2026-09-25', 'the last day with a settled play, by Eastern kickoff');
  assert.deepEqual([r.lastDay.wins, r.lastDay.losses], [1, 1]);
  assert.deepEqual([r.potd.wins, r.potd.losses], [1, 0], 'the Pick of the Day counts the days its post went out');
  assert.deepEqual([r.parlays.wins, r.parlays.losses], [0, 1], 'fun parlays on their own line');
  assert.equal(r.imported.wins, 1, 'the Week 1 legs listed apart');
  const priced = C.theRecord([...picks, { id: 'w1b', historicalImport: true, result: 'win', odds: -115, priceAssumed: true, kickoff: '2026-09-07T17:00:00Z' }], now);
  assert.equal(priced.season.wins, 3, 'a Week 1 line priced later counts in the record');
  assert.equal(priced.assumed, 1, 'and the record says its price is assumed');
  assert.equal(C.dayOf('2026-09-26T02:30:00Z'), '2026-09-25', 'a late Friday kickoff is Friday in the East');
  assert.equal(C.unitsFor({ result: 'win', odds: -110, units: 0.91 }), 0.91, 'units saved with the result stand as written');
  assert.equal(C.unitsFor({ result: 'win', odds: -110 }), 100 / 110, 'an older play is summed the same way');
  assert.equal(C.unitsFor({ result: 'loss', odds: -110, units: -1, earlyExit: true }), 0, 'an early-exit credit is zero');
  assert.equal(C.unitsFor({ result: 'void', odds: -110, units: 0 }), null, 'a void is out of the units');
  assert.equal(C.isParlay({ kind: 'parlays' }) && C.isParlay({ legs: [{}] }) && !C.isParlay({ kind: 'props' }), true);
});

test('the simple scorecard combines final model calls and keeps published parlays separate', () => {
  const board = {
    live: [
      { league: 'NFL', model: 'v2.0', season: 2026, updatedThrough: '2026-10-02T00:15Z', summary: { games: 9, side: [5, 3, 1], winner: [6, 2, 0], ou: [4, 4, 0] } },
      { league: 'CFB', model: 'v2.0', season: 2026, updatedThrough: '2026-10-03T00:00Z', summary: { games: 12, side: [7, 5, 0], winner: [10, 2, 0], ou: [8, 4, 1] } },
      { league: 'NFL', model: 'v2.0', season: 2025, summary: { side: [50, 0, 0], winner: [50, 0, 0], ou: [50, 0, 0] } },
      { league: 'NFL', model: 'v1', summary: { side: [99, 0, 0], winner: [99, 0, 0], ou: [99, 0, 0] } },
    ],
    props: { markets: [{ record: [3, 2, 0] }, { record: [4, 1, 1] }] },
  };
  const picks = [
    { league: 'NFL', kind: 'parlays', parlayType: 'longshot', result: 'win', odds: 400, riskUnits: .25 },
    { league: 'CFB', kind: 'parlays', parlayType: 'longshot', result: 'loss', odds: 1000, riskUnits: .25 },
    { league: 'NFL', kind: 'parlays', parlayType: 'ladder', result: 'win', odds: -110, riskUnits: .25 },
  ];
  const all = C.projectionScorecard(board, picks);
  assert.deepEqual(all.spread, [12, 8, 1]);
  assert.deepEqual(all.moneyline, [16, 4, 0]);
  assert.deepEqual(all.total, [12, 8, 1]);
  assert.deepEqual(all.props, [7, 3, 1]);
  assert.deepEqual(all.parlays, [1, 1, 0], 'the ladder stays out of the fun-ticket result');
  assert.deepEqual([all.games, all.updatedThrough], [21, '2026-10-03T00:00Z']);
  const nfl = C.projectionScorecard(board, picks, 'NFL');
  assert.deepEqual(nfl.spread, [5, 3, 1]);
  assert.deepEqual([nfl.games, nfl.updatedThrough], [9, '2026-10-02T00:15Z']);
  assert.deepEqual(C.projectionScorecard(board, picks, 'CFB').props, [0, 0, 0], 'an NFL-only prop comparison never appears under College');
});

test('the 80/20 Climb banks wins, protects the bank on a miss, finishes at $1,000 and stays out of the fun parlays', () => {
  const rung = (id, published, step, stake, payout, result, extra = {}) => ({ id, kind: 'parlays', parlayType: 'ladder', publishedAt: published,
    status: result ? 'settled' : 'active', result, odds: 100, riskUnits: 0.25, legs: [{ title: 'a' }, { title: 'b' }],
    ladder: { run: 1, step, stake, payout, start: 50, goal: 1000 }, ...extra });
  const picks = [rung('r1', '2026-09-27T12:30:00Z', 1, 50, 96, 'win'), rung('r2', '2026-09-28T12:30:00Z', 2, 77, 150, 'loss'),
    rung('r3', '2026-10-01T12:30:00Z', 1, 50, 99, null, { entryNote: 'Closed before its post went out', status: 'expired' }),
    rung('r4', '2026-10-03T12:30:00Z', 1, 50, 97, null)];
  const L = C.theLadder(picks);
  assert.deepEqual([L.run, L.step, L.stake, L.open.id, L.history.map(r => r.id)], [2, 1, 50, 'r4', ['r1', 'r2']]);
  assert.equal(L.best, 96);
  assert.deepEqual([L.banked, L.saved, L.bankPercent, L.ridePercent], [0, 19, 20, 80]);
  assert.deepEqual(L.accounting, { wagered: 127, returned: 96, net: -31, atRisk: 50, wins: 1, losses: 1, pushes: 0, voids: 0 });
  assert.deepEqual(L.history.map(r => r.ladderTotal.net), [46, -31], 'every settled rung preserves the running dollar result');
  const graded = C.theLadder([rung('g', '2026-09-27T10:45:06Z', 1, 50, 94, 'win', { entryNote: 'Closed to new entries at 8:46 AM ET, before its post went out: x' })]);
  assert.deepEqual([graded.step, graded.stake, graded.banked, graded.saved, graded.history.length], [2, 75, 19, 19, 1], 'a pulled rung counts and splits once graded');
  const waiting = C.theLadder([rung('w', '2026-09-28T10:45:06Z', 2, 75, 146, null,
    { entryNote: 'Closed to new entries before its post went out: injury', status: 'expired' })]);
  assert.equal(waiting.open.id, 'w', 'an ungraded pulled rung blocks the next one');
  const topInfo = { run: 1, step: 5, stake: 675, payout: 850, banked: 150, bankThisWin: 170,
    bankedAfter: 320, nextStake: 680, totalAfter: 1000, start: 50, goal: 1000 };
  const top = C.theLadder([rung('a', '2026-09-27T12:30:00Z', 5, 675, 850, 'win', { ladder: topInfo })]);
  assert.deepEqual([top.climbs.length, top.climbs[0].final, top.climbs[0].banked, top.run, top.stake], [1, 1000, 320, 2, 50]);
  assert.deepEqual([top.accounting.wagered, top.accounting.returned, top.accounting.net], [675, 850, 175]);
  assert.deepEqual(C.ladderSplit(94), { bank: 19, ride: 75 });
  const fun = { id: 'f', kind: 'parlays', parlayType: 'longshot', result: 'win', odds: 600, riskUnits: 0.25, legs: [{ title: 'x' }] };
  const rec = C.theRecord([...picks, fun]);
  assert.equal(rec.parlays.wins + rec.parlays.losses, 1, 'only the longshot is a fun parlay');
  assert.equal(rec.ladder.history.length, 2);
  assert.ok(C.isLadder(picks[0]) && !C.isLadder(fun));
});
