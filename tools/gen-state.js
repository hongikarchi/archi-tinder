#!/usr/bin/env node
/*
 * tools/gen-state.js — generate project/state.js for the project dashboard.
 *
 * DASHBOARD-AUTOGEN-1. Replaces the reporter-inline hand-authoring of state.js:
 * the LLM no longer transcribes 400+ lines of JSON — it edits Task.md (the human
 * content) and runs this script, which derives the deterministic keys and carries
 * the hand-curated keys verbatim from the prior state.js.
 *
 * Per-key source:
 *   meta.{updatedAt,head,branch}      git / clock
 *   meta.name                         prior (preserved)
 *   done / now / next                 Task.md parse (id/title/date/prs mechanical;
 *                                     note carried by id from prior, else seeded
 *                                     from the entry's first body line)
 *   agents                            .claude/agents/<name>.md frontmatter
 *                                     (name/model/effort mechanical; role carried
 *                                     by name from prior, else first description
 *                                     sentence)
 *   prs                               gh pr list (falls back to prior on failure)
 *   fileTree                          git ls-files (+ untracked when --local)
 *                                     joined with project/file-roles.json
 *   systemFlow/recommendationFlow/
 *   agentFlow/milestones              carried verbatim from prior state.js
 *
 * Usage:
 *   node tools/gen-state.js            -> writes project/state.js (committed)
 *   node tools/gen-state.js --local    -> writes project/state.local.js (gitignored,
 *                                         includes untracked files; for `make dashboard`)
 *
 * Exit non-zero on self-check failure. Drift (files without a role / orphan role
 * entries) is reported to stderr but is not fatal.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const LOCAL = process.argv.includes('--local');

// ---------------------------------------------------------------------------
// shell helpers
// ---------------------------------------------------------------------------
function git(args, opts = {}) {
  return execFileSync('git', args, { encoding: 'utf8', ...opts }).trim();
}
function tryRun(cmd, args) {
  try {
    return execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch (e) {
    return null;
  }
}

const ROOT = git(['rev-parse', '--show-toplevel']);
const p = (...parts) => path.join(ROOT, ...parts);

// ---------------------------------------------------------------------------
// time
// ---------------------------------------------------------------------------
function kst(date) {
  // -> 'YYYY-MM-DD HH:mm KST'
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(date).reduce((acc, x) => (acc[x.type] = x.value, acc), {});
  let hour = parts.hour === '24' ? '00' : parts.hour;
  return `${parts.year}-${parts.month}-${parts.day} ${hour}:${parts.minute} KST`;
}

// ---------------------------------------------------------------------------
// prior state.js (eval — it assigns window.PROJECT_STATE)
// ---------------------------------------------------------------------------
function loadPrior() {
  const file = p('project', 'state.js');
  if (!fs.existsSync(file)) return {};
  const sandbox = { window: {} };
  // eslint-disable-next-line no-new-func
  new Function('window', fs.readFileSync(file, 'utf8'))(sandbox.window);
  return sandbox.window.PROJECT_STATE || {};
}

// ---------------------------------------------------------------------------
// Task.md parsing
// ---------------------------------------------------------------------------
function decodeEntities(s) {
  return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
}

// Slice a markdown doc into the body lines of a `## <name>` section (up to the
// next `## ` heading).
function sectionLines(lines, name) {
  const start = lines.findIndex((l) => l.trim() === `## ${name}`);
  if (start === -1) return [];
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i++) {
    if (/^## (?!#)/.test(lines[i])) { end = i; break; }
  }
  return lines.slice(start + 1, end);
}

// Collect `{ header, body[] }` blocks for a given heading depth (### or ####)
// within a slice of lines. `body` runs until the next heading of the same-or-
// shallower depth.
function blocks(lines, depth) {
  const marker = '#'.repeat(depth) + ' ';
  const out = [];
  let cur = null;
  for (const line of lines) {
    const isHead = line.startsWith(marker) && line[depth] === ' ';
    // A shallower/equal heading closes the current block.
    const isBoundary = /^#{1,6} /.test(line) && (line.match(/^#+/)[0].length <= depth);
    if (isHead) {
      cur = { header: line.slice(depth + 1).trim(), body: [] };
      out.push(cur);
    } else if (isBoundary) {
      cur = null; // deeper sibling heading not matching marker; stop accumulating
    } else if (cur) {
      cur.body.push(line);
    }
  }
  return out;
}

function firstBodyNote(body) {
  for (let raw of body) {
    const t = raw.trim();
    if (!t) continue;
    if (/^#{1,6} /.test(t)) break;
    // strip list / checkbox / bold markers, keep inline content
    let s = t
      .replace(/^[-*]\s+\[[ xX]\]\s*/, '')
      .replace(/^[-*]\s+/, '')
      .replace(/\*\*/g, '')
      .trim();
    s = decodeEntities(s);
    if (s.length > 280) s = s.slice(0, 277).trimEnd() + '…';
    return s;
  }
  return '';
}

