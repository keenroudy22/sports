// Optional integration checks against the real app with a controlled scoreboard transport.
import assert from 'node:assert/strict';
const base=process.env.AUDIT_URL || 'http://localhost:8765/';
const target=await (await fetch('http://localhost:9234/json/new?about:blank',{method:'PUT'})).json();
const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
let id=0;const pending=new Map();
ws.onmessage=({data})=>{const p=JSON.parse(data);if(p.id){const [ok,no]=pending.get(p.id);pending.delete(p.id);p.error?no(p.error):ok(p.result);}};
const call=(method,params={})=>new Promise((ok,no)=>{pending.set(++id,[ok,no]);ws.send(JSON.stringify({id,method,params}));});
const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result?.value;};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function ready(){for(let i=0;i<80;i++){await pause(100);if(await ev(`!!document.querySelector('#view h1')`))return;}throw Error('page not ready');}
await call('Page.enable');await call('Runtime.enable');
await call('Emulation.setDeviceMetricsOverride',{width:375,height:850,deviceScaleFactor:1,mobile:true});
await call('Page.addScriptToEvaluateOnNewDocument',{source:`
  window.__calls=0;window.__fail=false;window.__ticks=[];window.__offset=0;
  const originalNow=Date.now;Date.now=()=>originalNow()+window.__offset;
  const originalInterval=window.setInterval;
  window.setInterval=(fn,ms,...args)=>{if(ms===60000)window.__ticks.push(fn);return originalInterval(fn,ms,...args);};
  const originalFetch=window.fetch;
  window.fetch=(url,options)=>{
    if(!String(url).includes('site.web.api.espn.com'))return originalFetch(url,options);
    window.__calls++;if(window.__fail)return Promise.reject(Error('test offline'));
    const event=i=>({id:'test'+i,date:new Date(originalNow()+3600000).toISOString(),competitions:[{
      date:new Date(originalNow()+3600000).toISOString(),status:{type:{state:'pre',name:'STATUS_SCHEDULED'}},
      competitors:[{homeAway:'away',team:{id:'a'+i,abbreviation:'AWY'}},{homeAway:'home',team:{id:'h'+i,abbreviation:'HME'}}],
      odds:[{provider:{name:'DraftKings'},moneyline:{away:{close:{odds:'+120'}},home:{close:{odds:'-140'}}}}]
    }]});
    return Promise.resolve({ok:true,json:async()=>({events:[event(1),event(2)]})});
  };`});
try {
 await call('Page.navigate',{url:base+'#scores/MLB'});await ready();await pause(800);
 // Select tomorrow when the controlled fixture crosses midnight in Eastern time.
 await ev(`(()=>{const day=KRLive.dayOf(Date.now()+3600000);document.querySelector('[data-set="scoresDate:'+day+'"]')?.click()})()`);await pause(700);
 assert.equal(await ev(`document.querySelectorAll('[data-persist^="odds-MLB-test"]').length`),2);
 await ev(`(()=>{const d=document.querySelector('[data-persist="odds-MLB-test1"]');d.open=true;d.querySelector('summary').focus();window.scrollTo(0,160);window.__beforeY=scrollY;window.__offset+=46000;window.__ticks.forEach(fn=>fn())})()`);await pause(700);
 assert.deepEqual(await ev(`(()=>{const d=document.querySelector('[data-persist="odds-MLB-test1"]');return [d.open,document.querySelector('[data-persist="odds-MLB-test2"]').open,document.activeElement===d.querySelector('summary'),Math.abs(scrollY-window.__beforeY)<3]})()`),[true,false,true,true]);
 await ev(`window.__fail=true;window.__offset+=46000;window.__ticks.forEach(fn=>fn())`);await pause(700);
 assert.equal(await ev(`document.querySelectorAll('[data-persist^="odds-"]').length`),0);
 assert.match(await ev(`document.querySelector('.live-freshness').textContent`),/unavailable.*last checked/);
 const count=await ev('window.__calls');await ev('window.__ticks.forEach(fn=>fn())');await pause(400);assert.equal(await ev('window.__calls'),count);
 await call('Page.navigate',{url:base+'#board/props'});await ready();await pause(300);
 assert.equal(await ev(`document.querySelector('.board-tabs [aria-current="page"]').textContent`),'Props');
 await call('Page.navigate',{url:base+'#trends'});await ready();await pause(300);
 const filter=await ev(`document.querySelector('input[type="search"]')?.outerHTML || ''`);
 if(filter){await ev(`(()=>{const e=document.querySelector('input[type="search"]');e.focus();e.value='check';window.__old=e;window.__ticks.forEach(fn=>fn())})()`);await pause(400);assert.equal(await ev(`document.activeElement===window.__old && window.__old.isConnected`),true);}
 console.log('PASS: refresh keeps one expanded game, focus and scroll; outage hides quotes, preserves honest freshness and backs off; Props navigation and focused input survive.');
} finally {await fetch('http://localhost:9234/json/close/'+target.id);ws.close();}
