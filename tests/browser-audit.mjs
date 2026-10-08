// Optional real-Chrome audit. Run a local site server and Chrome with --remote-debugging-port=9234.
// No dependencies, no production writes. Artifacts are outside the repository.
import fs from 'node:fs';
const base = process.env.AUDIT_URL || 'http://localhost:8765/';
const out = process.env.AUDIT_OUT || '/tmp/kookn-overnight-qa';
const port = process.env.AUDIT_PORT || '9234';
fs.mkdirSync(out, {recursive:true});
const target = await (await fetch(`http://localhost:${port}/json/new?about:blank`, {method:'PUT'})).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const waiting = new Map(), errors = [];
let activeRoute = null;
ws.onmessage = ({data}) => { const p = JSON.parse(data); if(p.id) { const [ok,no] = waiting.get(p.id) || []; waiting.delete(p.id); p.error ? no?.(p.error) : ok?.(p.result); } else if(p.method === 'Runtime.exceptionThrown') { const d=p.params.exceptionDetails; errors.push({route:activeRoute,text:d.text,url:d.url,line:d.lineNumber,column:d.columnNumber,description:d.exception?.description}); } };
const call = (method,params={}) => new Promise((ok,no) => { waiting.set(++id,[ok,no]);ws.send(JSON.stringify({id,method,params})); });
const ev = async expression => (await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result?.value;
const pause = ms => new Promise(r => setTimeout(r, ms));
await call('Page.enable'); await call('Runtime.enable'); await call('Network.enable');
await call('Network.setCacheDisabled',{cacheDisabled:true});
const widths = (process.env.AUDIT_WIDTHS || '320,375,390,430,768,1440').split(',').map(Number);
const routes = (process.env.AUDIT_ROUTES || 'today,board,board/props,board/favorites,games,stats,stats/search,trends,record,model,scores/MLB,scores/NHL,lab,schedule,ticket,more,research,arbs').split(',');
const results = [];
for (const width of widths) {
  await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
  for (const route of routes) {
    activeRoute = `${route}@${width}`;
    await call('Page.navigate',{url:base+'#'+route});
    for(let i=0;i<80;i++) { await pause(150); if(await ev(`!!document.querySelector('#view h1')`)) break; }
    await pause(250);
    await ev('document.fonts.ready.then(()=>true)');
    if(process.env.AUDIT_EXPAND) await ev(`document.querySelectorAll('details').forEach(e=>e.open=true)`);
    if(process.env.AUDIT_TEXT_SCALE) await ev(`document.querySelectorAll('#view *').forEach(e=>{if(!e.children.length) e.style.fontSize=(parseFloat(getComputedStyle(e).fontSize)*${Number(process.env.AUDIT_TEXT_SCALE)})+'px'})`);
    await pause(100);
    const result = await ev(`(() => {
      // These containers scroll horizontally by design; document-level overflow still fails below.
      const allowed = '.table-wrap,.seg,.filters,.board-tabs,.depth-line,.chip-scroll';
      const bad = [...document.querySelectorAll('#view *')].filter(e => {
        if(e.closest(allowed) || !e.getClientRects().length) return false;
        const r=e.getBoundingClientRect(); return r.right>innerWidth+1 || r.left < -1;
      }).slice(0,10).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,80)}));
      const clipped = [...document.querySelectorAll('#view .eyebrow,#view h1,#view h2,#view h3,#view .empty p')].filter(e=>{
        if(!e.getClientRects().length) return false;
        const range=document.createRange();range.selectNodeContents(e);const r=range.getBoundingClientRect();
        for(let p=e.parentElement;p && p.id !== 'view';p=p.parentElement) {
          if(['hidden','clip'].includes(getComputedStyle(p).overflowX)) {const b=p.getBoundingClientRect();if(r.right>b.right+2 || r.left<b.left-2) return true;}
        }
        return false;
      }).map(e=>e.textContent.slice(0,80));
      const text=document.querySelector('#view')?.textContent || '';
      const error=/did not load/i.test(text) || ['Could not load this page','The data for this page is unavailable right now'].some(message=>text.includes(message));
      return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,bad,clipped,title:document.querySelector('h1')?.textContent,error};
    })()`);
    results.push({route,...result});
    if(['today','schedule','scores/MLB','stats','trends','record/climb'].includes(route) && [375,1440].includes(width)) {
      const shot = await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      fs.writeFileSync(`${out}/${route.replaceAll('/','-')}-${width}.png`,Buffer.from(shot.data,'base64'));
    }
  }
}
fs.writeFileSync(`${out}/audit.json`,JSON.stringify({base,results,errors},null,2));
console.log(JSON.stringify({pages:results.length,issues:results.filter(r=>r.bad?.length || r.clipped?.length || r.error),errors},null,2));
await fetch(`http://localhost:${port}/json/close/${target.id}`); ws.close();
if(errors.length || results.some(r=>r.bad?.length || r.clipped?.length || r.error || r.scrollWidth>r.width+1)) process.exitCode=1;
