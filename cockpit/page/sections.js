// Milestone, sessions, asks with the embedded grill round and accounts. Formatting only.
'use strict';


function bar(value, scale, tick, over, thin, waiting) {
  if (value == null) return '<span class="bar" aria-hidden="true"></span>';
  const pct = (v) => Math.min(100, v / scale * 100).toFixed(1) + '%';
  return `<span class="bar" aria-hidden="true"><span class="fill${over ? ' over' : ''}${waiting ? ' waiting' : ''}" style="width: ${pct(value)}"></span>${tick == null ? '' : `<span class="tick${thin ? ' thin' : ''}" style="left: ${pct(tick)}"></span>`}</span>`;
}

function segments(total, filled, target) {
  const parts = Array.from({ length: total }, (_, i) => `<span class="seg${i < filled ? ' on' : ''}${i + 1 === target ? ' target' : ''}"></span>`).join('');
  return `<span class="segs" aria-hidden="true">${parts}</span>`;
}

// A busy session's dot breathes; the delay keeps its phase when the 5 s refresh rebuilds the page.
function worker(w) {
  const phase = `style="animation-delay: -${Date.now() % 2400}ms"`;
  return `<span class="worker ${h(w.state)}" title="${h(w.name)}: ${h(w.state)}"${w.state === 'busy' ? ' ' + phase : ''}>${h(w.name.slice(0, 2))}</span>`;
}

// DESIGN.md "Show what is live": bars that move while a session works, flat dots while it is idle. The phase comes
// from the clock and the row, so the refresh that rebuilds the page does not restart them and busy rows never move
// in lockstep; it carries no data.
function phase(index, period) {
  return `--phase: -${(Date.now() + index * 370) % period}ms`;
}

function glyph(motion, index) {
  return `<span class="eq ${motion}" aria-hidden="true" style="${phase(index, 1800)}"><i></i><i></i><i></i></span>`;
}

function sweep(motion, index) {
  return motion === 'resting' ? '' : `<span class="sweep ${motion}" aria-hidden="true" style="${phase(index, 2400)}"></span>`;
}

function roadmapStrip(stops) {
  return `<ol class="road">${stops.map((s) => {
    const pct = s.total ? Math.round(s.closed / s.total * 100) : 0;
    return `<li class="stop${s.current ? ' current' : ''}" title="${h(`${s.name}: ${s.title} · ${s.closed} of ${s.total} done criteria`)}">
      <span class="ring" style="--pct: ${pct}%"><span>${h(s.name)}</span></span>
      <span class="stop-text"><span class="clip">${h(s.title)}</span><span class="mono dim">${s.closed}/${s.total}</span></span></li>`;
  }).join('<li class="road-line" aria-hidden="true"></li>')}</ol>`;
}

function paceBars(days) {
  const top = Math.max(1, ...days);
  const week = days.slice(-7).reduce((a, b) => a + b, 0);
  return `<span class="pace" aria-hidden="true">${days.map((n, i) => `<span class="day${i >= 7 ? ' recent' : ''}" style="height: ${n ? Math.max(15, n / top * 100) : 6}%" title="${n} closed"></span>`).join('')}</span>
    <span class="sub"><b class="mono">${week}</b> closed in 7 days</span>`;
}

function tile(cell, left) {
  const note = left ? left.note : '';
  const nobody = cell.state !== 'closed' && !cell.workers.length;
  const who = left && left.who !== 'nobody' ? `${left.who}${left.age ? ' · ' + left.age : ''}` : (left && left.age) || '';
  return `<button class="tile ${h(cell.state)}${cell.is_goal ? ' goal' : ''}${left && left.amber ? ' warn' : ''}" data-bead="${h(cell.id)}" title="${h(note)}">
    <span class="tile-top"><span class="mono">${h(cell.id.replace(/^.*?\./, '.'))}</span>${cell.is_goal ? '<span class="amber">goal</span>' : `<span class="clip">${h(who)}</span>`}</span>
    <span class="tile-title">${h(cell.title)}</span>
    <span class="tile-who">${cell.workers.map(worker).join('')}${nobody ? `<span class="${left && left.amber ? 'amber' : 'dim'}">${waitingWord(left)}</span>` : ''}</span></button>`;
}

