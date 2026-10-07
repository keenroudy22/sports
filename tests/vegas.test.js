'use strict';
/* Vegas vs reality: the lazily loaded view renders the builder's payload (tests/fixtures/vegas.json is the
   exact output of scripts/vegas.py on the Python test's fixture stores). */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const C = require('../site/core.js');
const L = require('../site/live.js');
const P = require('../site/personal.js');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'vegas.json'), 'utf8'));

const load = () => {
  const sandbox = {
    module: { exports: {} }, exports: {}, KRCore: C, KRLive: L, KRPersonal: P,
    document: { querySelector: () => null },
    localStorage: { getItem: () => null, setItem: () => {} },
    console, URL, URLSearchParams, Intl, Date, Math, Map, Set, Promise,
    AbortController, TextEncoder, TextDecoder, setTimeout, clearTimeout, setInterval, clearInterval,
  };
  sandbox.globalThis = sandbox;
  sandbox.self = sandbox;
  sandbox.window = sandbox;
  vm.runInNewContext(fs.readFileSync('site/app.js', 'utf8'), sandbox, { filename: 'site/app.js' });
  vm.runInNewContext(fs.readFileSync('site/app-more.js', 'utf8'), sandbox, { filename: 'site/app-more.js' });
  return { api: sandbox.module.exports, factory: sandbox.KRMore };
};

const viewsWith = (payload, league = 'ALL') => {
  const { api, factory } = load();
  const requested = [];
  const context = api.moreContext({ maybe: async file => { requested.push(file); return file === 'app/vegas.json' ? payload : null; } });
  context.state.league = league;
  return { views: factory(context), requested };
};

const clean = html => {
  assert.doesNotMatch(html, /undefined|NaN|\[object Object\]|is not defined/);
  assert.match(html, /<h1>Vegas vs reality<\/h1>/);
};

test('the Vegas view renders closing-line numbers with their samples and the plain-words meaning', async () => {
  const { views, requested } = viewsWith(fixture);
  const html = await views.vegas({});
  clean(html);
  assert.deepEqual(requested, ['app/vegas.json']);
  assert.match(html, /closing lines/);
  /* "What this means" is the league's own sentence from the builder, never one line for every sport. */
  assert.match(html, /<b>What this means:<\/b> The closing moneyline favorite won 87\.5% of 8 games\./);
  assert.match(html, /At −110 you need 52\.4% just to break even\./);
  assert.doesNotMatch(html, /coin flip by design/);
  assert.doesNotMatch(html, /has no stored closing lines/);
  assert.match(html, /href="#record\/model"/);
  /* Every league gets a selector chip; the first is shown by default. */
  for (const league of ['NFL', 'CFB', 'NBA', 'CBB', 'EPL', 'MLS']) assert.match(html, new RegExp(`href="#vegas/${league}"`));
  assert.match(html, /aria-current="page">NFL</);
  /* The NFL fixture: 7–1 with a tie left out, 5 of 8 covered with 1 push, and n on the averages. */
  assert.match(html, /87\.5%/);
  assert.match(html, /7–1 · n=8 · 1 tie left out · by closing moneyline/);
  assert.match(html, /5 of 8 · 1 push/);
  assert.match(html, /n=9/);
  assert.match(html, /When Vegas says 70%, how often does it happen\?/);
  assert.match(html, /80–90%<\/td><td class="n">80\.0%<\/td><td class="n">100\.0%<br><span class="tiny muted">2 of 2<br>too few to read/);
  assert.match(html, /3 points is the most common NFL final margin/);
  assert.match(html, /Season by season/);
  assert.match(html, /Entertainment only, 21\+/);
});

