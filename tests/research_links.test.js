'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const C = require('../site/core.js');

const publicValues = (context, keys) => Object.fromEntries(keys.map(key => [key, context[key]]));
const queryOf = hash => new URLSearchParams(hash.split('?')[1] || '');
const withoutResearch = route => Object.fromEntries(Object.entries(route).filter(([key]) => key !== 'research'));

test('bare research and player routes preserve their existing path semantics and do not overwrite local defaults', () => {
  const routes = {
    '#charts': {view:'stats'},
    '#stats': {view:'stats',tab:'charts'},
    '#stats/search': {view:'stats',tab:'search'},
    '#players': {view:'stats'},
    '#board': {view:'board',tab:'games'},
    '#board/props': {view:'board',tab:'props'},
    '#lines': {view:'board'},
    '#trends/NFL-401872932': {view:'trends',id:'NFL-401872932'},
    '#player/cfb/4430878': {view:'player',league:'CFB',id:'4430878'},
  };
  for (const [hash, expected] of Object.entries(routes)) {
    assert.deepEqual(C.parseRoute(hash), expected, hash);
    assert.equal(C.researchContext(hash), null, hash);
  }
});

test('charts links round-trip the public sport, search, stat, sample and matchup filters', () => {
  const values = {
    league:'CFB',researchQuery:'Jeremiah Smith receiving yards',chartStat:'recYds',chartWindow:'last5',
    chartDay:'2026-10-10',chartPos:'WR',chartVenue:'away',chartOpponent:'2390',
  };
  const hash = C.researchHash('#charts', values);
  assert.equal(hash.split('?')[0], '#charts');
  const params = queryOf(hash);
  assert.equal(params.get('sport'), 'CFB');
  assert.equal(params.get('q'), values.researchQuery);
  assert.equal(params.get('stat'), 'recYds');
  assert.equal(params.get('sample'), 'last5');
  assert.equal(params.get('date'), '2026-10-10');
  assert.equal(params.get('position'), 'WR');
  assert.equal(params.get('venue'), 'away');
  assert.equal(params.get('opponent'), '2390');
  assert.deepEqual(publicValues(C.researchContext(hash), Object.keys(values)), values);
  assert.deepEqual(C.parseRoute(hash).research, C.researchContext(hash));
  assert.deepEqual(withoutResearch(C.parseRoute(hash)), {view:'stats'});
});

test('board links preserve their tab, market and public filters', () => {
  const values = {league:'NFL',researchQuery:'Bijan Robinson',propMarket:'rushing yards',boardDay:'week',boardScope:'settled',boardSort:'confidence'};
  const hash = C.researchHash('#board/props', values);
  assert.deepEqual(withoutResearch(C.parseRoute(hash)), {view:'board',tab:'props'});
  assert.deepEqual(publicValues(C.researchContext(hash), Object.keys(values)), values);
  const params = queryOf(hash);
  assert.equal(params.get('market'), 'rushing yards');
  assert.equal(params.get('date'), 'week');
  assert.equal(params.get('scope'), 'settled');
  assert.equal(params.get('sort'), 'confidence');
});

test('trends links preserve their game and selected evidence window without creating a quote', () => {
  const values = {league:'NFL',researchQuery:'London receiving yards',trendStat:'recYds',trendWindow:'last10',trendDay:'today',trendRate:'90',trendKind:'alternate'};
  const hash = C.researchHash('#trends/NFL-401872932', values);
  assert.deepEqual(withoutResearch(C.parseRoute(hash)), {view:'trends',id:'NFL-401872932'});
  assert.deepEqual(publicValues(C.researchContext(hash), Object.keys(values)), values);
  const params = queryOf(hash);
  assert.equal(params.get('stat'), 'recYds');
  assert.equal(params.get('sample'), 'last10');
  assert.equal(params.get('rate'), '90');
  assert.equal(params.get('kind'), 'alternate');
});

