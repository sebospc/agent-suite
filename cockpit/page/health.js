// Team health (the owner, 2026-10-16): the team's resources, one row each, every detail one click away. It only
// informs: what needs the owner is in Your tasks. Each dropdown is a table (ask 834b86: "solo datos, dinamicos,
// especialmente tabla"); a number opens its history from metrics.jsonl.
'use strict';

const LEVEL_TEXT = { act: 'ACT', watch: 'WATCH', ok: 'OK', unknown: 'UNKNOWN' };
const HISTORY_HOURS = 24;

function cellText(value, unit) {
  if (value == null || value === '') return '';
  if (unit === 'tokens') return value < 1000 ? String(value) : amount(value);  // a few hundred input tokens is not 0k
  if (unit === 'usd') return '$' + Number(value).toFixed(2);
  if (unit === 'pct') return value + '%';
  if (unit === 'gb') return Number(value).toFixed(1) + ' GB';
  if (unit === 'flag') return value ? 'yes' : 'no';
  return String(value);
}

function sortedRows(id, rows) {
  const by = ui.sort && ui.sort[id];
  if (!by) return rows;
  const sign = by.dir === 'asc' ? 1 : -1;
  // Empty cells sink, whichever way it sorts: an unread number is not a small one.
  return rows.slice().sort((a, b) => (a[by.key] == null) - (b[by.key] == null)
    || (a[by.key] < b[by.key] ? -sign : a[by.key] > b[by.key] ? sign : 0));
}

function histButton(id, rowId, key, label, text) {
  const open = ui.hist && ui.hist.area === id && ui.hist.row === rowId && ui.hist.key === key;
  return `<button class="cell${open ? ' on' : ''}" data-hist="${h(JSON.stringify([id, rowId, key, label]))}" aria-pressed="${open}" title="History, ${HISTORY_HOURS} h">${h(text)}</button>`;
}

function dataTable(id, t) {
  const by = (ui.sort && ui.sort[id]) || {};
  const head = t.columns.map((c) => `<th class="${c.unit === 'text' ? '' : 'num'}"><button class="sort" data-sort="${h(id + '|' + c.key)}"
    aria-sort="${by.key === c.key ? (by.dir === 'asc' ? 'ascending' : 'descending') : 'none'}">${h(c.label)}</button></th>`).join('');
  const body = sortedRows(id, t.rows).map((r) => `<tr>${t.columns.map((c) => {
    const text = cellText(r[c.key], c.unit);
    if (c.unit === 'text' || c.unit === 'flag' || text === '') return `<td class="${c.unit === 'text' ? 'clip' : 'num'}">${h(text)}</td>`;
    return `<td class="num">${histButton(id, String(r.id), c.key, `${r.id} · ${c.label}`, text)}</td>`;
  }).join('')}</tr>`).join('');
  const totals = t.totals.filter((x) => x.value != null).map((x) => `<span><span class="dim">${h(x.label)}</span> ${histButton(id, '_totals', x.key, `Total · ${x.label}`, cellText(x.value, x.unit))}</span>`).join('');
  return `<div class="caption dim">${h(t.caption)}</div>${totals ? `<div class="totals">${totals}</div>` : ''}
    ${t.rows.length ? `<div class="table-wrap"><table class="data"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>` : '<div class="caption dim">No rows.</div>'}
    ${historyLine(id)}`;
}

// One measure over time: a step line from metrics.jsonl, with its low, high and latest value.
function historyLine(id) {
  const q = ui.hist;
  if (!q || q.area !== id) return '';
  if (q.error) return `<div class="caption amber">${h(q.label)}: ${h(q.error)}</div>`;
  const points = (q.points || []).filter((p) => typeof p[1] === 'number');
  if (!points.length) return `<div class="caption dim">${h(q.label)}: ${q.points ? 'no value recorded in ' + HISTORY_HOURS + ' h yet' : 'reading'}</div>`;
  const unit = q.unit, values = points.map((p) => p[1]);
  // The axis starts at the first value in the window, so a new record does not draw as a dot at the right edge.
  const low = Math.min(...values), high = Math.max(...values), t0 = points[0][0], span = Math.max(1, ui.snapshot.read_at - t0);
  const x = (t) => ((t - t0) / span * 240).toFixed(1), y = (v) => (high === low ? 14 : 28 - (v - low) / (high - low) * 26).toFixed(1);
  const steps = points.map((p, i) => `${i ? `${x(p[0])},${y(points[i - 1][1])} ` : ''}${x(p[0])},${y(p[1])}`).join(' ') + ` 240,${y(values[values.length - 1])}`;
  return `<div class="spark-line"><span class="dim">${h(q.label)} · since ${new Date(t0 * 1000).toTimeString().slice(0, 5)}</span>
    <svg class="spark" viewBox="0 0 240 30" width="240" height="30" role="img" aria-label="${h(q.label)}: from ${h(cellText(values[0], unit))} to ${h(cellText(values[values.length - 1], unit))}"><polyline points="${steps}"/></svg>
    <span class="mono sub">low ${h(cellText(low, unit))} · high ${h(cellText(high, unit))} · now ${h(cellText(values[values.length - 1], unit))} · ${points.length} change${points.length === 1 ? '' : 's'}</span></div>`;
}

