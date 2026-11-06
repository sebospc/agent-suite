// Movable sections (the owner, 2026-10-16: "(the owner's words)"; the milestone first). Drag a section by its
// grip, or focus the grip and use the arrow keys: up and down within a column, left and right across. Kept per browser.
'use strict';

const DEFAULT_LAYOUT = { left: ['milestone', 'asks'], right: ['health', 'sessions', 'accounts', 'jobs'] };
const COLUMNS = ['left', 'right'];
let dragged = '';

function savedLayout() {
  try {
    const saved = JSON.parse(remembered('layout') || 'null');
    const all = [...DEFAULT_LAYOUT.left, ...DEFAULT_LAYOUT.right].sort().join();
    if (saved && [...saved.left, ...saved.right].sort().join() === all) return saved;
  } catch (e) { /* an old or broken value falls back to the default */ }
  return { left: [...DEFAULT_LAYOUT.left], right: [...DEFAULT_LAYOUT.right] };
}

const layout = savedLayout();

// Moving a section moves its element, so its content and state stay; moving the asks section reloads an open grill
// round's frame, whose answers are already saved.
function applyLayout() {
  COLUMNS.forEach((column) => layout[column].forEach((name) => $('col-' + column).appendChild($('box-' + name))));
  remember('layout', JSON.stringify(layout));
}

function place(name, column, index) {
  COLUMNS.forEach((c) => { layout[c] = layout[c].filter((n) => n !== name); });
  layout[column].splice(Math.max(0, Math.min(index, layout[column].length)), 0, name);
  applyLayout();
}

function where(name) {
  const column = COLUMNS.find((c) => layout[c].includes(name));
  return { column, index: layout[column].indexOf(name) };
}

function grip(name, title) {
  return `<button class="grip" data-grip="${name}" aria-label="Move ${h(title)}: drag it, or use the arrow keys" title="Drag to move">
    <svg width="10" height="14" viewBox="0 0 10 14" fill="currentColor" aria-hidden="true"><circle cx="2.5" cy="2.5" r="1.3"/><circle cx="7.5" cy="2.5" r="1.3"/><circle cx="2.5" cy="7" r="1.3"/><circle cx="7.5" cy="7" r="1.3"/><circle cx="2.5" cy="11.5" r="1.3"/><circle cx="7.5" cy="11.5" r="1.3"/></svg></button>`;
}

function dropIndex(column, y) {
  const boxes = layout[column].filter((n) => n !== dragged).map((n) => $('box-' + n));
  const after = boxes.findIndex((b) => y < b.getBoundingClientRect().top + b.getBoundingClientRect().height / 2);
  return after === -1 ? boxes.length : after;
}

document.addEventListener('pointerdown', (event) => {
  const handle = event.target.closest('[data-grip]');
  if (handle) $('box-' + handle.dataset.grip).draggable = true;  // only the grip starts a drag, so text stays selectable
});

document.addEventListener('dragstart', (event) => {
  const section = event.target.closest && event.target.closest('.box');
  if (!section) return;
  dragged = section.id.replace('box-', '');
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', dragged);
  section.classList.add('dragging');
});

COLUMNS.forEach((column) => {
  const element = () => $('col-' + column);
  document.addEventListener('DOMContentLoaded', () => {
    element().addEventListener('dragover', (event) => { if (dragged) { event.preventDefault(); element().classList.add('drop'); } });
    element().addEventListener('dragleave', (event) => { if (!element().contains(event.relatedTarget)) element().classList.remove('drop'); });
    element().addEventListener('drop', (event) => {
      event.preventDefault();
      element().classList.remove('drop');
      if (dragged) place(dragged, column, dropIndex(column, event.clientY));
    });
  });
});

document.addEventListener('dragend', () => {
  if (!dragged) return;
  $('box-' + dragged).classList.remove('dragging');
  $('box-' + dragged).draggable = false;
  COLUMNS.forEach((c) => $('col-' + c).classList.remove('drop'));
  dragged = '';
});

document.addEventListener('keydown', (event) => {
  const handle = event.target.closest && event.target.closest('[data-grip]');
  if (!handle || !['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
  event.preventDefault();
  const name = handle.dataset.grip, at = where(name);
  if (event.key === 'ArrowUp') place(name, at.column, at.index - 1);
  if (event.key === 'ArrowDown') place(name, at.column, at.index + 1);
  if (event.key === 'ArrowLeft') place(name, 'left', at.index);
  if (event.key === 'ArrowRight') place(name, 'right', at.index);
  document.querySelector(`[data-grip="${name}"]`).focus();
});

document.addEventListener('DOMContentLoaded', applyLayout);

document.addEventListener('pointerup', () => {
  if (!dragged) document.querySelectorAll('.box[draggable="true"]').forEach((b) => { b.draggable = false; });
});