function waitingWord(left) {
  if (!left) return 'nobody on it';
  return /waits for you|waits on you/.test(left.note) ? 'waits for you' : left.note.startsWith('Blocked') ? 'blocked' : 'nobody on it';
}

function renderMilestone(m) {
  $('box-milestone').hidden = Boolean(m.absent);  // a project that keeps no board or milestone has no section for it
  if (m.absent) return;
  if (!m.available) { box('milestone', 'Milestone', '', `<span class="amber">Unavailable: ${h(m.error)}</span>`, ''); return; }
  const g = m.goal, c = m.criteria;
  const leftById = Object.fromEntries(m.left.map((t) => [t.id, t]));
  const goal = g.available
    ? `<div class="stat"><span class="label">Goal</span><span class="figure"><b>${g.value}</b><span>/${g.total}</span></span>
        ${segments(g.total, g.value, g.target)}<span class="sub">target <b class="mono">${g.target}</b>${g.target_date ? ` by ${h(g.target_date)}` : ''}${g.next_eval ? ` · next eval ${h(g.next_eval)}` : ''} · <button class="link" data-key-open="ms:goal">${h(g.label)}</button></span></div>`
    : `<div class="stat"><span class="label">Goal</span><span class="amber">${h(g.error)}</span></div>`;
  const crits = c.cells.map((x) => `<span class="crit ${h(x.state)}${x.is_goal ? ' goal' : ''}"></span>`).join('');
  const criteria = `<div class="stat"><span class="label">Done criteria</span><span class="figure"><b>${c.closed}</b><span>/${c.total}</span></span>
      <span class="crits" role="img" aria-label="${c.total} done criteria: ${c.closed} closed, ${c.in_progress} in progress, ${c.blocked} blocked, ${c.open} open">${crits}</span>
      <span class="sub">${[[c.in_progress, 'worked on'], [c.blocked, 'blocked'], [c.open, 'open']].filter(([n]) => n).map(([n, w]) => `<b class="mono">${n}</b> ${w}`).join(' · ') || 'all closed'}</span>
      <span class="legend dim"><span class="crit closed"></span>closed <span class="crit in_progress"></span>worked on <span class="crit blocked"></span>blocked <span class="crit"></span>open</span>
      <span class="dim" style="font-size: 12px">${c.closed} of ${c.total} closed.${c.goal_open && c.total - c.closed ? ` The ${c.total - c.closed} left include the goal itself.` : ''}</span></div>`;
  const moving = `<div class="stat"><span class="label">Closed per day · 14 d</span>${paceBars(m.pace)}</div>`;
  const goalDetail = ui.expanded.has('ms:goal') ? `<div class="detail${ui.justOpened === 'ms:goal' ? ' enter' : ''}">${pairs([['Goal', g.label], ['Source', g.source],
    ['Target date', g.target_date || 'not in goal.json'], ['Next eval', g.next_eval || 'not in goal.json']])}</div>` : '';
  const open = c.cells.filter((x) => x.state !== 'closed');
  const busy = new Set(open.flatMap((x) => x.workers.filter((w) => w.state === 'busy').map((w) => w.name)));
  const f = m.found;
  const closed = m.closed_log.map((b) => logRow(b.at, `${beadLink(b.id)} ${h(b.title)} <span class="dim">· ${h(b.who)}</span>`));
  box('milestone', `${m.name}: ${m.title.replace(/^M\d+:\s*/, '')}`, '', '',
    `<div class="footer" style="padding-top: 8px">${h(m.subline)}</div>${roadmapStrip(m.roadmap)}<div class="hero">${goal}${criteria}${moving}</div>${goalDetail}
     <div class="group">Open criteria · ${open.length}${busy.size ? ` · <span class="live">${busy.size} working now</span>` : ' · nobody working now'}</div>
     <div class="tiles">${open.map((x) => tile(x, leftById[x.id])).join('') || '<span class="footer">All closed.</span>'}</div>
     <div class="footer">Found during ${h(m.name)}: ${f.total} beads, ${f.closed} closed, ${f.in_progress} in progress; never counted in its criteria. ${h(m.source)}.</div>
     ${logLine('milestone', closed, 'No bead closed under it in the last 7 days.')}`);
}

