# Make Web Service — Frontend + Backend

> This document covers the full web service: React frontend + Django backend.
> Read `00_FLOW.md` first — it defines the shared DB schema and overall system flow.

---

## 1. User Flow

```
Login → Setup → Project Config → LLM Search → Swipe → Favorites / AI Report
```

| Step | Page | Description |
|------|------|-------------|
| 1 | **LoginPage** | Social login (Google / Kakao / Naver) — no password, no manual sign-up |
| 2 | **SetupPage** | Choose: create new project or resume/update existing one |
| 3 | **ProjectSetupPage** | Name project, set area range filter (0–100,000 m²) |
| 4 | **LLMSearchPage** | Natural language search (e.g., "concrete museums in Japan") |
| 5 | **SwipePage** | Tinder-style card swiping with flip-to-gallery interaction |
| 6 | **FavoritesPage** | Liked buildings + predicted likes + AI persona report |

### Navigation

- Bottom tab bar: **Home** (New), **Swipe**, **Folders** (Results)
- Swipe tab disabled until a project is active
- State-based navigation (no URL router)

---

## 2. Tech Stack

### Frontend

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 18.3.1 |
| Build Tool | Vite | 7.3.1 |
| Styling | Tailwind CSS | 4.2.1 |
| Swipe Gestures | react-tinder-card | 1.6.4 |
| Animations | @react-spring/web | 9.7.5 |
| Grid Layout | react-masonry-css | 1.0.16 |
| Linting | ESLint | 9.39.1 |
| Language | JavaScript (JSX) | ES2020 |

### Backend

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | Django | 6.0.3 |
| API | Django REST Framework | 3.16.1 |
| Database | PostgreSQL + pgvector | 0.8.2 |
| LLM | Google Gemini (google-genai) | 1.10.0 |
| Language | Python | 3.12 |
| CORS | django-cors-headers | 4.9.0 |
| DB Adapter | psycopg2-binary | 2.9.11 |
| Vector ORM | pgvector (Python) | 0.3.0 |
| Auth | djangorestframework-simplejwt | 5.3.1 |
| Social Auth | social-auth-app-django | 5.4.1 |

> Note: **SentenceTransformers is NOT a dependency here.** Embeddings are pre-computed by Make DB (Stage 2). The backend only queries existing vectors via pgvector — no ML model needed.

---

## 3. Target File Structure

```
archithon-tinder/
├── 00_FLOW.md                   # Master flow + shared DB contract
├── 01_MAKE_DB.md                # Crawler/DB pipeline docs
├── 02_MAKE_WEB.md               # This file
├── frontend/                    # React app
│   ├── src/
│   │   ├── App.jsx              # Main app controller & state
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── SetupPage.jsx
│   │   │   ├── ProjectSetupPage.jsx
│   │   │   ├── LLMSearchPage.jsx
│   │   │   ├── SwipePage.jsx
│   │   │   └── FavoritesPage.jsx
│   │   ├── components/
│   │   │   ├── TabBar.jsx
│   │   │   ├── GalleryOverlay.jsx
│   │   │   └── BuildingCard.jsx
│   │   ├── api/
│   │   │   └── client.js        # API client with local fallback
│   │   ├── context/
│   │   │   └── AppContext.jsx   # React Context (userId, projects)
│   │   └── index.css
│   ├── public/
│   │   └── images/              # Symlink or copy from reference-crawling/images/
│   ├── .env
│   ├── package.json
│   └── vite.config.js
├── backend/                     # Django app
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── accounts/
│   │   │   ├── models.py        # UserProfile
│   │   │   ├── views.py         # LoginView, MeView
│   │   │   └── serializers.py
│   │   └── recommendation/
│   │       ├── models.py        # Project, AnalysisSession, SwipeEvent
│   │       ├── views.py         # All API endpoints
│   │       ├── services.py      # Gemini report generation
│   │       ├── engine.py        # Recommendation algorithm (pgvector queries only)
│   │       └── serializers.py
│   ├── .env
│   ├── requirements.txt
│   └── manage.py
```

> Note: No `data/` folder or `scripts/load_buildings.py` in backend. The database is fully populated by Make DB (Stage 3) before this project starts.

