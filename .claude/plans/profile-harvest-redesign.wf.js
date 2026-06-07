export const meta = {
  name: 'profile-harvest-redesign',
  description: 'FRONT-DESIGN-1 #179 profile redesign: header buttons + 4-stat row + Instagram follow popup + studios count',
  phases: [
    { title: 'Build', detail: 'back-maker studios count ∥ front-maker profile redesign' },
    { title: 'Review', detail: 'code-review ∥ security on working-tree diff' },
    { title: 'Verify', detail: 'lint/build/flake8/check + adversarial audit of blockers' },
  ],
}

// ───────────────────────── shared context ─────────────────────────
const BRANCH = 'feature/claude-profile-harvest'
const BASECTX = `
Repo: /Users/kms_laptop/Documents/archi-tinder/make_web
Branch: ${BRANCH} (origin/develop ALREADY merged in at commit 1b2c566 — do NOT merge/rebase/pull again).
HARD RULES for this task:
- Do NOT run any git write command (no add/commit/checkout/merge/stash). Leave changes uncommitted in the working tree. The session commits afterward.
- Stay strictly inside your file scope (backend/ for back-maker, frontend/ for front-maker).
- Follow CLAUDE.md + DESIGN.md conventions. No Tailwind/MUI/styled. Themed CSS vars only — no new hardcoded hex unless matching the file's existing pattern.
`

const BACK_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    filesChanged: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    fieldAdded: { type: 'string', description: 'exact serializer field name + how computed' },
    flake8: { type: 'string', enum: ['PASS', 'FAIL', 'SKIPPED'] },
    djangoCheck: { type: 'string', enum: ['PASS', 'FAIL', 'SKIPPED'] },
    notes: { type: 'string' },
  },
  required: ['filesChanged', 'summary', 'fieldAdded', 'flake8', 'djangoCheck', 'notes'],
}

const FRONT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    filesChanged: { type: 'array', items: { type: 'string' } },
    filesCreated: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    lint: { type: 'string', enum: ['PASS', 'FAIL', 'SKIPPED'] },
    build: { type: 'string', enum: ['PASS', 'FAIL', 'SKIPPED'] },
    deviations: { type: 'string', description: 'anything done differently from spec + why' },
  },
  required: ['filesChanged', 'filesCreated', 'summary', 'lint', 'build', 'deviations'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'PASS_WITH_MINORS', 'FAIL'] },
    blockers: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          file: { type: 'string' }, line: { type: 'string' },
          issue: { type: 'string' }, fix: { type: 'string' },
        },
        required: ['file', 'line', 'issue', 'fix'],
      },
    },
    minors: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['verdict', 'blockers', 'minors', 'summary'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    lint: { type: 'string', enum: ['PASS', 'FAIL'] },
    build: { type: 'string', enum: ['PASS', 'FAIL'] },
    flake8: { type: 'string', enum: ['PASS', 'FAIL', 'NA'] },
    djangoCheck: { type: 'string', enum: ['PASS', 'FAIL', 'NA'] },
    overall: { type: 'string', enum: ['PASS', 'FAIL'] },
    blockerAudit: { type: 'string', description: 'for each review blocker: real or false-positive, with reasoning' },
    extraFindings: { type: 'array', items: { type: 'string' } },
  },
  required: ['lint', 'build', 'flake8', 'djangoCheck', 'overall', 'blockerAudit', 'extraFindings'],
}

// ───────────────────────── Phase 1: Build ─────────────────────────
phase('Build')

