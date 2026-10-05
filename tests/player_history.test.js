'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../site/core.js');

// [eventId, date, provider season, week, season type, team, opponent, home, ...stats]
const row = (id, date, season, value, type = 2) => [id, date, season, 1, type, 'a', 'b', 1, value];

test('player history defaults to the provider current season, not calendar year or latest player appearance', () => {
  const rows = [row('jan', '2026-01-04', 2025, 150), row('prior', '2025-12-28', 2025, 120),
    row('current', '2026-09-06', 2026, 230), row('playoff', '2026-01-11', 2025, 300, 3)];
  assert.deepEqual(C.playerHistory(rows, 2026).map(r => r[0]), ['current']);
  assert.deepEqual(C.playerHistory(rows, 2025).map(r => r[0]), ['prior', 'jan'], 'January belongs to its saved football season');
  assert.deepEqual(C.playerHistory(rows.slice(0, 2), 2026), [], 'no current games does not silently fall back to an old season');
});

test('older seasons require an explicit year or All selection; postseason stays excluded', () => {
  const rows = [row('old', '2024-10-05', 2024, 0), row('prior', '2025-09-06', 2025, 11),
    row('post', '2025-12-30', 2025, 99, 3), row('now', '2026-09-05', 2026, 46)];
  assert.deepEqual(C.playerHistory(rows, 2026, 'all').map(r => r[0]), ['old', 'prior', 'now']);
  assert.deepEqual(C.playerHistory(rows, 2026, '2025').map(r => r[0]), ['prior']);
  assert.deepEqual(C.playerHistory(rows, 2026, 2024).map(r => r[0]), ['old']);
});

test('player windows apply after season and exclusive game-date cutoff, without importing old games', () => {
  const rows = [row('old', '2025-09-30', 2025, 900), ...Array.from({length: 8}, (_, i) =>
    row(String(i + 1), `2026-09-${String(i + 1).padStart(2, '0')}`, 2026, i + 1))].reverse();
  assert.deepEqual(C.playerHistory(rows, 2026, 'current', 'last5', '2026-09-07T20:00:00Z').map(r => r[0]), ['2', '3', '4', '5', '6']);
  assert.deepEqual(C.playerHistory(rows, 2026, 'current', 'last10', '2026-09-03').map(r => r[0]), ['1', '2']);
  assert.equal(C.playerHistory(rows, 2026, 'current', 'last20').length, 8);
});

test('player history preserves zero, negative and unknown observations and does not mutate stored rows', () => {
  const rows = [row('late', '2026-09-20', 2026, null), row('early', '2026-09-06', 2026, -2), row('zero', '2026-09-13', 2026, 0)];
  const snapshot = JSON.stringify(rows);
  const result = C.playerHistory(rows, 2026);
  assert.deepEqual(result.map(r => r[8]), [-2, 0, null]);
  assert.notEqual(result, rows);
  assert.equal(JSON.stringify(rows), snapshot);
  assert.equal(C.playerHistory(Array.from({length: 25}, (_, i) => row(String(i), `2026-09-${String(i + 1).padStart(2, '0')}`, 2026, i)), 2026).length, 25,
    'the full selected season is not silently capped at 20 games');
});

test('Landry Lyddy regression: current season excludes backup appearances from 2023–2025', () => {
  const values = [2, 51, 68, 0, 0, 11, 0, 128, 267, 46, 25, 194, 243];
  const dates = ['2023-10-07', '2023-10-14', '2023-10-21', '2024-10-05', '2024-11-02', '2025-09-06', '2025-09-13',
    '2025-11-08', '2025-11-15', '2026-09-05', '2026-09-12', '2026-09-19', '2026-09-26'];
  const rows = values.map((value, i) => row(String(i), dates[i], Number(dates[i].slice(0, 4)), value));
  const current = C.playerHistory(rows, 2026).map(r => r[8]);
  assert.deepEqual(current, [46, 25, 194, 243]);
  assert.deepEqual(C.hits(current, 206.5), {over: 1, under: 3, push: 0, n: 4});
  assert.equal(C.summarize(current).avg, 127);
  assert.equal(C.playerHistory(rows, 2026, 'all').length, 13);
});

