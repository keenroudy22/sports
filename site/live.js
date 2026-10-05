/* Free scoreboard transport. Successful observation time is never advanced by a failed request. */
(function (root) {
  'use strict';
  const dayOf = value => new Intl.DateTimeFormat('en-CA', {timeZone:'America/Indiana/Indianapolis',
    year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
  function createCache({fetcher, now = Date.now, changed = () => {}, ttl = 45000} = {}) {
    const rows = new Map(), pending = new Map();
    return { rows, pending, read(key, url, normalize) {
      const prior = rows.get(key);
      if (pending.has(key) || (prior && now() - prior.checkedAt < ttl)) return prior || null;
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 6500);
      const work = (async () => {
        // Register pending before a custom fetcher can throw synchronously.
        await Promise.resolve();
        try {
          const response = await fetcher(url, {cache:'no-store',signal:controller.signal});
          if (!response.ok) throw new Error('unavailable');
          const data = await response.json();
          if (!Array.isArray(data.events)) throw new Error('missing games');
          const games = data.events.map(normalize).filter(Boolean);
          rows.set(key, {games,at:now(),checkedAt:now(),failed:false});
        } catch (_) {
          rows.set(key, {...prior, games:prior?.games || [],at:prior?.at || null,checkedAt:now(),failed:true});
        } finally { clearTimeout(timer); pending.delete(key); changed(); }
      })();
      pending.set(key, work);
      return prior || null;
    }};
  }
  const freshness = (value, now = Date.now()) => !value?.at ? 'unavailable'
    : value.failed || now - value.at > 120000 ? 'stale' : 'fresh';
  function pregameOdds(competition, status) {
    if(status !== 'scheduled') return null;
    const book = (competition.odds || []).find(o => o.provider?.name === 'DraftKings');
    if(!book) return null;
    const price = value => /^[-+]?[1-9]\d+$/.test(String(value)) && Math.abs(Number(value)) >= 100 ? Number(value) : null;
    const line = value => value != null && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
    const rows = [];
    for(const side of ['away','home']) {
      const ml = price(book.moneyline?.[side]?.close?.odds);
      const spread = book.pointSpread?.[side]?.close;
      if(ml !== null) rows.push({side,market:'ML',price:ml});
      if(line(spread?.line) !== null && price(spread?.odds) !== null) rows.push({side,market:'Spread',line:line(spread.line),price:price(spread.odds)});
    }
    for(const side of ['over','under']) {
      const total = book.total?.[side]?.close;
      // ESPN prefixes total lines with o/u. The numeric field is parsed only after that exact prefix.
      const value = String(total?.line ?? '').replace(/^[ou]/i,'');
      if(line(value) !== null && price(total?.odds) !== null) rows.push({side,market:'Total',line:line(value),price:price(total.odds)});
    }
    return rows.length ? {book:'DraftKings',rows} : null;
  }
  function mergeGames(stored, snapshot, day) {
    const rows = new Map(stored.filter(g => g.date === day).map(g => [String(g.providerId),g]));
    for (const g of snapshot?.games || []) {
      if(dayOf(g.kickoff) !== day) continue;
      rows.set(g.providerId,{...rows.get(g.providerId),...g,date:day,
        scores:{home:g.teams.home.score,away:g.teams.away.score},updatedAt:new Date(snapshot.at).toISOString()});
    }
    return [...rows.values()].sort((a,b) => a.kickoff.localeCompare(b.kickoff));
  }
  const api = {dayOf,createCache,freshness,mergeGames,pregameOdds};
  if(typeof module !== 'undefined') module.exports=api; else root.KRLive=api;
})(typeof window !== 'undefined' ? window : globalThis);
