# Goal — ArchiTinder PRD (project constitution)

> **Read this when:** orchestrator / research / designer / reviewer needs a tiebreaker
> for a trade-off — "should we build this?" / "which persona wins?" / "is this in or
> out of scope?". This is the highest-level decision reference, intentionally short
> and stable.
>
> **NOT** a feature list (see `Task.md`), **NOT** system docs (see `Report.md`),
> **NOT** the algorithm spec (see `research/spec/requirements.md`), **NOT** visual
> rules (see `DESIGN.md`). Those layers are detailed and fluid; this layer is
> principled and rarely amended.
>
> **Tone**: principles + boundaries. Over-specification interferes with judgment.

---

## 0. Working Principle (how this project operates)

The order matters:

1. **Problem definition first.** Before code, identify what to build and why it's a
   problem worth solving. Research-driven.
2. **Plan as written artifact.** Step-by-step plan-as-document so problems are
   broken down and shareable, not held only in someone's head.
3. **Architecture > tactical code.** Once data structures and algorithm flow are
   correct, the code is straightforward. Conversely, if foundational structure is
   wrong, code piles up symptoms — bugs surface in unrelated places.
4. **Foundational correctness matters most.** Trade-off bias: invest disproportionately
   in getting the data shape, the matching algorithm, and the user-feedback loop right.
   Polish + features come AFTER the foundation holds.

This principle is why the project has 4 terminals (main / research / design / review)
with research as a first-class long-running dialog rather than a sub-step of
implementation. See `WORKFLOW.md`.

---

## 1. Why we exist (problem + thesis)

**Problem**: existing solutions for connecting architects with firms / clients /
peers are text-first and one-shot.
- `vmspace.com/job` and similar boards: text job postings, no continuous visual flow
  of a firm's actual work.
- Instagram / ArchDaily: visual but no mechanism to learn the viewer's taste and
  recommend matches.
- LinkedIn: professional graph but blind to aesthetic taste, the central currency
  in architecture.

**Thesis**: a swipe-based visual exploration that learns the user's aesthetic taste
in 30-50 cards, then recommends firms / persons / projects matching that taste,
produces more honest matching than keyword search OR follow-graph algorithms.
Architecture is a visual + tactile discipline; the discovery interface should be too.

**Analogy** (informal positioning): think Tinder × Pinterest, scoped to architecture.
The swipe surfaces taste; the matched results connect that taste to humans and
work. Not romance, not generic image discovery — a domain-specific bridge.

---

## 2. Elevator pitch (one sentence)

> Swipe building references to reveal your aesthetic taste — and match with firms,
> peers, and projects whose work resonates with it.

---

## 3. Target personas (priority order)

Decisions affecting multiple personas resolve by priority. Lower-priority personas
are never harmed for higher-priority gains, but feature design optimizes for the
top of the list.

### P1 — Firm → Jobseeker  *(PRIMARY)*

An architect (student, junior, mid-level) looking for the right firm to apply to.
Tired of scanning text job boards. Wants to *see* what each firm actually builds,
in continuous flow, and discover firms whose aesthetic matches theirs.

- Swipe complete → "MATCHED!" → taste-matched firm cards
- Click firm → profile (blue verified mark) → project gallery → external apply link
- Bonus surface: firm's published articles (Space, ArchDaily, news) aggregated by
  keyword crawl
- *Replaces / augments `vmspace.com/job`* by giving the firm a continuous-flow
  showcase instead of a stamped job posting

### P2 — Person → Person

A practicing or aspiring architect who wants to follow people whose taste they
trust ("editor's pick" model — like discovering a curator on Instagram).

- Swipe complete → taste-matched user cards
- Click user → profile (Instagram-feed style) → public boards
- Follow / "Love this!" reaction; external DM (Instagram, email)
- Public/private boards, set at project creation OR profile settings
- Profile fields: MBTI, avatar, bio

### P3 — Firm → Client

Someone (developer, individual client, institution) seeking a firm to commission.
Same flow as P1 — discover firm by aesthetic, click into profile, contact via
external link. UX is identical; the difference is only in the user's intent.

### P4 — Individual Solo  *(GATEWAY)*

Just here to look for inspiration / build a personal taste board. The current
single-user base flow already serves this.

P4 is also the **gateway**: most users start here (low commitment), then convert
to P1 / P2 / P3 once they see the matched results.

### Persona convergence

All four personas use the **same swipe → MATCHED! → 3-tab results landing** flow.
The tabs (Related Projects / Related Architects / Related Editors) are surfaced
to everyone; persona difference is which tab the user gravitates to and what they
do after click. *One product, four journeys.*

