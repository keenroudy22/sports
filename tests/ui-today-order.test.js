import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const app = fs.readFileSync(new URL('../site/app.js', import.meta.url), 'utf8');
const css = fs.readFileSync(new URL('../site/app.css', import.meta.url), 'utf8');
const body = (start, end) => { const a = app.indexOf(start), b = app.indexOf(end, a); assert.ok(a >= 0 && b > a, start); return app.slice(a, b); };

test('Today is rail, Climb, Leftovers, Prep List, then the fold (Kitchen Ticket, decision 22)', () => {
  const view = body('VIEWS.today = async', '/* ---------- a single best bet');
  const ret = view.slice(view.lastIndexOf('return `<div class="kt-today">'));
  const at = s => { const i = ret.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(at('${todayTop(') < at('${leftovers(') && at('${leftovers(') < at('${prepList(') && at('${prepList(') < at('${fold}'));
  const top = body('const todayTop =', 'const firstPaint =');
  const t = s => { const i = top.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(t('rail(rows.slice(0, 1)') < t('${climbStub(climb, past)}') && t('${climbStub(climb, past)}') < t('rail([...more, ...rows.slice(1)]'),
    'the first ticket, then the Climb stub inside the first screen, then the rest of the rail');
});

test('Off the card is the line-moved state only, and it lives in the fold, never on the rail', () => {
  const view = body('VIEWS.today = async', '/* ---------- a single best bet');
  assert.match(view, /const offCard = p => C\.pickState\(p, now\)\.word === 'Line moved'/);
  assert.match(view, /const todays = sched\.today\.filter\(p => straight\(p\) && !offCard\(p\)\)/);
  assert.match(view, /const later = sched\.upcoming\.filter\(p => straight\(p\) && !offCard\(p\)\)/);
  assert.match(view, /foldRow\('off-card', `Off the card · \$\{off\.length\}`/);
  assert.doesNotMatch(view, /onboard|class="proof"|statusRows|Research worth a look/);
});

test('Today keeps the footer below the fold while the first view loads', () => {
  assert.match(css, /main#view\s*\{\s*min-height:\s*calc\(100svh\s*-\s*160px\)/);
});