test('basketball shows the spread favorite and no priced-chance table; soccer shows the handicap', async () => {
  const { views } = viewsWith(fixture);
  const nba = await views.vegas({ league: 'NBA' });
  clean(nba);
  assert.match(nba, /aria-current="page">NBA</);
  assert.match(nba, /the spread favorite/);
  assert.doesNotMatch(nba, /When Vegas says 70%/);
  assert.match(nba, /within 5 pts of the line/);
  assert.match(nba, /No basketball moneylines are stored/);
  assert.match(nba, /What this means:<\/b> The closing spread favorite won 100\.0% of 4 games\./);
  assert.doesNotMatch(nba, /as often as its price|closing odds said/);
  const epl = await views.vegas({ league: 'EPL' });
  clean(epl);
  assert.match(epl, /Against the handicap/);
  assert.match(epl, /Over 2\.5 goals/);
  assert.match(epl, /2 won · 1 drew · 1 lost · n=4/);
  assert.match(epl, /Biggest upset in the stored prices: Norwich beat Man City 3-2/);
  /* One goal is singular; two goals plural. */
  assert.match(epl, /within 1 goal of the line \d/);
  assert.match(epl, /within 2 goals \d/);
  assert.doesNotMatch(epl, /within 1 goals/);
  assert.doesNotMatch(epl, /−110/);
  const mls = await views.vegas({ league: 'MLS' });
  clean(mls);
  assert.doesNotMatch(mls, /<h2>Against the|<h2>Totals|>Covered<\/th>|>Over<\/th>/);
  assert.match(mls, /no handicap or total/);
  assert.match(mls, /What this means:<\/b> The closing favorite won 50\.0% of 2 games, a draw counting as not won\./);
  assert.doesNotMatch(mls, /coin flip|usually wins|Against the spread|on totals|−110/);
});

test('the header sport picks the league, and an unknown league falls back safely and says so', async () => {
  const picked = await viewsWith(fixture, 'CBB').views.vegas({});
  assert.match(picked, /aria-current="page">College basketball</);
  assert.doesNotMatch(picked, /has no stored closing lines/);
  const unknown = await viewsWith(fixture).views.vegas({ league: 'XYZ' });
  clean(unknown);
  assert.match(unknown, /aria-current="page">NFL</);
  assert.match(unknown, /XYZ has no stored closing lines here; showing NFL\./);
  /* A header sport with no stored lines (MLB) says so instead of quietly showing NFL under an MLB header. */
  const mlb = await viewsWith(fixture, 'MLB').views.vegas({});
  clean(mlb);
  assert.match(mlb, /MLB has no stored closing lines here; showing NFL\./);
  /* On #vegas/<league>, changing the header sport drops the league from the hash so the new sport shows. */
  assert.match(fs.readFileSync('site/app.js', 'utf8'), /if \(route\.view === 'vegas' && route\.league\) return '#vegas';/);
});

test('a league without a meaning sentence shows no meaning card', async () => {
  const quiet = JSON.parse(JSON.stringify(fixture));
  delete quiet.leagues[0].meaning;
  const html = await viewsWith(quiet).views.vegas({});
  clean(html);
  assert.doesNotMatch(html, /What this means/);
});

test('a missing file shows an honest retry state instead of numbers', async () => {
  const html = await viewsWith(null).views.vegas({});
  assert.match(html, /Vegas numbers did not load/);
  assert.match(html, /data-retry/);
  assert.doesNotMatch(html, /%/);
});

test('text from the payload is escaped', async () => {
  const hostile = JSON.parse(JSON.stringify(fixture));
  hostile.leagues[0].facts = ['<img src=x onerror=alert(1)>'];
  hostile.leagues[0].name = '<b>NFL</b>';
  hostile.leagues[0].meaning = '<script>alert(2)</script>';
  const html = await viewsWith(hostile).views.vegas({});
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<b>NFL<\/b>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /<script>alert\(2\)/);
});

test('#vegas is a real route in both route maps and lives under Record', () => {
  assert.deepEqual(C.parseRoute('#vegas'), { view: 'vegas' });
  assert.deepEqual(C.parseRoute('#vegas/epl'), { view: 'vegas', league: 'EPL' });
  assert.deepEqual(C.parseRoute('#nonsense'), { view: 'today' });
  globalThis.KRCore = C;
  const { model: M } = require('../site/app.js');
  assert.deepEqual(M.resolve('#vegas'), { view: 'vegas', league: null });
  assert.deepEqual(M.resolve('#vegas/nba'), { view: 'vegas', league: 'NBA' });
  assert.equal(M.canonical(M.resolve('#vegas')), null);
  const app = fs.readFileSync('site/app.js', 'utf8');
  assert.match(app, /vegas: 'record'/);
  assert.match(app, /MORE_VIEW_NAMES = \[[^\]]*'vegas'/);
  assert.match(fs.readFileSync('site/app-more.js', 'utf8'), /href="#vegas">Vegas vs reality/);
});
