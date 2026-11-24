'use strict';

const dollars = new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'});
const money = cents => dollars.format(cents / 100);
const eastern = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', month: 'short', day: 'numeric',
  hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
});
const byId = id => document.getElementById(id);
const set = (id, value) => { byId(id).textContent = value; };

function render({balance, wins, losses, pushes, current, history, closed}) {
  set('balance', money(balance));
  set('record', [wins, losses, ...(pushes ? [pushes] : [])].join('–'));
  if (current) {
    const piece = byId('ticket').content.cloneNode(true);
    const fill = (selector, value) => { piece.querySelector(selector).textContent = value; };
    set('step-label', `Step ${current.step}`);
    set('slip-title', current.selection);
    const gameStarted = Date.now() >= Date.parse(current.startsAt);
    set('status', gameStarted ? 'Awaiting verified final' : `Starts ${eastern.format(new Date(current.startsAt))}`);
    fill('.matchup', current.matchup);
    fill('.price', `${String(current.odds).replace('-', '−')} · ${current.book}`);
    fill('.quote', `Price checked ${eastern.format(new Date(current.checkedAt))}`);
    fill('.risk', money(current.balance));
    fill('.return', money(current.winReturn));
    fill('.reason', current.reason);
    fill('.risk-note', current.countercase);
    for (const source of current.sources) {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.textContent = source.label;
      a.href = source.url;
      li.append(a);
      piece.querySelector('.sources').append(li);
    }
    byId('ticket').after(piece);
  } else {
    set('slip-title', closed ? 'Run complete' : 'Next play pending');
    set('status', closed ? 'See the final paper results below.' : 'The next verified play will appear here.');
  }

  for (const step of history.slice().reverse()) {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.textContent = `Step ${step.step} · ${step.selection}`;
    const result = document.createElement('a');
    result.href = step.resultUrl;
    result.textContent = `${step.result.toUpperCase()} · ${step.score} · ${money(step.after)}`;
    li.append(label, result);
    byId('history').append(li);
  }
  byId('empty').hidden = history.length > 0;
}

fetch('../data/app/secret-santa.json', {cache: 'no-cache'})
  .then(response => {
    if (!response.ok) throw new Error('Card unavailable');
    return response.json();
  })
  .then(render)
  .catch(() => { set('slip-title', 'Card unavailable'); set('status', 'Refresh to retry.'); });