function sortBy(spec) {
  const [id, key] = spec.split('|');
  const by = (ui.sort = ui.sort || {})[id];
  ui.sort[id] = { key, dir: by && by.key === key && by.dir === 'desc' ? 'asc' : 'desc' };
  render();
}

async function showHistory(spec) {
  const [area, rowId, key, label] = JSON.parse(spec);
  if (ui.hist && ui.hist.area === area && ui.hist.row === rowId && ui.hist.key === key) { ui.hist = null; return render(); }
  const grid = ui.snapshot.health.flatMap((a) => [Object.assign({ id: a.id }, a.table || {})].concat(a.more || [])).find((t) => t.id === area) || {};
  const unit = ((grid.columns || []).concat(grid.totals || []).find((c) => c.key === key) || {}).unit;
  ui.hist = { area, row: rowId, key, label, unit };
  render();
  try {
    const query = new URLSearchParams({ area, row: rowId, key, hours: HISTORY_HOURS });
    const body = await (await fetch('/api/history?' + query, { cache: 'no-store' })).json();
    if (ui.hist && ui.hist.area === area && ui.hist.key === key && ui.hist.row === rowId) Object.assign(ui.hist, { points: body.points, start: body.start, error: body.ok ? '' : body.error });
  } catch (e) { if (ui.hist) ui.hist.error = 'the cockpit server is not answering'; }
  render();
}

function areaDetail(area, s) {
  if (!area.table) return `<span class="text">${h(area.why)}</span><span class="dim">from ${h(area.source)}</span>`;
  const days = area.id === 'tokens' ? historyRow(s.tokens.days) : '';
  const more = (area.more || []).filter((t) => t.rows.length).map((t) => dataTable(t.id, t)).join('');
  // A lit area says why in one line; the table holds the rest.
  const why = area.level === 'act' || area.level === 'watch' ? `<div class="caption clip ${area.level === 'act' ? 'coral' : 'amber'}">${h(area.why)}</div>` : '';
  return `<div class="nested">${why}${days}${dataTable(area.id, area.table)}${more}<div class="caption dim" title="${h(area.rule)}">From ${h(area.source)}. ${readText(s.read_at)}</div></div>`;
}

// What is abnormal but handled, and what is clear: information, so it lives here and not in Your tasks.
function statusLines(s) {
  const lines = [['Handled by itself', s.handled], ['Clear', s.clear]].filter(([, l]) => l.length)
    .map(([name, l]) => row('line:' + name, 'line-row', `<span></span><span class="clip"><span class="dim">${name}:</span> ${h(l.join(' · '))}</span>`,
      `<ul>${l.map((x) => `<li>${h(x)}</li>`).join('')}</ul>`)).join('');
  return lines;
}

function renderHealth(s) {
  const rows = s.health.map((area) => row('health:' + area.id, 'health-row',
    `<span class="clip" style="font-weight: 600">${h(area.label)}</span><span class="mono clip${area.level === 'act' ? ' coral' : area.level === 'watch' ? ' amber' : ''}">${h(area.value)}</span>
     <span class="word ${h(area.level)}">${LEVEL_TEXT[area.level] || ''}</span>`, areaDetail(area, s))).join('');
  const worst = s.health.some((a) => a.level === 'act') ? 'warning' : s.health.some((a) => a.level === 'watch') ? 'caution' : '';
  box('health', 'Team health', '', h(`${s.health.filter((a) => a.level === 'ok').length} of ${s.health.length} OK`),
    `${rows}${statusLines(s)}<div class="footer">Only information here; anything that needs you is in Your tasks. Click a number for its history. ${readText(s.read_at)}</div>`, worst);
}
