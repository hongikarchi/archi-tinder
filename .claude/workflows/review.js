export const meta = {
  name: 'review',
  description: 'Heavy multi-dimensional adversarial review of the current branch diff (vs develop). Fans out one reviewer per dimension (correctness/security/performance/simplicity, Sonnet), then Opus adversarially verifies EACH finding (confirm real, drop false positives) as soon as its dimension returns. Read-only — runs no git mutations. Returns confirmed findings grouped by dimension+severity.',
  phases: [
    { title: 'Review', detail: 'one reviewer per dimension over the diff (Sonnet)' },
    { title: 'Verify', detail: 'Opus adversarial-verify of each finding' },
  ],
}

// args may arrive as a JSON string across the background-task boundary (see feature.js).
let a = args || {}
if (typeof a === 'string') {
  try { a = JSON.parse(a) } catch (e) { a = {} }
}
const range = a.range || 'origin/develop...HEAD'
const pathHint = a.paths && a.paths.length ? `\nLimit attention to these paths: ${a.paths.join(', ')}.` : ''

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'file', 'problem', 'fix'],
        properties: {
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          file: { type: 'string' },
          line: { type: 'string' },
          problem: { type: 'string' },
          fix: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['isReal', 'severity', 'reason'],
  properties: {
    isReal: { type: 'boolean' },
    severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
    reason: { type: 'string' },
  },
}

// Each dimension routes through an agentType that has repo tools (Read/Grep/Bash)
// so it can fetch the diff itself — workflow scripts cannot run git.
const DIMENSIONS = [
  { key: 'correctness', agentType: 'code-review', lens: 'logic bugs, API contract correctness front<->back, error handling at boundaries, missed edge cases, broken integration.' },
  { key: 'security', agentType: 'security-manager', lens: 'SQL injection, auth/permission bypass, secret/token leakage, XSS, endpoint injection, exposed IDs, missing is_publishable gate on building queries.' },
  { key: 'performance', agentType: 'code-review', lens: 'N+1 queries, unbounded loops/result sets, missing DB indexes, sync work in async paths, payload bloat, redundant recomputation.' },
  { key: 'simplicity', agentType: 'code-review', lens: 'duplication, dead code, over-abstraction, reinventing an existing util/helper, needless complexity that obscures intent.' },
]

function reviewPrompt(d) {
  return `Review ONLY the changes in this branch through the ${d.key.toUpperCase()} lens.\n\nDiff range: ${range}. First run \`git fetch origin develop --quiet\`, then \`git diff ${range} --stat\` and \`git diff ${range}\`; read changed files for context as needed.${pathHint}\n\nLens — ${d.lens}\n\nReport concrete findings with file, line, the problem, and a specific fix. Do NOT report style nits that do not change behavior. If the diff is clean on this lens, return an empty findings array.`
}

function verifyPrompt(f, dim) {
  return `Adversarially verify ONE review finding from the ${dim} lens. Read the ACTUAL changed code (diff range ${range}) — do not trust the finding. Decide isReal=true only if it is a genuine defect in the changed code; default to isReal=false if the finding is speculative, already mitigated, or a false positive. Re-grade severity if the finding over/under-states it.\n\nFinding: [${f.severity}] ${f.file}${f.line ? ':' + f.line : ''} — ${f.problem}`
}

// Pipeline: each dimension verifies as soon as its review returns (no barrier).
const results = await pipeline(
  DIMENSIONS,
  (d) => agent(reviewPrompt(d), { agentType: d.agentType, model: 'sonnet', phase: 'Review', label: `review:${d.key}`, schema: FINDINGS_SCHEMA }),
  (review, d) => parallel(
    ((review && review.findings) || []).map((f) => () =>
      agent(verifyPrompt(f, d.key), { model: 'opus', effort: 'high', phase: 'Verify', label: `verify:${d.key}`, schema: VERDICT_SCHEMA })
        .then((v) => ({ dimension: d.key, file: f.file, line: f.line || '', problem: f.problem, fix: f.fix, verdict: v }))
    ),
  ),
)

const confirmed = results
  .flat()
  .filter(Boolean)
  .filter((f) => f.verdict && f.verdict.isReal)
  .map((f) => ({ dimension: f.dimension, severity: f.verdict.severity, file: f.file, line: f.line, problem: f.problem, fix: f.fix, why: f.verdict.reason }))

const order = { critical: 0, high: 1, medium: 2, low: 3 }
confirmed.sort((x, y) => (order[x.severity] ?? 9) - (order[y.severity] ?? 9))

log(`review complete: ${confirmed.length} confirmed finding(s) across ${DIMENSIONS.length} dimensions`)

return {
  range,
  dimensions: DIMENSIONS.map((d) => d.key),
  confirmedCount: confirmed.length,
  bySeverity: {
    critical: confirmed.filter((f) => f.severity === 'critical').length,
    high: confirmed.filter((f) => f.severity === 'high').length,
    medium: confirmed.filter((f) => f.severity === 'medium').length,
    low: confirmed.filter((f) => f.severity === 'low').length,
  },
  confirmed,
}