const playerViewFixture = ({nextSeason = 2026, withNext = true} = {}) => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const body = source.match(/async function viewPlayer\(route\) \{([\s\S]*?)\n  \}\n\n  const chart =/)[1];
  const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
  const render = new AsyncFunction('C','state','get','head','nextGameFor','maybe','esc','DASH','watchButton','seg','stat','whenShort','section','quoteMeta','chart','empty','gameLog','ordinal','shareResearch','HEADSHOT','route',body);
  const keys = ['passYds'];
  const current = [row('old', '2025-12-28', 2025, 900), row('one', '2026-09-01', 2026, 10),
    row('two', '2026-09-08', 2026, 30), row('zero', '2026-09-15', 2026, 0), row('unknown', '2026-09-22', 2026, null),
    row('post', '2026-09-29', 2026, 999, 3)];
  current[2][6]='c'; current[2][7]=0;
  const players = {'1':{name:'Current Player',pos:'QB',rows:current}, '2':{name:'Prior Only',pos:'QB',rows:[row('prior-only','2025-12-28',2025,750)]}};
  const index = {season:2026,shards:1,players:[['1','Current Player','QB','a'],['2','Prior Only','QB','a']]};
  const teams = {teams:{a:{name:'Team A',abbr:'A'},b:{name:'Team B',abbr:'B'},c:{abbr:'C'}},defense:{season:2026,rows:{}}};
  const next = {side:'home',game:{id:'NFL-next',season:nextSeason,kickoff:'2099-10-05T20:00Z',home:{id:'a'},away:{id:'b'}},detail:{forecast:{players:{home:{players:[]}}}}};
  const lines = ['1','2'].map(athleteId=>({athleteId,gameId:'NFL-next',market:'passing yards',line:206.5,direction:'under',state:'open',odds:-110,observedAt:new Date().toISOString()}));
  const state = {historyPlayer:null,playerSeason:'current',playerWindow:'all',stat:'passYds'};
  const captured = {stats:[],charts:[],logs:[]};
  const stat = (label,value,note='') => {captured.stats.push({label,value,note});return `<stat>${label}:${value}:${note}</stat>`;};
  const get = async path => path==='app/players/NFL.json'?index:path.startsWith('app/players/NFL/')?{keys,players}:teams;
  const run = async (id='1',research) => {
    captured.stats=[];captured.charts=[];captured.logs=[];
    return render(C,state,get,(title,text)=>title+text,async()=>withNext?next:null,async()=>({lines}),C.esc,C.DASH,()=>'',()=>'',stat,C.whenShort,
      (title,body)=>title+body,()=>'',(rows,values)=>{captured.charts.push({rows,values});return 'chart';},
      (title,text)=>title+text,rows=>{captured.logs.push(rows);return 'log';},String,()=>'<button>Copy research link</button>',{NFL:athleteId=>`https://images.test/${athleteId}.png`},{league:'NFL',id,research});
  };
  return {state,captured,run,players,keys};
};

test('player detail current-season scope drives chart, averages, hit count, splits, and game log together', async () => {
  const f=playerViewFixture(), original=JSON.stringify(f.players);
  const html=await f.run();
  assert.match(html,/2026 season · 4 games/);
  assert.deepEqual(f.captured.charts[0].rows.map(r=>r[0]),['one','two','zero','unknown']);
  assert.deepEqual(f.captured.charts[0].values,[10,30,0,null]);
  assert.deepEqual(f.captured.logs[0].map(r=>r[0]),['one','two','zero','unknown']);
  const value=label=>f.captured.stats.find(s=>s.label===label)?.value;
  assert.equal(value('Average'),'13.3');assert.equal(value('Median'),'10.0');assert.equal(value('Hit count'),'3/3');
  assert.equal(value('Home'),'5.0');assert.equal(value('Away'),'30.0');assert.equal(value('Vs this opponent'),'5.0');
  assert.equal(value('Games'),4);
  assert.equal(f.captured.stats.find(s=>s.label==='Games').note,'3 with this stat recorded');
  assert.equal(JSON.stringify(f.players),original);
});

test('player detail places the player portrait directly beneath the profile header', async () => {
  const f=playerViewFixture();
  const html=await f.run();
  assert.match(html,/class="page-head who"/);
  assert.match(html,/class="player-profile-art"/);
  assert.match(html,/class="player-profile-photo" src="https:\/\/images\.test\/1\.png" alt="Current Player"/);
  assert.ok(html.indexOf('class="page-head who"') < html.indexOf('class="player-profile-art"'));
  assert.ok(html.indexOf('class="player-profile-art"') < html.indexOf('Copy research link'));
});

