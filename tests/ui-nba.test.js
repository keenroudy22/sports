'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const C=require('../site/core.js'),L=require('../site/live.js'),P=require('../site/personal.js');
function load(){const s={module:{exports:{}},exports:{},KRCore:C,KRLive:L,KRPersonal:P,document:{querySelector:()=>null},localStorage:{getItem:()=>null,setItem:()=>{}},console,URL,URLSearchParams,Intl,Date,Math,Map,Set,Promise,AbortController,TextEncoder,TextDecoder,setTimeout,clearTimeout,setInterval,clearInterval};s.window=s;s.self=s;s.globalThis=s;vm.runInNewContext(fs.readFileSync('site/app.js','utf8'),s);vm.runInNewContext(fs.readFileSync('site/app-games.js','utf8'),s);return s;}
test('NBA Today uses the actual lazy app interface and separates historical research from picks',async()=>{const s=load(),api=s.module.exports;const data={heading:'Opening night · October 20',scheduleFresh:true,games:[{seasonType:'regular-season',status:'scheduled',kickoff:'2026-10-20T23:00:00Z',teams:{home:{abbreviation:'NY'},away:{abbreviation:'SA'}},projection:{home:115,away:110,total:225,sparse:true},totalQuote:{line:221.5,over:-110,under:-110,book:'DraftKings',retrievedAt:'2026-10-09T21:00:00Z'}}],trends:[{window:'Last season · regular season',season:2026,name:'Real player',statName:'points',average:20,games:3,values:[18,20,22],dates:['2026-04-01','2026-04-03','2026-04-05']}],prep:[],prepNote:'Current-season games and fresh prices are required.',readiness:{stage:'log',cleanCaptureDays:1,cleanCaptureDaysRequired:14,paperGraded:0,paperGradesRequired:50},trial:{note:'No NBA Trial play has been posted.'}};const ctx=api.gamesContext({get:async path=>{assert.equal(path,'app/nba.json');return data;}});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'<h2>NBA live scores</h2>';const html=await views.nbaToday();for(const text of ['NBA Today','October 20','Research projection','Last season','Prep List','NBA Trial','No NBA Trial play has been posted','NBA live scores','evidence counts toward promotion to Best bets, not the opening-night Trial'])assert.ok(html.includes(text),text);assert.doesNotMatch(html,/moves forward only when both evidence gates clear|NFL|College football|did not load/);});
test('NBA-only renderer is selected before generic other-sport cards without touching NHL or MLB',()=>{const source=fs.readFileSync('site/app.js','utf8');assert.match(source,/if \(state\.league === 'NBA'\) return \(await ensureGames\(\)\)\.nbaToday\(\)/);});
test('NBA posted play leads research, while older results stay in the record fold',async()=>{
 const s=load(),api=s.module.exports,stamp=new Date(Date.now()+86400000).toISOString();
 const play={marketType:'total',direction:'under',line:220.5,odds:-110,book:'DraftKings',kickoff:stamp,teams:{away:{abbreviation:'BOS'},home:{abbreviation:'DET'}},card:'data/cards/trial.png'};
 const data={scheduleFresh:true,trial:{note:'No NBA Trial play has been posted.',plays:[{...play,line:219.5,result:'win',actual:210},play],record:{win:1,loss:0,units:.909,graded:1}}};
 const ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 let html=await views.nbaToday();assert.ok(html.indexOf('id="nba-plays"')<html.indexOf('Player projections vs lines'));
 assert.ok(html.indexOf('under 220.5')<html.indexOf('<summary>NBA Trial record'));
 assert.ok(html.indexOf('under 219.5')>html.indexOf('<summary>NBA Trial record'));
 assert.equal((html.match(/id="nba-plays"/g)||[]).length,1);
 data.trial.plays=[];html=await views.nbaToday();assert.ok(html.indexOf('No NBA Trial play has been posted.')<html.indexOf('Player projections vs lines'));
 assert.doesNotMatch(html,/BEST BET.*220.5/);
});
test('NBA team trends and frozen research cards are visible with season labels and escaped captions',async()=>{
 const s=load(),api=s.module.exports;
 const data={scheduleFresh:true,games:[],trends:[],prep:[],trial:{note:'Separate NBA Trial'},
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
 const data={games:[],scheduleFresh:true,trial:{note:'Separate NBA Trial'},playerProps:{availabilityAt:stamp,rows:[row,{...row,name:'Held player',projection:null,hold:'Availability: Out'}],holds:[{name:'Held player',reason:'Availability: Out'}]}};
 const ctx=api.gamesContext({get:async()=>data});ctx.state.league='NBA';const views=s.KRGames(ctx);views.gamesLive=async()=>'';
 let html=await views.nbaToday();for(const text of ['Player projections vs lines','My projection: 24','19.5','8/10','18/25','Last season','Availability: Out','FAVORITE PROP','Player availability checked'])assert.ok(html.includes(text),text);
 assert.ok(html.includes('Real &lt;player&gt;'));assert.ok(!html.includes('Real <player>'));
 data.playerProps.rows=[{...row,sourceAt:new Date(Date.now()-18000000).toISOString()}];html=await views.nbaToday();assert.ok(!html.includes('My projection: 24'));assert.ok(html.includes('Stale prices are hidden'));
});
