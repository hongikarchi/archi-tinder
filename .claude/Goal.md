# Goal

> Product vision and acceptance criteria.
> Code state: see Report.md. Task status: see Task.md.

---

## Vision

A social discovery platform for the architecture community.
Swipe building references to reveal your aesthetic taste, then connect
with matching firms, people, and projects.

## Target Personas

### P1. Firm → Jobseeker
Swipe complete → "MATCHED!" → taste-based firm recommendation cards (landing)
- Firm profile (blue-mark) → project card list
- Official website link (apply via info@mail)
- Published articles collection (Space, ArchDaily, news — keyword matching)
- Replaces vmspace.com/job + firms can showcase work in a continuous flow
- "Want to know more? Follow the link for details"

### P2. Person → Person
Swipe complete → similar-taste user recommendation cards (landing)
- User profile (Instagram feed style) → browse project boards
- Follow / "Love this!" reaction
- External DM link (Instagram, email)
- Public/private boards (set at project creation + profile settings)
- Profile page: MBTI, avatar
- "Editor's pick" — follow people with great aesthetic taste for curation

### P3. Firm → Client
Same flow as P1 (discover firm → profile → contact)

### P4. Individual Solo
Current app's base flow (reference exploration only)

## Common Flow

1. LLM chat asks reverse questions to refine user needs → persona classification
2. Swipe session → "MATCHED!" results screen
3. Landing shows recommendation cards (tab-based):
   - Related Projects
   - Related Architects / Offices
   - Related Users (Editors)
4. Click card → detail profile/project view
5. Want more? Follow external links for full info

## Current State (Phase 1-12 Complete)

- Single-user reference exploration complete
- Google OAuth + JWT auth
- 4-phase recommendation pipeline (exploring → analyzing → converged → completed)
- Gemini LLM search + persona report + Imagen 3 image generation
- Project CRUD, E2E test infrastructure
- 3465 buildings, 384-dim embeddings, Cloudflare R2 images

## Acceptance Criteria

- [ ] Firm profile page (blue-mark, project cards, external links)
- [ ] User profile page (MBTI, avatar, bio, boards)
- [ ] Public/private boards
- [ ] Follow system + "Love this!" reaction
- [ ] "MATCHED!" results screen + recommendation card landing (firm/user/project tabs)
- [ ] LLM reverse-questioning → persona classification
- [ ] Firm article crawl/keyword matching
- [ ] External DM links (Instagram, email)