---

## 4. Common flow (single user journey)

```
1. (Optional onboarding) LLM chat — reverse-questions to refine taste
2. Swipe session — typically 30-50 cards, learns aesthetic preference vector
3. "MATCHED!" celebratory screen + landing
4. 3-tab recommendation results: Projects / Offices / Users (Editors)
5. Click card → detail profile / project view
6. Want more? Follow external link (firm site, Instagram DM, email) for full info
```

The system stops at step 6. **External contact is intentional** — we are a
discovery layer, not a transaction layer.

---

## 5. Success metrics (KPIs)

What "winning" looks like, organized by question:

| Question | Metric (qualitative) |
|----------|----------------------|
| **Is the matching honest?** | Top-10 ⭐ bookmark rate (spec §2 primary metric). Late cards in a session should be more bookmarked than early cards. |
| **Are users coming back?** | Repeat-project-creation rate. A satisfied user starts a new project; a one-shot user does not. |
| **Does post-swipe engagement happen?** | Click-through on recommendation cards (Projects / Offices / Users tabs); time on profile pages. |
| **Are matches converting to action?** | Follow rate on user/editor profiles; "Love this!" reaction rate on boards; external-link click-through rate. |

Specific numerical targets per metric are deferred — they get set once we have
real launch data to baseline against. The metric **shape** is what's stable; the
**numbers** flex.

Anti-goals (metrics we do NOT optimize for):
- Session length (we want efficient taste-learning, not engagement traps)
- Total swipes (a user who finds their match in 25 swipes is more successful than
  one who swipes 200)

---

## 6. Out-of-scope (constitutional — orchestrator references this when asked "should we build X?")

We will **not** build:

- **Romance / dating.** P2 person-to-person matching is *aesthetic taste* matching,
  not romantic matching. Profile fields, board content, and recommendation copy
  must reflect this.
- **Real-estate transactions** (buying/selling property, listing apartments).
- **Materials marketplace** (sourcing, pricing, B2B procurement).
- **Contractor / construction-firm matching** (general-contractor finding, bidding).
- **Blueprint / drawing marketplace** (selling CAD files, license trading).
- **Design-as-a-service marketplace** (commissioning rendering, freelance bids).

We will **not** target (initial scope):

- **Markets outside Korea** (English UI is supported, but corpus + community focus
  is Korea-first; global expansion is a v3+ conversation).
- **Industries outside architecture** (interior design, landscape, furniture
  design — the corpus is `architecture_vectors`).

These boundaries are load-bearing for orchestrator's "should we add this feature?"
judgment. Crossing them requires explicit user reauthorization, not just an
agent's discretion.

---

## 7. Roadmap (phase milestones)

A coarse map of where we've been and where we're going. Detailed sprint planning
lives in `Task.md`; algorithm sequencing in `research/spec/research-priority-rebaselined.md`.

| Phase | Focus | Status |
|-------|-------|--------|
| 1-12 | Single-user reference exploration base (auth, 4-phase recommendation, Gemini search, persona report, project CRUD, E2E test infra, mobile polish, swipe bug fixes) | ✅ Complete |
| 13 | **Profile system** — Firm profile, User profile, public/private boards | 🟡 In progress (mockups ready; backend pending) |
| 14 | **Board system** — board detail view, follow, "Love this!" reaction | Pending |
| 15 | **Social foundation** — DM links (Instagram/email), MATCHED! results screen | Pending |
| 16 | **Recommendation expansion** — 3-tab landing (Projects / Offices / Users), persona-classified results | Pending |
| 17 | **LLM reverse-questioning** — chat-phase persona classifier (deeper than current 0-2 turn probe) | Pending |
| 18 | **External connections** — firm article crawl (Space, ArchDaily, news keyword matching), external DM wiring | Pending |
| post-18 | Long-term: scale (multi-region), monetization activation, possibly adjacent verticals (interior, landscape) — TBD | Future |

The **algorithm side** (search-flow refinements per `research/spec/requirements.md`)
runs orthogonally to the phase roadmap. Topics 01-12, IMP-1..IMP-9, INFRA-1 are
their own track; both must converge for v1 launch.

---

## 8. Business model (informational, not blocking decisions)

Four candidate revenue sources, weighted later from real data:

| Source | Notes |
|--------|-------|
| Research grants | Academic / govt funding for taste-discovery / matching research |
| Investment | Seed / Series A — needs traction proof from KPIs above |
| Data sale | Aggregated, anonymized taste / matching data — value depends on user volume + consent posture |
| Advertising | Firm-promoted cards in recommendation results — must not corrupt the matching algorithm |

**Constraint on monetization**: revenue mechanics that distort the matching
algorithm (paid placement that bypasses taste signal) are out-of-scope per §6's
"honest matching" thesis. Sponsored cards must be marked as such and must not
inflate `top-10 bookmark rate`-style metrics fraudulently.

---

## 9. Decision principles (tiebreaker rules for agents)

When two valid choices conflict, apply these in order:

1. **Out-of-scope check first** (§6). If a feature crosses a boundary, stop and
   ask the user — do not silently expand scope.
2. **Persona priority** (§3). When P1 vs P2 design conflict surfaces, P1 wins
   unless the user explicitly overrides.
3. **Foundation correctness > feature breadth** (§0). A correct algorithm with
   3 features beats a buggy algorithm with 30. Defer features when they pile on
   shaky foundations.
4. **Honest matching > engagement metrics** (§5 anti-goals). Do not introduce
   patterns that boost session length / total swipes at the cost of taste-match
   quality.
5. **External-dependency restraint**: prefer extending Gemini / HuggingFace /
   Imagen / Cloudflare R2 / Neon Postgres before adding a new external service.
   New dependencies need user approval.
6. **Spec is single source of truth** for algorithm decisions. If `research/spec/
   requirements.md` says X, code does X. If main believes spec is wrong, raise
   it to research terminal — do not fork behavior.
7. **Korea-first** (§6). When localization decisions conflict, Korean UX wins;
   English is supported, not co-equal.

---

## 10. Open research areas (delegated to research terminal)

These question domains are owned by `research/` (see `research/spec/requirements.md`
and `research/investigations/`). Main pipeline does NOT decide these unilaterally
— it implements per spec.

| Area | Currently in spec |
|------|-------------------|
| Search algorithm | spec v1.6 — RRF hybrid retrieval, HyDE V_initial, DPP diversity, K-Means + MMR, convergence detection, latency optimization stack (IMP-7/8/9 + INFRA-1) |
| User-feedback loop | spec §3 chat phase 0-2 turn probe; §4 swipe latency; §6 session event logging |
| Frontend UX exploration | gesture beyond swipe (tap / rotate / zoom / long-press); arrow-key support; should ❤️/❌ buttons remain or fade out? |
| DB quality | crawling pipeline (Make DB owned), data QC, legal posture (copyright, bot crawling) — out of `make_web` repo scope |
| User DB & consent | what user data to collect, consent flow at signup (Korean PIPA + GDPR), marketing-opt-in, retention policy — research pending |
| Performance bottlenecks | image (R2 latency), backend compute (algorithm), network RTT (Neon) — covered by spec v1.6 IMP-7/8/9 + INFRA-1 |
| Algorithm evaluation methodology | how to measure "matching quality" at scale; A/B cohort design; primary vs secondary metric weighting |

When a question arises that isn't on this list and isn't covered by spec → it
belongs in research terminal first, not in orchestrator-implement-then-debug.

---

## 11. Current sprint acceptance criteria (Phase 13-18 roadmap items)

Detailed sub-tasks live in `Task.md`. This is the headline checklist:

- [ ] Phase 13 — Firm profile page (blue verified mark, project cards, external links)
- [ ] Phase 13 — User profile page (MBTI, avatar, bio, boards)
- [ ] Phase 13 — Public/private boards (set at project creation + profile settings)
- [ ] Phase 14 — Board detail view (other users' boards)
- [ ] Phase 14 — Follow system + "Love this!" reaction
- [ ] Phase 15 — External DM links (Instagram, email)
- [ ] Phase 15 — "MATCHED!" results screen + recommendation card landing (3 tabs)
- [ ] Phase 16 — Recommendation expansion (firm/user/project tabs with match scores)
- [ ] Phase 17 — LLM reverse-questioning → persona classification
- [ ] Phase 18 — Firm article crawl / keyword matching (Space, ArchDaily, news)

---

## Document history

- **v2 — 2026-04-26**: rewritten as a constitution-style PRD per user request.
  Adds working principles, decision tiebreakers, out-of-scope clauses, business
  model surface, open research areas catalog. Original v1 (Phase 1-12 summary +
  acceptance checklist) preserved in spirit at §11; expanded everywhere else.
- **v1**: minimal vision + 4 personas + acceptance criteria checklist.