test('player links retain explicit historical scope and their path league wins over query sport', () => {
  const values = {league:'NFL',researchQuery:'receiving yards',stat:'recYds',playerSeason:'2025',playerWindow:'last20'};
  const hash = C.researchHash('#player/CFB/4430878', values);
  const route = C.parseRoute(hash);
  assert.deepEqual(withoutResearch(route), {view:'player',league:'CFB',id:'4430878'});
  assert.deepEqual(publicValues(route.research, ['league','researchQuery','stat','playerSeason','playerWindow']), {...values,league:'CFB'});
  assert.equal(queryOf(hash).get('season'), '2025');
  assert.equal(queryOf(hash).get('sample'), 'last20');
  assert.equal(C.parseRoute('#player/CFB/4430878?sport=NFL&stat=recYds').research.league, 'CFB');
});

test('query strings do not become part of deep-link identifiers and encoded punctuation survives', () => {
  const id = 'NFL-123/"<&?';
  const game = C.parseRoute('#game/' + encodeURIComponent(id) + '?sport=NFL&q=Atlanta');
  assert.equal(game.view, 'game');
  assert.equal(game.id, id);
  const player = C.parseRoute('#player/NFL/' + encodeURIComponent('id/with?punctuation') + '?q=Rec+yds');
  assert.equal(player.id, 'id/with?punctuation');
  const query = 'D’Andre Swift & Bears + receiving yards';
  const hash = C.researchHash('#stats/search', {league:'NFL',researchQuery:query});
  assert.equal(queryOf(hash).get('q'), query);
  assert.equal(C.researchContext(hash).researchQuery, query);
});

test('research route aliases keep working when they contain public context', () => {
  for (const [hash, expected] of [
    ['#charts', {view:'stats'}], ['#players', {view:'stats'}], ['#lines', {view:'board'}],
    ['#props', {view:'board'}], ['#stats/search', {view:'stats',tab:'search'}],
    ['#board/favorites', {view:'board',tab:'favorites'}],
  ]) {
    const linked = C.researchHash(hash, {league:'CFB',researchQuery:'yards'});
    assert.equal(linked.split('?')[0], hash);
    assert.deepEqual(withoutResearch(C.parseRoute(linked)), expected);
    assert.equal(C.researchContext(linked).league, 'CFB');
    assert.equal(C.researchContext(linked).researchQuery, 'yards');
  }
});

test('all supported sport choices remain explicit even when that sport has limited research', () => {
  for (const league of ['NFL','CFB','NBA','WNBA','CBB','MLB','NHL','EPL','MLS']) {
    const hash = C.researchHash('#charts', {league,researchQuery:'sample'});
    assert.equal(C.researchContext(hash).league, league);
    assert.equal(queryOf(hash).get('sport'), league);
  }
});

test('serialized research links allow only route-appropriate public fields and strip existing private parameters', () => {
  const values = {
    league:'NFL',researchQuery:'London',chartStat:'recYds',chartWindow:'last5',chartDay:'next',
    chartPos:'WR',chartVenue:'home',chartOpponent:'11',
    saved:[{id:'private-saved'}],watchlist:[{id:'private-watchlist'}],ticket:[{id:'private-ticket'}],
    stake:'private-stake',odds:'private-odds',quote:'private-quote',originalQuote:'private-original',
    unknown:'private-unknown',propMarket:'carries',trendKind:'alternate',playerSeason:'2025',
  };
  const before = JSON.stringify(values);
  const hash = C.researchHash('#charts?stake=private-old-stake&unknown=private-old-unknown', values);
  const allowed = new Set(['sport','q','stat','sample','date','position','venue','opponent']);
  for (const key of queryOf(hash).keys()) assert.ok(allowed.has(key), key);
  assert.doesNotMatch(hash, /private-|saved|watchlist|ticket|stake|odds|quote|unknown/i);
  assert.equal(JSON.stringify(values), before, 'sharing does not mutate browser-owned state');
  const context = C.researchContext('#charts?sport=NFL&q=London&ticket=private-ticket&stake=10&odds=-110&quote=private-quote');
  for (const key of ['ticket','stake','odds','quote','saved','watchlist','unknown']) assert.equal(context[key], undefined, key);
});

