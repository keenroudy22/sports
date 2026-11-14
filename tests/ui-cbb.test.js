'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('../site/core.js'),L=require('../site/live.js'),P=require('../site/personal.js');
function views(get){const s={module:{exports:{}},exports:{},KRCore:C,KRLive:L,KRPersonal:P,document:{querySelector:()=>null},localStorage:{getItem:()=>null,setItem:()=>{}},console,URL,URLSearchParams,Intl,Date,Math,Map,Set,Promise,AbortController,TextEncoder,TextDecoder,setTimeout,clearTimeout,setInterval,clearInterval};s.window=s;s.self=s;s.globalThis=s;vm.runInNewContext(fs.readFileSync('site/app.js','utf8'),s);vm.runInNewContext(fs.readFileSync('site/app-games.js','utf8'),s);return s.KRGames(s.module.exports.gamesContext({get,maybe:path=>get(path).catch(()=>null)}));}
test('CBB research separates prior season stats and historical quote from live bets',async()=>{
 const g={id:'CBB-1',date:'2099-11-02',kickoff:'2099-11-02T23:00Z',teams:{home:{name:'Home'},away:{name:'Away'}},projection:{home:72,away:68,total:140,winProb:.62,neutral:true,sparse:true},stats:{home:{current:{season:2027,games:0},prior:{season:2026,games:30,wins:20,losses:10,ppg:80,allowed:70}}},firstTotal:{line:145.5,book:'DraftKings',capturedAt:'2026-11-01T15:00Z'}};
 const v=views(async path=>path==='app/cbb.json'?{scheduleFresh:true,note:'Research, not picks.',games:[g],sheets:[{file:'cbb-sheet-2099-11-02-1.svg',date:g.date,page:1,pages:1}]}:{players:[]});
 const slate=await v.cbbToday();
 assert.match(slate,/cbb-slate[\s\S]*Projection sheets[\s\S]*Sheet 1\/1/);
 assert.doesNotMatch(slate,/Historical quote|pc-bar/);
 const html=await v.game({id:g.id});
 for(const t of ['2026–27','2025–26','No recorded games','Historical quote, not a live offer','Neutral court','pc-bar','Baseline model win chance','38%','62%'])assert.ok(html.includes(t),t);
 assert.doesNotMatch(html,/Best Bet|positive EV|\b0 scored/);
});
test('CBB cards show the projected favorite and keep missing book spreads explicit', async () => {
 const teams={home:{name:'Butler',abbreviation:'BTLR'},away:{name:'Pitt',abbreviation:'PITT'}};
 const game={id:'CBB-1',kickoff:'2099-11-02T23:00Z',teams,projection:{home:82.5,away:75.5,total:157.9,margin:7.1},
   firstTotal:{line:157.5,book:'DraftKings',capturedAt:'2026-11-12T23:00Z'}};
 const v=views(async path=>path==='app/cbb.json'?{games:[game],scheduleFresh:true}:{players:[]});
 for (const [margin, expected] of [[7.1,'BTLR -7.1'],[-3.2,'PITT -3.2'],[0,'Even']]) {
   game.projection.margin=margin;
   const slate=await v.cbbToday();
   assert.ok(slate.includes(`<small>Kook’n spread</small><b>${expected}</b>`));
   const html=await v.game({id:game.id});
   assert.ok(html.includes(`<span class="k">Spread</span><span>${expected}</span><span>Unavailable</span><span>—</span>`));
   assert.match(html, /Total<\/span><span>157\.9<\/span><span>157\.5/);
 }
});

test('fresh CBB spreads compare the same side and show exact odds on Today and game pages', async () => {
 const now = Date.now();
 const game = {id:'CBB-1', kickoff:new Date(now + 3600000).toISOString(),
   teams:{home:{name:'Butler',abbreviation:'BTLR'},away:{name:'Pitt',abbreviation:'PITT'}},
   projection:{home:82.5,away:75.5,total:157.9,margin:7.0},
   spreadQuote:{homeLine:-3.5,awayLine:3.5,homeOdds:-108,awayOdds:-112,book:'DraftKings',
     observedAt:new Date(now - 60000).toISOString()}};
 const v=views(async path=>path==='app/cbb.json'?{games:[game],scheduleFresh:true}:{players:[]});
 for (const [margin, difference] of [[7, '3.5 toward BTLR'], [0, '3.5 toward PITT'], [3.5, 'Same number']]) {
   game.projection.margin = margin;
   const slate=await v.cbbToday();
   assert.match(slate, /Book spread<\/small><b>BTLR -3\.5 · [−-]108/);
   const html=await v.game({id:game.id});
   assert.ok(html.includes(`<span>BTLR -3.5</span><span>${difference}</span>`));
   assert.match(html, /DraftKings via ESPN · checked/);
   assert.match(html, /BTLR -3\.5 \([−-]108\) · PITT \+3\.5 \([−-]112\)/);
 }
 for (const observedAt of [now - 14460000, now + 60000]) {
   game.spreadQuote.observedAt = new Date(observedAt).toISOString();
   const html = await v.game({id:game.id});
   assert.match(html, /<span>Unavailable<\/span>/);
   assert.doesNotMatch(html, /DraftKings via ESPN|PITT \+3\.5/);
   assert.match(await v.cbbToday(), /Book spread<\/small><b>Unavailable/);
 }
});