---

## 4. Backend: Data Models

### Django Models

**`accounts` app:**

```python
class UserProfile(models.Model):
    user         = models.OneToOneField(User, on_delete=CASCADE)
    display_name = models.CharField(max_length=100)
    avatar_url   = models.URLField(null=True, blank=True)   # profile picture from provider
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

class SocialAccount(models.Model):
    """Links a provider identity to a UserProfile. One user can have multiple providers."""
    PROVIDER_CHOICES = [
        ('google', 'Google'),
        ('kakao',  'Kakao'),
        ('naver',  'Naver'),
    ]
    user        = models.ForeignKey(UserProfile, on_delete=CASCADE, related_name='social_accounts')
    provider    = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_id = models.CharField(max_length=200)   # unique user ID from that provider
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('provider', 'provider_id')
```

**`recommendation` app:**

```python
class Project(models.Model):
    project_id        = models.UUIDField(primary_key=True, default=uuid4)
    user              = models.ForeignKey(UserProfile, on_delete=CASCADE)
    name              = models.CharField(max_length=200)
    liked_ids         = models.JSONField(default=list)   # list of building_id strings e.g. ["B00001", "B00042"]
    disliked_ids      = models.JSONField(default=list)   # list of building_id strings
    filters           = models.JSONField(default=dict)   # {program, min_area, max_area}
    analysis_report   = models.JSONField(null=True)      # keywords, dominant_axes
    final_report      = models.JSONField(null=True)      # Gemini persona output
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

class AnalysisSession(models.Model):
    session_id        = models.UUIDField(primary_key=True, default=uuid4)
    user              = models.ForeignKey(UserProfile, on_delete=CASCADE)
    project           = models.ForeignKey(Project, on_delete=CASCADE)
    status            = models.CharField(
                            choices=[('active', 'Active'), ('completed', 'Completed')],
                            default='active', max_length=20)
    total_rounds      = models.IntegerField(default=20)
    current_round     = models.IntegerField(default=0)
    preference_vector = models.JSONField(default=list)   # running 384-dim vector (list of floats)
    exposed_ids       = models.JSONField(default=list)   # building_ids shown so far (for dedup)
    created_at        = models.DateTimeField(auto_now_add=True)

class SwipeEvent(models.Model):
    session         = models.ForeignKey(AnalysisSession, on_delete=CASCADE)
    building_id     = models.CharField(max_length=20)    # e.g. "B00042" — stable across re-crawls
    action          = models.CharField(
                          choices=[('like', 'Like'), ('dislike', 'Dislike')],
                          max_length=10)
    idempotency_key = models.CharField(max_length=100, unique=True)
    created_at      = models.DateTimeField(auto_now_add=True)
```

> **Always use `building_id` to reference buildings — never name, slug, or any language-dependent field.**

### PostgreSQL Vector Table

Populated entirely by Make DB (Stage 3). Django does **not** create or migrate this table.
Django reads it via raw SQL / pgvector queries only.
**Schema defined in `00_FLOW.md` Section 4.4.**

---

## 5. API Endpoints

All endpoints are prefixed `/api/v1/`. Both frontend and backend use this contract.

### Authentication

**Flow**: Frontend uses each provider's JS SDK to get an access token → sends it to backend → backend verifies with provider → creates/links account → returns JWT.

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| POST | `/auth/social/google` | `{access_token}` | `{access, refresh, user}` |
| POST | `/auth/social/kakao` | `{access_token}` | `{access, refresh, user}` |
| POST | `/auth/social/naver` | `{access_token}` | `{access, refresh, user}` |
| POST | `/auth/token/refresh` | `{refresh}` | `{access}` |
| GET  | `/auth/me` | — | `{user_id, display_name, avatar_url}` |
| POST | `/auth/logout` | `{refresh}` | `204` (blacklists refresh token) |

**Response `user` object:**
```json
{
  "user_id": "uuid string",
  "display_name": "string",
  "avatar_url": "string | null",
  "providers": ["google", "kakao"]
}
```

