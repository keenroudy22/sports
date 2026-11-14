'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const C = require('../site/core.js');
const L = require('../site/live.js');
const P = require('../site/personal.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const moreSource = fs.readFileSync('site/app-more.js', 'utf8');
const playerSource = fs.readFileSync('site/app-player.js', 'utf8');

const loadBrowserApi = () => {
  const sandbox = {
    module: { exports: {} }, exports: {}, KRCore: C, KRLive: L, KRPersonal: P,
    document: { querySelector: () => null }, location: { hash: '' },
    localStorage: { getItem: () => null, setItem: () => {} },
    console, URL, URLSearchParams, Intl, Date, Math, Map, Set, Promise,
    AbortController, TextEncoder, TextDecoder, setTimeout, clearTimeout, setInterval, clearInterval,
  };
  sandbox.globalThis = sandbox;
  sandbox.self = sandbox;
  sandbox.window = sandbox;
  vm.runInNewContext(source, sandbox, { filename: 'site/app.js' });
  vm.runInNewContext(moreSource, sandbox, { filename: 'site/app-more.js' });
  vm.runInNewContext(playerSource, sandbox, { filename: 'site/app-player.js' });
  return { api: sandbox.module.exports, factory: ctx => ({ ...sandbox.KRMore(ctx), ...sandbox.KRPlayer(ctx) }) };
};

test('the real app shared interface renders every lazy view with fixture data', async () => {
  const { api, factory } = loadBrowserApi();
  assert.equal(typeof api.moreContext, 'function');
  assert.equal(typeof factory, 'function');

  const base = api.moreContext();
  assert.equal(typeof base.wl, 'function');
  assert.equal(typeof base.roiOf, 'function');
  assert.equal(typeof base.opponentTrendText, 'function', 'the lazy player page receives its opponent-adjusted trend helper');
  Object.assign(base.state, {
    league: 'ALL', record: { season: 'current', phase: 'current', q: '' },
    watchlist: [], ticket: [], stake: { amount: 1, mode: 'units', unit: 20 },
    arb: { first: 150, second: -130, bankroll: 100 },
  });
  const today = { games: [], picks: [], freshness: {}, health: [], generatedAt: '2026-10-08T18:00:00Z' };
  const routeFixture = { climbRoute: { run: 3, step: 2, saved: 42,
    weekly: {weekStart:'2026-10-19',posted:1,maximum:3,remaining:2},
    image: 'data/cards/climb-route.png', rows: [
      { kind: 'cashed', step: 1, league: 'CFB', day: 'THU 10/8', clock: '7 PM',
        bet: 50, cashes: 81, bank: 16, legs: [{ title: 'Iowa +4.5', odds: -110,
          book: 'FanDuel', href: '#pick/real-rung' }] },
      { kind: 'next', step: 2, league: 'NFL', day: 'SUN 10/11', clock: '1 PM',
        bet: 65, cashes: 106, bank: 21, legs: [] },
    ] } };
  const team = { id: '1', name: 'Fixture Team', abbr: 'FIX', color: '#123456', games: [], defense: [] };
  const context = api.moreContext({
    etDay: () => '2026-10-22',
    get: async path => path === 'app/record.json' ? routeFixture : today,
    maybe: async path => path === 'app/teams/CFB/1.json' ? team
      : path === 'app/players/CFB.json' ? { season: 2026, players: [] }
      : path === 'scoreboard.json' ? { picks: { rows: [] } } : null,
    allPicks: async () => [],
    teamDirectory: async () => ({ teams: { 1: team }, defense: { season: 2026, rows: [] } }),
    lineData: async () => ({ lines: [] }),
    ticketRows: async () => [],
    ticketSummary: () => '<p>Ticket fixture</p>',
  });
  const views = factory(context);
  const cases = [
    ['record', views.record, { tab: 'official' }],
    ['fun', views.record, { tab: 'fun' }],
    ['climb', views.record, { tab: 'climb' }],
    ['start', views.start, {}],
    ['saved', views.saved, {}],
    ['ticket', views.ticket, {}],
    ['arbs', views.arbs, {}],
    ['schedule', views.schedule, {}],
    ['status', views.status, {}],
    ['feedback', views.feedback, {}],
    ['more', views.more, {}],
    ['glossary', views.glossary, {}],
    ['lab', views.lab, {}],
    ['vegas', views.vegas, {}],
  ];
  assert.equal(views.responsible, undefined);
  assert.equal(views.team, undefined, 'the team page lives in the Games bundle');
  const moreHtml = await views.more({});
  assert.doesNotMatch(moreHtml, /Responsible gaming|#responsible/);
  for (const [name, render, route] of cases) {
    const html = await render(route);
    assert.equal(typeof html, 'string', name);
    assert.match(html, /<h1/, name);
    assert.doesNotMatch(html, /Something did not load|is not defined/, name);
  }
  const climbHtml = await views.record({ tab: 'climb' });
  assert.match(climbHtml, /climb-route\.png/);
  assert.match(climbHtml, /#pick\/real-rung/);
  assert.doesNotMatch(climbHtml, /Next step · not posted yet/);
  assert.match(climbHtml, /next pick is not selected/);
  assert.doesNotMatch(climbHtml, /Plan · typical −160/);
  assert.match(climbHtml, /standalone Thursday and Monday/);
  assert.match(climbHtml, /2-3 alternate-line legs at one book; two preferred/);
  assert.match(climbHtml, /Target combined odds: -200 to -150/);
  assert.match(climbHtml, /This week: 1 of 3 steps used across all restarts/);
  assert.match(climbHtml, /NBA is research-only for the Climb/);
  routeFixture.climbRoute.weekly.weekStart = '2026-10-12';
  assert.doesNotMatch(await views.record({tab:'climb'}), /This week: 1 of 3/);
});

test('official record always renders the separate Chef record without changing overall results', async () => {
  const {api,factory}=loadBrowserApi();
  const picks=[{id:'chef',league:'CFB',season:2026,kind:'props',lane:'chef_pick',posted:true,
    riskUnits:1,odds:100,result:'loss',kickoff:'2026-10-28T00:00Z',settledAt:'2026-10-28T04:00Z',
    title:'Player over 2.5 catches',chefEvidence:{policy:'chef-forward-ev-v1'}}];
  const ctx=api.moreContext({allPicks:async()=>picks, get:async()=>({}),
    maybe:async path=>path==='scoreboard.json'?{picks:{rows:[{id:'chef',clv:1}]}}:null});
  Object.assign(ctx.state,{league:'CFB',record:{season:'current',phase:'current',q:''}});
  const html=await factory(ctx).record({tab:'official'});
  assert.match(html,/id="chef-record"/);
  assert.match(html,/Forward EV policy/);
  assert.match(html,/Included in the overall best-bet record/);
  assert.match(html,/beat the closing line on 1 of 1/);
  assert.equal(C.recordBreakdown(picks).all.losses,1);
});


test('Results splits moneylines from spreads and uses saved graded estimates', async () => {
  const { api, factory } = loadBrowserApi();
  const pick = {league:'CFB', season:2026, kind:'gamePicks', lane:'best_bet',
    posted:true, riskUnits:1, odds:100, kickoff:'2026-10-28T00:00Z', title:'Example'};
  const picks = [
    {...pick,id:'ml',marketType:'moneyline',result:'win',probabilityAtPublication:{calibrated:true,chance:.55}},
    {...pick,id:'spread',marketType:'spread',result:'loss',earlyExit:true,probabilityAtPublication:{calibrated:true,chance:.56}},
    {...pick,id:'push',marketType:'spread',result:'push',probabilityAtPublication:{calibrated:true,chance:.65}},
    {...pick,id:'held',marketType:'total',result:'win',probabilityAtPublication:{calibrated:false,chance:.66}},
  ];
  const ctx = api.moreContext({allPicks:async()=>picks,get:async()=>({}),maybe:async()=>null});
  Object.assign(ctx.state,{league:'CFB',record:{season:'current',phase:'current',q:''}});
  const html = await factory(ctx).record({tab:'official'});
  assert.match(html, /Results by market[\s\S]*Moneylines<\/td><td class="n">1–0–0/);
  assert.match(html, /Spreads<\/td><td class="n">0–1–1<\/td><td class="n red">−1\.00u/);
  const calibration = html.split('Posted win chances vs results')[1].split('</details>')[0];
  assert.match(calibration, /50–&lt;60%[\s\S]*55\.5%[\s\S]*1\/2 · 50\.0%/);
  assert.doesNotMatch(calibration, /60–&lt;70%/);
});

test('the Chef record survives a rolling release with an older cached core', async () => {
  const {api,factory}=loadBrowserApi();
  const ctx=api.moreContext({allPicks:async()=>[],get:async()=>({}),maybe:async()=>null});
  ctx.C={...C,chefRecord:undefined};
  Object.assign(ctx.state,{league:'CFB',record:{season:'current',phase:'current',q:''}});
  const html=await factory(ctx).record({tab:'official'});
  assert.match(html,/id="chef-record"/);
  assert.match(html,/No Chef/);
});

test('NBA record keeps posted player terms and voids separate from team margins', async()=>{
 const {api,factory}=loadBrowserApi();
 const p={id:'NBA-prop-test',league:'NBA',kind:'props',lane:'best_bet',posted:true,season:new Date().getUTCFullYear()+1,
   marketType:'prop',market:'ast',player:'Real Player',athleteId:'12',stat:'ast',direction:'over',line:5.5,
   odds:-110,book:'DraftKings',riskUnits:.5,kickoff:new Date().toISOString(),result:'void',actual:null,
   title:'Real Player OVER 5.5 assists',displayTitle:'Real Player OVER 5.5 assists'};
 const ctx=api.moreContext({get:async()=>({games:[],picks:[],communityPicks:[]}),maybe:async()=>null,allPicks:async()=>[p]});
 ctx.state.league='NBA';const views=factory(ctx);
 const html=await views.record({tab:'official'});
 assert.match(html,/Real Player over 5.5 assists/);assert.match(html,/void/);assert.match(html,/0.5u/);assert.doesNotMatch(html,/final null|undefined/);
});

test('NBA milestone board groups verified history by matchup and keeps milestones separate from prices', async()=>{
 const {api,factory}=loadBrowserApi(), kickoff=new Date(Date.now()+3600000).toISOString(), checked=new Date().toISOString();
 const keys=['pts','reb','ast','fg3m','pra','pa','pr','ra','min','fgm','fga','ftm','fta','stl','blk','tov','plusMinus'];
 const values=[12,4,3,1,19,15,16,7,30,4,8,3,4,1,0,1,5];
 const rows=Array.from({length:6},(_,i)=>[`g${i}`,`2026-11-${String(i+1).padStart(2,'0')}`,2027,0,2,'1','2',i%2,'BBB',...values]);
 const index={season:2027,shards:2,players:[['1','Example Guard','G','1','AAA','2026-11-12',6,{games:6,minutes:30,values:{pts:12,ast:3}}]]};
 const games={games:[{id:'NBA-77',providerId:'77',kickoff,status:'scheduled',teams:{away:{id:'1',name:'Alpha Aces',shortName:'Aces',abbreviation:'AAA'},home:{id:'2',name:'Beta Bears',shortName:'Bears',abbreviation:'BBB'}}}]};
 const props={rows:[{eventId:'77',athleteId:'1',stat:'pts',kickoff,line:11.5,over:-110,under:100,book:'DraftKings',sourceAt:checked,projection:{value:12}}]};
 const ctx=api.moreContext({get:async path=>path==='app/players/NBA.json'?index:path==='app/nba.json'?games:path==='app/nba-props.json'?props:path==='app/players/NBA/1.json'?{keys,players:{1:{name:'Example Guard',pos:'G',projection:index.players[0][7],rows}}}:null,
   maybe:async path=>path==='app/nba-props.json'?props:null});
 ctx.state.league='NBA';
 const html=await factory(ctx).basketballMilestones({league:'NBA'});
 assert.match(html,/Alpha Aces/);assert.match(html,/Example Guard/);assert.match(html,/10\+ PTS/);
 assert.match(html,/L5[\s\S]*5\/5/);assert.match(html,/Book main line 11\.5/);assert.match(html,/Kook’n 12/);
 assert.match(html,/line=9\.5/);assert.match(html,/Historical hit rate · not a probability/);
 assert.match(html,/line=9\.5&amp;direction=over&amp;game=NBA-77/);
 assert.match(html,/Milestone price not verified/);assert.doesNotMatch(html,/90% chance|best bet/i);
 const views=factory(ctx);
 const chart=await views.player({league:'NBA',id:'1',stat:'pts',line:'9.5',direction:'over'});
 assert.match(chart,/<small>Chart line<\/small><b class="num">9\.5/);
 assert.match(chart,/6 of 6 over 9\.5 in the games shown/);
 assert.doesNotMatch(chart,/DraftKings|11\.5 -110/);
 ctx.state.player.key=null;
 const exact=await views.player({league:'NBA',id:'1',stat:'pts',line:'11.5',direction:'under'});
 assert.match(exact,/<small>Book line<\/small><b class="num">11\.5/);
 assert.match(exact,/Under 11\.5 \+100<\/b> at DraftKings/);
 assert.match(exact,/0 of 6 under 11\.5 in the games shown/);
 props.rows.push({ ...props.rows[0], book:'FanDuel', under:-115, sourceAt:new Date(Date.now()-1000).toISOString() });
 ctx.state.player.key=null;
 const selectedBook=await views.player({league:'NBA',id:'1',stat:'pts',line:'11.5',direction:'under',book:'FanDuel'});
 assert.match(selectedBook,/Under 11\.5 -115<\/b> at FanDuel/);
 props.rows.pop();
 const laterKickoff = new Date(Date.parse(kickoff) + 86400000).toISOString();
 games.games.push({ ...games.games[0], id:'NBA-78', providerId:'78', kickoff:laterKickoff });
 props.rows.push({ ...props.rows[0], eventId:'78', kickoff:laterKickoff, under:-125, projection:{value:10} });
 ctx.state.player.key=null;
 const selectedGame=await views.player({league:'NBA',id:'1',stat:'pts',line:'11.5',direction:'under',book:'DraftKings',game:'NBA-78'});
 assert.match(selectedGame,/Under 11\.5 -125<\/b> at DraftKings/);
 assert.match(selectedGame,/<small>Kook’n projection<\/small><b class="num">10/);
 props.rows.pop();
 games.games.pop();
 props.rows[0].hold='Availability: Questionable';
 props.rows[0].projection=null;
 ctx.state.player.key=null;
 const held=await views.player({league:'NBA',id:'1',stat:'pts',line:'11.5',direction:'under'});
 assert.match(held,/<small>Kook’n projection<\/small><b class="num">Held/);
 assert.match(held,/Projection held:<\/b> Availability: Questionable/);
 assert.match(held,/0 of 6 under 11\.5 in the games shown/);
 const milestoneHold=await views.basketballMilestones({league:'NBA'});
 assert.match(milestoneHold,/Book main line 11\.5[^<]*Projection held/);
 assert.doesNotMatch(milestoneHold,/Kook’n 12|Kook’n 3/);
});


test('NBA charts use the selected matchup file and keep an unrecorded stat on its own line', async () => {
  const {api,factory}=loadBrowserApi(), seen=[];
  const generatedAt=new Date().toISOString(), kickoff=new Date(Date.now()+3600000).toISOString();
  const index={season:2027,shards:2,players:[['1','Example Guard','G','1','AAA']]};
  const game={id:'NBA-77',providerId:'77',kickoff,teams:{away:{id:'1',name:'Alpha'},home:{id:'2',name:'Beta'}}};
  const row={eventId:'77',athleteId:'1',stat:'ast',line:4.5,over:-114,under:100,book:'FanDuel',sourceAt:generatedAt,kickoff,
    projection:{value:5.2,low:2,high:8,minutes:27.5},currentRole:{minutes:[22,28,27]}};
  const ctx=api.moreContext({get:async path=>{
    seen.push(path);
    if (path==='app/players/NBA.json') return index;
    if (path==='app/players/NBA/1.json') return {keys:['pts'],players:{'1':{name:'Example Guard',pos:'G',
      rows:[['5','2026-11-11',2027,0,2,'1','2',0,'BBB',12]]}}};
    if (path==='app/nba.json') return {generatedAt,games:[game],matchupPropEvents:['77']};
    if (path==='app/nba-props/77.json') return {generatedAt,rows:[row]};
    throw Error(path);
  }});
  const views=factory(ctx);
  const linked=await views.player({league:'NBA',id:'1',stat:'ast',line:'4.5',direction:'over',book:'FanDuel',game:'NBA-77'});
  assert.match(linked,/href="#game\/NBA-77">‹ Matchup/);
  assert.match(linked,/id="nba-stat">Assists/);
  assert.match(linked,/Over 4\.5 -114<\/b> at FanDuel/);
  assert.match(linked,/Kook’n range:<\/b> 2–8/);
  assert.match(linked,/Kook’n minutes:<\/b> 27\.5/);
  assert.match(linked,/Recent workload:<\/b> 22 \/ 28 \/ 27 minutes/);
  ctx.state.player.key=null;
  const moved=await views.player({league:'NBA',id:'1',stat:'ast',line:'4.5',direction:'over',book:'DraftKings',game:'NBA-77'});
  assert.match(moved,/The exact matchup quote and projection are unavailable/);
  assert.doesNotMatch(moved,/Kook’n range:|5\.2|Over 4\.5 -114/);
  assert.match(linked,/No recorded values for this stat/);
  assert.doesNotMatch(linked,/figcaption|0 of 0/);
  assert.deepEqual(seen.filter(path=>path.includes('nba-props')),['app/nba-props/77.json','app/nba-props/77.json']);
  seen.length=0;
  ctx.state.player.key=null;
  const history=await views.player({league:'NBA',id:'1',stat:'pts',game:'NBA-88'});
  assert.match(history,/id="nba-stat">Points/);
  assert.match(history,/Recorded game results/);
  assert.ok(!seen.some(path=>path.includes('nba-props')));
});

test('a completed matchup chart uses the pregame sample and holds the current projection', async () => {
  const {api,factory}=loadBrowserApi();
  const game={id:'CBB-77',kickoff:'2026-11-10T03:00:00Z',status:'final',
    teams:{away:{id:'1',name:'Alpha'},home:{id:'2',name:'Beta'}}};
  const keys=['pts'], entry=['1','Example Guard','G','1','AAA'];
  const rows=[['5','2026-11-08',2027,0,2,'1','2',0,'BBB',12],
    ['77','2026-11-09',2027,0,2,'1','2',0,'BBB',40],
    ['81','2026-11-12',2027,0,2,'1','3',0,'CCC',36]];
  const files={
    'app/players/CBB.json':{season:2027,shards:2,players:[entry]},
    'app/players/CBB/1.json':{keys,players:{'1':{name:'Example Guard',pos:'G',rows,projection:{status:'ready',values:{pts:22}}}}},
    'app/cbb.json':{games:[]},
    'sports.json':{leagues:{CBB:{games:[game]}}}
  };
  const views=factory(api.moreContext({get:async path=>files[path],maybe:async path=>files[path]}));
  const html=await views.player({league:'CBB',id:'1',stat:'pts',line:'16.5',game:'CBB-77'});
  assert.match(html,/at Beta/);
  assert.match(html,/Pregame projection is unavailable for this matchup/);
  assert.match(html,/Points: 12 against 16\.5/);
  assert.doesNotMatch(html,/gameId\/(77|81)|<b class="num">22<\/b>/);
});

test('NBA Prop Finder search uses the complete matchup quotes and keeps the unfiltered preview small', async () => {
 const {api,factory}=loadBrowserApi(), now=Date.now();
 const kickoff=new Date(now+3600000).toISOString(), generatedAt=new Date(now-60000).toISOString();
 const game={id:'NBA-77',providerId:'77',kickoff,status:'scheduled'};
 const featured={eventId:'77',athleteId:'1',name:'Featured Guard',stat:'pts',kickoff,line:10.5,over:-110,
   side:'over',book:'FanDuel',sourceAt:generatedAt,projection:{value:12}};
 const quote={...featured,athleteId:'2',name:'Rotation Guard',line:8.5,book:'DraftKings'};
 const files={'app/players/NBA.json':{players:[]},'app/nba.json':{games:[game],matchupPropEvents:['77'],generatedAt},
   'app/nba-props.json':{rows:[featured],generatedAt},'app/nba-props/77.json':{rows:[featured,quote],generatedAt}};
 const paths=[];
 const read=async path=>{paths.push(path);return files[path];};
 const ctx=api.moreContext({get:read,maybe:read}),views=factory(ctx);
 assert.doesNotMatch(await views.basketballPlayers({league:'NBA'}),/Rotation Guard/);
 assert.ok(!paths.includes('app/nba-props/77.json'));
 ctx.state.players.q='Rotation Guard';
 assert.match(await views.basketballPlayers({league:'NBA'}),/line=8\.5&amp;direction=over&amp;book=DraftKings&amp;game=NBA-77/);
 assert.ok(paths.includes('app/nba-props/77.json'));
});

test('basketball prop finder links short histories and exact saved prices without false lean styling', async () => {
 const { api, factory } = loadBrowserApi();
 const now = Date.now(), kickoff = new Date(now + 3600000).toISOString();
 const index = { players: [['1','Aidan McDowell','G','10','SHSU','2026-11-11',1,null],
   ['2','Bench Guard','G','10','SHSU','2026-11-10',2,null]] };
 const row = { eventId:'77', athleteId:'1', name:'Aidan McDowell', teamAbbr:'SHSU', kickoff, stat:'pts', line:15.5,
   over:102, under:-120, side:'under', book:'DraftKings', sourceAt:new Date(now - 5 * 3600000).toISOString(),
   projection:{value:13.2}, favorite:true };
 const props = { rows:[row] };
 const ctx = api.moreContext({ get:async () => index, maybe:async () => props });
 ctx.state.players.q = 'mcdowell aidan';
 const views = factory(ctx);
 let html = await views.basketballPlayers({ league:'CBB' });
 assert.match(html, /#player\/CBB\/1\?stat=pts[\s\S]*1 recorded game[\s\S]*Game log/);
 assert.doesNotMatch(html, /Bench Guard|No recorded player/);
 html = await views.basketballPlayers({ league:'NBA' });
 assert.match(html, /stat=pts&amp;line=15\.5&amp;direction=under&amp;book=DraftKings&amp;game=NBA-77/);
 assert.match(html, /Under -120 · DraftKings · Earlier quote/);
 assert.match(html, /Saved line/);
 assert.doesNotMatch(html, /Research lean/);
 row.sourceAt = new Date(now).toISOString();
 assert.match(await views.basketballPlayers({ league:'NBA' }), /Research lean/);
 props.rows.push({ ...row, stat:'ast', hold:'Availability: Questionable', projection:null });
 html = await views.basketballPlayers({ league:'NBA' });
 assert.match(html, /Player directory/);
 assert.doesNotMatch(html, /13\.2|Research lean/);
});
