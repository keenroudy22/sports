'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const C=require('../site/core.js');
const source=fs.readFileSync('site/app.js','utf8');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;

test('public stat names normalize to stored columns and partial market searches remain useful',()=>{
  assert.equal(C.researchContext('#player/NFL/1?stat=receptions').stat,'rec');
  assert.equal(C.researchContext('#player/NFL/1?stat=carries').stat,'car');
  assert.equal(C.researchContext('#charts?stat=receptions').chartStat,'rec');
  assert.equal(C.researchContext('#trends?stat=carries').trendStat,'car');
  assert.equal(C.researchMatches('yards','Rec yds'),true);
  assert.equal(C.researchMatches('receiving','recYds'),true);
  assert.equal(C.researchMatches('CAR','Carries'),false);
});

test('chart research search recognizes a market plus player/team and never ignores the other words', async()=>{
  const body=source.match(/async function playerCharts\(league\) \{([\s\S]*?)\n  \}\n\n  async function playerSearch/)[1];
  const render=new AsyncFunction('C','state','maybe','empty','CHART_STATS','chartHas','chartRows','savePreferences','dayLabel','esc','whenShort','chartTeam','seg','resetFilters','league',body);
  const data={season:2026,games:[{id:'one',day:'2026-10-05',kickoff:'2099-10-05T20:00Z',away:{name:'Carolina Panthers',abbreviation:'CAR'},home:{name:'Detroit Lions',abbreviation:'DET'}}],players:[
    {id:'a',gameId:'one',side:'away',name:'Player One',pos:'RB',rows:[{date:'2026-09-01',stats:{rushYds:0,recYds:12}}],lines:{rushYds:{line:20.5,direction:'over'}}},
    {id:'b',gameId:'one',side:'home',name:'Player Two',pos:'RB',rows:[{date:'2026-09-01',stats:{rushYds:70,recYds:3}}]},
  ]};
  const state={...C.RESEARCH_DEFAULTS,researchQuery:'CAR rushing yards'};
  const run=()=>render(C,state,async path=>path.includes('player-charts')?data:{teams:{}},(a,b,c='')=>a+b+c,
    ['rushYds','recYds','passYds'],(p,k)=>p.rows.some(r=>Object.hasOwn(r.stats,k)),p=>C.chartHistory(p.rows,C.researchStat(state.researchQuery,['rushYds','recYds','passYds'])||state.chartStat,state),()=>{},C.dayLabel,C.esc,C.whenShort,
    (team,game,players,key)=>players.map(p=>`${p.name}:${key}`).join(''),()=>'',()=>'', 'NFL');
  let html=await run();
  assert.match(html,/Player One:rushYds/);assert.doesNotMatch(html,/Player Two:rushYds/);
  assert.match(html,/data-input="researchQuery"/);
  state.researchQuery='Player One over 20.5 rushing yards';
  html=await run();assert.match(html,/Player One:rushYds/);
  state.researchQuery='Missing Player rushing yards';
  html=await run();assert.match(html,/No matching player history/);assert.doesNotMatch(html,/Player One:rushYds/);
  state.researchQuery='passing yards';
  html=await run();assert.match(html,/No matching player history/);assert.match(html,/Pass yds · no history/);
  state.researchQuery='';state.chartStat='passYds';
  html=await run();assert.match(html,/No matching player history/);assert.match(html,/Pass yds · no history/);
});

test('chart links open the exact selected stat and sample without any copied quote or private ticket',()=>{
  const expression=source.match(/const playerChartCard = ([\s\S]*?);\n\n  const chartTeam/)[1];
  const make=new Function('C','state','esc','pic','HEADSHOT','miniPlayerChart','return '+expression);
  const card=make(C,{researchQuery:'Player carries',chartWindow:'last5',ticket:[{odds:900}],stake:999},C.esc,()=>'',{NFL:()=>''},()=> 'chart');
  const html=card({id:'123',name:'Player',pos:'RB'},'car','NFL');
  const href=html.match(/href="([^"]+)"/)[1].replaceAll('&amp;','&');
  const context=C.parseRoute(href).research;
  assert.deepEqual([context.stat,context.playerSeason,context.playerWindow],['car','current','last5']);
  assert.doesNotMatch(href,/odds|ticket|stake|900|999/);
});