**Account linking**: If a user logs in with Google, then later logs in with Kakao using the same email, they are linked to the same `UserProfile`. Matching is done by email — if email matches an existing account, the new provider is added to `SocialAccount`.

### Projects

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| GET | `/projects` | — | `[Project]` |
| POST | `/projects` | `{name, filters}` | `Project` |
| PATCH | `/projects/{id}` | `{name?, filters?}` | `Project` |
| DELETE | `/projects/{id}` | — | `204` |
| GET | `/projects/{id}/report` | — | `{analysis_report, final_report}` |
| POST | `/projects/{id}/report/generate` | — | `{final_report}` (triggers Gemini) |

### Analysis Sessions

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| POST | `/analysis/sessions` | `{user_id, project_id, filters}` | `{session_id, total_rounds, next_image, progress}` |
| POST | `/analysis/sessions/{id}/swipes` | `{user_id, project_id, building_id, action, idempotency_key}` | `{progress, next_image, is_completed}` |
| GET | `/analysis/sessions/{id}/result` | — | `{liked_images, predicted_images, analysis_report}` |

> **Auth scoping**: `GET /analysis/sessions/{id}/result` must verify that `session.user == request.user`. Return `403` if the session belongs to a different user.

### Images

| Method | Endpoint | Response |
|--------|----------|----------|
| GET | `/images/diverse-random` | `[ImageCard]` (10 diverse random buildings) |

### LLM Query Parsing

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| POST | `/api/parse-query` | `{query: string}` | `{structured_filters, suggestions}` |

### `ImageCard` Response Schema

Used by session and image endpoints:

```json
{
  "building_id": "string — e.g. 'B00042', stable canonical key",
  "slug": "string — URL-safe identifier",
  "name_en": "string — canonical English name",
  "project_name": "string — display name (may be non-English)",
  "image_url": "string — path to cover image, e.g. '/media/images/B00042/0_main.jpg'",
  "gallery": ["string", "..."],
  "metadata": {
    "axis_typology": "string | null",
    "axis_architects": "string | null",
    "axis_country": "string | null",
    "axis_area_m2": "number | null",
    "axis_year": "number | null",
    "axis_mood": "string | null",
    "axis_material": "string | null",
    "axis_tags": ["string"]
  }
}
```

> **Image serving**: Django serves images via `MEDIA_URL`. Configure `MEDIA_ROOT` to point at the `images/` directory produced by Make DB Stage 2. Image URLs follow: `/media/images/{building_id}/{order}_{filename}`. Do NOT serve images as frontend static files — they live outside the frontend build and are too large to bundle.

---

## 6. Recommendation Algorithm

Implemented in `backend/apps/recommendation/engine.py` (ported from `ARCHITON/2. analysis/analysis.py`).

### Session Lifecycle

```
1. POST /analysis/sessions
   → Select first 10 diverse images (maximizing embedding distance)
   → Return first image + session_id

2. POST /analysis/sessions/{id}/swipes  (repeated 20 times)
   → Update preference vector:
       like:    pref_vector += 0.5 * image_embedding
       dislike: pref_vector -= 1.0 * image_embedding
   → Normalize vector
   → Epsilon-greedy next selection:
       - epsilon starts at 0.18, decays 0.5%/round, min 0.05
       - With prob epsilon: pick random unexposed building
       - Otherwise: pick top cosine similarity to pref_vector
   → Return next_image + progress

3. GET /analysis/sessions/{id}/result
   → Query top 20 by cosine similarity to final pref_vector
   → Exclude already-exposed buildings
   → Return liked_images + predicted_images
```

### Constants (in `config/settings.py`)

```python
RECOMMENDATION = {
    "total_rounds": 20,
    "like_weight": 0.5,
    "dislike_weight": -1.0,
    "initial_epsilon": 0.18,
    "epsilon_decay": 0.005,
    "min_epsilon": 0.05,
    "initial_explore_rounds": 10,
    "top_k_results": 20,
}
```

---

## 7. LLM Integration (Gemini)

Implemented in `backend/apps/recommendation/services.py`.

### Query Parsing (`/api/parse-query`)