test('player detail includes older observations only after explicit season choice and labels that scope', async () => {
  const f=playerViewFixture();
  await f.run();
  f.state.playerSeason='all';
  const all=await f.run();
  assert.match(all,/All seasons · 5 games/);
  assert.deepEqual(f.captured.charts[0].rows.map(r=>r[0]),['old','one','two','zero','unknown']);
  assert.deepEqual(f.captured.logs[0].map(r=>r[0]),['old','one','two','zero','unknown']);
  assert.equal(f.captured.stats.find(s=>s.label==='Average').value,'235.0');
  assert.equal(f.captured.stats.find(s=>s.label==='Hit count').value,'3/4');
  f.state.playerSeason='2025';
  const prior=await f.run();
  assert.match(prior,/2025 season · 1 game/);
  assert.deepEqual(f.captured.charts[0].values,[900]);
  assert.deepEqual(f.captured.logs[0].map(r=>r[0]),['old']);
});

test('opening another player restores current-season defaults and an old-only player stays empty', async () => {
  const f=playerViewFixture({withNext:false});
  await f.run();f.state.playerSeason='all';f.state.playerWindow='last5';
  const html=await f.run('2');
  assert.equal(f.state.historyPlayer,'NFL:2');assert.equal(f.state.playerSeason,'current');assert.equal(f.state.playerWindow,'all');
  assert.match(html,/0 games this season/);assert.match(html,/No games in this season/);
  assert.equal(f.captured.charts.length,0);assert.deepEqual(f.captured.logs[0],[]);
  assert.equal(f.captured.stats.find(s=>s.label==='Average').value,C.DASH);
  assert.equal(f.captured.stats.find(s=>s.label==='Games').value,0);
  assert.doesNotMatch(html,/750/,'last year is never displayed as current-season history');
});

test('player detail honors upcoming event season metadata before the player index season', async () => {
  const f=playerViewFixture({nextSeason:2025});
  const html=await f.run();
  assert.match(html,/2025 season · 1 game/);
  assert.deepEqual(f.captured.charts[0].values,[900]);
});

test('explicit player links restore stat, season and sample; bare links still open current season', async () => {
  const f=playerViewFixture();
  const context=C.researchContext('#player/NFL/1?stat=passYds&season=2025&sample=last5');
  const html=await f.run('1',context);
  assert.match(html,/2025 season · 1 game · last 5/);
  assert.deepEqual(f.captured.charts[0].values,[900]);
  assert.equal(f.state.stat,'passYds');
  f.state.historyPlayer=null; // A bare route is a new entry, not an instruction to reuse an older season.
  await f.run();
  assert.equal(f.state.playerSeason,'current');
  assert.deepEqual(f.captured.charts[0].values,[10,30,0,null]);
});

test('an explicit player stat with no stored coverage never silently substitutes another stat', async () => {
  const f=playerViewFixture();
  await f.run('1',C.researchContext('#player/NFL/1?stat=car'));
  assert.equal(f.state.stat,'car');
  assert.deepEqual(f.captured.charts[0].values,[null,null,null,null]);
  assert.equal(f.captured.stats.find(s=>s.label==='Average').value,C.DASH);
});

test('skill-player pages offer Any TD and the observed scoring and usage stats', async () => {
  const f=playerViewFixture({withNext:false});
  f.keys.splice(0,f.keys.length,'rushTD','recTD','recLong','rzTgt','i10Tgt','snapPct');
  f.players['1'].pos='TE';
  f.players['1'].rows=[
    ['one','2026-09-01',2026,1,2,'a','b',1,0,1,18,2,1,.7],
    ['two','2026-09-08',2026,2,2,'a','c',0,0,0,25,3,2,.8],
    ['three','2026-09-15',2026,3,2,'a','b',1,1,0,12,1,1,.6],
  ];
  const html=await f.run();
  for(const [key,label] of [['anyTD','Any TD'],['recTD','Rec TD'],['recLong','Long rec'],['rzTgt','RZ targets'],['i10Tgt','Inside-10 tgts'],['snapPct','Snap %']]) {
    assert.match(html,new RegExp(`stat:${key}[^>]*>${label}`));
  }
  assert.equal(f.state.stat,'anyTD');
  assert.deepEqual(f.captured.charts[0].values,[1,0,1]);
  assert.equal(f.captured.stats.find(s=>s.label==='Average').value,'0.7');
});