test('Trends shares the query and links the selected evidence stat and history window',async()=>{
  const body=source.match(/async function viewTrends\(route\) \{([\s\S]*?)\n  \}\n\n  async function viewMore/)[1];
  const render=new AsyncFunction('C','get','state','esc','odds','ago','whenShort','head','boardTabs','seg','resetFilters','empty','route',body);
  const row={player:'Player One',athleteId:'123',league:'NFL',gameId:'NFL-1',team:{name:'Carolina Panthers',abbr:'CAR'},matchup:'CAR at DET',title:'Player One over 3.5 receptions',
    kind:'main',stat:'rec',direction:'over',line:3.5,odds:-110,book:'Book',kickoff:'2099-10-05T20:00Z',observedAt:new Date().toISOString(),history:Array.from({length:6},(_,i)=>({date:`2026-09-0${i+1}`,value:5}))};
  const state={...C.RESEARCH_DEFAULTS,league:'NFL',researchQuery:'CAR receptions',trendWindow:'last5'};
  const run=()=>render(C,async()=>({rows:[row],generatedAt:new Date().toISOString()}),state,C.esc,C.odds,C.ago,C.whenShort,()=>'',()=>'',()=>'',()=>'',title=>title,{});
  const html=await run();
  assert.match(html,/5\/5 games/);assert.match(html,/data-input="researchQuery" value="CAR receptions"/);
  const href=html.match(/href="(#player[^\"]+)"/)[1].replaceAll('&amp;','&');
  assert.deepEqual([C.parseRoute(href).research.stat,C.parseRoute(href).research.playerWindow],['rec','last5']);
  state.researchQuery='unknown player receptions';assert.match(await run(),/No trends match/);
});

test('control changes save the current history entry, so browser Back/Forward cannot lose the latest query',()=>{
  const rememberBody=source.match(/function rememberContext\(\) \{([^\n]+)\}/)[1];
  const saveBody=source.match(/const savePreferences = \(\) => \{([^\n]+)\};/)[1];
  const state={...C.RESEARCH_DEFAULTS,league:'NFL'},location={hash:'#stats',href:'https://example.test/#stats'};
  const history={state:null,replaceState(next){this.state=next;}};
  const preferences=()=>C.researchPreferences(state);
  const remember=new Function('history','preferences','C','location','state','window',rememberBody);
  const save=new Function('saved','preferences','rememberContext',saveBody);
  const update=()=>save({set(){}},preferences,()=>remember(history,preferences,C,location,state,{scrollY:120}));
  state.researchQuery='London changed';update();const charts=history.state;
  location.hash='#board/props';location.href='https://example.test/#board/props';state.researchQuery='Bijan';update();const board=history.state;
  assert.equal(charts.kr.researchQuery,'London changed');assert.equal(board.kr.researchQuery,'Bijan');
  assert.equal(board.kr.scroll,120);assert.equal(board.kr.ticket,undefined);
});

test('copy has an immediate selectable fallback and changing Save/Add labels keeps stable focus identity',()=>{
  assert.match(source,/field\.value=url\.href;field\.hidden=false/);
  assert.match(source,/type="url" readonly hidden data-copy-url/);
  assert.match(source,/url\.search=''/,'top-level tracking or account parameters are not copied');
  assert.match(source,/boardTabs\('charts',tab==='charts'\)/,'legacy directory/defense controls do not advertise unsupported sharing');
  const body=source.match(/const focusKey = el => \{([\s\S]*?)\n      \};/)[1];
  const key=new Function('el',body);
  const el=(attribute,value,label)=>({tagName:'BUTTON',textContent:label,hasAttribute:name=>name===attribute,getAttribute:name=>name===attribute?value:null});
  assert.equal(key(el('data-watch','line-1','Save')),key(el('data-watch','line-1','Saved')));
  assert.equal(key(el('data-add','line-1','+')),key(el('data-add','line-1','✓')));
  assert.notEqual(key(el('data-watch','line-1','Save')),key(el('data-watch','line-2','Save')));
});