```
Input: "concrete museums in Japan after 2010"

→ Gemini prompt: extract structured filters from natural language

Output:
{
  "structured_filters": {
    "location_country": "Japan",
    "program": "Museum",
    "material": "concrete",
    "year_min": 2010
  },
  "suggestions": []
}
```

### Persona Report (`/projects/{id}/report/generate`)

```
Input: list of liked building_ids (from Project.liked_ids — never slugs)

→ Query PostgreSQL WHERE building_id IN (liked_ids) for building attributes
→ Aggregate top attributes (program, mood, material, country, architect)
→ Gemini prompt: generate architect persona

Output (stored as final_report on Project):
{
  "persona_type": "The Philosopher",
  "one_liner": "You find meaning in weight and shadow.",
  "description": "Your selections reveal a preference for...",
  "dominant_programs": ["Museum", "Education"],
  "dominant_moods": ["minimalist", "introspective"],
  "dominant_materials": ["concrete", "stone"]
}
```

> `dominant_programs` values must come from the normalized vocabulary in `00_FLOW.md` Section 4.5 only. Never use raw building_type strings like "Cultural Center".

---

## 8. Frontend Architecture

### Component Hierarchy

```
App.jsx (state manager)
├── LoginPage
├── SetupPage
│   └── ProjectSetupPage
│       └── LLMSearchPage
├── SwipePage
│   ├── TinderCard (library)
│   └── GalleryOverlay
└── FavoritesPage
    ├── FolderDetail
    │   └── BuildingCard
    └── GalleryOverlay
```

### State Management

- React `useState` + `useEffect` (no Redux/Zustand)
- `AppContext.jsx` for shared state: `userId`, `projects`, `activeProjectId`
- `localStorage` for projects persistence (key: `archithon_projects_{userId}`)
- `sessionStorage` for current session user (key: `archithon_user`)
- `api/client.js` auto-falls back to `localSession.js` if backend unreachable
  - **Offline fallback scope**: `localSession.js` is a **demo-only** fallback using a hardcoded subset of buildings bundled in `src/data/sample_buildings.json` (50–100 entries). It simulates the swipe flow with simplified in-memory state but does NOT run the epsilon-greedy algorithm or Gemini reports. Show a persistent banner: "Offline mode — results are illustrative only."
  - Do NOT attempt to replicate the full recommendation engine client-side. The fallback exists only to let users preview the UI without a backend.

### Styling

- Tailwind CSS utility classes only (no inline style objects)
- CSS variables in `index.css` for theme colors:

```css
:root {
  --color-bg:       #0f0f0f;
  --color-surface:  #1a1a1a;
  --color-border:   #2d2d2d;
  --color-accent:   #3b82f6;
  --color-purple:   #8b5cf6;
  --color-pink:     #f43f5e;
  --color-orange:   #fb923c;
}
```

---

## 9. Environment Variables

### Backend (`.env` in `backend/`)

```env
DJANGO_SECRET_KEY=<generated secret>
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

GEMINI_API_KEY=<google gemini api key>

DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=<password>
DB_NAME=architon

CORS_ALLOWED_ORIGINS=http://localhost:5173

# Social login — obtain from each provider's developer console
GOOGLE_CLIENT_ID=<google oauth client id>
GOOGLE_CLIENT_SECRET=<google oauth client secret>

KAKAO_CLIENT_ID=<kakao rest api key>
KAKAO_CLIENT_SECRET=<kakao client secret (optional for kakao)>

NAVER_CLIENT_ID=<naver client id>
NAVER_CLIENT_SECRET=<naver client secret>
```

### Frontend (`.env` in `frontend/`)

```env
VITE_API_BASE_URL=http://localhost:8001/api/v1

# Social login client IDs (public — safe to expose in frontend)
VITE_GOOGLE_CLIENT_ID=<google oauth client id>
VITE_KAKAO_JS_KEY=<kakao javascript key>
VITE_NAVER_CLIENT_ID=<naver client id>
VITE_NAVER_CALLBACK_URL=http://localhost:5173/auth/naver/callback
```

---

## 10. Code Issues to Fix (from Old Repos)

### Frontend Issues

