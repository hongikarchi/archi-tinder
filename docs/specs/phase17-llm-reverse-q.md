# Phase 17 — LLM Reverse-Questioning + Persona Classification

**Status**: Pending implementation. Replan Q6 (2026-05-14) resolved the
load-bearing "where in flow" question — Option A confirmed: reverse-
question lives in the first 0-2 turns of the **Taste-tab** LLM chat
(pre-swipe). Remaining open dimensions are listed in §2.

**Owner**: admin-driven dialogue.

**Pre-context**: `.claude/Goal.md` § 7 Phase 17 — "LLM chat asks reverse
questions to refine user needs → persona classification (P1-P4) →
per-persona UI branching". Post-2026-05-14 the chat surface lives in the
**Taste tab** (renamed from Search Flow per the 3-tab cutover).

---

## 1. Personas (per Goal.md § 3)

- **P1**: 일자리 찾는 jobseeker (Firm → Jobseeker — PRIMARY)
- **P2**: 인재 찾는 firm (Firm → Hiring)
- **P3**: 프로젝트 클라이언트 (Project client)
- **P4**: 호기심 individual (Curious browser)

## 2. Open dimensions (still need admin decision)

| Dimension | Question | Notes |
|---|---|---|
| ~~Where in flow~~ | ~~Pre-swipe / Post-swipe / Hybrid?~~ | **RESOLVED 2026-05-14 (Replan Q6 = Option A)**: pre-swipe, in the first 0-2 turns of the Taste-tab LLM chat. |
| Reverse-Q examples | Adversarial / implicit / non-verbal (deduce from filter shape)? | Affects prompt design. |
| Per-persona UI branching | Silent classification + tailored cards / explicit "I am: ☐ jobseeker ☐ hiring ..." prompt? | UX trade-off. |
| Persona drift | User can be P1 in one session, P2 in another — explicit support? | Persistence model. |
| Persona representation shape | Structured `{persona_type, one_liner, styles[], programs[]}` vs flat string `persona_label`? | Existing Phase 13 mocks disagree (UserProfilePage uses structured `persona_summary`; legacy PostSwipe mock used flat `persona_label`). Resolve here. |
| Persona persistence | Per-session / per-user / per-user-with-current-session-override? | Storage decision. |
| Confidence + override | Low-confidence classification: ask user, or silent commit? | Implementation detail. |

## 3. Existing data placeholder

`UserProfile.persona_summary = JSONField(default=dict)` is already
reserved by Phase 13 PROF2 migration. Phase 17 lands the actual
computation logic + populates this field. Until then, the field stays
empty and the UserProfilePage hides the persona section when
`persona_summary == {}`.

## 4. Critical interaction with Taste-tab chat phase (RESOLVED)

Replan Q6 confirmed **Option A**: Phase 17 reverse-Q lives in the
first 0-2 turns of the Taste-tab LLM chat, **before** swipe. This means
the chat phase budget must absorb the persona inference cost. The
current 0-2 turn probe stays; Phase 17 enriches what those turns do
rather than adding new turns.

- Pre-swipe chat phase TTFC budget (4000 ms per `docs/algorithm.md`)
  must NOT regress.
- If the persona inference call (Gemini) cannot complete in the existing
  budget, fall back to a deferred silent classification post-swipe and
  surface persona on the Profile tab once available.

## 5. Acceptance criteria (illustrative — finalise post-dialogue)

- Persona classification commits to `UserProfile.persona_summary` with
  a versioned schema (e.g. `{schema_version: 1, persona_type, ...}`).
- TTFC for the Taste-tab chat phase does not regress beyond the
  current 4000 ms budget (per `docs/algorithm.md`).
- Per-persona UI branching (if chosen) doesn't introduce new console
  errors or 4xx-5xx responses.
- Persona override path tested (low-confidence → user can correct).

## 6. Dependencies

- Phase 13 PROF2 (`UserProfile.persona_summary` field shipped).
- May depend on Phase 16 Recommendation Expansion if persona drives
  recommendation ordering (REC2 / REC3 in `docs/specs/phase16-recommendation-expansion.md`).
- Builds on Push S2 (canonical_v2_buildings cutover) only indirectly —
  persona logic operates on `liked_ids` aggregates, not direct building
  table reads.

---

_Last swept (S8 2026-05-14)_: Q6 marked RESOLVED (Option A pre-swipe);
Search Flow → Taste-tab terminology updated; cross-spec link to
phase16 added.