function renderSessions(s) {
  const rows = s.sessions, running = rows.filter((r) => r.state !== 'off'), off = rows.filter((r) => r.state === 'off');
  const scale = Math.max(200000, ...rows.map((r) => Math.max(r.context || 0, r.spot || 0) * 1.1));
  const startScale = Math.max(1, ...rows.map((r) => Math.max(r.start_load || 0, r.start_limit ? r.start_limit.limit : 0) * 1.1));
  const counts = ['busy', 'idle'].map((st) => `${rows.filter((r) => r.state === st).length} ${st}`).concat(`${off.length} off`).join(' · ');
  const head = `<div class="row head team-row"><span>Session</span><span>State</span><span class="wide">Model</span><span>Context / sweet spot</span><span class="wide" title="What it loads before any work (CLAUDE.md, system prompt, tools, memory); tick: its role's usual plus its margin">Start / limit</span><span class="wide">Bead</span></div>`;
  const compacting = new Set((s.actions || []).filter((a) => a.kind === 'compact' && a.state === 'waiting').map((a) => a.session));
  const body = running.map((r, i) => {
    const flagged = r.stuck || r.marks.length || r.drift;
    const motion = compacting.has(r.name) ? 'compacting' : r.state === 'busy' ? 'working' : 'resting';
    // The account sits in the agent cell, not a column of its own (owner 2026-10-19, pg-i0zr).
    const cells = `<span class="agent-cell" title="${r.account ? 'account ' + h(r.account) : ''}"><span class="clip" style="font-weight: 600">${h(r.name)}${flagged ? ' <span class="amber" title="see its detail">●</span>' : ''}</span>${r.account ? `<span class="mono dim">${h(r.account)}</span>` : ''}</span>
      <span class="state ${h(r.state)}">${glyph(motion, i)}${h(r.state)}</span>
      <span class="wide clip ${r.drift ? 'amber' : 'sub'}" title="${h(r.drift)}">${h([r.model, r.effort].filter(Boolean).join(' · '))}${r.drift ? ' ≠ team.json' : ''}</span>
      <span class="ctx"><span class="mono${r.over ? ' amber' : ''}" style="font-size: 13px">${r.context == null ? (r.context_note || '') : k(r.context) + (r.spot ? ' / ~' + k(r.spot) : '')}</span>${bar(r.context, scale, r.spot, r.over, false, motion === 'compacting')}</span>
      <span class="wide ctx"><span class="mono${r.start_over ? ' amber' : ''}" style="font-size: 13px">${r.start_load == null ? '' : '~' + k(r.start_load) + (r.start_limit ? ' / ' + k(r.start_limit.limit) : '')}</span>${r.start_load == null ? '<span></span>' : bar(r.start_load, startScale, r.start_limit ? r.start_limit.limit : null, r.start_over)}</span>
      <span class="wide bead-cell" style="font-size: 13px">${beadIn(r.bead) ? beadLink(beadIn(r.bead), r.bead) : ''}${KIND_TAG[r.kind] ? `<span class="tag ${h(r.kind)}">${KIND_TAG[r.kind]}</span>` : ''}</span>${sweep(motion, i)}`;
    return row('session:' + r.name, 'team-row', cells, sessionDetail(r, s));
  }).join('');
  const offLine = off.length ? `<div class="row line-row"><span></span><span class="off">Off: ${h(off.map((r) => r.name).join(', '))}</span></div>` : '';
  const anyOver = rows.some((r) => r.over || r.haiku_over_step);
  box('sessions', 'Sessions', `${running.length}/${rows.length}`, h(counts),
    `${head}${body}${offLine}${s.price_mark ? `<div class="footer amber">${h(s.price_mark)}</div>` : ''}
     <div class="footer">Bar: context now (measured); tick: that session's sweet spot (~ heuristic, from the cost model). ${readText(s.read_at)} From transcripts (context, model, effort, turns; skills in each detail), settings files and ps (plugins, in each detail), herdr (state, pane), cswap (account), bd (bead), team.json (intended model and effort), config/prices.json (the sweet spot's prices).</div>
     ${logLine('sessions', controlsLog(s.controls_today), 'You sent no control today.')}`, anyOver ? 'caution' : '');
}

