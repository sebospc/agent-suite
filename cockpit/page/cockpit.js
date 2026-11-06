// Renders /api/snapshot. Every rule lives in the Python core; this file formats, opens and closes, and wires buttons.
'use strict';

const POLL_MS = 5000;
const NEEDS_SHOWN = 5;  // the owner, 2026-10-16: Needs you never pushes the rest off the screen
const LEVEL_WORDS = { act: 'ACT', watch: 'WATCH', ok: 'OK', unknown: 'UNKNOWN' };
const ICONS = {
  warning: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M5.6 1.8h4.8l3.4 3.4v4.8l-3.4 3.4H5.6L2.2 10V5.2Z" stroke-linejoin="round"/><path d="M8 4.8v3.6" stroke-linecap="round"/><circle cx="8" cy="10.9" r="0.75" fill="currentColor" stroke="none"/></svg>',
  caution: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M8 2.2 14.2 13.3H1.8Z" stroke-linejoin="round"/><path d="M8 6.4v3.2" stroke-linecap="round"/><circle cx="8" cy="11.4" r="0.75" fill="currentColor" stroke="none"/></svg>',
  chev: '<svg class="chev" width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M3.5 1.5 7 5l-3.5 3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};
const SOURCE_NAMES = { board: 'board (bd)', asks: 'panel.json', live: 'live sessions', accounts: 'cswap', balancer: 'balancer log',
  gate: 'gate', plan: 'team.json', tokens: 'daily tokens', transcripts: 'transcripts',
  classifier: 'Jev', history: 'tokens per day', past: 'transcripts, 14 days', landed: 'commits today', decisions: 'decision log', commits: 'commit ids' };
// A light names the box it opens; the core calls the sessions box "sessions".
const BOX_OF_TAB = { milestone: 'milestone', sessions: 'sessions', asks: 'asks', accounts: 'accounts', jobs: 'jobs', needs: 'asks', health: 'health' };

const ui = { open: JSON.parse(remembered('open') || '{}'), expanded: new Set(), allNeeds: false, sourcesOpen: '',
  copied: {}, sentAt: {}, controlError: {}, wrongError: {}, snapshot: null, grillBusy: false, grillError: '', light: '',
  picked: new Set(), answerError: {}, drafts: {} };

function remembered(key) { try { return localStorage.getItem('cockpit.' + key); } catch (e) { return null; } }
function remember(key, value) { try { localStorage.setItem('cockpit.' + key, value); } catch (e) { /* private window */ } }
function h(text) { return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]); }
function k(tokens) { return tokens == null ? '' : Math.round(tokens / 1000) + 'k'; }
function millions(tokens) { return tokens == null ? '' : (tokens / 1e6).toFixed(1) + 'M'; }
function $(id) { return document.getElementById(id); }
// Every region says which read its numbers come from (design chat D11); the page redraws only when a read changes.
function readText(readAt) {
  if (!readAt) return '';
  const at = new Date(readAt * 1000);
  return `Read at ${ui.snapshot.read_seconds || at.toTimeString().slice(0, 8)}.`;
}
function isOpen(box) { return ui.open[box] !== false; }

// The shared shape of every section: a header that opens and closes it, then its body.
function box(name, title, count, summary, body, lit, target) {
  const section = $('box-' + name);
  section.dataset.open = String(isOpen(name));
  section.classList.toggle('lit', lit === 'caution');
  section.classList.toggle('lit-warning', lit === 'warning');
  (target || section).innerHTML = `<div class="box-bar">${grip(name, title)}<button class="box-head" data-box="${name}" aria-expanded="${isOpen(name)}">${ICONS.chev}
      <h2 id="h-${name}">${h(title)}</h2>${count === '' ? '' : `<span class="count">${h(count)}</span>`}<span class="summary">${summary}</span></button></div>
    <div class="box-body">${body}</div>`;
}

// A one-line row; clicking anywhere on it but its own buttons opens its detail underneath.
function row(key, cls, cells, detail) {
  const open = ui.expanded.has(key);
  return `<div class="row toggle ${cls}${open ? ' open' : ''}" data-key="${h(key)}" role="button" tabindex="0" aria-expanded="${open}">${cells}</div>
    ${open ? `<div class="detail${key === ui.justOpened ? ' enter' : ''}">${detail}</div>` : ''}`;
}

