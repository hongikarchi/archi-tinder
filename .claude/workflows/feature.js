export const meta = {
  name: 'feature',
  description: 'Build+review CORE of the feature pipeline: decompose -> back-maker/front-maker -> code-review + security-manager -> Opus adversarial-verify -> 2-cycle fix loop. STOPS at commit-ready and returns a structured result. Never runs git (commit/push/PR/merge) — the publish gate lives in the main session, outside this workflow.',
  phases: [
    { title: 'Build', detail: 'back-maker then front-maker (Sonnet); skip the side a task does not touch' },
    { title: 'Review', detail: 'code-review + security-manager in parallel (Sonnet)' },
    { title: 'Verify', detail: 'Opus adversarial-verify of findings: confirm real, drop false positives' },
  ],
}

// ---------------------------------------------------------------------------
// HARD INVARIANT (CLAUDE.md publish gate): this workflow performs NO git
// operations. It returns { commitReady, ... } and hands back to the main
// session, which runs git-commit -> app-test -> reporter-inline and then STOPS
// at the publish gate. Adding a git push/PR/merge here would violate the gate.
//
// MODEL TIERING (spend-posture decision): every agent() call PINS model
// explicitly — agentType swaps the system prompt + tools but model still
// defaults to inherit-main-loop (= Opus). Workers run Sonnet; the verify/judge
// pass runs Opus. Leaving model implicit would silently run every worker on
// Opus and defeat the cost decision.
//
// args shape (passed by the launching session):
//   {
//     taskId:    'BACK-LLM-1',                 // for labels/logs
//     backend:   { spec, files: [], contract } | null,
//     frontend:  { spec, files: [] } | null,   // contract filled from backend result
//     acceptance: ['...'],                      // acceptance criteria for review
//     cyclesUsed: 0,                            // fix cycles already spent (e.g. a prior app-test FAIL re-launch)
//     fixOrders:  null | [ {file, problem, fix} ]  // present on a fix re-launch
//   }
// ---------------------------------------------------------------------------

const MAKER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['status', 'built', 'apiContract', 'notes'],
  properties: {
    status: { type: 'string', enum: ['done', 'blocked'] },
    built: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'change'],
        properties: { file: { type: 'string' }, change: { type: 'string' } },
      },
    },
    apiContract: { type: 'string', description: 'endpoint(s) + method + request/response shape this maker implemented, or "none"' },
    notes: { type: 'string', description: 'tests/lint run, blockers, anything the reviewer must know' },
  },
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
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

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['finalVerdict', 'confirmedFindings', 'droppedFalsePositives', 'rationale'],
  properties: {
    finalVerdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    confirmedFindings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'file', 'problem', 'fix'],
        properties: {
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          file: { type: 'string' },
          problem: { type: 'string' },
          fix: { type: 'string' },
        },
      },
    },
    droppedFalsePositives: { type: 'array', items: { type: 'string' } },
    rationale: { type: 'string' },
  },
}

const spec = args || {}
const taskId = spec.taskId || 'feature'
const acceptance = (spec.acceptance || []).map((a) => `- ${a}`).join('\n') || '- (none supplied)'

if (!spec.backend && !spec.frontend) {
  return { commitReady: false, blocked: 'no backend or frontend spec supplied', cyclesUsed: spec.cyclesUsed || 0 }
}