// The kind of work in the Bead column (design chat S4); off and next-milestone work stand out.
const KIND_TAG = { dod: 'criterion', found: 'found', p0: 'P0', next: 'next M', off: 'off', role: 'role', idle: 'idle' };

const EFFECT_MARK = { done: '<span class="dim">✓</span>', confirmed: '<span class="dim">✓</span>', waiting: '<span class="amber">…</span>',
  not_seen: '<span class="coral">✗</span>', failed: '<span class="coral">✗</span>' };

function effectLine(e) {
  return `<div class="effect ${h(e.state)}${ui.lastActed === e.id ? ' enter' : ''}" role="status">${EFFECT_MARK[e.state] || ''}<span>${h(e.text)}</span></div>`;
}

// Phase 2 controls: each one names why it is off when it is, and its result is read back from the transcript.
function controlsFor(r, s) {
  if (r.state === 'off' || !r.pane) return '';
  const compact = `<button class="btn${r.can_compact ? ' primary' : ''}" data-control="compact" data-session="${h(r.name)}"${r.can_compact ? '' : ' disabled'}>Compact ${h(r.name)}</button>`;
  const clear = `<button class="btn" data-control="clear" data-session="${h(r.name)}"${r.can_clear ? '' : ' disabled'} title="${h(r.clear_why)}">Clear at task end</button>`;
  const effort = `<span class="seg-control" role="group" aria-label="Effort of ${h(r.name)}">${s.efforts.map((level) =>
    `<button data-control="effort" data-session="${h(r.name)}" data-level="${level}" aria-pressed="${level === r.effort}"${level === r.effort ? ' disabled' : ''}>${level}</button>`).join('')}</span>`;
  const why = [r.can_compact ? '' : (r.over || r.haiku_over_step) && r.why, r.can_clear ? '' : r.clear_why].filter((x) => x && !/notes were not saved/.test(x));
  const error = ui.controlError[r.name];
  const effects = s.actions.filter((e) => e.session === r.name).map(effectLine).join('');
  return `<div class="actions">${compact}${clear}<span class="dim">Effort</span>${effort}</div>
    ${why.length ? `<span class="dim">${h(why.join(' '))}</span>` : ''}${error ? `<span class="amber">${h(error)}</span>` : ''}
    <div aria-live="polite">${effects}</div>`;
}

// The Sessions log: the owner's controls sent today and what the transcript proved, read back from actions.jsonl.
function controlsLog(today) {
  const t = today || { rows: [], error: '' };
  if (t.error) return [logRow('', `<span class="amber">Log unreadable: ${h(t.error)}</span>`)];
  return t.rows.map((d) => logRow(d.t, `${EFFECT_MARK[d.state] || ''} ${h(d.session)}: ${h(d.result || `Typed ${d.text}; waiting for its proof.`)}`));
}

function sessionDetail(r, s) {
  // A button kept in ui.expanded, not <details>: the read every few seconds rebuilds the detail and would close it.
  const howKey = 'how:' + r.name, howOpen = ui.expanded.has(howKey);
  const how = r.inputs.length ? `<button class="link" data-key-open="${h(howKey)}" aria-expanded="${howOpen}">How the sweet spot is worked out</button>
    ${howOpen ? pairs([['Formula', 'P + √(2 · g · C / r); window = sweet spot + 33k']].concat(r.inputs.map((i) => [i.name, i.value]))) : ''}` : '';
  return `${[r.stuck, ...r.marks, r.drift].filter(Boolean).map((x) => `<span class="amber">${h(x)}</span>`).join('')}
    ${beadIn(r.bead) ? `<div class="actions">${beadLink(beadIn(r.bead), 'Open ' + beadIn(r.bead))}</div>` : ''}
    ${pairs([['Working on', [r.bead, r.tag].filter(Boolean).join(' · ')], ['Context', r.context == null ? (r.context_note || r.why) : `${k(r.context)}${r.spot ? `, sweet spot ${k(r.spot)} (${r.spot_kind})` : ''}`],
      ['Start load', r.start_load == null ? '' : `~${k(r.start_load)} before any work (its first request minus the message that started it)${r.start_limit ? `; its role usually starts at ${k(r.start_limit.usual)} (${r.start_limit.starts} starts in 14 days), limit ${k(r.start_limit.limit)}` : '; no usual yet (fewer than 3 starts in 14 days)'}`],
      ['Base', r.base ? `${k(r.base)}: what it re-reads on every turn before any work (CLAUDE.md, tools, memory); no compaction goes below it` : ''], ['Age', r.age], ['Compactions today', r.compactions_today.join('; ') || 'none'], ['Window', r.window ? `${k(r.window)} from its next launch (--autocompact ${r.window}); applied once launches read team.json` : ''], ['Idle for', r.idle_for],
      ['Plugins', r.plugins_error || r.plugins.concat((r.hook_plugins || []).map(m => `${m} (SessionStart hook)`)).join(', ')], ['Skills used', r.skills.join(', ')],
      ['Modes at its last start', r.start_modes_note || r.start_modes.join(', ')], ['Launch flags', r.flags.join(' ')]])}
    ${r.suggested ? `<span class="${r.suggested.agrees ? 'dim' : 'amber'}">Jev suggests ${h(r.suggested.model)}, ${h(r.suggested.effort)} and a ${h(r.suggested.window)} window for its work${r.suggested.agrees ? ', as it runs' : ''}${r.suggested.next ? `; its next bead ${h(r.suggested.bead)} starts ${h(r.suggested.start)}` : ''}. See Background jobs for what the autopilot applies.</span>
` : ''}
    ${controlsFor(r, s)}${how}`;
}