const backPrompt = `${BASECTX}
TASK (backend, tiny): Add a Studios count to the user profile API so the frontend stat row can show it at page load.

1. Open backend/apps/accounts/serializers.py → class UserProfileSerializer.
2. Add a SerializerMethodField named exactly 'saved_studios_count'. It returns the count of architect studios this user follows = ArchitectFollow rows where follower == this UserProfile.
   - ArchitectFollow lives in apps.social.models. Its 'follower' FK points at the UserProfile (the same model UserProfileSerializer serializes — confirm by reading apps/social/models.py ArchitectFollow + how UserSavedStudiosView filters: it uses ArchitectFollow.objects.filter(follower__user_id=user_id)).
   - Implement get_saved_studios_count(self, obj): return ArchitectFollow.objects.filter(follower=obj).count()  (import ArchitectFollow locally inside the method to avoid app-load circular import, mirroring how other cross-app counts are done if any; a top-level import is fine if it doesn't cycle — check).
   - Add 'saved_studios_count' to Meta.fields AND to read_only_fields.
3. NO migration (computed field only). NO model change.
4. Verify: cd backend && python3 -m flake8 apps/accounts/serializers.py --max-line-length=120  AND  python3 manage.py check. Report both.
Return the structured result.`

const frontPrompt = `${BASECTX}
TASK (frontend): Redesign the user profile per the LOCKED design below. This is a refactor that MOVES existing UI (do not duplicate — delete originals when relocating).

═══ LOCKED DESIGN ═══
• Top bar (ProfileHeader) right side:
    - isMe:    [Share icon] [Edit icon] [Logout icon]   (logout already exists — keep it; add Share+Edit before it)
    - not me:  [Share icon] [Follow button]
• Hero (ProfileHero): avatar · name · STAT ROW (4 stats) · persona flip · external links. NOTHING else.
    - Stat row order + sources: Boards(boardsTotalCount) · Studios(user.saved_studios_count ?? 0) · Followers(followerCount) · Following(user.following_count)
    - Stat clicks: Boards→onSelectTab('boards'); Studios→onSelectTab('studios'); Followers→onOpenFollowModal('followers'); Following→onOpenFollowModal('following')
    - REMOVE from ProfileHero entirely: the !isMe action row (Follow + Message + Share buttons, ~lines 201-272), the isMe Share button (~lines 274-299), the ShareCardModal import + mount + shareOpen state + IconShare import. (Follow & Share relocate to the header; the Message DM stub is non-functional and not in the agreed layout → drop it.)
• Content tabs: keep the EXISTING Boards | Studios tab bar as-is. Do NOT add a Following tab (the popup replaces it).
• Followers/Following lists = Instagram-style POPUP MODAL (click stat count → modal overlay with the list). Deep-link pages /user/:id/followers|following stay (fallback) but now share fetch logic with the modal.

═══ FILES ═══
1. frontend/src/hooks/useFollowList.js  (NEW) — extract the fetch+pagination currently inside FollowListPage.jsx into a reusable hook:
   export default function useFollowList(userId, mode) → returns { users, loading, error, hasMore, loadMore, retry }.
   - Uses getFollowers/getFollowing from ../api/social.js (mode 'followers'|'following').
   - Same behavior as FollowListPage's fetchPage/loadMore/initial-effect (page state, append, has_more, error capture). The CONSUMER owns the IntersectionObserver sentinel and calls loadMore().
2. frontend/src/pages/userProfile/FollowListPage.jsx  (MODIFY) — refactor to consume useFollowList (drop its inline fetch state; keep its header/sentinel/observer/empty/error/loading UI). Behavior unchanged for users.
3. frontend/src/components/profile/FollowListModal.jsx  (NEW) — popup overlay.
   - Props: { userId, mode, onClose }.
   - Fixed full-screen dim backdrop (rgba black ~0.6), centered panel max-width 420, max-height ~70vh, themed surface (var(--color-surface)), radius var(--radius-lg), border var(--color-border).
   - Header row: title (팔로워 if mode==='followers' else 팔로잉) + close ✕ button.
   - Body: scrollable; uses useFollowList(userId, mode) + renders <FollowList users onOpenUser emptyMessage/> + its own IntersectionObserver sentinel for loadMore + loading/error/empty states (mirror FollowListPage).
   - onOpenUser(u): navigate('/user/'+u.user_id) then onClose().
   - Backdrop click + ✕ + Esc key → onClose. Stop propagation on panel click.
4. frontend/src/pages/userProfile/ProfileHeader.jsx  (MODIFY) — extend props to { isMe, onLogout, onShare, onEdit, onFollow, isFollowing, isFollowingPending }.
   - Right cluster when isMe: Share icon-button (IconShare) → onShare; Edit icon-button (IconEdit) → onEdit; then the EXISTING logout button (unchanged). 44×44 icon buttons, match the file's existing inline-hover style (transparent bg, var(--color-text-dim/2), hover lightens).
   - Right cluster when !isMe: Share icon-button (IconShare) → onShare; Follow button → onFollow (compact, minHeight ~38; pink gradient 'linear-gradient(135deg,#ec4899,#f43f5e)' white text when !isFollowing, var(--color-surface-2) + var(--color-text-2) + border when isFollowing; disabled when isFollowingPending; label 'Following' w/ chevron when following else 'Follow').
   - import { IconShare, IconEdit } from '../../components/icons'.
5. frontend/src/pages/userProfile/ProfileHero.jsx  (MODIFY) — per LOCKED DESIGN above. New props: add onOpenFollowModal, onSelectTab, savedStudiosCount. Drop now-unused props (isFollowing/isFollowingPending/onToggleFollow) and Share/ShareCardModal/IconShare. Stat row becomes 4 entries with the click wiring above. Keep avatar/name/persona/external-links exactly as-is.
6. frontend/src/pages/UserProfilePage.jsx  (MODIFY):
   - Add state: const [shareOpen, setShareOpen] = useState(false); const [followModal, setFollowModal] = useState(null)  // null | 'followers' | 'following'
   - <ProfileHeader> call: pass isMe, onLogout, onShare={() => setShareOpen(true)}, onEdit={() => setShowEditProfile(true)}, onFollow={handleToggleFollow}, isFollowing, isFollowingPending.
   - <ProfileHero> call: pass user, boardsTotalCount, followerCount, savedStudiosCount={user.saved_studios_count ?? 0}, isMe, onSelectTab={(t) => t === 'studios' ? handleStudiosTab() : setActiveTab('boards')}, onOpenFollowModal={(m) => setFollowModal(m)}. Remove isFollowing/isFollowingPending/onToggleFollow props from ProfileHero.
   - DELETE the standalone "Edit Profile button" block (the isMe block right after </ProfileHero>, ~lines 433-463) — Edit now lives in the header.
   - Mount near the existing EditProfileModal (bottom): ShareCardModal when shareOpen (import ShareCardModal from '../components/ShareCardModal.jsx'; <ShareCardModal user={user} onClose={() => setShareOpen(false)} />), and FollowListModal when followModal (import from '../components/profile/FollowListModal.jsx'; <FollowListModal userId={user.user_id} mode={followModal} onClose={() => setFollowModal(null)} />).
   - The IconEdit import in UserProfilePage may become unused after deleting the Edit button — remove it if so (eslint no-unused).

═══ DISCIPLINE ═══
- Themed CSS vars; match each file's existing inline-style + inline-hover idiom (do not introduce CSS Modules for the moved buttons — consistency with these files; Codex does the pixel/hover-polish pass after).
- Verify github-light theme reasoning first (dark-origin source must not assume dark).
- Run: cd frontend && npm run lint && npm run build. Both must pass. Report results + any deviation.
Return the structured result.`

