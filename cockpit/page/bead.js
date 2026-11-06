// Opens any bead id on the page as a card: what the board says about it, its links and its comments.
'use strict';

const STATUS_MARK = { closed: '●', in_progress: '◐', blocked: '⊘', open: '○' };

function beadLink(id, label) {
  return id ? `<button class="bead-link mono" data-bead="${h(id)}" title="Open ${h(id)}">${h(label || id)}</button>` : '';
}

// "pg-a18q.53 +2" in a sessions row: the first word is the bead.
function beadIn(text) {
  const match = /^(\S+-[\w.]+)/.exec(text || '');
  return match ? match[1] : '';
}

function linked(title, list) {
  if (!list.length) return '';
  return `<div class="bead-part"><h3>${h(title)}</h3><ul>${list.map((b) => `<li class="bead-line">
    <span class="${b.status === 'blocked' ? 'amber' : 'dim'}" title="${h(b.status)}">${STATUS_MARK[b.status] || '·'}</span>${beadLink(b.id)}<span class="clip">${h(b.title)}</span></li>`).join('')}</ul></div>`;
}

function text(title, body) {
  return body ? `<div class="bead-part"><h3>${h(title)}</h3><p class="prose">${h(body)}</p></div>` : '';
}

async function openBead(id) {
  const dialog = $('bead-dialog');
  dialog.innerHTML = `<div class="bead-card"><p class="dim">Opening ${h(id)}...</p></div>`;
  if (!dialog.open) dialog.showModal();
  let card;
  try {
    const response = await fetch('/api/bead?id=' + encodeURIComponent(id), { cache: 'no-store' });
    card = await response.json();
    if (!response.ok) throw new Error(card.error);
  } catch (e) {
    dialog.innerHTML = `<div class="bead-card"><p class="amber">${h(e.message || 'The cockpit server did not answer.')}</p><button class="btn" id="close-bead">Close</button></div>`;
    return;
  }
  const facts = [card.status.replace('_', ' '), card.priority, card.type, card.milestone, card.assignee, card.updated && 'updated ' + card.updated]
    .filter(Boolean).map((f) => `<span>${h(f)}</span>`).join('<span class="dim">·</span>');
  dialog.innerHTML = `<div class="bead-card">
    <div class="bead-top"><span class="mono dim">${h(card.id)}</span><button class="btn" id="close-bead" aria-label="Close">Close</button></div>
    <h2 id="bead-title">${h(card.title)}</h2>
    <div class="facts">${facts}</div>
    ${card.labels.length ? `<div class="facts dim">${card.labels.map((l) => `<span class="mono">${h(l)}</span>`).join('')}</div>` : ''}
    ${text('Description', card.description)}${text('Notes', card.notes)}${text('Why it closed', card.close_reason)}
    ${linked('Parent', card.parent)}${linked('Blocked by', card.blocked_by)}${linked('Related', card.related)}${linked('Children', card.children)}
    ${card.comments.length ? `<div class="bead-part"><h3>Comments · ${card.comments.length}</h3>${card.comments.map((c) => `<div class="comment">
      <span class="dim">${h(c.author)} · ${h(c.at)}</span><p class="prose">${h(c.text)}</p></div>`).join('')}</div>` : ''}
    <p class="dim">From the last board read (bd export). Read only: change it with bd in a session.</p></div>`;
}

document.addEventListener('DOMContentLoaded', () => {
  const dialog = $('bead-dialog');
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });  // a click on the backdrop
});