// Each ask is answered in its row (the owner, 2026-10-16); a grill round opens in its own tab for the ticked ones.
function askDetail(q) {
  if (!q.is_ask) return `<span class="text">${h(q.text)}</span><span>${h(q.meta)}</span>`;
  const options = q.options.map((o, i) => {
    const letter = String.fromCharCode(65 + i);
    return `<button class="btn${q.rec === letter ? ' primary' : ''}" data-answer="${h(q.id)}" data-option="${letter}">${letter}. ${h(o)}</button>`;
  }).join('');
  return `<span class="text">${h(q.text)}</span><span>${h(q.meta)}</span>
    ${q.rec ? `<span>Recommended: ${h(q.rec)}. ${h(q.why)}</span>` : ''}
    <div class="actions">${options}</div>
    <div class="actions"><input class="own" id="own-${h(q.id)}" data-draft="${h(q.id)}" value="${h(ui.drafts[q.id] || '')}" aria-label="Your own answer to ${h(q.id)}" placeholder="Or your own words" maxlength="2000">
      <button class="btn" data-answer="${h(q.id)}" data-own="1">Save my words</button></div>
    ${ui.answerError[q.id] ? `<span class="amber" role="status">${h(ui.answerError[q.id])}</span>` : ''}`;
}

function renderAsks(a, s) {
  if (a.absent) { box('asks', 'Your tasks', s.needs.length, '', actionsBody(s)); return; }
  if (!a.available) { box('asks', 'Your tasks', s.needs.length, `<span class="amber">questions unavailable: ${h(a.error)}</span>`, actionsBody(s)); return; }
  const grill = a.grill || {};
  const open = new Set(a.rows.filter((q) => q.is_ask).map((q) => q.id));
  [...ui.picked].forEach((id) => { if (!open.has(id)) ui.picked.delete(id); });  // an answered ask leaves the selection
  const line = (q) => {
    const mark = q.is_ask ? (q.kind === 'blocker' ? '<span class="coral">●</span>' : '<span class="amber">●</span>') : '<span class="dim">○</span>';
    const pick = q.is_ask ? `<input type="checkbox" data-pick="${h(q.id)}" aria-label="Put ${h(q.id)} in the grill round"${ui.picked.has(q.id) ? ' checked' : ''}>` : '<span></span>';
    return row('ask:' + q.id, 'ask-row', `${pick}${mark}${q.is_ask ? `<span class="mono dim clip">${h(q.id)}</span>` : beadLink(q.id)}<span class="clip">${h(q.text)}</span><span class="sub" style="font-size: 13px">${h(q.kind)}</span>`,
      askDetail(q));
  };
  const questions = a.rows.filter((q) => q.is_ask), tickets = a.rows.filter((q) => !q.is_ask);
  const rows = `${actionsBody(s)}<div class="group">Questions · ${questions.length}</div>${questions.map(line).join('') || '<div class="footer">No question waits on you.</div>'}
    ${tickets.length ? `<div class="group">Tickets · ${tickets.length} · beads on you, not questions</div>${tickets.map(line).join('')}` : ''}`;
  const n = ui.picked.size;
  const error = ui.grillError || grill.error;
  const answers = (a.log || []).map((x) => logRow(x.t, `<span class="mono dim">${h(x.id)}</span> ${h(x.answer)} <span class="dim">· ${h(x.text)}</span>`));
  const lit = a.blockers || s.needs.some((n) => n.level === 'warning') ? 'warning' : s.needs.length ? 'caution' : '';
  box('asks', 'Your tasks', s.needs.length + a.rows.length, h(`${s.needs.length} action${s.needs.length === 1 ? '' : 's'}, ${a.summary}`),
    `${rows}<div class="footer" style="display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center">
      <button class="btn" id="start-grill"${!n || ui.grillBusy ? ' disabled' : ''}>${h(ui.grillBusy ? 'Opening the round...' : n ? `Open a grill round for ${n} ticked` : 'Tick asks for a grill round')}</button>
      ${grill.url ? `<a class="link" href="${h(grill.url)}" target="_blank" rel="noopener">Round open in its tab</a>` : ''}
      <span>Open a question to answer it; answers and actions wait in the bar at the top until you confirm, then go out together (ask_owner.py answer, in your words). A ticket is a bead on you, not a question.</span></div>
     ${error ? `<div class="footer amber">${h(error)}</div>` : ''}<div class="footer">${h(a.source)}</div>
     <div aria-live="polite">${logLine('asks', answers, 'No answer saved today.')}</div>`, lit);
}