test('malformed chart filters normalize to visible defaults, including real calendar dates', () => {
  const context = C.researchContext('#charts?sport=NFL&stat=made-up&sample=last999&date=2026-02-30&position=none&venue=neutral&opponent=1234567890123');
  const keys = ['chartStat','chartWindow','chartDay','chartPos','chartVenue','chartOpponent'];
  assert.deepEqual(publicValues(context, keys), publicValues(C.RESEARCH_DEFAULTS, keys));
  for (const date of ['2026-13-01','2026-00-01','2026-10-32','2026-1-05','undefined']) {
    assert.equal(C.researchContext('#charts?date=' + date).chartDay, C.RESEARCH_DEFAULTS.chartDay, date);
  }
  assert.equal(C.researchContext('#charts?date=2024-02-29').chartDay, '2024-02-29');
  assert.equal(C.researchContext('#charts?opponent=11').chartOpponent, '11');
});

test('invalid board, trend and player filters do not leak obsolete or arbitrary choices into active state', () => {
  const board = C.researchContext('#board/props?market=total%20TD&date=tomorrow&scope=private&sort=odds');
  const boardKeys = ['propMarket','boardDay','boardScope','boardSort'];
  assert.deepEqual(publicValues(board, boardKeys), publicValues(C.RESEARCH_DEFAULTS, boardKeys));
  const trends = C.researchContext('#trends?stat=totalTD&sample=all&date=tomorrow&rate=101&kind=all');
  const trendKeys = ['trendStat','trendWindow','trendDay','trendRate','trendKind'];
  assert.deepEqual(publicValues(trends, trendKeys), publicValues(C.RESEARCH_DEFAULTS, trendKeys));
  const player = C.researchContext('#player/NFL/4430878?season=never&sample=last999&stat=invented');
  assert.equal(player.playerSeason, 'current');
  assert.equal(player.playerWindow, 'all');
  assert.notEqual(player.stat, 'invented');
});

test('hostile or malformed URL text cannot throw or retain control characters in the public query', () => {
  for (const hash of ['#charts?q=%E0%A4%A', '#charts/%ZZ?q=abc%', '#player/NFL/%?q=test', '#trends/NFL-%ZZ?q=%']) {
    assert.doesNotThrow(() => C.parseRoute(hash), hash);
    assert.doesNotThrow(() => C.researchContext(hash), hash);
  }
  const context = C.researchContext('#charts?q=London%00%0A%0D%09receiving%20yards');
  assert.doesNotMatch(context.researchQuery, /[\x00-\x1f\x7f]/);
  const longQuery = C.researchContext('#charts?q=' + 'x'.repeat(1000));
  assert.ok(longQuery.researchQuery.length <= 160);
  const hash = C.researchHash('#charts', {league:'NFL',researchQuery:'London\u0000\nreceiving yards'});
  assert.doesNotMatch(queryOf(hash).get('q') || '', /[\x00-\x1f\x7f]/);
});

test('a copied view provides defaults for absent filters instead of inheriting a recipient’s prior selections', () => {
  const context = C.researchContext('#charts?sport=CFB&q=Smith');
  const keys = ['chartStat','chartWindow','chartDay','chartPos','chartVenue','chartOpponent'];
  assert.deepEqual(publicValues(context, keys), publicValues(C.RESEARCH_DEFAULTS, keys));
  assert.equal(context.league, 'CFB');
  assert.equal(context.researchQuery, 'Smith');
  const original = {league:'NFL',researchQuery:'old query',chartStat:'rushYds',chartVenue:'home',chartOpponent:'11'};
  const restored = {...original,...context};
  assert.equal(restored.chartVenue, 'all');
  assert.equal(restored.chartOpponent, 'all');
  assert.equal(restored.chartStat, C.RESEARCH_DEFAULTS.chartStat);
});