// Parse a Done `### ` header into { id, title, completedAt, prs }.
function parseDoneHeader(header) {
  const h = decodeEntities(header);
  const m = h.match(/\s—\s(?:RESOLVED|SHIPPED)\b/);
  const head = m ? h.slice(0, m.index) : h;
  const tail = m ? h.slice(m.index) : '';
  const completedAt = (tail.match(/(\d{4}-\d{2}-\d{2})/) || [])[1] || '';
  // PR numbers only from the citation tail (avoids mid-title "(supersedes PR #N)")
  const prs = [...tail.matchAll(/#(\d+)/g)].map((x) => Number(x[1]));
  // id = first ' — ' segment if it looks like an id; else first token; else slug
  const segs = head.split(/\s—\s/);
  let id, title;
  const first = segs[0].trim();
  const looksId = (s) => /^#?[A-Za-z0-9][\w.\-]*$/.test(s) && /[0-9A-Z]/.test(s);
  if (segs.length > 1 && looksId(first)) {
    id = first;
    title = segs.slice(1).join(' — ').trim();
  } else if (looksId(first.split(/\s+/)[0])) {
    const sp = first.indexOf(' ');
    id = sp === -1 ? first : first.slice(0, sp);
    title = (sp === -1 ? '' : first.slice(sp + 1)) + (segs.length > 1 ? ' — ' + segs.slice(1).join(' — ') : '');
    title = title.trim();
  } else {
    title = head.trim();
    id = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'item';
  }
  return { id, title, completedAt, prs };
}

function parseTaskMd(text, prior) {
  const lines = text.split('\n');
  const priorDone = Object.fromEntries((prior.done || []).map((d) => [d.id, d]));
  const priorNext = Object.fromEntries(
    ['xhigh', 'high', 'medium', 'low'].flatMap((b) => ((prior.next || {})[b] || []).map((x) => [x.id, x]))
  );
  const priorNow = Object.fromEntries((prior.now || []).map((n) => [n.id, n]));

  // Done — top 8
  const done = blocks(sectionLines(lines, 'Done'), 3).slice(0, 8).map((b) => {
    const { id, title, completedAt, prs } = parseDoneHeader(b.header);
    const note = priorDone[id] ? priorDone[id].note : firstBodyNote(b.body);
    const out = { id, title, completedAt };
    if (prs.length) out.prs = prs;
    out.note = note;
    return out;
  });

  // Next — buckets
  const nextLines = sectionLines(lines, 'Next');
  const bucketMap = { 'X-HIGH': 'xhigh', HIGH: 'high', MEDIUM: 'medium', LOW: 'low' };
  const next = { xhigh: [], high: [], medium: [], low: [] };
  // map each ### bucket heading to its key (tolerant of trailing text like
  // "### HIGH (urgent)" — match the first token only), then group its #### items
  const buckets3 = blocks(nextLines, 3);
  for (const b of buckets3) {
    const label = b.header.trim().toUpperCase().split(/[\s(]/)[0];
    const key = bucketMap[label];
    if (!key) continue;
    for (const item of blocks(b.body, 4)) {
      const segs = decodeEntities(item.header).split(/\s—\s/);
      const id = segs[0].trim();
      const title = segs.slice(1).join(' — ').trim();
      const note = priorNext[id] ? priorNext[id].note : firstBodyNote(item.body);
      next[key].push({ id, title, note });
    }
  }

  // Now
  const now = blocks(sectionLines(lines, 'Now'), 3).map((b) => {
    const segs = decodeEntities(b.header).split(/\s—\s/);
    const id = segs[0].trim();
    const title = segs.slice(1).join(' — ').trim();
    const note = priorNow[id] ? priorNow[id].note : firstBodyNote(b.body);
    return { id, title, note };
  });

  return { done, now, next };
}

// ---------------------------------------------------------------------------
// agents
// ---------------------------------------------------------------------------
function parseFrontmatter(md) {
  const m = md.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return {};
  const fm = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (kv) fm[kv[1]] = kv[2].replace(/^["']|["']$/g, '').trim();
  }
  return fm;
}
function firstSentence(s) {
  if (!s) return '';
  const m = s.match(/^.*?[.。](\s|$)/);
  return (m ? m[0] : s).trim();
}
function buildAgents(prior) {
  const dir = p('.claude', 'agents');
  const priorByName = Object.fromEntries((prior.agents || []).map((a) => [a.name, a]));
  if (!fs.existsSync(dir)) return prior.agents || [];
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith('.md'))
    .map((f) => {
      const fm = parseFrontmatter(fs.readFileSync(path.join(dir, f), 'utf8'));
      const name = fm.name || f.replace(/\.md$/, '');
      const role = priorByName[name] ? priorByName[name].role : firstSentence(fm.description);
      return { name, role, model: fm.model || 'sonnet', effort: fm.effort || 'default' };
    })
    .sort((a, b) => a.name.localeCompare(b.name, 'en'));
}

// ---------------------------------------------------------------------------
// prs (gh; fall back to prior on any failure)
// ---------------------------------------------------------------------------
function buildPrs(prior) {
  const raw = tryRun('gh', [
    'pr', 'list', '--base', 'develop', '--state', 'merged', '--limit', '8',
    '--json', 'number,title,mergedAt,mergeCommit',
  ]);
  if (!raw) {
    process.stderr.write('[gen-state] gh unavailable/offline — keeping prior prs[]\n');
    return prior.prs || [];
  }
  let list;
  try { list = JSON.parse(raw); } catch { return prior.prs || []; }
  return list.map((pr) => ({
    number: pr.number,
    title: pr.title,
    mergedAt: pr.mergedAt,
    mergedAtKST: pr.mergedAt ? kst(new Date(pr.mergedAt)) : null,
    sha: pr.mergeCommit && pr.mergeCommit.oid ? pr.mergeCommit.oid.slice(0, 7) : null,
  }));
}

// ---------------------------------------------------------------------------
// fileTree
// ---------------------------------------------------------------------------
function buildFileTree() {
  const tracked = git(['ls-files']).split('\n').filter(Boolean);
  let paths = tracked;
  if (LOCAL) {
    const untracked = git(['ls-files', '--others', '--exclude-standard']).split('\n').filter(Boolean);
    paths = [...new Set([...tracked, ...untracked])];
  }
  paths.sort();

  let roles = {};
  const rolesFile = p('project', 'file-roles.json');
  if (fs.existsSync(rolesFile)) {
    try { roles = JSON.parse(fs.readFileSync(rolesFile, 'utf8')); } catch (e) {
      process.stderr.write(`[gen-state] file-roles.json parse error: ${e.message}\n`);
    }
  }

  const fileTree = paths.map((fp) => ({ path: fp, role: roles[fp] || '' }));

  // drift report
  const missing = paths.filter((fp) => !roles[fp]);
  const orphan = Object.keys(roles).filter((k) => !paths.includes(k));
  if (missing.length) {
    process.stderr.write(`[gen-state] ${missing.length} file(s) without a role description:\n`);
    missing.slice(0, 20).forEach((m) => process.stderr.write(`  - ${m}\n`));
    if (missing.length > 20) process.stderr.write(`  … and ${missing.length - 20} more\n`);
  }
  if (orphan.length) {
    process.stderr.write(`[gen-state] ${orphan.length} role entr(y/ies) for deleted file(s):\n`);
    orphan.forEach((o) => process.stderr.write(`  - ${o}\n`));
  }
  return fileTree;
}

// ---------------------------------------------------------------------------
// serializer -> readable JS source
// ---------------------------------------------------------------------------
function serStr(s) {
  // Multi-line -> template literal (keeps mermaid pretty + hand-editable). Escape
  // backslash FIRST, then the two sequences that can break out of a template literal.
  if (s.includes('\n')) {
    return '`' + s.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$\{/g, '\\${') + '`';
  }
  return "'" + s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n') + "'";
}
function serKey(k) {
  return /^[A-Za-z_$][\w$]*$/.test(k) ? k : JSON.stringify(k);
}
function ser(v, ind) {
  const pad = '  '.repeat(ind);
  const pad1 = '  '.repeat(ind + 1);
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (typeof v === 'string') return serStr(v);
  if (Array.isArray(v)) {
    if (v.length === 0) return '[]';
    if (v.every((e) => typeof e === 'number')) return '[' + v.join(', ') + ']';
    const items = v.map((e) => pad1 + ser(e, ind + 1));
    return '[\n' + items.join(',\n') + ',\n' + pad + ']';
  }
  const keys = Object.keys(v);
  if (keys.length === 0) return '{}';
  const items = keys.map((k) => pad1 + serKey(k) + ': ' + ser(v[k], ind + 1));
  return '{\n' + items.join(',\n') + ',\n' + pad + '}';
}

const HEADER = `/*
 * project/state.js — ArchiTinder Make Web project state.
 *
 * AUTO-GENERATED by tools/gen-state.js (DASHBOARD-AUTOGEN-1, 2026-06-01+).
 * Do NOT hand-edit the auto sections — re-run \`node tools/gen-state.js\` instead.
 * Hand-curated keys (systemFlow / recommendationFlow / agentFlow / milestones, and
 * each done/next note + agent role) are carried verbatim from the prior file; edit
 * those in the prior state.js (or Task.md for new note seeds) and re-run.
 *
 * Per-key source:
 *   meta/done/now/next  <- Task.md (+ git for meta)            [auto]
 *   agents              <- .claude/agents/<name>.md frontmatter [auto]
 *   prs                 <- gh pr list (prior on offline)        [auto]
 *   fileTree            <- git ls-files U project/file-roles.json [auto]
 *   systemFlow/recommendationFlow/agentFlow/milestones          [hand-curated, carried]
 *
 * Loaded via <script> by project/dashboard.html (file:// double-click — no fetch,
 * no server at LOAD time; generation is the build step). dashboard.html also loads
 * project/state.local.js (gitignored) after this file when present, so
 * \`make dashboard\` shows a fresher local view without dirtying this committed file.
 *
 * Time convention: human-facing timestamps are \`YYYY-MM-DD HH:mm KST\`; PRs also
 * carry raw ISO 8601 UTC (mergedAt).
 */
`;

// ---------------------------------------------------------------------------
// build
// ---------------------------------------------------------------------------
function build() {
  const prior = loadPrior();
  const taskText = fs.readFileSync(p('Task.md'), 'utf8');
  const { done, now, next } = parseTaskMd(taskText, prior);

  const head =
    tryRun('git', ['rev-parse', '--short', 'origin/develop']) ||
    git(['rev-parse', '--short', 'HEAD']);
  const branch = git(['rev-parse', '--abbrev-ref', 'HEAD']);

  const state = {
    meta: {
      name: (prior.meta && prior.meta.name) || 'ArchiTinder — Make Web',
      updatedAt: kst(new Date()),
      head,
      branch,
    },
    done,
    now,
    next,
    prs: buildPrs(prior),
    agents: buildAgents(prior),
    fileTree: buildFileTree(),
    systemFlow: prior.systemFlow || { title: '', mermaid: '' },
    recommendationFlow: prior.recommendationFlow || { title: '', mermaid: '' },
    agentFlow: prior.agentFlow || { title: '', mermaid: '' },
    milestones: prior.milestones || [],
  };

  const source = HEADER + 'window.PROJECT_STATE = ' + ser(state, 0) + ';\n';
  return { source, prior };
}

function selfCheck(source) {
  const sandbox = { window: {} };
  // eslint-disable-next-line no-new-func
  new Function('window', source)(sandbox.window);
  const s = sandbox.window.PROJECT_STATE;
  const required = ['meta', 'done', 'now', 'next', 'prs', 'agents', 'fileTree',
    'systemFlow', 'recommendationFlow', 'agentFlow', 'milestones'];
  for (const k of required) {
    if (!(k in s)) throw new Error(`self-check: missing key '${k}'`);
  }
  if (!Array.isArray(s.done) || !Array.isArray(s.prs) || !Array.isArray(s.fileTree)) {
    throw new Error('self-check: done/prs/fileTree must be arrays');
  }
  return s;
}

// Guard the serializer: carried-verbatim keys must survive the round-trip intact.
// Catches silent value corruption (e.g. an unescaped backslash in a hand-edited
// mermaid block) that selfCheck's key/shape assertions alone would miss.
function verifyCarry(state, prior) {
  for (const k of ['systemFlow', 'recommendationFlow', 'agentFlow']) {
    if (prior[k] && state[k] && state[k].mermaid !== prior[k].mermaid) {
      throw new Error(`carry-forward drift: ${k}.mermaid does not match prior state.js`);
    }
  }
  if (prior.milestones && JSON.stringify(state.milestones) !== JSON.stringify(prior.milestones)) {
    throw new Error('carry-forward drift: milestones does not match prior state.js');
  }
}

function main() {
  const { source, prior } = build();
  const s = selfCheck(source);   // throws (non-zero exit) on malformed output
  verifyCarry(s, prior);         // throws if a carried key was corrupted in serialization
  const outName = LOCAL ? 'state.local.js' : 'state.js';
  fs.writeFileSync(p('project', outName), source);
  process.stderr.write(
    `[gen-state] wrote project/${outName} — done:${s.done.length} now:${s.now.length} ` +
    `prs:${s.prs.length} agents:${s.agents.length} files:${s.fileTree.length}` +
    (LOCAL ? ' (local, incl. untracked)' : '') + '\n'
  );
}

main();