// Each section's log: one "Log (N)" line at its bottom, closed by default, opening in place (the owner, 2026-10-16).
function logLine(name, rows, empty, count) {
  const key = 'log:' + name, open = ui.expanded.has(key);
  const body = rows.join('') || logRow('', `<span class="dim">${h(empty)}</span>`);
  return `<div class="footer"><button class="link" data-key-open="${key}" aria-expanded="${open}">Log (${count == null ? rows.length : count})</button></div>
    ${open ? `<div class="log${ui.justOpened === key ? ' enter' : ''}">${body}</div>` : ''}`;
}

function logRow(time, html) {
  return `<div class="log-row"><span class="mono dim">${h(time)}</span><span>${html}</span></div>`;
}

function pairs(list) {
  const shown = list.filter(([, v]) => v !== '' && v != null);
  return shown.length ? `<div class="pairs">${shown.map(([n, v]) => `<span>${h(n)}</span><span>${h(v)}</span>`).join('')}</div>` : '';
}

async function poll() {
  try {
    const response = await fetch('/api/snapshot', { cache: 'no-store' });
    if (response.ok) {
      // A new server or new page files: load the new page, unless the owner has something staged to send.
      const build = response.headers.get('X-Cockpit-Build');
      if (ui.build && build && build !== ui.build && !(ui.staged || []).length) { location.reload(); return; }
      ui.build = build || ui.build;
      const text = await response.text();
      if (text === ui.lastText) return;  // nothing changed: leave the page alone, so nothing re-animates
      ui.lastText = text; ui.snapshot = JSON.parse(text); render();
    }
    else { $('read-time').textContent = 'first read still running'; }
  } catch (e) { $('read-time').textContent = 'the cockpit server is not answering'; }
}

// A refresh rebuilds the rows; give focus back to the same control so the keyboard does not lose its place.
function focusKey() {
  const el = document.activeElement;
  if (!el || el === document.body) return '';
  for (const attr of ['data-key', 'data-key-open', 'data-sort', 'data-hist', 'data-need', 'data-box', 'data-goto', 'data-grip', 'data-control', 'data-wrong', 'data-pick', 'data-draft', 'id']) {
    if (el.hasAttribute(attr)) return `[${attr}="${CSS.escape(el.getAttribute(attr))}"]`;
  }
  return '';
}

function render() {
  const focused = focusKey();
  draw();
  const again = focused && document.querySelector(focused);
  if (again && again !== document.activeElement) {
    again.focus({ preventScroll: true });
    if (again.dataset.draft) again.setSelectionRange(again.value.length, again.value.length);
  }
}

function draw() {
  const s = ui.snapshot;
  $('read-time').textContent = `read ${s.read_seconds || s.read_clock} · every ${s.refresh_s} s`;
  // The refresh line fills until the next read; it starts at the snapshot's read time, not at this redraw.
  $('read-time').insertAdjacentHTML('beforeend', `<span class="beat" aria-hidden="true" style="--period: ${s.refresh_s}s; --since: -${Math.max(0, Date.now() / 1000 - s.read_at).toFixed(1)}s"></span>`);
  // A source that broke is amber; one that waits on a team change (balancer log, team.json, gate logs) is quiet.
  const broken = Object.entries(s.sources).filter(([, r]) => !r.ok && !r.pending && !r.absent);
  const pending = Object.entries(s.sources).filter(([, r]) => !r.ok && r.pending);
  [['sources-toggle', broken, 'broken', 'unavailable'], ['pending-toggle', pending, 'pending', 'not set up yet']].forEach(([id, list, kind, word]) => {
    $(id).hidden = list.length === 0;
    $(id).textContent = `${list.length} source${list.length === 1 ? '' : 's'} ${word}`;
    $(id).setAttribute('aria-expanded', String(ui.sourcesOpen === kind));
  });
  // The daily price check: the header says so when config/prices.json differs from Anthropic's page.
  const differs = (s.prices && s.prices.differences) || [];
  $('prices-toggle').hidden = differs.length === 0;
  $('prices-toggle').textContent = `prices differ from Anthropic's page (${differs.length})`;
  $('prices-toggle').setAttribute('aria-expanded', String(ui.sourcesOpen === 'prices'));
  const listed = ui.sourcesOpen === 'broken' ? broken.map(([n, r]) => `${SOURCE_NAMES[n] || n}: ${r.error}`)
    : ui.sourcesOpen === 'pending' ? pending.map(([n, r]) => `${SOURCE_NAMES[n] || n}: ${r.error}`)
    : ui.sourcesOpen === 'prices' ? differs.concat(`Checked ${s.prices.checked} against ${s.prices.source}`) : [];
  $('sources').hidden = listed.length === 0;
  $('sources').innerHTML = listed.map((line) => `<li>${h(line)}</li>`).join('');
  renderPause(s.pause);
  renderHealth(s); renderMilestone(s.milestone); renderSessions(s); renderAsks(s.asks, s); renderAccounts(s); renderJobs(s);
  renderStaged();
}

