'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const C = require('../site/core.js');
const L = require('../site/live.js');
const P = require('../site/personal.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const moreSource = fs.readFileSync('site/app-more.js', 'utf8');

const loadBrowserApi = () => {
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
  vm.runInNewContext(source, sandbox, { filename: 'site/app.js' });
  vm.runInNewContext(moreSource, sandbox, { filename: 'site/app-more.js' });
  return { api: sandbox.module.exports, factory: sandbox.KRMore };
};

test('the real app shared interface renders every lazy view with fixture data', async () => {
  const { api, factory } = loadBrowserApi();
  assert.equal(typeof api.moreContext, 'function');
  assert.equal(typeof factory, 'function');

  const base = api.moreContext();
  assert.equal(typeof base.wl, 'function');
  assert.equal(typeof base.roiOf, 'function');
  assert.equal(typeof base.opponentTrendText, 'function', 'the lazy player page receives its opponent-adjusted trend helper');
  Object.assign(base.state, {
    league: 'ALL', record: { season: 'current', phase: 'current', q: '' },
    watchlist: [], ticket: [], stake: { amount: 1, mode: 'units', unit: 20 },
    arb: { first: 150, second: -130, bankroll: 100 },
  });
  const today = { games: [], picks: [], freshness: {}, health: [], generatedAt: '2026-10-08T18:00:00Z' };
  const routeFixture = { climbRoute: { run: 3, step: 2, saved: 42,
    weekly: {weekStart:'2026-10-19',posted:1,maximum:3,remaining:2},
    image: 'data/cards/climb-route.png', rows: [
      { kind: 'cashed', step: 1, league: 'CFB', day: 'THU 10/8', clock: '7 PM',
        bet: 50, cashes: 81, bank: 16, legs: [{ title: 'Iowa +4.5', odds: -110,
          book: 'FanDuel', href: '#pick/real-rung' }] },
      { kind: 'next', step: 2, league: 'NFL', day: 'SUN 10/11', clock: '1 PM',
        bet: 65, cashes: 106, bank: 21, legs: [] },
    ] } };
  const team = { id: '1', name: 'Fixture Team', abbr: 'FIX', color: '#123456', games: [], defense: [] };
  const context = api.moreContext({
    etDay: () => '2026-10-22',
    get: async path => path === 'app/record.json' ? routeFixture : today,
    maybe: async path => path === 'app/teams/CFB/1.json' ? team
      : path === 'app/players/CFB.json' ? { season: 2026, players: [] }
      : path === 'scoreboard.json' ? { picks: { rows: [] } } : null,
    allPicks: async () => [],
    teamDirectory: async () => ({ teams: { 1: team }, defense: { season: 2026, rows: [] } }),
    lineData: async () => ({ lines: [] }),
    ticketRows: async () => [],
    ticketSummary: () => '<p>Ticket fixture</p>',
  });
  const views = factory(context);
  const cases = [
    ['record', views.record, { tab: 'official' }],
    ['fun', views.record, { tab: 'fun' }],
    ['climb', views.record, { tab: 'climb' }],
    ['start', views.start, {}],
    ['saved', views.saved, {}],
    ['ticket', views.ticket, {}],
    ['arbs', views.arbs, {}],
    ['schedule', views.schedule, {}],
    ['status', views.status, {}],
    ['feedback', views.feedback, {}],
    ['more', views.more, {}],
    ['glossary', views.glossary, {}],
    ['lab', views.lab, {}],
    ['vegas', views.vegas, {}],
  ];
  assert.equal(views.responsible, undefined);
  assert.equal(views.team, undefined, 'the team page lives in the Games bundle');
  const moreHtml = await views.more({});
  assert.doesNotMatch(moreHtml, /Responsible gaming|#responsible/);
  for (const [name, render, route] of cases) {
    const html = await render(route);
    assert.equal(typeof html, 'string', name);
    assert.match(html, /<h1/, name);
    assert.doesNotMatch(html, /Something did not load|is not defined/, name);
  }
  const climbHtml = await views.record({ tab: 'climb' });
  assert.match(climbHtml, /climb-route\.png/);
  assert.match(climbHtml, /#pick\/real-rung/);
  assert.doesNotMatch(climbHtml, /Next step · not posted yet/);
  assert.match(climbHtml, /next pick is not selected/);
  assert.doesNotMatch(climbHtml, /Plan · typical −160/);
  assert.match(climbHtml, /standalone Thursday and Monday/);
  assert.match(climbHtml, /2-3 alternate-line legs at one book; two preferred/);
  assert.match(climbHtml, /Target combined odds: -200 to -150/);
  assert.match(climbHtml, /This week: 1 of 3 steps used across all restarts/);
  assert.match(climbHtml, /NBA is research-only for the Climb/);
  routeFixture.climbRoute.weekly.weekStart = '2026-10-12';
  assert.doesNotMatch(await views.record({tab:'climb'}), /This week: 1 of 3/);
});

test('official record always renders the separate Chef record without changing overall results', async () => {
  const {api,factory}=loadBrowserApi();
  const picks=[{id:'chef',league:'CFB',season:2026,kind:'props',lane:'chef_pick',posted:true,
    riskUnits:1,odds:100,result:'loss',kickoff:'2026-10-28T00:00Z',settledAt:'2026-10-28T04:00Z',
    title:'Player over 2.5 catches',chefEvidence:{policy:'chef-forward-ev-v1'}}];
  const ctx=api.moreContext({allPicks:async()=>picks, get:async()=>({}),
    maybe:async path=>path==='scoreboard.json'?{picks:{rows:[{id:'chef',clv:1}]}}:null});
  Object.assign(ctx.state,{league:'CFB',record:{season:'current',phase:'current',q:''}});
  const html=await factory(ctx).record({tab:'official'});
  assert.match(html,/id="chef-record"/);
  assert.match(html,/Forward EV policy/);
  assert.match(html,/Included in the overall best-bet record/);
  assert.match(html,/beat the close on 1 of 1/);
  assert.equal(C.recordBreakdown(picks).all.losses,1);
});
