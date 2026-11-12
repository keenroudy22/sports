/* Device-local research tools. No account, telemetry, notifications or wager execution. */
(function(root) {
  'use strict';
  const leagues = ['NFL','CFB','NBA','WNBA','CBB','MLB','NHL','EPL','MLS'];
  const league = value => ['ALL',...leagues].includes(value) ? value : 'ALL';
  const key = row => JSON.stringify([row.league || String(row.gameId || '').split('-')[0], row.gameId,
    row.athleteId || '', row.market || row.marketType || '', row.direction || '', row.book || '']);
  function snapshot(row, now = Date.now()) {
    return {type:'line', key:'line:'+key(row), title:row.title || row.player || 'Saved line',
      league:row.league || String(row.gameId || '').split('-')[0], gameId:row.gameId, athleteId:row.athleteId,
      market:row.market, marketType:row.marketType, direction:row.direction, book:row.book,
      line:row.line, odds:row.odds, observedAt:row.observedAt, kickoff:row.kickoff,
      href:row.athleteId ? `#player/${league(row.league || String(row.gameId || '').split('-')[0])}/${encodeURIComponent(row.athleteId)}` : `#game/${encodeURIComponent(row.gameId)}`,
      savedAt:new Date(now).toISOString()};
  }
  function changes(saved, rows, now = Date.now()) {
    if (saved.type !== 'line') return {state:'reference', text:'Saved for your research'};
    if (Date.parse(saved.kickoff) <= now) return {state:'started', text:'Game started · saved quote is not live'};
    const candidates = rows.filter(r => key(r) === key(saved) && r.state === 'open' &&
      Number.isFinite(r.odds) && now - Date.parse(r.observedAt) >= 0 && now - Date.parse(r.observedAt) <= 4*3600000);
    candidates.sort((a,b) => Number(b.line === saved.line)-Number(a.line === saved.line) || Date.parse(b.observedAt)-Date.parse(a.observedAt));
    const current = candidates[0];
    if (!current) return {state:'unavailable', text:'No fresh matching quote · check your book'};
    const moved = current.line !== saved.line || current.odds !== saved.odds;
    return {state:moved?'changed':'same', text:moved?'Changed since you saved it':'Same as your saved quote', current};
  }
  function sportRoute(route, selected) {
    if (route.view === 'scores') return '#scores/'+league(selected);
    if (['game','team'].includes(route.view)) return '#games';
    if (route.view === 'player') return '#stats';
    if (route.view === 'trends' && route.id) return '#trends';
    return null;
  }
  const html = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function betslipAction(pick, now = Date.now(), compact = false) {
    if (!pick || pick.result || Date.parse(pick.kickoff) <= now || /withdr(?:ew|awn)|removed.*recommendation/i.test(pick.entryNote || '')) return '';
    const slip=pick.betslip||{}, legs=Number(slip.legsMatched)||(pick.legs||[]).length||1, book=slip.book||pick.book||'sportsbook';
    const note=compact?'':'<p class="small muted" style="margin-top:7px">Kook’n never places the wager. Confirm every leg, line and price in the sportsbook before submitting.</p>';
    if (/^https:\/\//.test(slip.url||'') && slip.status==='ready' && slip.legsMatched===slip.legsRequested)
      return `<a class="betslip-action${compact?' compact':''}" href="${html(slip.url)}" target="_blank" rel="noopener noreferrer"><span><small>KOOK’N BETSLIP · ${legs}/${legs} MATCHED</small><strong>Open ${legs>1?'parlay':'bet'} in ${html(book)}</strong></span><b aria-hidden="true">↗</b></a>${note}`;
    if (pick.betslipPrompt)
      return `<button type="button" class="betslip-action${compact?' compact':''}" data-gambly-prompt="${html(encodeURIComponent(pick.betslipPrompt))}"><span><small>KOOK’N BETSLIP · EXACT ${legs>1?`${legs} LEGS`:'LINE'}</small><strong>Build in Gambly</strong></span><b aria-hidden="true">↗</b></button>${note}`;
    return '';
  }
  function installBetslipHandler(notify) {
    document.addEventListener('click', async event => {
      const button=event.target.closest&&event.target.closest('[data-gambly-prompt]'); if(!button)return;
      let text=''; try{text=decodeURIComponent(button.dataset.gamblyPrompt)}catch(_){text=button.dataset.gamblyPrompt}
      const opened=window.open('https://gambly.com/chat','_blank','noopener,noreferrer');
      try{await navigator.clipboard.writeText(text);notify('Exact ticket copied. Paste it in Gambly to match the slip.')}catch(_){window.prompt('Copy this exact ticket, then paste it in Gambly:',text)}
      if(!opened)notify('Ticket copied. Open Gambly and paste it to build the slip.');
    });
  }
  const api = {leagues,league,key,snapshot,changes,sportRoute,betslipAction,installBetslipHandler};
  if(typeof module !== 'undefined') module.exports=api; else root.KRPersonal=api;
})(typeof window !== 'undefined' ? window : globalThis);