| # | Issue | Fix |
|---|-------|-----|
| F1 | Massive inline style objects | Replace with Tailwind classes |
| F2 | Empty `catch {}` blocks | Add error logging + user toast/message |
| F3 | Hardcoded API URLs | Use `import.meta.env.VITE_API_BASE_URL` |
| F4 | Props drilling (3-4 levels) | Use `AppContext` for shared state |
| F5 | Hardcoded card dimensions (340x480) | Responsive CSS with aspect-ratio |
| F6 | Unused code: `ResultBoard.jsx`, `raw_database_v5.json`, `vite-project/` | Delete |
| F7 | `localSession.js` Map never cleared | Clear on logout |

### Backend Issues

| # | Issue | Fix |
|---|-------|-----|
| B1 | No tests | Add unit tests (models, algorithm, API) |
| B2 | `DEBUG=True`, `CORS_ALLOW_ALL_ORIGINS=True` | Use `.env` for config |
| B3 | Legacy + Django duplication | Remove `analysis_api_server.py`, consolidate into Django |
| B4 | No logging | Add Python `logging` throughout |
| B5 | Algorithm constants hardcoded | Move to `settings.RECOMMENDATION` dict |
| B6 | No pagination | Add `?page=` and `?limit=` params |
| B7 | API versioning inconsistent | All endpoints under `/api/v1/` |

### Integration Issues

| # | Issue | Fix |
|---|-------|-----|
| I1 | Swipe endpoint mismatch | Backend must expose `POST /sessions/{id}/swipes` (not batch) |
| I2 | LLM runs on separate server | Move `parse-query` into Django: `POST /api/v1/api/parse-query` |
| I3 | DB data mismatch (140 vs 766 buildings) | Use crawler output as single source |
| I4 | Image serving unclear | Serve from Django `MEDIA_URL` or Nginx static |

---

## 11. Reconstruction Phases

### Phase 0 — Clean Frontend (No Backend Needed)

**Goal**: Remove junk, add config, fix styles.

- [ ] Replace `LoginPage` with social login buttons (Google / Kakao / Naver) — no username/password form
- [ ] Delete `vite-project/`, `src/ResultBoard.jsx`, `src/raw_database_v5.json`
- [ ] Move `src/` to `frontend/src/`, update `vite.config.js`
- [ ] Add `frontend/.env` with `VITE_API_BASE_URL`
- [ ] Replace all inline style objects with Tailwind classes
- [ ] Extract theme colors to CSS variables in `index.css`
- [ ] Replace hardcoded card width with `aspect-ratio: 3/4` CSS
- [ ] Replace empty `catch {}` with error logging
- [ ] Add `AppContext.jsx` to eliminate props drilling

### Phase 1 — Backend Setup

**Goal**: Clean Django project connected to the already-populated PostgreSQL.
**Prerequisite**: Make DB Stage 3 must be complete — `architecture_vectors` must have data.

- [ ] Initialize `backend/` directory with Django project
- [ ] Configure PostgreSQL connection in `settings.py` via `.env` (same DB as Make DB Stage 3)
- [ ] Verify connection: `SELECT COUNT(*) FROM architecture_vectors;` should return > 0
- [ ] Create Django models: `UserProfile`, `Project`, `AnalysisSession`, `SwipeEvent`
  - Do NOT create a migration for `architecture_vectors` — it's owned by Make DB
- [ ] Implement social auth endpoints (see Section 5 — Authentication):
  - `POST /api/v1/auth/social/google` — verify Google access token, return JWT
  - `POST /api/v1/auth/social/kakao` — verify Kakao access token, return JWT
  - `POST /api/v1/auth/social/naver` — verify Naver access token, return JWT
  - `POST /api/v1/auth/token/refresh` — refresh JWT
  - `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`
- [ ] Create `SocialAccount` model and handle account linking by email
- [ ] Implement project CRUD: `GET/POST /api/v1/projects`, `PATCH/DELETE /api/v1/projects/{id}`
- [ ] Add logging: Django logger to file + console

### Phase 2 — Recommendation Engine

**Goal**: Port epsilon-greedy vector algorithm cleanly.

- [ ] Create `backend/apps/recommendation/engine.py`
- [ ] Implement `POST /api/v1/analysis/sessions`:
  - Filter candidates by project filters (program, area range)
  - Select 10 diverse initial images via max-distance pgvector query
  - Return first image + session state
