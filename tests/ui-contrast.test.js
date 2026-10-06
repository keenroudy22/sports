'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const css = fs.readFileSync('site/next/app.css', 'utf8');
const root = css.match(/:root\s*\{([\s\S]*?)\}/)[1];
const colors = Object.fromEntries([...root.matchAll(/--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})/g)].map(m => [m[1], m[2]]));
const luminance = hex => {
  const rgb = hex.slice(1).match(/../g).map(x => parseInt(x, 16) / 255).map(x => x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
};
const ratio = (a, b) => {
  const [hi, lo] = [luminance(colors[a]), luminance(colors[b])].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test('all approved text/background token pairs meet WCAG AA', () => {
  const pairs = [
    ['chalk', 'felt-night'], ['dim', 'felt-night'], ['chalk', 'felt'], ['dim', 'felt'],
    ['kookd', 'felt-night'], ['burnt-text', 'felt-night'],
    ['ticket-dim', 'ticket'], ['ticket-green', 'ticket'], ['ticket-red', 'ticket'],
    ['kookd-ink', 'kookd'], ['burnt-ink', 'burnt'],
  ];
  for (const [fg, bg] of pairs) assert.ok(ratio(fg, bg) >= 4.5, `${fg} on ${bg}: ${ratio(fg, bg).toFixed(2)}:1`);
});
