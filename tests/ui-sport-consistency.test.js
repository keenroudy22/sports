'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('../site/core.js'),L=require('../site/live.js'),P=require('../site/personal.js');
// One Eastern date for both the renderer and its scheduled fixture.
const now=Date.parse('2026-11-02T19:00:00Z');
class FixtureDate extends Date {
 constructor(...args){super(...(args.length ? args : [now]));}
 static now(){return now;}
}
function desk(league,files={}){
 const s={module:{exports:{}},exports:{},KRCore:C,KRLive:L,KRPersonal:P,document:{querySelector:()=>null},localStorage:{getItem:()=>null,setItem:()=>{}},console,URL,URLSearchParams,Intl,Date:FixtureDate,Math,Map,Set,Promise,AbortController,TextEncoder,TextDecoder,setTimeout,clearTimeout,setInterval,clearInterval};s.window=s;s.self=s;s.globalThis=s;
 for(const file of ['site/app.js','site/app-games.js'])vm.runInNewContext(fs.readFileSync(file,'utf8'),s);
 const get=async path=>files[path] || {};
 const ctx=s.module.exports.gamesContext({get,maybe:get,liveFor:()=>null});ctx.state.league=league;ctx.state.games.q='';ctx.state.games.upDay='all';
 return {ctx,views:s.KRGames(ctx)};
}
const kickoff=new Date(now+3600000).toISOString();
const game=(id='one')=>({id,kickoff,date:L.dayOf(kickoff),status:'scheduled',teams:{home:{name:'Home Club',abbreviation:'H'},away:{name:'Away Club',abbreviation:'A'}}});
test('score-only sport pages share tabs, date and team search without football placeholders',async()=>{
 for(const league of ['WNBA','MLB','NHL','EPL','MLS']){
  const {ctx,views}=desk(league,{'sports.json':{leagues:{[league]:{games:[game()]}}}});
  const html=await views.games({tab:'upcoming'});
  for(const text of ['Upcoming','Live &amp; scores','Finals','Find a team','Home Club','Tomorrow'])assert.ok(html.includes(text),`${league}: ${text}`);
  assert.doesNotMatch(html,/Football only for projections|class="pc-bar"/);
  ctx.state.games.q='not-a-team';assert.doesNotMatch(await views.games({tab:'upcoming'}),/Home Club/);
 }
});
test('NBA and CBB games share navigation/search and isolate team filtering',async()=>{
 for(const league of ['NBA','CBB']){
  const file=league==='NBA'?'app/nba.json':'app/cbb.json';
  const data={scheduleFresh:true,generatedAt:'2026-11-02T19:00:00Z',games:[{...game(),projection:{home:72,away:68,total:140,winProb:.6}}],sheets:[]};
  const {ctx,views}=desk(league,{[file]:data});let html=await views.games({tab:'upcoming'});
  for(const text of ['Upcoming','Live &amp; scores','Finals','Find a team','Home Club','pc-bar'])assert.ok(html.includes(text),`${league}: ${text}`);
  ctx.state.games.q='not-a-team';html=await views.games({tab:'upcoming'});assert.doesNotMatch(html,/Home Club|class="pc-bar"/);
 }
});
test('All sports includes supported CBB cards; sheet links change with source version',async()=>{
 const g={...game('CBB-one'),projection:{home:72,away:68,total:140,winProb:.6}};
 const data={scheduleFresh:true,generatedAt:'2026-11-02T19:00:00Z',games:[g],sheets:[{date:g.date,file:'cbb-sheet.svg',page:1,pages:1}]};
 const {views}=desk('ALL',{'app/today.json':{games:[]},'app/cbb.json':data});
 assert.match(await views.games({tab:'upcoming'}),/Home Club/);
 const cbb=desk('CBB',{'app/cbb.json':data});const html=await cbb.views.cbbToday();assert.match(html,/cbb-sheet\.svg\?v=2026-11-02T19%3A00%3A00Z/);
});