// One build+review+verify pass. fixOrders is the confirmed findings to fix on a retry.
async function pass(fixOrders) {
  const fixBlock = fixOrders && fixOrders.length
    ? `\n\nThis is a FIX cycle. Address ONLY these confirmed findings, do not re-architect:\n${fixOrders.map((f) => `- [${f.severity}] ${f.file}: ${f.problem} -> ${f.fix}`).join('\n')}`
    : ''

  // --- Build phase: back first (front needs its API contract), then front ---
  let backend = null
  if (spec.backend) {
    backend = await agent(
      `Implement the BACKEND for task ${taskId}.\n\nSpec:\n${spec.backend.spec}\n\nFiles likely touched: ${(spec.backend.files || []).join(', ') || '(decide)'}\n\nAcceptance criteria:\n${acceptance}${fixBlock}\n\nFollow CLAUDE.md backend conventions. Run flake8 + apply any migration you create. Report the exact API contract you implemented.`,
      { agentType: 'back-maker', model: 'sonnet', phase: 'Build', label: `back-maker:${taskId}`, schema: MAKER_SCHEMA },
    )
    if (backend && backend.status === 'blocked') {
      return { commitReady: false, blocked: `back-maker blocked: ${backend.notes}`, backend }
    }
  }

  let frontend = null
  if (spec.frontend) {
    const contract = (backend && backend.apiContract) || spec.frontend.contract || 'none'
    frontend = await agent(
      `Implement the FRONTEND for task ${taskId}.\n\nSpec:\n${spec.frontend.spec}\n\nFiles likely touched: ${(spec.frontend.files || []).join(', ') || '(decide)'}\n\nBackend API contract to consume:\n${contract}\n\nAcceptance criteria:\n${acceptance}${fixBlock}\n\nConsult DESIGN.md before any style/layout change. Run ESLint + build.`,
      { agentType: 'front-maker', model: 'sonnet', phase: 'Build', label: `front-maker:${taskId}`, schema: MAKER_SCHEMA },
    )
    if (frontend && frontend.status === 'blocked') {
      return { commitReady: false, blocked: `front-maker blocked: ${frontend.notes}`, backend, frontend }
    }
  }

  const changedFiles = [...(backend?.built || []), ...(frontend?.built || [])].map((b) => b.file)
  const filesLine = changedFiles.join(', ') || '(none reported)'
  const contractLine = (backend && backend.apiContract) || '(no backend change)'

  // --- Review phase: code-review + security-manager in parallel (Sonnet) ---
  const [review, security] = await parallel([
    () => agent(
      `Review the changes for task ${taskId}.\nChanged files: ${filesLine}\nAPI contract: ${contractLine}\nAcceptance criteria:\n${acceptance}\n\nCheck integration correctness, API contract front<->back, logic bugs, error handling at boundaries, obvious perf. Return verdict + findings.`,
      { agentType: 'code-review', model: 'sonnet', phase: 'Review', label: `code-review:${taskId}`, schema: FINDINGS_SCHEMA },
    ),
    () => agent(
      `Security scan of the changes for task ${taskId}.\nChanged files: ${filesLine}\n\nScan backend (SQL injection, auth bypass, secret leakage), frontend (XSS, token storage, endpoint injection), database (raw SQL params, exposed IDs). Return verdict + findings.`,
      { agentType: 'security-manager', model: 'sonnet', phase: 'Review', label: `security:${taskId}`, schema: FINDINGS_SCHEMA },
    ),
  ])

  const rawFindings = [
    ...((review && review.findings) || []),
    ...((security && security.findings) || []),
  ]

  // --- Verify phase: Opus adversarial-verify; no findings -> trivially PASS ---
  let verify
  if (rawFindings.length === 0) {
    verify = { finalVerdict: 'PASS', confirmedFindings: [], droppedFalsePositives: [], rationale: 'No findings from review or security.' }
  } else {
    verify = await agent(
      `Adversarially verify these review/security findings for task ${taskId}. For EACH, decide if it is a REAL defect in the changed code or a false positive — read the actual code, do not trust the finding. Drop false positives. finalVerdict = FAIL if any confirmed finding is critical/high, else PASS (medium/low may ship with a note).\n\nChanged files: ${filesLine}\n\nFindings:\n${rawFindings.map((f) => `- [${f.severity}] ${f.file}${f.line ? ':' + f.line : ''}: ${f.problem}`).join('\n')}`,
      { model: 'opus', phase: 'Verify', label: `verify:${taskId}`, schema: VERIFY_SCHEMA },
    )
  }

  return {
    commitReady: verify.finalVerdict === 'PASS',
    verify,
    review,
    security,
    built: [...(backend?.built || []), ...(frontend?.built || [])],
    apiContract: contractLine,
  }
}

// --- Fix loop: max 2 fix cycles total, shared budget across session re-launches ---
let cyclesUsed = spec.cyclesUsed || 0
let fixOrders = spec.fixOrders || null
let result

while (true) {
  result = await pass(fixOrders)
  if (result.blocked) {
    log(`BLOCKED: ${result.blocked}`)
    return { ...result, cyclesUsed }
  }
  if (result.commitReady) {
    log(`commit-ready after ${cyclesUsed} fix cycle(s)`)
    break
  }
  if (cyclesUsed >= 2) {
    log(`fix budget exhausted (${cyclesUsed} cycles) — returning FAIL for session to handle`)
    break
  }
  cyclesUsed++
  fixOrders = result.verify.confirmedFindings
  log(`fix cycle ${cyclesUsed}: ${fixOrders.length} confirmed finding(s)`)
}

return {
  commitReady: result.commitReady,
  cyclesUsed,
  built: result.built,
  apiContract: result.apiContract,
  confirmedFindings: result.verify.confirmedFindings,
  reviewVerdict: result.review ? result.review.verdict : 'PASS',
  securityVerdict: result.security ? result.security.verdict : 'PASS',
  rationale: result.verify.rationale,
}