test('CBB Today previews six matchups and Games keeps the complete slate', async () => {
 const kickoff = '2099-11-02T23:00:00Z';
 const games = Array.from({length: 9}, (_, i) => ({id: `CBB-${i+1}`, kickoff,
   teams:{home:{name: `Home ${i}`}, away:{name: `Away ${i}`}}}));
 const v = views(async () => ({games, scheduleFresh:true}));
 const today = await v.cbbToday({preview:true});
 assert.equal((today.match(/class="cbb-slate-row"/g) || []).length, 6);
 assert.match(today, /#games\/upcoming\?sport=CBB">View all 9 matchups/);
 assert.match(today, /Compare spreads[\s\S]*Player charts[\s\S]*class="cbb-slate-row"/);
 assert.doesNotMatch(today, /#game\/CBB-9/);
 const complete = await v.cbbToday({gamesPage:true});
 assert.equal((complete.match(/class="cbb-slate-row"/g) || []).length, 9);
 assert.match(complete, /#game\/CBB-9/);
});
test('CBB research handles missing payload instead of football fallback',async()=>{const html=await views(async()=>{throw Error('offline');}).cbbToday();assert.match(html,/CBB research could not be loaded/);assert.doesNotMatch(html,/NFL/);});

test('CBB score-only payload does not fabricate a probability bar',async()=>{
 const g={id:'CBB-old',kickoff:'2099-11-02T23:00Z',teams:{home:{name:'Home'},away:{name:'Away'}},projection:{home:72,away:68,total:140,neutral:false},stats:{}};
 const html=await views(async()=>({scheduleFresh:true,games:[g]})).game({id:g.id});
 assert.doesNotMatch(html,/class="pc-bar"|NaN%|undefined%/);assert.match(html,/72.0/);
});

test('CBB posted picks retain exact terms, result and source separation',async()=>{
 const p={id:'CBB-pick',publishedAt:'2026-11-03T15:00Z',kickoff:'2026-11-03T23:00Z',marketType:'spread',direction:'away',line:10.5,odds:-118,book:'DraftKings',reason:'Current rotation case.',countercase:'Frontcourt mismatch.',game:{teams:{away:{name:'Away',abbreviation:'AWY'},home:{name:'Home',abbreviation:'HOM'}}},result:'loss',actual:-12};
 const html=views(async()=>({})).cbbPicks({picks:{plays:[p],win:0,loss:1,units:-1,note:'Separate from model research.'}});
 for(const text of ['AWY +10.5','-118','LOSS','-1.00u','Current rotation case.','Frontcourt mismatch.','Separate from model research.','AWY scoring margin: -12'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/positive EV|fair odds|guarantee/);
});

test('basketball cards open matchup details and NBA props stay in their own game', async () => {
  const kickoff = '2099-11-02T23:00Z';
  const teams = {home:{id:'1',name:'Home',abbreviation:'HOM'},away:{id:'2',name:'Away',abbreviation:'AWY'}};
  const cbb = {id:'CBB-1',kickoff,teams,projection:{home:72,away:68,total:140}};
  const nba = {id:'NBA-2',providerId:'2',kickoff,teams,status:'scheduled',projection:{home:112,away:108,total:220}};
  const prop = {eventId:'2',athleteId:'42',team:'1',teamName:'Home',name:'Matched player',kickoff,stat:'pts',statName:'Points',line:15.5,over:-110,under:-110,book:'FanDuel',side:'over',sourceAt:new Date().toISOString(),projection:{value:17.2,low:11,high:23}};
  const v = views(async path => {
    if (path === 'app/cbb.json') return {games:[cbb],scheduleFresh:true};
    if (path === 'app/nba.json') return {games:[nba]};
    if (path === 'app/nba-props.json') return {rows:[prop,{...prop,eventId:'3',name:'Other game player'}]};
    if (path === 'app/players/NBA.json') return {players:[['42','Matched player','G','1','HOM','2099-10-31',5,{minutes:31,values:{pts:17.2}}]]};
    if (path === 'app/players/CBB.json') return {players:[['43','College player','G','2','AWY','2099-10-31',5,{minutes:30,recentMinutes:[28,31,30],values:{pts:14.1,reb:5.2,ast:3.1},recent:{pts:13.8}}]]};
    throw Error(path);
  });
  assert.match(await v.cbbToday(), /href="#game\/CBB-1"/);
  const college = await v.game({id:'CBB-1'});
  assert.match(college, /Away at Home/);
  assert.match(college, /College player[\s\S]*prop-vs-label">Book<\/span><b aria-label="Book line unavailable">—<\/b>[\s\S]*prop-vs-label">Kook’n<\/span><b>14\.1/);
  assert.match(college, /#player\/CBB\/43\?stat=pts/);
  const matchup = await v.game({id:'NBA-2'});
  assert.match(matchup, /Matched player/);
  assert.match(matchup, /prop-vs-label">Book<\/span><b>15\.5[\s\S]*prop-vs-label">Kook’n<\/span><b>17\.2[\s\S]*Projection gap[\s\S]*Kook’n range 11\.0–23\.0/);
  assert.match(matchup, /#player\/NBA\/42\?stat=pts&amp;line=15\.5&amp;direction=over&amp;book=FanDuel&amp;game=NBA-2/);
  assert.doesNotMatch(matchup, /Other game player/);
});

test('NBA matchup stat keeps the first ranked comparison and checks team IDs', async () => {
  const kickoff = new Date(Date.now()+3600000).toISOString(), sourceAt = new Date().toISOString();
  const nba = {id:'NBA-2',providerId:'2',kickoff,status:'scheduled',teams:{
    home:{id:'1',name:'Home',abbreviation:'HOM'},away:{id:'2',name:'Away',abbreviation:'AWY'}}};
  const quote = {eventId:'2',athleteId:'42',team:'1',name:'Matched player',kickoff,sourceAt,stat:'pts',
    line:15.5,book:'FanDuel',over:-110,under:-110,side:'over',projection:{value:17.2}};
  const rows = [quote,{...quote,line:17.5,book:'DraftKings',under:-115},
    {...quote,athleteId:'43',team:'999',teamName:'Home',name:'Wrong roster'},
    {...quote,athleteId:'44',team:'1',name:'Research player'},
    {...quote,athleteId:'44',team:'1',name:'Research player',line:30.5,book:'DraftKings'}];
  const v = views(async path => {
    if (path === 'app/nba.json') return {games:[nba],generatedAt:'same',matchupPropEvents:['2']};
    if (path === 'app/nba-props/2.json') return {rows,generatedAt:'same'};
    if (path === 'app/players/NBA.json') return {players:[]};
    throw Error(path);
  });
  const first = await v.game({id:nba.id});
  assert.match(first, /NBA\/42\?stat=pts&amp;line=15\.5&amp;direction=over&amp;book=FanDuel/);
  assert.doesNotMatch(first,/Wrong roster|line=30\.5/);
});
test('basketball matchup links retain verified scores and charts when a game leaves pregame research', async () => {
  const kickoff = new Date(Date.now() - 4 * 3600000).toISOString();
  const teams = {home:{id:'1',name:'Home',abbreviation:'HOM'},away:{id:'2',name:'Away',abbreviation:'AWY'}};
  const game = {id:'CBB-3',providerId:'3',status:'final',kickoff,teams,scores:{home:82,away:74}};
  const heldGame = {id:'CBB-4',status:'scheduled',kickoff,teams,scores:{home:0,away:0}};
  const v = views(async path => {
    if (path === 'app/cbb.json') return {games:[]};
    if (path === 'sports.json') return {leagues:{CBB:{games:[game,heldGame]}}};
    if (path === 'app/players/CBB.json') return {players:[['43','College player','G','2','AWY',kickoff.slice(0,10),5,{minutes:30,values:{pts:14.1},recent:{pts:13.8}}]]};
    throw Error(path);
  });
  const final = await v.game({id:game.id});
  assert.match(final, /Away at Home/);
  assert.match(final, /Final<\/small><b class="num">74<i> – <\/i>82/);
  assert.match(final, /#player\/CBB\/43\?stat=pts&amp;game=CBB-3/);
  assert.match(final, /L5 avg 13\.8/);
  assert.doesNotMatch(final, /14\.1|Kook’n minutes 30|Matchup unavailable/);
  const waiting = await v.game({id:heldGame.id});
  assert.match(waiting, /Score update pending/);
  assert.doesNotMatch(waiting, />0<i> – /);
});
