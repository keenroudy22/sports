'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../site/core.js');

test('a qualifying Upset Watch renders percentages without relying on another view’s local helpers', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const body = source.match(/const upsetRow = game => \{([\s\S]*?)\n  \};/)[1];
  const render = new Function('C', 'esc', 'odds', 'whenShort', 'ago', 'game', body);
  const html = render(C, C.esc, C.odds, C.whenShort, C.ago, {
    id: 'NFL-test', league: 'NFL', kickoff: '2026-10-04T17:00:00Z',
    upsetWatch: {team: 'Underdog', odds: 160, opponentOdds: -192, book: 'DraftKings',
      modelChance: .6, marketChanceNoVig: .369, observedAt: '2026-10-02T16:00:00Z'}
  });
  assert.match(html, /Model 60%/);
  assert.match(html, /market 37%/);
  assert.match(html, /not a calibrated value bet/);
  assert.match(html, /#game\/NFL-test/);
});

test('Underdog Watch stays visible and separates outright winners from spread covers', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  assert.match(source, /const underdogWatch = \(games, board\) =>/);
  assert.match(source, /Outright upset candidates/);
  assert.match(source, /Underdog spread value/);
  assert.match(source, /Covering does not mean winning outright/);
  assert.match(source, /\$\{underdogWatch\(now, board\)\}/,
    'the Today page renders the permanent section without a qualifying-candidate conditional');
});

test('Today keeps the season scorecard above the research counter', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const today = source.slice(source.indexOf('async function viewToday()'), source.indexOf('const modelCard ='));
  assert.ok(today.indexOf("section('Season scorecard · model accuracy'") > today.indexOf('transparent-record'));
  assert.ok(today.indexOf("section('Season scorecard · model accuracy'") < today.indexOf('research-heading'));
  assert.equal((today.match(/scorecardCard\(/g) || []).length, 1, 'Today renders one prominent scorecard');
});

test('the Lab tracks season futures without presenting a public play', () => {
  const source = fs.readFileSync('site/app.js', 'utf8');
  const lab = source.slice(source.indexOf('async function viewLab()'), source.indexOf('function viewArbs()'));
  assert.match(lab, /Season futures/);
  assert.match(lab, />Planned</);
  assert.match(lab, /Original price, book, date and every later move will be preserved/);
  assert.match(lab, /Research watches stay separate from official plays/);
  assert.doesNotMatch(lab, /official futures? (?:pick|play)/i);
});