const build = await parallel([
  () => agent(backPrompt, { agentType: 'back-maker', label: 'back:studios-count', phase: 'Build', schema: BACK_SCHEMA }),
  () => agent(frontPrompt, { agentType: 'front-maker', label: 'front:profile-redesign', phase: 'Build', schema: FRONT_SCHEMA }),
])
const [backRes, frontRes] = build
log(`Build done. backend: ${backRes ? backRes.flake8 + '/' + backRes.djangoCheck : 'NULL'} · frontend lint/build: ${frontRes ? frontRes.lint + '/' + frontRes.build : 'NULL'}`)

// ───────────────────────── Phase 2: Review ─────────────────────────
phase('Review')

const reviewCtx = `${BASECTX}
Review the UNCOMMITTED working-tree changes on this branch (run: git --no-pager diff  AND  git status --short ; new untracked files: read them directly). This is the FRONT-DESIGN-1 #179 profile redesign:
- backend: UserProfileSerializer gains a 'saved_studios_count' SerializerMethodField (no migration).
- frontend: profile buttons relocated to ProfileHeader; ProfileHero stat row now 4 stats with tab/popup wiring; new FollowListModal (Instagram popup) + new useFollowList hook; FollowListPage refactored to the hook; UserProfilePage mounts Share/Follow/Edit modals + drops the old inline Edit button.
Backend summary: ${backRes ? JSON.stringify(backRes) : 'n/a'}
Frontend summary: ${frontRes ? JSON.stringify(frontRes) : 'n/a'}
`