const propModalFixture = ({season=2025,kickoff='2025-10-01T20:00Z'}={}) => {
  const source=fs.readFileSync('site/app.js','utf8');
  const body=source.match(/async function propContext\(row\) \{([\s\S]*?)\n  \}\n\n  \/\* One player line/)[1];
  const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
  const render=new AsyncFunction('C','maybe','newestFirst','esc','fixed','ordinal','chart','empty','row',body);
  const rows=[row('older','2024-10-01',2024,900),row('prior-game','2025-09-20',2025,10),
    row('target-game','2025-10-01',2025,250),row('later','2025-10-08',2025,300),row('current','2026-09-01',2026,500)];
  const payloads={
    'app/players/NFL.json':{season:2026,shards:1},
    'app/players/NFL/0.json':{keys:['passYds'],players:{1:{name:'Historic Player',pos:'QB',rows}}},
    'app/teams/NFL.json':{teams:{a:{abbr:'A'},b:{abbr:'B'}},defense:{season:2026,rows:{b:{g:8,QB:{passYds:666.1}}},
      last5:{b:{QB:{passYds:777.1}}},prior:{season:2025,rows:{b:{g:12,QB:{passYds:888.1}}}}}},
    'app/games/NFL-target.json':{season,home:{id:'a'},away:{id:'b'},forecast:{players:{home:{players:[]}}}},
    'app/teams/NFL/b.json':{games:[],defense:[
      {gameId:'older-defense',date:'2024-09-18',season:2024,opp:'a',allowed:{QB:{passYds:901}}},
      {gameId:'old-before',date:'2025-09-18',season:2025,opp:'a',allowed:{QB:{passYds:112}}},
      {gameId:'old-zero',date:'2025-09-19',season:2025,opp:'a',allowed:{QB:{passYds:0}}},
      {gameId:'old-unknown',date:'2025-09-20',season:2025,opp:'a',allowed:{QB:{passYds:null}}},
      {gameId:'old-same-day',date:'2025-10-01',season:2025,opp:'a',allowed:{QB:{passYds:333}}},
      {gameId:'old-after',date:'2025-10-08',season:2025,opp:'a',allowed:{QB:{passYds:444}}},
      {gameId:'current-before',date:'2026-09-08',season:2026,opp:'a',allowed:{QB:{passYds:221}}},
      {gameId:'current-same-day',date:'2026-09-15',season:2026,opp:'a',allowed:{QB:{passYds:333}}},
      {gameId:'current-after',date:'2026-09-20',season:2026,opp:'a',allowed:{QB:{passYds:555}}},
    ]},
  };
  const charts=[];
  const run=()=>render(C,async path=>payloads[path] || null,list=>[...list].sort((a,b)=>String(b[1]).localeCompare(String(a[1]))),
    C.esc,C.fixed,String,(rows,values)=>{charts.push({rows,values});return 'chart';},(title,text)=>title+text,
    {league:'NFL',athleteId:'1',position:'QB',market:'passing yards',line:206.5,direction:'under',gameId:'NFL-target',kickoff});
  return {run,charts};
};

test('a historical prop modal uses its event season and only observations before that game', async () => {
  const f=propModalFixture(),html=await f.run(),charts=f.charts;
  assert.match(html,/2025 season · 1 game/);
  assert.deepEqual(charts[0].rows.map(r=>r[0]),['prior-game']);
  assert.deepEqual(charts[0].values,[10]);
  assert.match(html,/1 of 1 under 206.5/);
  assert.match(html,/1-game average 10.0/);
  assert.doesNotMatch(html,/900|250|300|500/,'older and later player values stay outside the event-season history');
  assert.match(html,/Pregame defense rankings are unavailable/);
  assert.doesNotMatch(html,/666\.1|777\.1|888\.1/,'current aggregate, last-five and prior aggregate ranks do not leak into an old receipt');
  assert.deepEqual(charts[1].rows.map(r=>r[0]),['old-before','old-zero','old-unknown']);
  assert.deepEqual(charts[1].values,[112,0,null],'defense history honors season/date and preserves zero versus unknown');
});

test('a historical receipt from this season cannot show present-day aggregate defense ranks', async () => {
  const f=propModalFixture({season:2026,kickoff:'2026-09-15T20:00Z'}),html=await f.run();
  assert.match(html,/Pregame defense rankings are unavailable/);
  assert.doesNotMatch(html,/666\.1|777\.1|888\.1/);
  assert.deepEqual(f.charts[1].rows.map(r=>r[0]),['current-before']);
  assert.deepEqual(f.charts[1].values,[221]);
});

test('unknown kickoff fails closed for aggregate defense comparisons; future same-season matchup retains them', async () => {
  const unknown=await propModalFixture({season:2026,kickoff:null}).run();
  assert.match(unknown,/Pregame defense rankings are unavailable/);
  assert.doesNotMatch(unknown,/666\.1|777\.1|888\.1/);
  const future=await propModalFixture({season:2026,kickoff:'2099-09-15T20:00Z'}).run();
  assert.match(future,/666\.1/);assert.match(future,/777\.1/);assert.match(future,/888\.1/);
});
