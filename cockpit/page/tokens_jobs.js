// The Tokens section and the Background jobs section (the owner, 2026-10-16). Formatting only.
'use strict';

function amount(tokens) { return tokens == null ? '' : tokens < 1e6 ? k(tokens) : millions(tokens); }

// Tokens per day over 7 days, today last: whether compaction and the autopilot bring the team's spend down.
function historyRow(days) {
  if (!days.length) return '';
  // Without cache first (the owner, 56fba6); with cache is the detail in the tip.
  const top = Math.max(1, ...days.map((d) => d.no_cache));
  // Hover or focus a bar for its day and spend (the owner, 2026-10-16: "pasar el mouse ... cuanto se gasto cada dia").
  const bars = days.map((d, i) => `<span class="day${i === days.length - 1 ? ' recent' : ''}" tabindex="0" style="height: ${Math.max(6, d.no_cache / top * 100)}%"
    data-tip="${h(d.day)}${i === days.length - 1 ? ' so far' : ''}: ${amount(d.no_cache)} without cache, ${amount(d.tokens)} with" aria-label="${h(d.day)}: ${millions(d.no_cache)} tokens without cache, ${millions(d.tokens)} with"></span>`).join('');
  return `<div class="row line-row history"><span></span><span class="history-line"><span class="dim">Per day</span><span class="pace" role="group" aria-label="Tokens per day without cache">${bars}</span>
    <span class="dim">last 3 days</span><span class="mono sub">${days.slice(-3).map((d) => `${amount(d.no_cache)}/${millions(d.tokens)}`).join(' · ')}</span><span class="dim">without/with cache</span></span></div>`;
}

function renderJobs(s) {
  const j = s.jobs;
  if (!j) return;
  const rows = j.jobs.map((x) => row('job:' + x.id, 'job-row', `<span style="font-weight: 600">${h(x.name)}</span>
      <span class="mono dim clip" style="font-size: 12px" title="Last ran">${h(x.last)}</span>
      <span class="clip${x.level ? ' amber' : ' sub'}" style="font-size: 13px">${h(x.did)}</span><span class="clip dim" style="font-size: 12px" title="Runs next">${h(x.next || '')}</span>`,
    pairs([['Does', x.what]].concat(x.detail, [['Did', x.did], ['Runs next', x.next || '']])))).join('');
  const head = '<div class="row head job-row"><span>Job</span><span>Last</span><span>Did</span><span>Next</span></div>';
  const log = j.log_error ? [logRow('', `<span class="amber">Log unreadable: ${h(j.log_error)}</span>`)]
    : j.log.map((r) => logRow(r.t, `${EFFECT_MARK[r.state] || ''} ${h(r.text)}${wrongButton(r)}`));
  const lit = j.jobs.some((x) => x.level);
  box('jobs', 'Background jobs', j.jobs.length, lit ? '<span class="amber">one needs a look</span>' : 'run by themselves',
    `${head}${rows}${hooksGroup(s)}<div class="footer">Nothing to set: each runs by itself. From actions.jsonl, the balancer's decision log, the collector, the price page and the settings files' hooks.</div>
     ${logLine('jobs', log, 'Nothing from the autopilot today and no balancer choice in 24 h.')}`, lit ? 'caution' : '');
}

// The owner's wrong click on an autopilot decision (design pg-o1sq Q5): undone at the next idle moment when it can be,
// always kept as an example for Jev.
function wrongButton(r) {
  if (!r.id) return '';
  if (r.wrong) return ` <span class="dim">${h(r.wrong)}</span>`;
  const error = ui.wrongError[r.id];
  return ` <button class="link" data-wrong="${h(r.id)}">Wrong</button>${error ? ` <span class="amber">${h(error)}</span>` : ''}`;
}

async function markWrong(id) {
  try {
    const body = await (await fetch('/api/wrong', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) })).json();
    if (body.ok) delete ui.wrongError[id]; else ui.wrongError[id] = body.error;
  } catch (e) { ui.wrongError[id] = 'The cockpit server did not answer; nothing was marked.'; }
  ui.lastText = ''; render(); setTimeout(poll, 500);
}

// The team's Claude Code hooks, shown and never changed (the owner, 2026-10-16: "only view and logs").
function hooksGroup(s) {
  if (s.hooks_error) return `<div class="group">Hooks</div><div class="footer amber">Settings not read: ${h(s.hooks_error)}</div>`;
  if (!s.hooks.length) return '<div class="group">Hooks · 0</div><div class="footer">No hook in the settings files the cockpit reads.</div>';
  return `<div class="group">Hooks · ${s.hooks.length}</div>` + s.hooks.map((x, i) => row('hook:' + i, 'job-row',
    `<span class="clip" style="font-weight: 600">${h(x.script)}</span><span></span>
     <span class="clip sub" style="font-size: 13px">${h(x.did)}</span><span class="clip dim" style="font-size: 12px">on ${h(x.events.join(', '))}</span>`,
    pairs([['Runs on', x.events.join(', ')], ['Command', x.commands.join(' ; ')], ['From', x.sources.join(', ')], ['Log', x.log || 'none known']]))).join('');
}