const reviews = await parallel([
  () => agent(`${reviewCtx}
You are code-review. Focus on integration correctness: prop contracts between UserProfilePage↔ProfileHeader↔ProfileHero (no missing/renamed props, no leftover references to removed props/state/imports), the useFollowList extraction preserving FollowListPage behavior (pagination, error, empty), FollowListModal fetch/observer correctness + cleanup (Esc/backdrop/unmount listener removal), no duplicate UI (Share/Follow/Edit must exist in exactly one place), no unused imports (eslint), and that user.saved_studios_count is safely defaulted. Report blockers (must-fix before commit) vs minors. Verdict PASS / PASS_WITH_MINORS / FAIL.`,
    { agentType: 'code-review', label: 'review:integration', phase: 'Review', schema: REVIEW_SCHEMA }),
  () => agent(`${reviewCtx}
You are security-manager. Scan the diff: the new saved_studios_count field (no over-exposure / no N+1 that an attacker could weaponize — it's a COUNT, fine, but confirm it's read-only + not user-settable via UserProfileSelfUpdateSerializer), FollowListModal navigation (no open-redirect / no injection via user_id path — should be numeric), no token/secret leakage, no XSS via display_name/avatar_url rendering (React escapes, but flag any dangerouslySetInnerHTML / href injection). Verdict PASS / PASS_WITH_MINORS / FAIL with blockers.`,
    { agentType: 'security-manager', label: 'review:security', phase: 'Review', schema: REVIEW_SCHEMA }),
])
const [codeReview, security] = reviews
const allBlockers = [
  ...(codeReview?.blockers || []).map(b => ({ ...b, src: 'code-review' })),
  ...(security?.blockers || []).map(b => ({ ...b, src: 'security' })),
]
log(`Review: code-review=${codeReview?.verdict || 'NULL'} (${codeReview?.blockers?.length || 0} blockers) · security=${security?.verdict || 'NULL'} (${security?.blockers?.length || 0} blockers)`)

// ───────────────────────── Phase 3: Verify ─────────────────────────
phase('Verify')

const verify = await agent(`${BASECTX}
You are the final pre-commit verifier. Do TWO things, read-only (no edits, no git writes):
1. Run the gates and report each:
   - cd frontend && npm run lint   (PASS/FAIL)
   - cd frontend && npm run build  (PASS/FAIL)
   - cd backend && python3 -m flake8 apps/accounts/serializers.py --max-line-length=120  (PASS/FAIL/NA)
   - cd backend && python3 manage.py check  (PASS/FAIL/NA)
   overall = PASS only if lint+build pass and backend gates are PASS or NA.
2. Adversarially audit each review blocker below — for EACH, read the actual code and decide: REAL (genuine, must fix) or FALSE-POSITIVE (reviewer mistake), with one-line reasoning. Also surface any blocker the reviewers MISSED (extraFindings) — especially: a prop passed but not consumed, a removed state still referenced, an unused import that breaks eslint, or the popup modal leaking an event listener.
Review blockers to audit: ${JSON.stringify(allBlockers)}
Return the structured result.`,
  { agentType: 'code-review', label: 'verify:gates+audit', phase: 'Verify', schema: VERIFY_SCHEMA })

return {
  backend: backRes,
  frontend: frontRes,
  codeReview,
  security,
  verify,
  blockers: allBlockers,
}
