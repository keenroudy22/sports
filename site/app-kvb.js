(function () {
  'use strict';

  const STYLE = `<style id="kvb-styles">
    .kt-kvb{margin-top:24px;padding:18px;border:1px solid color-mix(in srgb,var(--kook) 38%,var(--line));border-radius:18px;background:linear-gradient(145deg,rgba(32,199,116,.09),rgba(255,255,255,.018) 42%,rgba(255,184,77,.045));box-shadow:inset 0 1px rgba(255,255,255,.035)}
    .kvb-head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:14px}.kvb-head h2{font:700 clamp(28px,5vw,38px)/.95 var(--display);letter-spacing:.01em}.kvb-head p{margin-top:6px;color:var(--muted);font-size:14px}.kvb-count{text-align:right;color:var(--dim);font-size:12px;white-space:nowrap}.kvb-count b{display:block;color:var(--kook);font-size:18px}
    .kvb-grid{display:grid;gap:12px}.kvb-card{min-width:0;padding:15px;border:1px solid var(--line);border-radius:15px;background:color-mix(in srgb,var(--felt-night) 91%,white);overflow:hidden}.kvb-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.kvb-player{display:flex;align-items:center;gap:9px;min-width:0}.kvb-player>span:last-child{min-width:0}.kvb-player b{display:block;font-size:17px;line-height:1.1}.kvb-player small{display:block;color:var(--dim);margin-top:3px}.kvb-status{flex:none;padding:4px 7px;border-radius:999px;border:1px solid var(--line);font-size:10px;font-weight:800;letter-spacing:.07em;text-transform:uppercase}.kvb-status.official,.kvb-status.clears{color:var(--kook);border-color:color-mix(in srgb,var(--kook) 55%,var(--line));background:rgba(32,199,116,.09)}.kvb-status.close{color:#ffd18b;border-color:rgba(255,184,77,.45);background:rgba(255,184,77,.08)}.kvb-status.pass{color:var(--dim)}
    .kvb-numbers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:13px 0 8px}.kvb-number{padding:9px 8px;border-radius:10px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.045)}.kvb-number small,.kvb-number em{display:block;color:var(--dim);font-size:10px;font-style:normal;white-space:nowrap}.kvb-number b{display:block;margin:2px 0;font:700 21px/1 var(--display);font-variant-numeric:tabular-nums}.kvb-number.kook b{color:var(--kook)}
    .kvb-price{font-size:12px;color:var(--muted);margin-bottom:8px}.kvb-price b{color:var(--chalk)}.kvb-rates{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:10px 0}.kvb-rate{position:relative;overflow:hidden;padding:7px 8px;border:1px solid var(--line);border-radius:9px}.kvb-rate:after{content:"";position:absolute;left:0;bottom:0;height:3px;width:var(--rate);background:var(--kook)}.kvb-rate small,.kvb-rate b{display:block}.kvb-rate small{font-size:10px;color:var(--dim)}.kvb-rate b{font-size:14px}.kvb-read{display:grid;gap:4px;margin-top:8px;font-size:12px}.kvb-read .risk{color:var(--dim)}.kvb-card .chart-wrap{overflow-x:auto;padding-top:20px;-webkit-overflow-scrolling:touch}.kvb-card .chart,.kvb-card .chart-x{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(26px,1fr);gap:5px;min-width:100%}.kvb-card .chart{position:relative;height:86px;border-bottom:1px solid var(--line)}.kvb-card .chart .col{position:relative;height:100%}.kvb-card .chart .bar{position:absolute;left:0;right:0;border-radius:4px 4px 0 0}.kvb-card .chart .bar.hit{background:var(--kookd)}.kvb-card .chart .bar.miss{background:var(--burnt)}.kvb-card .chart .bar.push,.kvb-card .chart .bar.unknown{background:var(--push)}.kvb-card .chart .bar span{position:absolute;top:-16px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--chalk);white-space:nowrap}.kvb-card .chart .line{position:absolute;left:0;right:0;z-index:1;border-top:2px dashed var(--chalk);opacity:.8}.kvb-card .chart .line span{position:absolute;right:0;top:-17px;padding:0 3px;border-radius:3px;background:var(--felt-night);font-size:10px}.kvb-card .chart-x{margin-top:3px;color:var(--dim);font-size:9px}.kvb-card .chart-x span{text-align:center}.kvb-card .chart-cap{margin-top:5px;color:var(--dim);font-size:11px}.kvb-card .zero{position:absolute;left:0;right:0;border-top:1px solid var(--line)}.kvb-actions{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:11px;padding-top:9px;border-top:1px solid var(--line);font-size:12px}.kvb-actions span{color:var(--dim)}.kvb-actions a{font-weight:700}.kvb-foot{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:13px;font-size:12px}.kvb-foot p{color:var(--dim)}.kvb-foot a{white-space:nowrap;font-weight:700}
    @media(max-width:430px){.kt-kvb{padding:14px;margin-left:-2px;margin-right:-2px}.kvb-head{align-items:flex-start}.kvb-count{display:none}.kvb-number b{font-size:19px}.kvb-foot{align-items:flex-start;flex-direction:column}.kvb-card .chart,.kvb-card .chart-x{grid-auto-columns:minmax(24px,1fr)}}
  </style>`;

  window.KRKvb = function (ctx) {
    const { C, esc, headshot, oddsText, whenShort, pctText, isNum, historyChart, hasValue } = ctx;
    if (!document.getElementById('kvb-styles')) document.head.insertAdjacentHTML('beforeend', STYLE);
    const COMMON = { recYds: 0, rushYds: 1, passYds: 2, rec: 3, car: 4, cmp: 5, att: 6 };
    const LABEL = { recYds: 'Receiving yards', rushYds: 'Rushing yards', passYds: 'Passing yards', rec: 'Receptions', car: 'Carries', cmp: 'Completions', att: 'Pass attempts' };
    const floor = { recYds: 15.5, rushYds: 15.5, passYds: 100, rec: 1.5, car: 5.5, cmp: 10.5, att: 15.5 };
    const number = (value, stat) => isNum(value) ? C.statValue(value, stat) : '–';
    const rates = (values, line, direction, size) => {
      const sample = values.slice(size ? -size : 0).filter(isNum);
      const hits = sample.filter(value => C.thresholdResult(value, line, direction) === 'hit').length;
      return { games: sample.length, hits, pct: sample.length ? Math.round(100 * hits / sample.length) : null };
    };
    const rate = (label, value) => `<span class="kvb-rate" style="--rate:${value.pct || 0}%"><small>${label}</small><b>${value.pct == null ? '–' : `${value.pct}% · ${value.hits}/${value.games}`}</b></span>`;
    const status = vm => vm.official ? ['official', 'Official play'] : hasValue(vm) ? ['clears', 'Price clears'] : vm.edge > 0 ? ['close', 'Price is close'] : ['pass', 'Direction only'];
    const directionFits = vm => {
      if (vm.official || !isNum(vm.projection) || !isNum(vm.line)) return true;
      return String(vm.direction).toLowerCase() === 'under' ? Number(vm.projection) < Number(vm.line) : Number(vm.projection) > Number(vm.line);
    };
    const projectionFits = vm => {
      if (vm.official || !isNum(vm.projection) || !isNum(vm.line)) return true;
      const ratio = Math.abs(Number(vm.projection) - Number(vm.line)) / Math.max(Math.abs(Number(vm.line)), 1);
      return !vm.caution && !(ratio > .5 && !hasValue(vm)) && ratio <= 1;
    };
    const choose = rows => {
      const byMarket = new Map();
      rows.filter(vm => vm.isProp && Object.hasOwn(COMMON, vm.stat) && vm.calibrated && !vm.thin && !vm.limited && !vm.src?.roleSuspect && !vm.src?.priceSuspect
        && (vm.official || Number(vm.line) >= floor[vm.stat]) && directionFits(vm) && projectionFits(vm)).forEach(vm => {
          const key = [vm.gameId, vm.athleteId, vm.stat, String(vm.direction).toLowerCase()].join('|');
          const old = byMarket.get(key);
          if (!old || Number(vm.official) > Number(old.official) || (vm.edge ?? -99) > (old.edge ?? -99)) byMarket.set(key, vm);
        });
      const ranked = [...byMarket.values()].sort((a, b) => Number(Boolean(b.official)) - Number(Boolean(a.official)) || Number(hasValue(b)) - Number(hasValue(a))
        || (b.edge ?? -99) - (a.edge ?? -99) || COMMON[a.stat] - COMMON[b.stat] || String(a.kickoff).localeCompare(String(b.kickoff)));
      const picked = [], players = new Set();
      for (const vm of ranked) if (!players.has(vm.athleteId) && picked.push(vm) && players.add(vm.athleteId) && picked.length === 3) break;
      for (const vm of ranked) if (picked.length < 3 && !picked.includes(vm)) picked.push(vm);
      return picked;
    };
    const card = (vm, charts, gameMap) => {
      const player = (charts.players || []).find(p => p.gameId === vm.gameId && String(p.id) === String(vm.athleteId));
      const values = (player?.rows || []).map(row => row.stats?.[vm.stat]).filter(isNum);
      const sample = values.slice(-10), dates = (player?.rows || []).filter(row => isNum(row.stats?.[vm.stat])).slice(-10).map(row => String(row.date || '').slice(5));
      const l5 = rates(values, vm.line, vm.direction, 5), l10 = rates(values, vm.line, vm.direction, 10), season = rates(values, vm.line, vm.direction);
      const [tone, word] = status(vm), gap = isNum(vm.projection) ? Math.abs(vm.projection - vm.line) : null;
      const game = gameMap.get(vm.gameId), team = player && game ? (game[player.side] || {}).abbreviation : '';
      const direction = String(vm.direction).toLowerCase();
      const priceRead = hasValue(vm) ? `Kook’n ${pctText(vm.chance)} clears the ${pctText(vm.needs)} this price needs by ${vm.edge.toFixed(1)} points.`
        : vm.edge > 0 ? `The math is positive by ${vm.edge.toFixed(1)} points, but it has not cleared the full release bar.`
          : `Kook’n ${pctText(vm.chance)} does not clear the ${pctText(vm.needs)} this price needs. Direction only—not a bet at this price.`;
      const chart = sample.length ? historyChart(sample, dates, Number(vm.line), String(vm.direction).toLowerCase(), { legend: false, format: value => number(value, vm.stat) }) : '<p class="small muted">No recorded game log for this market yet.</p>';
      return `<article class="kvb-card"><div class="kvb-top"><div class="kvb-player">${headshot(vm.league, vm.athleteId, 'sm', null, vm.position)}<span><b>${esc(vm.player || vm.title)}</b><small>${esc([team, vm.position, LABEL[vm.stat]].filter(Boolean).join(' · '))}</small></span></div><span class="kvb-status ${tone}">${word}</span></div>
        <div class="kvb-body"><div><div class="kvb-numbers"><span class="kvb-number"><small>Book line</small><b>${esc(direction.toUpperCase().slice(0,1))} ${esc(number(vm.line, vm.stat))}</b><em>${esc(oddsText(vm.odds))}</em></span><span class="kvb-number kook"><small>Kook’n</small><b>${esc(number(vm.projection, vm.stat))}</b><em>${gap == null ? 'No gap' : `${esc(number(gap, vm.stat))} difference`}</em></span><span class="kvb-number"><small>Chance gap</small><b>${vm.edge == null ? '–' : `${vm.edge > 0 ? '+' : ''}${esc(vm.edge)}%`}</b><em>${esc(pctText(vm.chance))} vs ${esc(pctText(vm.needs))}</em></span></div><p class="kvb-price"><b>${esc(vm.book || '')} ${esc(oddsText(vm.odds))}</b> · ${esc(vm.age.label)} · ${esc(whenShort(vm.kickoff))}</p><div class="kvb-rates">${rate('L5', l5)}${rate('L10', l10)}${rate('Season', season)}</div><div class="kvb-read"><p><b>Kook read:</b> ${esc(direction === 'under' ? 'Projection is below the line.' : 'Projection is above the line.')}</p><p class="risk">${esc(priceRead)}</p></div></div><div>${chart}</div></div>
        <div class="kvb-actions"><span>Research unless marked Official</span><a href="${esc(C.playerLineHref(vm))}">Full player chart →</a></div></article>`;
    };
    const home = ({ rows = [], charts = {}, games = [], league = 'NFL' } = {}) => {
      const selected = choose(rows);
      if (!selected.length) return '';
      const gameMap = new Map(games.map(game => [game.id, game]));
      const clears = selected.filter(vm => vm.official || hasValue(vm)).length;
      const content = `<div class="kvb-grid">${selected.map(vm => card(vm, charts, gameMap)).join('')}</div>`;
      return `<section class="kt-kvb" id="today-kvb" aria-labelledby="kvb-h"><div class="kvb-head"><div><p class="eyebrow green">Common player props first</p><h2 id="kvb-h">Kook vs. Book</h2><p>Our number. Their line. Your call.</p></div><div class="kvb-count"><b>${selected.length}</b>shortlisted · ${clears} clear</div></div>${content}<div class="kvb-foot"><p>Prices move. A projection gap alone is not value; the price still has to clear.</p><a href="#research/players?sport=${esc(String(league).toUpperCase())}">All player props →</a></div></section>`;
    };
    return { home };
  };
}());
