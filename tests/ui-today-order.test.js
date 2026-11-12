import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const app = fs.readFileSync(new URL('../site/app.js', import.meta.url), 'utf8');
const css = fs.readFileSync(new URL('../site/app.css', import.meta.url), 'utf8');
const body = (start, end) => { const a = app.indexOf(start), b = app.indexOf(end, a); assert.ok(a >= 0 && b > a, start); return app.slice(a, b); };

test('Today leads with decisions and Kook vs. Book, then groups lower-priority research under one fold', () => {
  const view = body('VIEWS.today = async', '/* ---------- a single best bet');
  const extra = view.slice(view.indexOf('const extraToday = ['), view.indexOf('const rest2 = ['));
  const atExtra = s => { const i = extra.indexOf(s); assert.ok(i >= 0, s); return i; };
  const extraOrder = ['prepList(', "ktSec('upsets'", "ktSec('pulled'", "ktSec('off-card'", 'COMMUNITY', "ktSec('sports'"].map(atExtra);
  assert.deepEqual(extraOrder, extraOrder.slice().sort((a, b) => a - b), 'Prep, underdogs, closed plays, community and sports stay in a predictable order');
  const rest = view.slice(view.indexOf('const rest2 = ['));
  const at = s => { const i = rest.indexOf(s); assert.ok(i >= 0, s); return i; };
  const order = ['leftovers(', "ktSec('games'", 'nbaSummary', "ktSec('fun'", 'class="today-more"'].map(at);
  assert.deepEqual(order, order.slice().sort((a, b) => a - b), 'Results, games, NBA and fun precede the secondary fold');
  assert.match(view, /<details class="today-more"><summary>More today<\/summary>/);
  assert.doesNotMatch(view, /kt-fold|foldRow/);
  const top = body('const todayTop =', 'const firstPaint =');
  const t = s => { const i = top.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(t('rail(currentBets') < t('${postedSummary ? postedSummary.html')
    && t('${otherTickets}') < t('${postedSummary ? postedSummary.html')
    && t('${postedSummary ? postedSummary.html') < t('<nav class="today-tools"')
    && t('<nav class="today-tools"') < t('${market}')
    && t('${market}') < t('${climbStub(climb, past)}') && t('${climbStub(climb, past)}') < t('${proof}')
    && t('${proof}') < t('${nextSlate}') && t('${nextSlate}') < t('rail(later,'),
  'all current best bets lead, followed by research tools, Kook vs. Book, Climb, season line, then explicitly labeled off-day prep');
});

test('Off the card is the line-moved state only: its own visible section, never on the rail', () => {
  const view = body('VIEWS.today = async', '/* ---------- a single best bet');
  assert.match(view, /const offCard = p => C\.pickState\(p, now\)\.word === 'Line moved'/);
  assert.match(view, /const todays = sched\.today\.filter\(p => straight\(p\) && !offCard\(p\)\)/);
  assert.match(view, /const later = sched\.upcoming\.filter\(p => straight\(p\) && !offCard\(p\)\)/);
  assert.match(view, /off\.length \? ktSec\('off-card', `Off the card · \$\{off\.length\}`/);
  assert.doesNotMatch(view, /onboard|statusRows/);
});

test('Today keeps the footer below the fold while the first view loads, and uses both columns on a wide screen', () => {
  assert.match(css, /main#view\s*\{\s*min-height:\s*calc\(100svh\s*-\s*160px\)/);
  assert.match(css, /@media \(min-width: 1000px\) \{ \.kt-today \{ display: grid; grid-template-columns: minmax\(0, 440px\) minmax\(0, 1fr\)/);
  assert.doesNotMatch(css, /kt-fold/, 'the fold styles left with the fold');
});

test('Today\'s restored rows meet the 14 px floor and research rows stack on a phone (research board untouched)', () => {
  assert.match(css, /\.kt-kind \{ font: 500 14px/);
  assert.match(css, /\.kt-cd \{ font: 500 14px/);
  assert.match(css, /\.pc-meta \{[^}]*font-size: 14px/);
  assert.match(css, /\.pc-mid span \{ font-size: 14px/);
  assert.match(css, /\.kt-worth \.row-title > div > span, [^{]*\.kt-worth \.row-fair \{ font-size: 14px; \}/);
  assert.match(css, /\.kt-worth \.row-main \{ grid-template-columns: minmax\(0, 1fr\) auto; grid-template-areas: 'title title' 'price price' 'meter meter' 'edge fair';/, 'stacked at every width (the right column is narrow at 1440)');
  assert.match(css, /\.kt-worth \.lbl \{ position: static;/, 'labels stay visible beside the numbers');
});

test('the Climb stub has breathing room below the first ticket', () => {
  assert.match(css, /\.kt-climb\s*\{\s*margin-top:\s*32px\s*;/);
  assert.match(css, /\.kt-stub \{[^}]*border-radius: 15px;[^}]*background: linear-gradient/, 'the Climb is a flat dashboard card, not a paper receipt');
});
