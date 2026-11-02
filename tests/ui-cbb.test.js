'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('../site/core.js'),L=require('../site/live.js'),P=require('../site/personal.js');
function views(get){const s={module:{exports:{}},exports:{},KRCore:C,KRLive:L,KRPersonal:P,document:{querySelector:()=>null},localStorage:{getItem:()=>null,setItem:()=>{}},console,URL,URLSearchParams,Intl,Date,Math,Map,Set,Promise,AbortController,TextEncoder,TextDecoder,setTimeout,clearTimeout,setInterval,clearInterval};s.window=s;s.self=s;s.globalThis=s;vm.runInNewContext(fs.readFileSync('site/app.js','utf8'),s);vm.runInNewContext(fs.readFileSync('site/app-games.js','utf8'),s);return s.KRGames(s.module.exports.gamesContext({get}));}
test('CBB research separates prior season stats and historical quote from live bets',async()=>{
 const g={id:'CBB-1',date:'2099-11-02',kickoff:'2099-11-02T23:00Z',teams:{home:{name:'Home'},away:{name:'Away'}},projection:{home:72,away:68,total:140,winProb:.62,neutral:true,sparse:true},stats:{home:{current:{season:2027,games:0},prior:{season:2026,games:30,wins:20,losses:10,ppg:80,allowed:70}}},firstTotal:{line:145.5,book:'DraftKings',capturedAt:'2026-11-01T15:00Z'}};
 const v=views(async path=>{assert.equal(path,'app/cbb.json');return {scheduleFresh:true,note:'Research, not picks.',games:[g],sheets:[{file:'cbb-sheet-2099-11-02-1.svg',date:g.date,page:1,pages:1}]};});
 const html=await v.cbbToday();for(const t of ['CBB projections &amp; stats','2026–27','2025–26','No recorded games','Historical quote, not a live offer','Neutral court','Sheet 1/1','pc-bar','Baseline model win chance','38%','62%'])assert.ok(html.includes(t),t);
 assert.doesNotMatch(html,/Best Bet|positive EV|\b0 scored/);
});
test('CBB research handles missing payload instead of football fallback',async()=>{const html=await views(async()=>{throw Error('offline');}).cbbToday();assert.match(html,/CBB research could not be loaded/);assert.doesNotMatch(html,/NFL/);});

test('CBB score-only payload does not fabricate a probability bar',async()=>{
 const g={id:'CBB-old',kickoff:'2099-11-02T23:00Z',teams:{home:{name:'Home'},away:{name:'Away'}},projection:{home:72,away:68,total:140,neutral:false},stats:{}};
 const html=await views(async()=>({scheduleFresh:true,games:[g]})).cbbToday();
 assert.doesNotMatch(html,/class="pc-bar"|NaN%|undefined%/);assert.match(html,/72.0/);
});