// Pause / Resume (design chat AP3, L6): brain's hook blocks commits, pushes and bead claims while the mark is set; the
// banner shows whether any got in after it.
function renderPause(p) {
  const paused = Boolean(p && p.paused);
  $('pause-team').textContent = paused ? 'Resume the team' : 'Pause the team';
  $('pause-team').setAttribute('aria-pressed', String(paused));
  $('paused').hidden = !paused;
  if (!paused) return;
  const slipped = [p.commits.length ? `${p.commits.length} commit${p.commits.length === 1 ? '' : 's'} (${p.commits.join(', ')})` : '',
    p.claims.length ? `${p.claims.length} bead claim${p.claims.length === 1 ? '' : 's'} (${p.claims.join(', ')})` : ''].filter(Boolean);
  $('paused').innerHTML = `<b>The team is paused since ${h(p.since)}.</b> ${slipped.length
    ? `<span class="coral">Since then: ${h(slipped.join(' and '))}. The pause hook did not hold; tell brain (TEAM_DEPENDENCIES 7).</span>`
    : `No commit${p.commits_read ? '' : ' (commits not read)'} and no bead claim since.`}`;
}

async function togglePause() {
  const paused = !(ui.snapshot.pause && ui.snapshot.pause.paused);
  try {
    const response = await fetch('/api/pause', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paused }) });
    const body = await response.json();
    if (!body.ok) $('read-time').textContent = body.error;
  } catch (e) { $('read-time').textContent = 'the cockpit server is not answering'; }
  ui.lastText = ''; setTimeout(poll, 500);
}

// Your tasks' Actions group (the owner, 2026-10-16: what needs the owner goes to the tasks panel).
function actionsBody(s) {
  const shown = ui.allNeeds ? s.needs : s.needs.slice(0, NEEDS_SHOWN);
  // A row the owner acted on stays, dimmed, with its result in place of its source until the next read drops it (N5).
  const rows = shown.map((n) => {
    const copied = ui.copied[n.id];
    const sent = n.action_kind === 'send' || n.action_kind === 'control'
      ? s.actions.find((e) => e.session === n.target && ui.sentAt[n.id] && e.id === ui.sentAt[n.id]) : null;
    const done = Boolean(copied || sent);
    const label = copied ? `Copied ${copied}` : sent ? (sent.state === 'done' ? 'Done' : 'Sent') : n.action_label;
    const cells = `<span class="level ${n.level}">${ICONS[n.level]}<span class="level-word">${n.level === 'warning' ? 'Warning' : 'Caution'}</span></span>
      <span class="clip">${h(n.text)}</span>
      <button class="btn" data-need="${h(n.id)}"${n.action_kind === 'none' || done ? ' disabled' : ''}>${h(label)}</button>`;
    const pasted = copied ? (n.target ? `Copied at ${copied}. Paste it into ${n.target}'s pane.` : `Copied at ${copied}. Paste it into a terminal.`) : '';
    const typed = n.action_kind === 'send' ? `Confirming types this into ${n.target}'s pane: ${n.action_payload}` : '';
    return row('need:' + n.id, 'need-row' + (done ? ' acted' : ''), cells, `<span class="text">${h(n.text)}</span>${pairs([['Level', n.level === 'warning' ? 'Warning' : 'Caution'],
      [sent ? 'Result' : 'Source', sent ? sent.text : n.source], ['Copied', pasted], ['Sends', sent ? '' : typed]])}${ui.controlError[n.target] ? `<span class="amber" role="status">${h(ui.controlError[n.target])}</span>` : ''}`);
  }).join('');
  const more = s.needs.length > NEEDS_SHOWN
    ? `<div class="footer"><button class="link" id="more-needs" aria-expanded="${ui.allNeeds}">${ui.allNeeds ? 'Show fewer' : `Show ${s.needs.length - NEEDS_SHOWN} more`}</button></div>` : '';
  return `<div class="group">Actions · ${s.needs.length}</div>${rows || '<div class="footer">No action waits on you.</div>'}${more}`;
}

