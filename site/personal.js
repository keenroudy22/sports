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
  const api = {leagues,league,key,snapshot,changes,sportRoute};
  if(typeof module !== 'undefined') module.exports=api; else root.KRPersonal=api;
})(typeof window !== 'undefined' ? window : globalThis);
