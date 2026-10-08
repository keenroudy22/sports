'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const banned = /\b(?:launchd|pipeline|deskRuns|desk runs?|next run|automated|automation|I look again|hosted refresh|every 5 min|every 30 min|climb check|behind the scenes|pre-post review|delivery checks|release schedule|data status|scans?|scheduled check|the desk|the owner|kitchen.s closed|ladder step)\b|closed to new entries at \d{1,2}:\d{2}/i;

test('the phone-facing shell does not tell readers private publishing times', () => {
  for (const name of ['index.html', 'app.js', 'app-more.js', 'app-games.js', 'core.js', 'live.js', 'personal.js']) {
    assert.doesNotMatch(fs.readFileSync(`site/${name}`, 'utf8'), banned, name);
  }
});

test('whole-word checks spare player names and normal timing facts', () => {
  for (const good of ['Valdes-Scantling', 'Inactives post at 6:45 PM', 'No automatic betting',
                      'not automatically a good price', '2026-10-08T12:00:00Z']) assert.doesNotMatch(good, banned);
  for (const bad of ['next run', 'the desk', 'Ladder step 2']) assert.match(bad, banned);
});