function act(id) {
  const need = ui.snapshot.needs.find((n) => n.id === id);
  if (!need) return;
  if (need.action_kind === 'jump') { goTo(need.action_payload); return; }  // the payload names the box
  if (need.action_kind === 'control') { stageControl(need.action_payload, need.target, '', id); return; }
  if (need.action_kind === 'send') { stageControl('need', need.target, '', id); return; }
  const at = new Date().toTimeString().slice(0, 5);
  navigator.clipboard.writeText(need.action_payload).then(() => { ui.copied[id] = at; ui.expanded.add('need:' + id); render(); });
}

function goTo(tab) {
  const name = BOX_OF_TAB[tab];
  if (!name) return;
  ui.open[name] = true; remember('open', JSON.stringify(ui.open)); render();
  $('box-' + name).scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('box-' + name).querySelector('.box-head').focus({ preventScroll: true });
}

function toggleRow(key) {
  if (ui.expanded.has(key)) ui.expanded.delete(key); else { ui.expanded.add(key); ui.justOpened = key; }
  render();
  ui.justOpened = '';  // only the row just opened rises in; a refresh redraws it still
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (button) {
    if (button.dataset.need) return act(button.dataset.need);
    if (button.dataset.wrong) return markWrong(button.dataset.wrong);
    if (button.dataset.sort) return sortBy(button.dataset.sort);
    if (button.dataset.hist) return showHistory(button.dataset.hist);
    if (button.dataset.answer) return stageAnswer(button.dataset.answer, button.dataset.option || '', Boolean(button.dataset.own));
    if (button.dataset.goto) return goTo(button.dataset.goto);
    if (button.dataset.box) { ui.open[button.dataset.box] = !isOpen(button.dataset.box); remember('open', JSON.stringify(ui.open)); return render(); }
    if (button.dataset.control) return stageControl(button.dataset.control, button.dataset.session, button.dataset.level || '');
    if (button.id === 'send-staged') return sendStaged();
    if (button.id === 'discard-staged') { ui.staged = []; ui.stagedError = ''; return render(); }
    if (button.id === 'more-needs') { ui.allNeeds = !ui.allNeeds; return render(); }
    if (button.id === 'sources-toggle' || button.id === 'pending-toggle' || button.id === 'prices-toggle') {
      const kind = { 'sources-toggle': 'broken', 'pending-toggle': 'pending', 'prices-toggle': 'prices' }[button.id];
      ui.sourcesOpen = ui.sourcesOpen === kind ? '' : kind; return render();
    }
    if (button.dataset.bead) return openBead(button.dataset.bead);
    if (button.dataset.keyOpen) return toggleRow(button.dataset.keyOpen);
    if (button.id === 'close-bead') return $('bead-dialog').close();
    if (button.id === 'start-grill') return startGrill();
    if (button.id === 'pause-team') return togglePause();
  }
  const clicked = event.target.closest('[data-key]');
  // A row inside another row's detail (Team health's tables) toggles itself; the detail's own text toggles nothing.
  const detail = event.target.closest('.detail');
  if (clicked && !event.target.closest('a, summary, input') && (!detail || detail.contains(clicked))) toggleRow(clicked.dataset.key);
});

// A ticked ask and a half-typed answer survive the redraw a new read brings.
document.addEventListener('change', (event) => {
  const id = event.target.dataset && event.target.dataset.pick;
  if (!id) return;
  if (event.target.checked) ui.picked.add(id); else ui.picked.delete(id);
  render();
});
document.addEventListener('input', (event) => {
  if (event.target.dataset && event.target.dataset.draft) ui.drafts[event.target.dataset.draft] = event.target.value;
});

document.addEventListener('keydown', (event) => {
  const clicked = event.target.closest && event.target.closest('[data-key]');
  if (clicked && event.target === clicked && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault(); toggleRow(clicked.dataset.key);
  }
});

window.addEventListener('DOMContentLoaded', () => { poll(); setInterval(poll, POLL_MS); });
