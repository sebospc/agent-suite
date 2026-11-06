# Asks through grill-with-ui

The owner: "(the owner's words)".

grill-with-ui is the team's skill (`reference/grill-with-ui/`, also in the project repo
`.claude/skills/grill-with-ui/`; based on plannotator's interactive grill UI). It serves one local
page per grill session; questions show their recommendation, lettered options, a discussion thread
each, and a Send button.

**Changed 2026-10-16 (the owner: "no es buena idea embeeber grill me en el cokcpit"):** the round is no longer
embedded. Each ask is answered in its row of Your asks (an option, or the owner's own words, saved at once with
`ask_owner.py answer`). The owner ticks the asks they want in a round, blocking or not, and the round opens in its own
tab. A comment in a question's thread is typed into the pane of the session that asked, through the logged control
path, and the thread says so. Beads without an ask stay listed until brain writes their question. The sections below
describe the first design; "It can be embedded" and step 3's embed no longer apply.

## It can be embedded

`server.mjs serve --session <dir>` listens on `127.0.0.1:<port>` and writes the url to
`<dir>/server.json`. It sends no `X-Frame-Options` or CSP frame headers, so the cockpit page can show
it in an `<iframe src="http://127.0.0.1:<port>/">`. POST `/send` checks the Origin against its own
origin; inside the iframe the page's origin is the grill server's, so sends work. No change to the
skill is needed.

## The flow

1. The cockpit gathers the owner's pending items: open asks in `panel.json`, plus open beads that
   wait on the owner with no ask (assignee `owner`, or a done criterion the owner must approve, or a
   blocked done criterion). For a bead without an ask, it first creates one with `ask_owner.py add`
   so the panel stays the record (owner rule 10 in the project repo CLAUDE.md).
2. It writes a grill session: one question per ask (`title` = ask text, `body` = its reply/context
   and coverage, `options` = the ask's options lettered, `rec` = the ask's recommendation and why).
   Use `node server.mjs patch --session <dir>`; never write state.json by hand.
3. It starts `server.mjs serve` for that session and embeds the url.
4. The cockpit is the agent side of the grill, deterministically:
   - an `answer` action → `ask_owner.py answer <id> "<the owner's words: option text, or their typed answer>"`,
     then patch the question to `answered`;
   - a thread comment → forward it, word for word, as one message to the session that asked
     (`by` in the ask), through herdr; when that session replies (it patches the thread with
     `server.mjs patch` or answers via a file the cockpit watches), the reply shows in the thread.
5. The asks list shows each ask leaving `panel.json` asks for `answered`, which is the proof.

## Recommendation on every ask (done Oct 16)

`ask_owner.py add` now requires `--rec <option letter>` and `--why "<one paragraph>"` and stores
`rec: {option, why}` on the ask, the same shape a grill question uses. Asks created before that have
no `rec`: show "no recommendation given" for them rather than inventing one.

## In the mockup

`design/mockup/Main.dc.html`, section "Your asks": the pending list, "Answer these 3 in a grill
round", and a simulated embedded grill with three real items from the Oct 15 board (ask 696253, and
beads pg-a18q.30 and pg-a18q.51 that had no ask).
