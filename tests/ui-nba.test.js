'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const C=require('../site/core.js'),L=require('../site/live.js'),P=require('../site/personal.js');
function load(){const s={module:{exports:{}},exports:{},KRCore:C,KRLive:L,KRPersonal:P,document:{querySelector:()=>null},localStorage:{getItem:()=>null,setItem:()=>{}},console,URL,URLSearchParams,Intl,Date,Math,Map,Set,Promise,AbortController,TextEncoder,TextDecoder,setTimeout,clearTimeout,setInterval,clearInterval};s.window=s;s.self=s;s.globalThis=s;vm.runInNewContext(fs.readFileSync('site/app.js','utf8'),s);vm.runInNewContext(fs.readFileSync('site/app-games.js','utf8'),s);return s;}
test('NBA games do not fetch player details; player views retain every row and handle detail failure',async()=>{
 const s=load(),api=s.module.exports,seen=[],stamp=new Date().toISOString(),kickoff=new Date(Date.now()+3600000).toISOString();
 const base={games:[],scheduleFresh:true,playerPropsFile:'nba-props.json',playerProps:{availabilityAt:stamp}};
 const rows=Array.from({length:8},(_,i)=>({name:'Player '+i,teamName:'Home',kickoff,sourceAt:stamp,statName:'points',line:4.5,over:-110,under:-110,book:'DraftKings',hold:'Role not confirmed'}));
 let fail=false;
 const views=s.KRGames(api.gamesContext({get:async path=>{seen.push(path);if(fail)throw Error('offline');return {rows};}}));
 await views.nbaToday({data:base,embedded:true,mode:'lines',type:'games'});assert.equal(seen.length,0);
 const html=await views.nbaToday({data:base,embedded:true,mode:'players'});
 assert.deepEqual(seen,['app/nba-props.json']);for(let i=0;i<8;i++)assert.ok(html.includes('Player '+i));
 assert.ok(!base.playerProps.rows,'renderer does not mutate cached overview');
 fail=true;const error=await views.nbaToday({data:base,embedded:true,mode:'players'});
 assert.ok(error.includes('Player comparisons could not be loaded'));assert.ok(!error.includes('Player 0'));
});
test('NBA Today uses the actual lazy app interface and separates historical research from picks',async()=>{const s=load(),api=s.module.exports;const data={heading:'Opening night · October 20',scheduleFresh:true,games:[{seasonType:'regular-season',status:'scheduled',kickoff:'2026-10-20T23:00:00Z',teams:{home:{abbreviation:'NY'},away:{abbreviation:'SA'}},projection:{home:115,away:110,total:225,sparse:true},totalQuote:{line:221.5,over:-110,under:-110,book:'DraftKings',retrievedAt:'2026-10-09T21:00:00Z'}}],trends:[{window:'Last season · regular season',season:2026,name:'Real player',statName:'points',average:20,games:3,values:[18,20,22],dates:['2026-04-01','2026-04-03','2026-04-05']}],prep:[],prepNote:'Current-season games and fresh prices are required.',readiness:{stage:'log',cleanCaptureDays:1,cleanCaptureDaysRequired:14,paperGraded:0,paperGradesRequired:50},trial:{note:'No NBA play has been posted.'}};const ctx=api.gamesContext({get:async path=>{assert.equal(path,'app/nba.json');return data;}});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'<h2>NBA live scores</h2>';const html=await views.nbaToday();for(const text of ['NBA Today','October 20','Research projection','Last season','Prep List','NBA picks','No NBA play has been posted','NBA live scores','Saved pregame forecasts and later outcomes are tracked separately from posted picks'])assert.ok(html.includes(text),text);assert.doesNotMatch(html,/moves forward only when both evidence gates clear|NFL|College football|did not load/);});
test('NBA-only renderer is selected before generic other-sport cards without touching NHL or MLB',()=>{const source=fs.readFileSync('site/app.js','utf8');assert.match(source,/if \(state\.league === 'NBA'\) return \(await ensureGames\(\)\)\.nbaToday\(\)/);});
test('NBA delayed schedule snapshots never show past-tip projections or fabricated live scores',async()=>{
 const s=load(),api=s.module.exports,kickoff=new Date().toISOString(),stamp=new Date().toISOString();
 const g={id:'NBA-lag',status:'scheduled',kickoff,teams:{home:{name:'Home',abbreviation:'HOM'},away:{name:'Away',abbreviation:'AWY'}},scores:{home:0,away:0},projection:{home:114,away:110,total:224},totalQuote:{line:220.5,over:-110,under:-110,book:'DraftKings',retrievedAt:stamp}};
 const data={games:[g],scheduleFresh:true},views=s.KRGames(api.gamesContext({get:async()=>data}));
 const html=await views.nbaToday({data,embedded:true,mode:'lines',type:'games'}),summary=views.nbaSummary(data);
 for(const page of [html,summary]){assert.match(page,/Update pending/);assert.match(page,/Tip time passed/);assert.match(page,/#games\/live\?sport=NBA/);assert.doesNotMatch(page,/<small>Projected<\/small>|114|110|224|220.5|nba-comparison|<small>Live<\/small>/);}
 assert.equal(g.status,'scheduled');assert.equal(g.projection.total,224,'source remains unchanged');
 g.status='in_progress';g.scores={home:22,away:20};assert.match(views.nbaSummary(data),/<small>Live<\/small>/);assert.doesNotMatch(views.nbaSummary(data),/Update pending/);
 g.status='final';assert.match(views.nbaSummary(data),/<small>Final<\/small>/);
});
test('NBA current minutes remain distinct from confirmed workload and old production rates',async()=>{
 const s=load(),api=s.module.exports,stamp=new Date().toISOString(),kickoff=new Date(Date.now()+3600000).toISOString();
 const row={name:'Current player',teamName:'Home',kickoff,sourceAt:stamp,rosterAt:stamp,statName:'points',line:15.5,over:-110,under:-110,book:'DraftKings',hold:'Starting role changed this season; current workload review needed',currentRole:{games:2,minutes:[28,32],starts:2,asOf:stamp,source:'https://www.espn.com/boxscore'}};
 const views=s.KRGames(api.gamesContext({get:async()=>({})}));
 const html=await views.nbaToday({data:{games:[],playerProps:{rows:[row]}},embedded:true,mode:'players'});
 for(const word of ['This season’s workload','28 / 32 minutes','2 starts','Roster checked','not tonight’s confirmed minutes','Starting role changed'])assert.ok(html.includes(word),word);
 assert.doesNotMatch(html,/News-aware estimate|FAVORITE PROP|Historical baseline:/);
});
test('NBA matchups show spread total and moneyline pairs without inventing picks or probabilities',async()=>{
 const s=load(),api=s.module.exports,stamp=new Date().toISOString(),kickoff=new Date(Date.now()+3600000).toISOString();
 const g={id:'NBA-1',kickoff,status:'scheduled',teams:{home:{name:'Home',abbreviation:'HOM'},away:{name:'Away',abbreviation:'AWY'}},projection:{home:114,away:110,total:224,margin:4},spreadQuote:{homeLine:-3.5,awayLine:3.5,home:-110,away:-110,book:'DraftKings',retrievedAt:stamp},totalQuote:{line:220.5,over:-115,under:-105,book:'DraftKings',retrievedAt:stamp},moneylineQuote:{home:-150,away:130,book:'DraftKings',retrievedAt:stamp}};
 const ctx=api.gamesContext({get:async()=>({games:[g]})});ctx.state.league='NBA';const views=s.KRGames(ctx);
 let html=await views.games({tab:'upcoming'});
 for(const word of ['Spread','Difference','220.5','Moneyline: HOM','+130','0.5 toward HOM','3.5 higher','Projection differences, not picks'])assert.ok(html.includes(word),word);
 assert.doesNotMatch(html,/Estimated win chance|My side|No lean/);
 g.spreadQuote.retrievedAt=new Date(Date.now()-18000000).toISOString();
 html=await views.games({tab:'upcoming'});assert.ok(!html.includes('0.5 toward HOM'));assert.ok(html.includes('Moneyline: HOM'));assert.ok(html.includes('Unavailable'));
 g.status='final';g.scores={home:112,away:111};html=await views.games({tab:'final'});
 assert.doesNotMatch(html,/Moneyline: HOM|nba-comparison|Book total/);
});
test('All sports Games merges NBA into day counts, search and finals without college filters hiding it',async()=>{
 const s=load(),api=s.module.exports,stamp=new Date(Date.now()+3600000).toISOString();
 const n={id:'NBA-join',status:'scheduled',kickoff:stamp,teams:{away:{name:'Boston Celtics',abbreviation:'BOS'},home:{name:'Detroit Pistons',abbreviation:'DET'}},projection:{away:110,home:114,total:224,sparse:true}};
 const f={id:'CFB-join',league:'CFB',kickoff:stamp,home:{name:'Home College',abbr:'HC'},away:{name:'Away College',abbr:'AC'},v2:{home:30,away:20,total:50},tier:'mismatch',window:'night'};
 // Keep distinct Eastern dates even when the suite runs just before midnight or across DST.
 const data={games:[n,{...n,id:'NBA-next',kickoff:new Date(Date.parse(stamp)+172800000).toISOString()}]},ctx=api.gamesContext({get:async()=>({games:[f]}),maybe:async path=>path==='app/nba.json'?data:null,withLive:games=>({games,refreshed:{}})});
 ctx.state.league='ALL';ctx.state.games.upDay='all';ctx.state.games.nav={window:'noon',close:true,conf:'all'};
 const views=s.KRGames(ctx);let html=await views.games({});assert.match(html,/Boston Celtics/);assert.match(html,/All · 3/);assert.doesNotMatch(html,/No game matches these filters/);
 ctx.state.games.q='Detroit';html=await views.games({});assert.match(html,/Boston Celtics/);assert.doesNotMatch(html,/Home College/);
 ctx.state.games.q='';data.games=[{...n,status:'final',scores:{away:110,home:114}}];html=await views.games({tab:'final'});assert.match(html,/Boston Celtics/);assert.match(html,/Final/);
 ctx.state.league='CFB';html=await views.games({});assert.doesNotMatch(html,/Boston Celtics/);
});
test('embedded NBA research honors mode, type, query and stale-price boundaries',async()=>{
 const s=load(),api=s.module.exports,stamp=new Date().toISOString(),kickoff=new Date(Date.now()+3600000).toISOString();
 const row={name:'NBA Player',teamName:'Boston Celtics',kickoff,sourceAt:stamp,statName:'points',line:10.5,over:-110,under:-115,book:'DraftKings',hold:'Availability: Out'};
 const data={scheduleFresh:true,games:[],playerProps:{rows:[row]},teamTrends:[{team:{name:'Boston Celtics'},window:'Last season',season:2026,games:10,points:110,allowed:108}]};
 const ctx=api.gamesContext({get:async()=>{throw Error('embedded data should be reused')}}),views=s.KRGames(ctx);
 let html=await views.nbaToday({data,research:true,embedded:true,mode:'lines',type:'props',q:'Boston'});
 assert.match(html,/NBA Player/);assert.doesNotMatch(html,/Matchups & projections|Team trends|id="nba-plays"|NBA Today<\/h1>/);
 html=await views.nbaToday({data,research:true,embedded:true,mode:'trends'});assert.match(html,/Boston Celtics/);assert.doesNotMatch(html,/NBA Player/);
 html=await views.nbaToday({data,research:true,embedded:true,mode:'players',type:'games'});assert.match(html,/NBA Player/);
 html=await views.nbaToday({data,research:true,embedded:true,mode:'lines',q:'no match'});assert.doesNotMatch(html,/NBA Player/);
 data.playerProps.rows=[{...row,sourceAt:new Date(Date.now()-18000000).toISOString()}];html=await views.nbaToday({data,research:true,embedded:true,mode:'players'});assert.doesNotMatch(html,/NBA Player/);assert.match(html,/Stale prices are hidden/);
});
test('NBA Today and All-sports summary use football projection cards and separate upcoming dates',async()=>{
 const s=load(),api=s.module.exports,now=new Date(),today=now.toISOString(),tomorrow=new Date(+now+86400000).toISOString();
 const game=(id,kickoff,away,home)=>({id,kickoff,status:'scheduled',teams:{away:{id:'1',name:away,abbreviation:'AWY',logo:'https://a.espncdn.com/a.png'},home:{id:'2',name:home,abbreviation:'HOM'}},projection:{away:110,home:114,total:224,sparse:true}});
 const data={games:[game('NBA-today',today,'Boston Celtics','Detroit Pistons'),game('NBA-tomorrow',tomorrow,'Tomorrow Away','Tomorrow Home')],scheduleFresh:true,readiness:{readyForLiveTrial:true},trial:{note:'NBA picks is open.'}};
 const ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 const html=await views.nbaToday(),fold=html.indexOf('<summary>Upcoming NBA');
 assert.ok(html.indexOf('Matchups &amp; projections')<0);assert.ok(html.indexOf('Matchups & projections')<html.indexOf('Player projections vs lines'));
 assert.match(html,/class="proj"/);assert.ok(html.includes('Boston Celtics'));assert.ok(html.includes('a.espncdn.com/a.png'));
 assert.ok(html.indexOf('Tomorrow Away')>fold);assert.ok(!html.slice(0,fold).includes('Tomorrow Away'));
 assert.ok(html.includes('NBA picks · model research'));assert.ok(!html.includes('NBA picks starts Oct. 20'));
 const summary=views.nbaSummary(data);assert.ok(summary.includes('Today’s NBA'));assert.ok(summary.includes('Boston Celtics'));assert.ok(!summary.includes('Tomorrow Away'));
 assert.equal((summary.match(/class="small muted nba-history"/g)||[]).length,1);
 assert.doesNotMatch(summary,/Thin history|class="caution"|Research projection, not a best bet/);
 assert.match(summary,/last season’s team ratings/);
 assert.match(html,/Research projections/);
});
test('projection grid fits its own container instead of forcing viewport columns',()=>{
 const css=fs.readFileSync('site/app.css','utf8');
 assert.match(css,/\.projs \{[^}]*repeat\(auto-fit, minmax\(min\(100%, 320px\), 1fr\)\)/);
 assert.doesNotMatch(css,/@media[^{}]*\{\s*\.projs\s*\{[^}]*repeat\([23],/);
});
test('NBA neutral context does not erase football-specific history or FCS warnings',()=>{
 const s=load(),api=s.module.exports,ctx=api.gamesContext({get:async()=>({})});
 const game={id:'CFB-1',league:'CFB',kickoff:new Date().toISOString(),away:{name:'Away'},home:{name:'Home'},v2:{away:10,home:20,total:30,sparse:true}};
 assert.match(ctx.projCard(game),/Thin history/);
 assert.match(ctx.projCard({...game,fcs:true}),/FBS vs FCS/);
 assert.doesNotMatch(ctx.projCard({...game,league:'NBA'}),/Thin history/);
});
test('NBA Research and Games expose stored projections instead of a football-only dead end',async()=>{
 const s=load(),api=s.module.exports,kickoff=new Date(Date.now()+3600000).toISOString();
 const data={games:[{id:'NBA-1',kickoff,status:'scheduled',teams:{away:{name:'Boston Celtics',abbreviation:'BOS'},home:{name:'Detroit Pistons',abbreviation:'DET'}},projection:{away:110,home:114,total:224}}],scheduleFresh:true};
 const ctx=api.gamesContext({get:async path=>{assert.equal(path,'app/nba.json');return data;}});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 const games=await views.games({tab:'upcoming'});assert.ok(games.includes('Boston Celtics'));assert.ok(!games.includes('Football only for projections'));
 const research=await views.nbaToday({research:true});assert.ok(research.includes('NBA projections, props &amp; trends'));assert.ok(!research.includes('id="nba-plays"'));
 const source=fs.readFileSync('site/app.js','utf8');assert.ok(source.includes("if (state.league === 'NBA') return (await ensureGames()).nbaToday({ research: true })"));
});
test('NBA posted play leads research, while older results stay in the record fold',async()=>{
 const s=load(),api=s.module.exports,stamp=new Date(Date.now()+86400000).toISOString();
 const play={marketType:'total',direction:'under',line:220.5,odds:-110,book:'DraftKings',kickoff:stamp,teams:{away:{abbreviation:'BOS'},home:{abbreviation:'DET'}},card:'data/cards/trial.png'};
 const data={scheduleFresh:true,trial:{note:'No NBA play has been posted.',plays:[{...play,line:219.5,result:'win',actual:210},play],record:{win:1,loss:0,units:.909,graded:1}}};
 const ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 let html=await views.nbaToday();assert.ok(html.indexOf('id="nba-plays"')<html.indexOf('Player projections vs lines'));
 assert.ok(html.indexOf('under 220.5')<html.indexOf('<summary>NBA record'));
 assert.ok(html.indexOf('under 219.5')>html.indexOf('<summary>NBA record'));
 assert.equal((html.match(/id="nba-plays"/g)||[]).length,1);
 data.trial.plays=[{...play,kickoff:new Date(Date.now()-3600000).toISOString()}];html=await views.nbaToday();
 assert.ok(html.indexOf('under 220.5')<html.indexOf('<summary>NBA record'),'live and awaiting-final plays stay above research');
 data.trial.plays=[];html=await views.nbaToday();assert.ok(html.indexOf('No NBA play has been posted.')<html.indexOf('Player projections vs lines'));
 assert.doesNotMatch(html,/BEST BET.*220.5/);
});
test('NBA team trends and frozen research cards are visible with season labels and escaped captions',async()=>{
 const s=load(),api=s.module.exports;
 const data={scheduleFresh:true,games:[],trends:[],prep:[],trial:{note:'Separate NBA picks'},
  teamTrends:[{window:'LAST SEASON',season:2026,team:{name:'Boston Celtics'},points:119.6,allowed:108.4,games:10,first:'2026-03-01T00:00:00Z',last:'2026-04-01T00:00:00Z'}],
  editorial:[{title:'NBA PROJECTIONS',day:'2026-10-20',card:'data/cards/nba-projections-2026-10-20.png',text:'Boston Celtics <script>bad</script>'}]};
 const ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';
 const views=s.KRGames(ctx);views.gamesLive=async()=>'';const html=await views.nbaToday();
 for(const text of ['Team trends','Boston Celtics','119.6','108.4','Last 10 recorded games','LAST SEASON','NBA research cards','nba-projections-2026-10-20.png'])assert.ok(html.includes(text),text);
 assert.ok(!html.includes('<script>bad</script>'));assert.ok(html.includes('&lt;script&gt;'));
});
test('NBA prop view shows numeric projection, exact-line samples and holds without fabricated probability',async()=>{
 const s=load(),api=s.module.exports;const stamp=new Date().toISOString(),kickoff=new Date(Date.now()+3600000).toISOString();
 const row={name:'Real <player>',teamName:'Detroit Pistons',kickoff,sourceAt:stamp,statName:'points',line:19.5,over:-110,under:-115,book:'DraftKings',side:'over',gap:4.5,favorite:true,projection:{value:24,minutes:30,season:2026,window:'Last season',sample:10,low:15,high:30},last5:{hits:4,games:5},last10:{hits:8,games:10},seasonHistory:{hits:18,games:25},why:'30 minutes × own rate',caution:'Not opponent-adjusted.'};
 const data={games:[],scheduleFresh:true,trial:{note:'Separate NBA picks'},playerProps:{availabilityAt:stamp,rows:[row,{...row,name:'Held player',projection:null,hold:'Availability: Out'}],holds:[{name:'Held player',reason:'Availability: Out'}]}};
 const ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 let html=await views.nbaToday();for(const text of ['Player projections vs lines','Historical baseline: 24','19.5','8/10','18/25','Last season','Availability: Out','FAVORITE PROP','Player availability checked','not a confirmed workload'])assert.ok(html.includes(text),text);
 assert.ok(html.includes('Real &lt;player&gt;'));assert.ok(!html.includes('Real <player>'));
 data.playerProps.rows=[{...row,projection:{...row.projection,value:16,minutes:20,baselineValue:24,baselineMinutes:30,minutesBasis:'analyst-estimate'},roleReview:{headline:'Bench <role>',explanation:'My estimate, not a limit.',checkedAt:stamp,sources:[{url:'https://example.com/news',label:'Current report'}]}}];
 html=await views.nbaToday();for(const text of ['News-aware estimate: 16','20 estimated minutes','Old baseline: 24 at 30','not a coach-announced limit','Bench &lt;role&gt;','Current report'])assert.ok(html.includes(text),text);
 data.playerProps.rows=[{...row,sourceAt:new Date(Date.now()-18000000).toISOString()}];html=await views.nbaToday();assert.ok(!html.includes('Historical baseline: 24'));assert.ok(html.includes('Stale prices are hidden'));
});
test('NBA projection bars use stored model chances and hide unknown, invalid and started estimates',async()=>{
 const s=load(),api=s.module.exports,kickoff=new Date(Date.now()+3600000).toISOString();
 const g={id:'NBA-bar',kickoff,status:'scheduled',teams:{away:{name:'Away',abbreviation:'AWY',color:'#003087'},home:{name:'Home',abbreviation:'HOM',color:'#ce1141'}},projection:{away:110,home:114,total:224,winProb:.73}};
 const data={games:[g],scheduleFresh:true},ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 for (const html of [await views.games({tab:'upcoming'}),await views.nbaToday(),await views.nbaToday({research:true})]) {
  assert.match(html,/Model win chance: Away 27%, Home 73%/);
  assert.match(html,/width:27\.0%;background:#003087/);assert.match(html,/width:73\.0%;background:#ce1141/);
  assert.match(html,/not injury-adjusted or a bet/);
 }
 g.rosterContext={adjustedMarkets:[],note:'Baseline score model.',holds:['Unknown <rotation>']};
 assert.match(await views.nbaToday(),/Unknown &lt;rotation&gt;/);
 g.rosterContext={adjustedMarkets:['total'],note:'Roster-adjusted total.',holds:[]};
 assert.match(await views.nbaToday(),/not injury-adjusted or a bet/);
 g.rosterContext.adjustedMarkets.push('margin');
 assert.match(await views.nbaToday(),/validated roster adjustment applied; not a bet/);
 delete g.rosterContext;
 for (const chance of [undefined,null,-.1,1.1,NaN,true]) {
  g.projection.winProb=chance;
  assert.doesNotMatch(await views.nbaToday(),/class="pc-bar"/);
 }
 g.projection.winProb=.73;
 for (const status of ['in_progress','final']) {
  g.status=status;assert.doesNotMatch(await views.nbaToday(),/class="pc-bar"/);
 }
 g.status='scheduled';g.kickoff=new Date(Date.now()-3600000).toISOString();
 assert.doesNotMatch(await views.nbaToday(),/class="pc-bar"/);
 g.kickoff=kickoff;g.projection.winProb=.5;
 assert.match(await views.nbaToday(),/Model win chance: Away 50%, Home 50%/);
 const football=ctx.projCard({league:'CFB',away:{name:'Away'},home:{name:'Home'},v2:{away:20,home:24,total:44,winProb:.6}});
 assert.match(football,/Estimated win chance: Away 40%, Home 60%/);
});

test('posted NBA props show the exact player stat and DNP void without a missing team or null final',async()=>{
 const s=load(),api=s.module.exports;
 const play={id:'NBA-prop-test',marketType:'player',player:'Real <Player>',stat:'reb',direction:'under',line:6.5,odds:105,book:'DraftKings',riskUnits:.5,kickoff:new Date(Date.now()+3600000).toISOString(),teams:{home:{abbreviation:'HOM'},away:{abbreviation:'AWY'}},card:'data/cards/prop.png'};
 const data={games:[],trial:{plays:[play],record:{win:0,loss:0,units:0}}};
 const ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 let html=await views.nbaToday({data});assert.match(html,/Real &lt;Player&gt; under 6.5 rebounds/);assert.match(html,/0.5u/);assert.doesNotMatch(html,/undefined/);
 play.result='void';play.actual=null;html=await views.nbaToday({data});assert.match(html,/void/);assert.doesNotMatch(html,/final null|final undefined/);
});

test('All-sports Today shows actual posted NBA props before matchup research',()=>{
 const s=load(),views=s.KRGames(s.module.exports.gamesContext());
 const play={id:'NBA-prop-all',marketType:'player',player:'Real Player',stat:'pts',direction:'over',line:20.5,odds:-110,book:'DraftKings',riskUnits:.5,kickoff:new Date().toISOString(),teams:{home:{abbreviation:'HOM'},away:{abbreviation:'AWY'}},card:'data/cards/prop.png'};
 const html=views.nbaSummary({games:[],trial:{plays:[play],record:{win:0,loss:0,units:0}}});
 assert.match(html,/Real Player over 20.5 points/);assert.match(html,/data\/cards\/prop.png/);assert.doesNotMatch(html,/undefined/);
});
