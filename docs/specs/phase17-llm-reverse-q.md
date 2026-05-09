# Phase 17 — LLM Reverse-Questioning + Persona Classification

**Status**: Pending dialogue. Has cross-spec interaction with Search Flow (chat phase TTFC budget) — flag this as load-bearing before any implementation.

**Owner**: admin-driven dialogue.

**Pre-context**: Goal.md Phase 17 — "LLM chat asks reverse questions to refine user needs → persona classification (P1-P4) → per-persona UI branching".

---

## 1. Personas (per Goal.md)

- **P1**: 일자리 찾는 jobseeker (looking to be hired)
- **P2**: 인재 찾는 firm (hiring)
- **P3**: 프로젝트 클라이언트 (specific project client)
- **P4**: 호기심 individual (curious browser)

## 2. Open dimensions (need admin decision before implementation)

| Dimension | Question | Notes |
|---|---|---|
| **Where in flow** | Pre-swipe (extends current chat phase, inflates latency budget) / Post-swipe (uses taste signal) / Hybrid? | **Load-bearing — interacts with Search Flow chat phase budget.** |
| Reverse-Q examples | Adversarial / implicit / non-verbal (deduce from filter shape)? | Affects prompt design. |
| Per-persona UI branching | Silent classification + tailored cards / explicit "I am: ☐ jobseeker ☐ hiring ..." prompt? | UX trade-off. |
| Persona drift | User can be P1 in one session, P2 in another — explicit support? | Persistence model. |
| Persona representation shape | Structured `{persona_type, one_liner, styles[], programs[]}` vs flat string `persona_label`? | Designer mocks disagree (UserProfilePage uses structured `persona_summary`; PostSwipeLandingPage uses flat `persona_label`). |
| Persona persistence | Per-session / per-user / per-user-with-current-session-override? | Storage decision. |
| Confidence + override | Low-confidence classification: ask user, or silent commit? | Implementation detail. |

## 3. Existing data placeholder

`UserProfile.persona_summary = JSONField(default=dict)` is already reserved by Phase 13 PROF2 migration. Phase 17 lands the actual computation logic + populates this field. Until then, the field stays empty and the UserProfilePage hides the persona section when `persona_summary == {}`.

## 4. Critical interaction with Search Flow chat phase

If Phase 17's reverse-Q lives **pre-swipe** (extends chat phase): inflates Time-To-First-Card (TTFC) budget. Three options:

- **Option A**: Phase 17 reverse-Q goes post-swipe (uses taste signal); pre-swipe chat phase stays as-is (current 0-2 turn probe).
- **Option B**: Phase 17 reverse-Q replaces / augments chat phase; TTFC re-budgeted.
- **Option C**: Hybrid — light persona inference pre-swipe (1 turn max), full reverse-Q post-swipe.

Resolve in dialogue; do not silently extend chat phase.

## 5. Acceptance criteria (illustrative — finalise post-dialogue)

- Persona classification commits to `UserProfile.persona_summary` with a versioned schema.
- TTFC for the search flow does not regress beyond current 4000 ms budget (per `docs/algorithm.md`).
- Per-persona UI branching (if chosen) doesn't introduce new console errors / 4xx-5xx.
- Persona override path tested.

## 6. Dependencies

- Phase 13 PROF2 (`UserProfile.persona_summary` field shipped).
- May depend on Phase 16 Recommendation Expansion if persona drives rec ordering.