- [ ] Implement `POST /api/v1/analysis/sessions/{id}/swipes`:
  - Validate idempotency key
  - Update preference vector (like +0.5, dislike -1.0, normalize)
  - Epsilon-greedy next image selection
  - Detect convergence / round completion
- [ ] Implement `GET /api/v1/analysis/sessions/{id}/result`:
  - Top 20 via pgvector cosine similarity
  - Return `ImageCard` format
- [ ] Implement `GET /api/v1/images/diverse-random`
- [ ] Move algorithm constants to `settings.RECOMMENDATION`
- [ ] Write unit tests for preference vector update logic

### Phase 3 — LLM Integration (Gemini)

**Goal**: Add AI features inside Django.

- [ ] Add `GEMINI_API_KEY` to `.env` and settings
- [ ] Implement `POST /api/v1/api/parse-query`:
  - Prompt Gemini to extract structured filters from natural language
  - Return `{structured_filters, suggestions}`
- [ ] Implement `POST /api/v1/projects/{id}/report/generate`:
  - Aggregate liked building attributes from PostgreSQL
  - Prompt Gemini for persona archetype
  - Store as `final_report` on Project model
- [ ] Implement `GET /api/v1/projects/{id}/report`

### Phase 4 — Frontend ↔ Backend Integration

**Goal**: Wire frontend to real backend, verify full flow.

- [ ] Update `frontend/src/api/client.js` to match Phase 1-3 endpoints exactly
- [ ] Wire LoginPage → social provider SDK → `POST /auth/social/{provider}` → store JWT in `localStorage`
- [ ] Auto-refresh JWT before expiry using `POST /auth/token/refresh`
- [ ] Wire SwipePage → `POST /analysis/sessions` + `POST /sessions/{id}/swipes`
- [ ] Wire FavoritesPage → `GET /sessions/{id}/result` + display Gemini persona report
- [ ] Wire LLMSearchPage → `POST /api/parse-query` (now inside Django, not separate server)
- [ ] Image serving: configure Django `MEDIA_URL` + `MEDIA_ROOT` for building images
- [ ] Test offline fallback: disconnect backend, verify `localSession.js` shows demo flow with "Offline mode" banner and sample_buildings.json data

### Phase 5 — Testing & Polish

**Goal**: Working end-to-end product.

- [ ] Full flow test: login → create project → LLM search → swipe 20 cards → view report
- [ ] Add loading skeletons (image-heavy pages)
- [ ] Add pagination to project list and image endpoints
- [ ] Mobile: fix touch targets, test on 375px viewport
- [ ] Secure settings: `DEBUG=False`, CORS restricted, valid SECRET_KEY
- [ ] Backend integration tests: auth, swipe session, results
- [ ] Fix all issues from Section 10

---

## 12. Scripts

### Frontend

```bash
cd frontend/
npm install
npm run dev          # http://localhost:5173
npm run build
npm run lint
```

### Backend

`backend/requirements.txt` must include:

```
django>=6.0.3
djangorestframework>=3.16.1
djangorestframework-simplejwt>=5.3.1
social-auth-app-django>=5.4.1
django-cors-headers>=4.9.0
psycopg2-binary>=2.9.11
pgvector>=0.3.0
google-genai>=1.10.0
python-dotenv>=1.0.0
requests>=2.31.0        # for verifying tokens with provider APIs
```

```bash
cd backend/
pip install -r requirements.txt
python manage.py migrate          # only migrates Django models (NOT architecture_vectors)
python manage.py createsuperuser
python manage.py runserver 8001   # http://localhost:8001
```

> No data loading step. PostgreSQL is already populated by Make DB Stage 3.

---

*See `00_FLOW.md` for shared DB schema and overall system architecture.*
*See `01_MAKE_DB.md` for Stage 1–3 (Crawl, ML, PostgreSQL).*
*Old frontend ref: https://github.com/yywon1/archithon-app*
*Old backend ref: https://github.com/dain75954929-wq/ARCHITON/*
*Last updated: 2026-03-27*