async function startGrill() {
  // The tab opens on the click itself, so the browser does not block it as a popup.
  const tab = window.open('about:blank', '_blank');
  ui.grillBusy = true; ui.grillError = ''; render();
  try {
    const response = await fetch('/api/grill', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: [...ui.picked] }) });
    const body = await response.json();
    if (body.ok && tab) tab.location = body.url; else { ui.grillError = body.error || 'The round did not open.'; if (tab) tab.close(); }
  } catch (e) { ui.grillError = 'The cockpit server did not answer.'; if (tab) tab.close(); }
  ui.grillBusy = false;
  await poll();
}

function quota(label, pct, mark, over, resets) {
  return `<span class="quota"><span class="dim">${label}</span>${bar(pct == null ? null : pct, 100, mark, over, true)}<span class="num">${pct == null ? '?' : Math.round(pct) + '%'}</span>
    <span class="mono dim clip" style="font-size: 12px">${h(resets)}</span></span>`;
}

function renderAccounts(s) {
  const accounts = s.accounts.map((a) => row('account:' + a.number, 'account-row',
    `<span style="font-weight: 600">Acct <span class="mono">${h(a.number)}</span></span>${quota('5h', a.five_hour, a.mark, a.over_mark, a.five_hour_resets)}${quota('7d', a.seven_day, null, false, a.seven_day_resets)}
     <span class="clip ${a.status && a.status !== 'ok' ? 'amber' : 'dim'}" style="font-size: 13px">${h(a.status && a.status !== 'ok' ? a.status : a.sessions)}</span>`,
    pairs([['Sessions', a.sessions], ['5h resets', a.five_hour_resets], ['7d resets', a.seven_day_resets], ['Status', a.status],
      ['Value age', a.age ? a.age + (a.status && a.status !== 'ok' ? ', the last good one' : '') : '']]))).join('');
  const none = s.accounts_error ? `<div class="footer amber">Unavailable: ${h(s.accounts_error)}</div>` : s.accounts.length ? '' : '<div class="footer">cswap lists no account.</div>';
  const limited = s.accounts.filter((a) => (a.status && a.status !== 'ok') || a.over_mark).length;
  box('accounts', 'Accounts', s.accounts.length, limited ? `<span class="amber">${limited} limited</span>` : '',
    `${accounts}${none}<div class="footer">Measured by cswap list --json; each account's value age is in its detail. ${readText(s.read_at)} The balancer's choices are under Background jobs.</div>`, limited ? 'caution' : '');
}
