/*
 * project/state.js — ArchiTinder Make Web project state.
 *
 * Data source for project/dashboard.html. Loaded via <script> (no fetch,
 * so dashboard.html opens by double-click — no local server needed).
 *
 * Maintained by the `reporter` agent at session end. Code-derived sections
 * (tasks, prs, fileMap) are regenerated; semi-static sections (roadmap,
 * personas, architecture, flow) are updated when they change.
 */
window.PROJECT_STATE = {
  meta: {
    project: 'ArchiTinder — Make Web',
    updated: '2026-05-23',
    branch: 'develop',
    head: '877e82c',
  },

  tasks: {
    open: [
      { id: 'AUTH1', title: 'Kakao / Naver OAuth', note: 'Google-only today; Korean users need domestic login' },
    ],
    inProgress: [
      { id: 'DESIGN-REWORK', title: 'Design-system redesign — per-component rework', note: 'Foundation shipped (PR #54). Remaining: ~7,700 LOC inline styles → CSS Modules, light-theme visuals, leaf→hub order.' },
    ],
    note: 'Full phase roadmap → Roadmap tab. Detailed ledger: .claude/Task.md',
  },

  roadmap: [
    { phase: '1–12', focus: 'Single-user reference exploration base (auth, 4-phase recommendation, Gemini search, persona report, project CRUD, E2E infra)', status: 'shipped' },
    { phase: '13', focus: 'Profile system — firm + user profiles, public/private boards', status: 'shipped' },
    { phase: '14', focus: 'Board system — board detail view, follow, "Love this!" reaction', status: 'shipped' },
    { phase: '15', focus: 'Social foundation — external DM links, MATCHED! results screen', status: 'shipped' },
    { phase: '16', focus: 'Recommendation expansion — Profile-tab office + user recs', status: 'pending' },
    { phase: '17', focus: 'LLM reverse-questioning — pre-swipe persona classification', status: 'pending' },
    { phase: '18', focus: 'External connections — firm article crawl (Space, ArchDaily, news)', status: 'pending' },
    { phase: '19–26', focus: 'Tab 3-structure replan + P1–P6 latency/UX overhaul', status: 'shipped' },
    { phase: 'design', focus: 'Design-system redesign — light-mode tokens, 4-theme switcher, frontend rework', status: 'in progress' },
  ],

  personas: [
    { id: 'P1', name: 'Firm → Jobseeker', tag: 'PRIMARY', desc: 'an architect looking for the right firm to apply to' },
    { id: 'P2', name: 'Person → Person', desc: 'follow people whose aesthetic taste you trust' },
    { id: 'P3', name: 'Firm → Client', desc: 'a client seeking a firm to commission' },
    { id: 'P4', name: 'Individual Solo', tag: 'GATEWAY', desc: 'inspiration / personal taste board — most users start here' },
  ],

  prs: [
    { n: 72, title: 'feat: board UX — edit mode, name edit, swipe finish button, result save (PR #71 recreation + Codex defect fixes)', date: '2026-05-23' },
    { n: 70, title: 'chore: session-end reporter housekeeping — record external PR triage + add DEV-ENV1', date: '2026-05-22' },
    { n: 69, title: 'perf(frontend): image loading — 4s→2s timeout, lazy gallery, preload cap 3', date: '2026-05-22' },
    { n: 68, title: 'fix: UserSerializer.user_id source — user.id not profile id', date: '2026-05-22' },
    { n: 66, title: 'fix: discovery 499s timeout + LLM chat abort — gunicorn workers + per-endpoint client timeouts', date: '2026-05-22' },
    { n: 65, title: 'chore: reporter DB-split deploy session-end sync', date: '2026-05-22' },
    { n: 61, title: 'feat: app-test FEATURE-SCOPED mode — lighter gate for non-swipe PRs', date: '2026-05-22' },
    { n: 60, title: 'chore: reporter PR2 session-end housekeeping', date: '2026-05-22' },
  ],

  architecture: {
    stack: 'React 18 + Vite (frontend) · Django 4.2 LTS + DRF + pgvector + Gemini (backend) · Neon PostgreSQL',
    databases: [
      { alias: 'default', role: 'Make Web app data — accounts / profiles / recommendation / social. Django ORM + migrations target this only. DB name: user_data (57 migrations, 23 tables).' },
      { alias: 'buildings', role: 'Make-DB-owned canonical_v2_buildings (~39,776 rows) — read-only raw SQL, never ORM or migrate. DB name: neondb.' },
    ],
    deploy: 'Railway (backend) · Vercel (frontend) · Cloudflare R2 (images) · Neon Postgres — all Singapore region',
    notes: [
      'All building references use canonical_bld_id (TEXT PK); queries gate on is_publishable = true.',
      'JWT auth: access 1hr / refresh 30d, rotate + blacklist.',
      'Google login via auth-code flow.',
      'DB-split live in production as of 2026-05-22 (deploy PR #63, cutover deploy 69c9473a).',
      'local-dev Neon branch (br-rough-wildflower-a115ukd4) provisioned 2026-05-23 — backend/.env now points here, not prod.',
    ],
  },

  fileMap: {
    'frontend/src': ['api/', 'components/', 'context/', 'hooks/', 'layouts/', 'pages/', 'utils/'],
    'backend/apps': ['accounts/', 'profiles/', 'recommendation/', 'social/'],
    'docs': ['algorithm.md', 'database-schema.md', 'COLLAB_HANDOFF.md', 'specs/'],
  },

  flow: {
    session: 'One Claude Code session — the orchestrator. Owns architecture, schema, auth, product + release decisions, and review. Dispatches sub-agents; does not write feature code itself.',
    skill: 'orchestrate — the feature-implementation playbook the session runs itself.',
    agents: [
      { name: 'back-maker', role: 'Django/DRF backend code' },
      { name: 'front-maker', role: 'React/Vite frontend code' },
      { name: 'code-review', role: 'static code review — inner loop, per change, pre-commit' },
      { name: 'security-manager', role: 'security scan — inner loop, per change, pre-commit' },
      { name: 'app-test', role: 'pre-push gate — live browser user-journey + drift check' },
      { name: 'git-manager', role: 'single commit — never pushes' },
      { name: 'git-publisher', role: 'push / PR / merge / develop→main deploy' },
      { name: 'reporter', role: 'session-end — updates Task.md + this dashboard state' },
    ],
  },
};
