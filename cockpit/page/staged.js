// Answers and actions wait here until one confirm sends them all (the owner, 2026-10-17, panel d00915: "(the owner's words)"). Copy, jump, Pause and the grill round stay instant.
'use strict';

ui.staged = [];  // {key, label, item, session, needId, askId}; one per ask, per need, per session control

function stage(entry) {
  const at = ui.staged.findIndex((s) => s.key === entry.key);
  // Clicking what is already staged takes it back; a different choice for the same thing replaces it.
  if (at >= 0 && ui.staged[at].label === entry.label) ui.staged.splice(at, 1);
  else if (at >= 0) ui.staged[at] = entry;
  else ui.staged.push(entry);
  render();
}

function stageAnswer(id, option, own) {
  const text = own ? (($('own-' + id) || {}).value || '').trim() : '';
  if (own && !text) { ui.answerError[id] = 'Type your words first.'; render(); return; }
  ui.answerError[id] = '';
  stage({ key: 'answer:' + id, label: `Answer ${id}: ${own ? `"${text}"` : option}`, askId: id,
          item: { type: 'answer', id, option: own ? '' : option, text } });
}

function stageControl(kind, session, level, needId) {
  ui.controlError[session] = '';
  const label = needId ? `${ui.snapshot.needs.find((n) => n.id === needId).action_label} (${session})` : `${kind}${level ? ' ' + level : ''} ${session}`;
  stage({ key: needId ? 'need:' + needId : `control:${session}:${kind}`, label, session, needId,
          item: { type: 'action', kind, session: kind === 'need' ? needId : session, level } });
}

function stagedKey(button) {
  if (button.dataset.answer) return ['answer:' + button.dataset.answer, button.dataset.own ? '' : button.dataset.option];
  if (button.dataset.need) return ['need:' + button.dataset.need, ''];
  if (button.dataset.control) return [`control:${button.dataset.session}:${button.dataset.control}`, button.dataset.level || ''];
  return ['', ''];
}

function renderStaged() {
  const bar = $('staged');
  bar.hidden = ui.staged.length === 0 && !ui.stagedError;
  bar.innerHTML = `<span class="staged-count">${ui.staged.length} staged</span>
    <span class="clip">${h(ui.staged.map((s) => s.label).join(' · '))}</span>
    <button class="btn primary" id="send-staged"${ui.staged.length && !ui.sending ? '' : ' disabled'}>${ui.sending ? 'Sending...' : `Confirm and send ${ui.staged.length}`}</button>
    <button class="btn" id="discard-staged"${ui.staged.length && !ui.sending ? '' : ' disabled'}>Discard</button>
    ${ui.stagedError ? `<span class="amber" role="status">${h(ui.stagedError)}</span>` : ''}`;
  document.querySelectorAll('[data-answer], [data-need], [data-control]').forEach((button) => {
    const [key, level] = stagedKey(button);
    const entry = ui.staged.find((s) => s.key === key);
    button.classList.toggle('staged', Boolean(entry && (!level || entry.item.option === level || entry.item.level === level)));
  });
}

async function sendStaged() {
  const sending = ui.staged.slice();
  ui.sending = true; ui.stagedError = ''; render();
  try {
    const response = await fetch('/api/batch', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: sending.map((s) => s.item) }) });
    const body = await response.json();
    const results = body.results || [];
    // What went through leaves the bar; what failed stays staged with its reason in its row.
    ui.staged = sending.filter((s, i) => !(results[i] && results[i].ok));
    sending.forEach((s, i) => {
      const result = results[i];
      if (!result) return;
      if (s.askId) { if (result.ok) delete ui.drafts[s.askId]; else ui.answerError[s.askId] = result.error; }
      else if (result.ok) { ui.lastActed = result.id; if (s.needId) ui.sentAt[s.needId] = result.id; ui.expanded.add('session:' + s.session); }
      else ui.controlError[s.session] = result.error;
    });
    ui.stagedError = body.error || '';
  } catch (e) { ui.stagedError = 'The cockpit server did not answer; nothing was confirmed sent.'; }
  ui.sending = false; ui.lastText = ''; render(); setTimeout(poll, 800);
}
