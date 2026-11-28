'use strict';

const dollars = new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'});
const money = cents => dollars.format(cents / 100);
const eastern = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', month: 'short', day: 'numeric',
  hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
});
const byId = id => document.getElementById(id);
const set = (id, value) => { byId(id).textContent = value; };

function render({run = 1, balance, wins, losses, pushes, current, history, closed, passToday, goalCents, targetOdds}) {
  set('balance', money(balance));
  set('record', [wins, losses, ...(pushes ? [pushes] : [])].join('–'));
  set('step-label', `Run ${run}`);
  if (goalCents && balance > 0 && balance < goalCents && !closed) {
    let cents = balance;
    let steps = 0;
    while (cents < goalCents) {
      cents += Math.round(cents * 100 / Math.abs(targetOdds));
      steps++;
    }
    set('remaining', `${steps} more full ${steps === 1 ? 'win' : 'wins'} at −${Math.abs(targetOdds)} would reach the goal.`);
  }
  if (current) {
    const piece = byId('ticket').content.cloneNode(true);
    const fill = (selector, value) => { piece.querySelector(selector).textContent = value; };
    set('step-label', `Run ${run} · Step ${current.step}`);
    set('slip-title', current.selection);
    const gameStarted = Date.now() >= Date.parse(current.startsAt);
    set('status', gameStarted ? 'Awaiting verified final' : `Starts ${eastern.format(new Date(current.startsAt))}`);
    fill('.matchup', current.matchup || '');
    if (current.legs) {
      const list = piece.querySelector('.legs');
      list.hidden = false;
      for (const leg of current.legs) {
        const li = document.createElement('li');
        li.textContent = `${leg.selection} · ${leg.matchup} · ${eastern.format(new Date(leg.startsAt))}`;
        list.append(li);
      }
    }
    fill('.price', `${current.odds > 0 ? '+' + current.odds : String(current.odds).replace('-', '−')} · ${current.book}`);
    fill('.quote', `Price checked ${eastern.format(new Date(current.checkedAt))}`);
    fill('.risk', money(current.balance));
    fill('.return', money(current.winReturn));
    fill('.reason', current.reason);
    if (current.countercase) fill('.risk-note', current.countercase);
    else {
      piece.querySelector('.risk-note').previousElementSibling.remove();
      piece.querySelector('.risk-note').remove();
    }
    for (const source of current.sources || []) {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.textContent = source.label;
      a.href = source.url;
      li.append(a);
      piece.querySelector('.sources').append(li);
    }
    byId('ticket').after(piece);
  } else {
    set('slip-title', closed ? 'Run complete' : passToday ? 'Pass for now' : 'Next play pending');
    set('status', closed ? 'See the final paper results below.' : passToday || 'The next verified play will appear here.');
  }

  for (const step of history.slice().reverse()) {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.textContent = `Run ${step.run ?? 1} · Step ${step.step} · ${step.selection}`;
    const withdrawn = step.result === 'withdrawn';
    const result = document.createElement(withdrawn || step.legs ? 'span' : 'a');
    if (withdrawn) {
      result.textContent = `WITHDRAWN PREGAME · ${money(step.after)} carried forward`;
    } else if (step.legs) {
      result.textContent = `${step.result.toUpperCase()} · ${money(step.after)}`;
      for (const leg of step.legs) {
        const a = document.createElement('a');
        a.href = leg.resultUrl;
        a.textContent = `${leg.selection} · ${leg.result.toUpperCase()} · ${leg.score}`;
        label.append(document.createElement('br'), a);
      }
    } else {
      result.href = step.resultUrl;
      result.textContent = `${step.result.toUpperCase()} · ${step.score} · ${money(step.after)}`;
    }
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