test('research search matches all query tokens across player, team and exact-title market context', () => {
  const fields = ['Drake London','Atlanta Falcons','ATL','Rec yds'];
  assert.equal(C.researchMatches('London Falcons receiving yards', ...fields), true);
  assert.equal(C.researchMatches('ATL drake recYds', ...fields), true);
  assert.equal(C.researchMatches('London receptions', ...fields), false);
  assert.equal(C.researchMatches('London Chiefs receiving yards', ...fields), false);
  assert.equal(C.researchMatches('', ...fields), true);
  assert.equal(C.researchMatches('  LONDON   receiving YARDS  ', ...fields), true);
  assert.equal(C.researchMatches('Drake London over 61.5 receiving yards', 'Drake London Over 61.5 Rec yds', 'Atlanta Falcons'), true);
});

test('research search understands stored keys, display labels and public market names in both directions', () => {
  for (const [key, label, phrase] of [
    ['recYds','Rec yds','receiving yards'], ['rushYds','Rush yds','rushing yards'],
    ['passYds','Pass yds','passing yards'],
  ]) {
    assert.equal(C.researchMatches(phrase, key), true, `${phrase} finds ${key}`);
    assert.equal(C.researchMatches(phrase, label), true, `${phrase} finds ${label}`);
    assert.equal(C.researchMatches(key, phrase), true, `${key} finds ${phrase}`);
  }
  for (const [label, phrase] of [['Carries','rush attempts'],['Completions','passing completions'],['Receptions','receptions']]) {
    assert.equal(C.researchMatches(phrase, label), true, `${phrase} finds ${label}`);
    assert.equal(C.researchMatches(label, phrase), true, `${label} finds ${phrase}`);
  }
});

test('team abbreviations remain teams and cannot be mistaken for internal stat keys', () => {
  assert.equal(C.researchMatches('CAR', 'Carolina Panthers', 'CAR', 'Bryce Young', 'Pass yds'), true);
  assert.equal(C.researchMatches('CAR', 'Atlanta Falcons', 'ATL', 'Bijan Robinson', 'Carries'), false);
  assert.equal(C.researchMatches('carries', 'Carolina Panthers', 'CAR', 'Bryce Young', 'Pass yds'), false);
  assert.equal(C.researchStat('CAR', ['car','att','passYds']), null);
});

test('stat recognition prefers complete market phrases and only selects a stat supported by that view', () => {
  const supported = ['recYds','rushYds','passYds','car','att','cmp','rec'];
  for (const [query, expected] of [
    ['Drake London receiving yards','recYds'], ['Rec yds','recYds'], ['recYds','recYds'],
    ['Bijan Robinson rush attempts','car'], ['rushing attempts','car'], ['passing attempts','att'],
    ['pass completions','cmp'], ['receptions','rec'], ['rushing yards','rushYds'], ['passing yards','passYds'],
  ]) assert.equal(C.researchStat(query, supported), expected, query);
  assert.equal(C.researchStat('rush attempts', ['att','recYds']), null, 'a missing carries stat must not fall back to passing attempts');
  assert.equal(C.researchStat('passing yards', ['rushYds','recYds']), null);
  assert.equal(C.researchStat('Falcons', supported), null);
});

test('unsupported combined markets never invent an available component stat', () => {
  const supported = ['recYds','rushYds','passYds','car','att','cmp','rec','passTD','rushTD','recTD'];
  for (const query of ['total TD','total touchdowns','rush + rec yards','rushing + receiving yards','rushing and receiving yards','passing and rushing yards','rush + rec TD']) {
    assert.equal(C.researchStat(query, supported), null, query);
  }
});
