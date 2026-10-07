import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const app = fs.readFileSync(new URL('../site/app.js', import.meta.url), 'utf8');
const css = fs.readFileSync(new URL('../site/app.css', import.meta.url), 'utf8');

test('Today shows the official bet before season proof and onboarding', () => {
  const start = app.indexOf('return `${head(`Today ·');
  const end = app.indexOf("${laterHtml ? section('More best bets'", start);
  const today = app.slice(start, end);
  assert.ok(start >= 0 && end > start);
  assert.ok(today.indexOf('<section class="section">${heroHtml}</section>') < today.indexOf('${onboard}'));
  assert.ok(today.indexOf('<p class="proof">') < today.indexOf('${onboard}'));
});

test('Today keeps the footer below the fold while the first view loads', () => {
  assert.match(css, /main#view\s*\{\s*min-height:\s*calc\(100svh\s*-\s*160px\)/);
});

test('a moved or expired quote is outside More best bets', () => {
  assert.match(app, /const upcoming = later\.filter\(p => !offCard\(p\)\)/);
  assert.match(app, /off = \[\.\.\.sched\.today, \.\.\.later\]\.filter\(p => !C\.isParlay\(p\) && !pulled\(p\) && offCard\(p\)\)/);
  assert.match(app, /Off the card · \$\{off\.length\}/);
});
