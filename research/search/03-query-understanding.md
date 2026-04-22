# Query Understanding: Parsed Filters + Semantic Recovery of the Raw Query

## Status
Ready for Implementation

## Question
Beyond adding a lexical/BM25 channel (topic 01), how should archi-tinder recover the *semantic* content of a user's NL query — which today is parsed into SQL filters and then discarded — given our hard constraint that the 384-dim MiniLM embedding model is not a local dependency?

## TL;DR
- **The algorithm spec already assumes HyDE and the implementation silently dropped it.** `research/algorithm.md:13-16` mandates that Phase 0 embeds an LLM-generated visual-description paragraph into `V_initial` and uses it for cosine pool ranking. The live code at `backend/apps/recommendation/engine.py:289-367` skips that step entirely — pool creation is pure `CASE WHEN` on parsed filters, no query-derived vector is ever computed. Fixing this closes a larger gap than any new-technique addition.
- **Recommended path**: *session-aware LLM query expansion fed to topic 01's lexical channel* as the no-new-infra first ship, plus a **flag-gated HyDE V_initial** using the HuggingFace Inference API on the exact same `paraphrase-multilingual-MiniLM-L12-v2` model (384-dim, identical vector space, remote call — does not violate the "no local SentenceTransformers" rule). Gemini's embedding API is ruled out (min 768-dim; Matryoshka truncation to 384 not tested per Google docs).
- **Defer**: α-weighted query/preference blend inside the MMR phase; full Query2doc pseudo-document concatenation for lexical. Both are small deltas once the V_initial + session-aware pieces land.

## Context (Current State)

The raw NL query is lost at two distinct points, both in the semantic path:

- `backend/apps/recommendation/services.py:93-134` — `parse_query()` returns `{reply, filters, filter_priority}` and the **raw text is not in the return value**. Non-filter tokens (e.g., "courtyard", "louvre", "feels protective") are discarded.
- `backend/apps/recommendation/engine.py:289-367` — `create_bounded_pool()` receives only `filters` + `filter_priority` + `seed_ids`. It builds a pool via weighted `CASE WHEN` on eight filter fields; **there is no text embedding involved at any step**. This directly contradicts the algorithm spec.
- `backend/apps/recommendation/views.py:859-889` — `ParseQueryView.post()` calls `parse_query()` then immediately discards `query` (only `parsed['filters']`, `parsed['reply']`, `parsed['filter_priority']` are returned).
- `research/algorithm.md:13-16` (Phase 0 definition) — explicitly specifies: *"The LLM generates a rich, paragraph-length visual description of the ideal architecture based on the prompt. This text is embedded using the paraphrase-multilingual-MiniLM-L12-v2 model to create the initial vector V_initial. Fetch the top N items that pass the hard filters and have the highest cosine similarity to V_initial."* — this is textbook HyDE.
- `CLAUDE.md` — states "SentenceTransformers is NOT a dependency here — embeddings are pre-computed." This constrains *local* embedding, not remote. A remote Inference API call to the same model family produces vectors in the same 384-dim space without importing the library.
- `architecture_vectors.embedding` is `VECTOR(384)` and was produced with `paraphrase-multilingual-MiniLM-L12-v2` ([HuggingFace model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) confirms 384-dim, 50-language support, and Inference API availability).

Consequence of the current state: a query like "minimalist concrete housing with a sense of refuge" becomes `{program: Housing, style: Minimalist?, material: Concrete}` — the "sense of refuge" semantic is completely lost, and the spec's compensating mechanism (V_initial HyDE) is absent from the code.

## Findings

### 1. The "discarded raw query" problem has four named remedies in the literature
The recent query-optimization survey ([Liu et al. 2024, *A Survey of Query Optimization in LLMs*](https://arxiv.org/html/2412.17558)) organizes the space as: **query expansion**, **query decomposition**, **query disambiguation**, **query abstraction**. Ranked by latency: expansion (one extra LLM call, cheapest) < disambiguation < abstraction < decomposition (multi-call, error cascades). For sparse/lexical retrievers, Query2doc-style expansion dominates; for dense retrievers, HyDE-style or embedding-blend methods lead.

### 2. HyDE: what it is and why our algorithm spec already describes it
[Gao et al. 2023, *Precise Zero-Shot Dense Retrieval without Relevance Labels* (ACL)](https://aclanthology.org/2023.acl-long.99/) — HyDE works in four steps: (1) prompt an instruction-following LLM to write a hypothetical answer/document for the query, (2) embed that hypothetical document with **the same encoder used for the corpus**, (3) use the resulting vector as the retrieval key, (4) let "the encoder's dense bottleneck" filter hallucinations by projecting to the real-corpus neighborhood. The method outperforms Contriever unsupervised baselines across tasks and generalizes to non-English. Our algorithm.md Phase 0 is a domain-specialized HyDE: the "hypothetical document" is a visual description of the ideal building. The **requirement is that generated-document embedding and corpus embedding share a model** — hence the 384-dim MiniLM lock-in.

### 3. HyDE latency and cost in production
- Added latency: one LLM generation per query, typically **25–60%** over plain dense retrieval on small LLMs, up to +43–60% on Gemma 1B/4B ([HyDE vs RAG comparison](https://beyondscale.tech/blog/hyde-vs-rag-retrieval-augmented-generation), [Milvus HyDE primer](https://milvus.io/ai-quick-reference/what-is-hyde-hypothetical-document-embeddings-and-when-should-i-use-it)).
- Our cost context: we already call Gemini 2.5-flash once per session-start in `parse_query()`. Expanding that single call to produce both `filters` and a `visual_description` paragraph is ~zero marginal latency. The remaining cost is the 384-dim embedding call. Against a session that subsequently runs 15–25 swipes, one additional 200–400 ms embedding call amortizes cleanly.
- HyDE's hallucination risk ([Zilliz HyDE analysis](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings)) is mitigated here because the vector is only used to *rank* a bounded pool that still respects hard filters — the worst case is mis-ordering, not surfacing nonsense.

### 4. Query2doc and the rewriting→lexical-channel handoff
[Wang et al. 2023, *Query2doc* (arXiv:2303.07678)](https://arxiv.org/abs/2303.07678) — generate a pseudo-document with an LLM, **concatenate it to the original query string**, and hand the concatenated text to BM25. Works for sparse retrievers; improvements transfer to dense retrievers at smaller magnitudes. Elastic's production-search team observes: "When using dense vector search or hybrid retrieval, simple query rewriting terms offer marginal gains. The best results come from using QR to *boost* existing hybrid scores rather than replacing them" ([Elastic Search Labs on LLM query rewriting](https://www.elastic.co/search-labs/blog/query-rewriting-llm-search-improve)). Practical conclusion for us: *the LLM-generated visual description is the same artifact that (a) HyDE embeds for V_initial and (b) Query2doc hands to tsvector for topic 01's lexical branch.* One LLM call, two retrieval channels.

### 5. Session-aware rewriting without any embedding
[Zuo et al. 2023, *Context-Aware Query Rewriting for E-Commerce* (ACL Industry)](https://aclanthology.org/2023.acl-industry.59/) — session history disambiguates vague intent dramatically on e-commerce. The archi-tinder analog: mid-session, the user has liked 3–5 buildings; a Gemini rewrite prompt that takes `raw_query + liked_buildings` and produces an enriched rewrite is pure-LLM, no embedding, no new infra. This is the cheapest win when a user types a new query *into an existing session* (e.g., after initial convergence the user types "more like the one with the copper roof"). Not relevant to cold start, but highly relevant to follow-up queries.

### 6. Multilingual / Korean considerations
[Kim et al. 2025, *Improving Korean-English Cross-Lingual Retrieval* (arXiv:2507.08480)](https://arxiv.org/html/2507.08480) — multilingual encoders carry the bulk of CLIR load; lexical channels benefit from explicit English-rewriting when most documents are English-dominant. Our `architecture_vectors` has English-dominant text fields (`visual_description`, `tags`, `name_en`). For Korean queries, the Gemini rewrite can emit bilingual output: Korean-preserving for the semantic (V_initial) side, English-expanded for the lexical side.

### 7. Embedding-dimension compatibility (the constraint that picks the tech)
- `paraphrase-multilingual-MiniLM-L12-v2`: **384-dim**, 50 languages, available via HuggingFace Inference API ([HF model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)).
- Gemini embedding (`gemini-embedding-001` / `text-embedding-004`): MRL-based with supported outputs of **128–3072**; docs recommend 768/1536/3072; **384 is not in the recommended or validated set** ([Gemini Embeddings docs](https://ai.google.dev/gemini-api/docs/embeddings)). MRL *permits* truncation but Google's docs do not confirm 384 has quality parity.
- Even if we truncated Gemini embeddings to 384, the resulting vectors live in *Gemini's* representation space, not MiniLM's. Cosine similarity between a Gemini-384 query and a MiniLM-384 building embedding is ill-defined — they are different geometries. **Ruled out**.
- HF Inference API on the exact MiniLM model yields vectors in the *same* space as our stored embeddings. Cost: free tier ~50 req/hr, PRO ~$9/mo with 20× credits, dedicated endpoints for higher volume ([HF Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing)). Cold-start on first request can add 2–5 s ([AWS SageMaker Serverless HF cold start note](https://aws.amazon.com/blogs/machine-learning/host-hugging-face-transformer-models-using-amazon-sagemaker-serverless-inference/)); acceptable if mitigated with a warm-up ping after Django boot.

### 8. Alpha-weighted query⊕preference blend
[Superlinked VectorHub: Personalized Search](https://superlinked.com/vectorhub/articles/personalized-search-vector-embeddings) — "arithmetically adding the query vector and the user preference vector to create a new query vector" is a common pattern. Vespa formalizes it in rank profiles, e.g. `log(bm25(text)) + 0.5 * closeness(field, embedding)` ([Vespa Neural Search Tutorial — Sease](https://sease.io/2023/02/vespa-neural-search-tutorial.html)). **Our constraint**: we'd need the query embedding anyway — which is exactly what Option C below produces. Once V_initial exists, blending is a trivial per-phase α schedule.

## Options

### Option A — Session-aware LLM rewriting only (no embedding)
Extend `parse_query()` to return a `rewritten_query` and `expanded_keywords` list alongside filters. In mid-session follow-up queries, feed liked-building summaries into the rewrite prompt. Use `expanded_keywords` as a `should` clause on topic 01's tsvector channel. No V_initial, no new dependency.
- Pros: Zero new infra; one extra ~200 ms Gemini call on the existing LLM path; cleanly hands to topic 01's lexical branch.
- Cons: Doesn't close the algorithm.md Phase 0 spec gap; pure-cosine pool ranking still misses the semantic of the query; fails on queries that *must* hit the semantic channel (e.g., "a building that feels hopeful").
- Complexity: **Low** (~half day on the backend).
- Expected impact: Medium on follow-up queries, small on cold-start.

### Option B — Blend Gemini embedding of the rewritten query with preference vector
Embed the Gemini-rewritten query via `text-embedding-004`, truncate MRL to 384, blend `α·q_embed + (1-α)·pref_vec`.
- Pros: Uses the Gemini SDK already in the codebase.
- Cons: **Cross-space comparison.** Gemini's 384-truncated embedding does not share geometry with MiniLM's 384; `cosine(gemini_384_vec, minilm_384_vec)` is not a well-defined similarity. Google does not confirm MRL parity at 384. **Broken at first principles.**
- Complexity: Low to implement, but the output is wrong.
- Expected impact: **Negative or random.** Do not ship.

### Option C — HyDE V_initial via HuggingFace Inference API (recommended)
Restore the algorithm.md Phase 0 HyDE path: after `parse_query()` returns filters, run a second Gemini call (or combine with the first via a richer JSON schema) producing a paragraph-length `visual_description`. POST that to `https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` to obtain a 384-dim vector in the *same embedding space* as the stored building embeddings. Replace or re-score the current CASE WHEN pool with cosine similarity to that vector. Respects the "no local SentenceTransformers" rule (remote call, no pip dependency).
- Pros: Closes the algorithm.md Phase 0 spec gap directly; uses the exact corpus encoder so vectors are geometrically valid; keeps filter-priority as a pre-filter; cleanly composes with topic 01's lexical branch (the same generated description is the Query2doc pseudo-doc); provides the missing V_initial for future α-blend options; handles multilingual queries because MiniLM is multilingual end-to-end.
- Cons: New external dependency (HF Inference API) — requires API token, rate-limit handling, cold-start warmup, fallback to pure-filter path on failure. Adds ~300–600 ms to cold start (one LLM call + one embedding call); acceptable given the one-per-session cost amortized over 15–25 swipes.
- Complexity: **Medium** (1–2 days: prompt change, HF client, flag, fallback, migration).
- Expected impact: **Highest among options** — restores a core design decision that was silently dropped, improves pool quality on every semantic-nuanced query, and unlocks downstream α-blend and lexical-channel gains with zero new moving parts.

### Option D — Full Query2doc pseudo-document to lexical channel only
Generate a Query2doc pseudo-document, concatenate with the raw query, pass to topic 01's `plainto_tsquery`. No embedding.
- Pros: Strong precedent for sparse retrieval gains ([Wang et al. 2023](https://arxiv.org/abs/2303.07678)); no new dep beyond what topic 01 introduces.
- Cons: Does not touch the semantic side at all; we still have the "raw query discarded in the vector path" problem; only as good as the lexical channel from topic 01. Doesn't close the Phase 0 gap.
- Complexity: Low once topic 01 ships.
- Expected impact: Medium on lexical-side retrieval; zero on cosine side.

## Recommendation

**Ship Option C as the primary fix, with Option A's session-aware rewriting bolted on as a free extension of the same Gemini prompt change.** Both become one commit series, because the mechanism is a single Gemini call that now returns four fields instead of three: `{reply, filters, filter_priority, visual_description}`. The `visual_description` serves three consumers:
1. HF Inference API → 384-dim V_initial vector → used by a new `create_bounded_pool_hybrid()` path that re-ranks the CASE WHEN pool by cosine to V_initial (or replaces it in the no-filter case).
2. Topic 01's tsvector branch (Query2doc-style) — concatenated to the raw query before `plainto_tsquery`.
3. Mid-session rewrite prompt input — when a user submits a second NL query in an existing session, Gemini sees the liked-building summary alongside the raw query and emits a more specific `visual_description`.

**Defer Option B permanently** unless Google publishes validated MiniLM-compatible embeddings or we rebuild the corpus with Gemini-native embeddings (a Make DB–owned decision per `CLAUDE.md`). **Defer Option D** — topic 01 can pick it up directly as an extension of its lexical branch.

Flag everything behind `HYDE_VINITIAL_ENABLED` in `config/settings.py` so initial deployment is pure-filter-only, then flipped after a benchmarking run via `algo-tester`.

## Open Questions

- **HF Inference API reliability SLO.** Free tier rate limit (~50/hr) and cold start (2–5 s) are real. For production, a paid dedicated endpoint or a tiny FastAPI sidecar container that loads the model once costs less and is more predictable. Need to measure first. If HF free tier is insufficient, the sidecar option must be weighed against `CLAUDE.md`'s "not a dependency" rule — a sidecar service is architecturally distinct from an in-process dependency. Recommend raising the question with the team before scaling.
- **When does V_initial stop being useful?** Once the user has liked 3+ buildings, the preference vector dominates. Algorithm.md says V_initial seeds the pool, then K-Means takes over. Should V_initial be retained as a weak prior via `α·V_initial + (1-α)·pref_vec` during the exploring phase only? Decay schedule TBD.
- **Prompt stability for visual-description generation.** A one-paragraph hypothetical document is more structurally variable than a filter JSON. Need a few-shot prompt with architectural vocabulary anchors so outputs stay within the corpus's lexical distribution.
- **Fallback ordering.** If HF call fails, current pure-CASE-WHEN path is the fallback. If Gemini call fails, current fallback in services.py:131 returns empty filters. Need clear precedence: filter-failure → random; embedding-failure → filter-only ranking.
- **Multilingual rewriting prompt.** When query is Korean, should `visual_description` be produced in Korean (MiniLM is multilingual, vectors comparable), English (matches corpus text), or bilingual? Recommend a single bilingual paragraph — MiniLM handles both; topic 01's `'simple'` tsvector also tolerates both.
- **Cache key for V_initial.** Same query text should not re-embed. Recommend a small LRU keyed on `hash(visual_description)` keyed at the process level; invalidate when prompt version changes.

## Proposed Tasks for Main Terminal

All changes are in `backend/apps/recommendation/` + one settings entry + one optional sidecar question to the ops lane. No frontend or schema changes.

1. **BACK-QU-1** — `services.py:_PARSE_QUERY_PROMPT`: extend the prompt schema to produce `visual_description: string` (1 paragraph, 60–120 words, architectural vocabulary). Return it from `parse_query()` alongside existing fields: `{'reply', 'filters', 'filter_priority', 'visual_description', 'raw_query'}`. Include two few-shot examples anchoring style, material, spatial-feel vocabulary.
2. **BACK-QU-2** — `services.py` new function `embed_hypothetical(text: str) -> list[float] | None`: POST to `https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` with `{"inputs": text, "options": {"wait_for_model": true}}`. Return 384-float vector. On 503/timeout, retry once after 3 s; on permanent failure, return `None`. Read `HUGGINGFACE_API_TOKEN` from settings; warm-up ping at Django app-ready.
3. **BACK-QU-3** — `engine.py` new function `create_bounded_pool_hybrid(filters, filter_priority, v_initial, seed_ids, target)`: if `v_initial` is non-None, first apply the CASE WHEN filter pass to shortlist (LIMIT `2*target`), then `ORDER BY embedding <=> %s::vector LIMIT %s` against `v_initial` for final ordering. If `v_initial` is None, fall through to existing `create_bounded_pool()`. Preserve the `seed_ids` force-include behavior.
4. **BACK-QU-4** — `views.py:ParseQueryView.post()` and any session-create view that calls `create_bounded_pool`: after `parse_query()`, call `embed_hypothetical(parsed['visual_description'])`, then call `create_bounded_pool_hybrid(..., v_initial=v)` when `settings.RECOMMENDATION['HYDE_VINITIAL_ENABLED']` is True. When False, existing code path unchanged.
5. **BACK-QU-5** — `config/settings.py` `RECOMMENDATION` dict (lines ~131-144): add `HYDE_VINITIAL_ENABLED: False`, `HYDE_V_ALPHA: 1.0` (future α-blend for exploring phase, currently unused). Add top-level `HUGGINGFACE_API_TOKEN = env('HUGGINGFACE_API_TOKEN', default='')`.
6. **BACK-QU-6** — `services.py` extend `parse_query()` to accept optional `session_context: dict | None` with `{'liked_summaries': [...]}`. When provided, the Gemini prompt is augmented with liked-building summary context so `visual_description` is session-personalized. Used only for mid-session re-query, not cold start.
7. **BACK-QU-7** — Module-level LRU cache on `embed_hypothetical` keyed by `hash(text) + prompt_version_tag`; cap 128 entries to keep memory flat. Invalidate on prompt version bump.
8. **BACK-QU-8** — Handshake with topic 01: when `01-hybrid-retrieval` lands, its tsvector branch should consume `parsed['raw_query'] + ' ' + parsed['visual_description']` as the Query2doc pseudo-document fed to `plainto_tsquery`. Left as coordination item for the orchestrator, not a code change in this topic.
9. **TEST-QU-1** — `backend/tests/test_sessions.py`: two parametrized tests — flag=False asserts the code path is identical to the pre-change pool creation; flag=True with mocked `embed_hypothetical` returning a canned 384-vector asserts `create_bounded_pool_hybrid` is called and the result is re-ranked by cosine. Also test the HF 503 path: `embed_hypothetical` returns None, behavior degrades to existing `create_bounded_pool` with no error surfaced to the user.
10. **ALGO-QU-1** — After shipping flag-off, run algo-tester comparing precision/recall of the top 20 bounded-pool buildings (vs a held-out persona "ideal set") across flag states. Target: no regression in like rate, measurable precision lift on queries with > 3 non-filter tokens. If positive, flip the flag in production.

## Sources

- [Gao, Ma, Lin, Callan 2023 — Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE), ACL Anthology](https://aclanthology.org/2023.acl-long.99/) — canonical HyDE paper.
- [HyDE on arXiv (2212.10496)](https://arxiv.org/abs/2212.10496)
- [Wang et al. 2023 — Query2doc: Query Expansion with LLMs, arXiv 2303.07678](https://arxiv.org/abs/2303.07678)
- [Liu et al. 2024 — A Survey of Query Optimization in Large Language Models, arXiv 2412.17558](https://arxiv.org/html/2412.17558) — taxonomy: expansion/decomposition/disambiguation/abstraction.
- [Zuo et al. 2023 — Context-Aware Query Rewriting for E-Commerce, ACL Industry Track](https://aclanthology.org/2023.acl-industry.59/) — session-aware rewriting precedent.
- [Kim et al. 2025 — Improving Korean-English Cross-Lingual Retrieval, arXiv 2507.08480](https://arxiv.org/html/2507.08480) — multilingual rewriting considerations.
- [Elastic Search Labs — Query rewriting strategies for LLMs & search engines](https://www.elastic.co/search-labs/blog/query-rewriting-llm-search-improve) — production observation that rewriting helps lexical more than dense.
- [Superlinked VectorHub — Personalized Search with Vector Embeddings](https://superlinked.com/vectorhub/articles/personalized-search-vector-embeddings) — α-blend pattern.
- [Vespa Neural Search Tutorial — Sease](https://sease.io/2023/02/vespa-neural-search-tutorial.html) — rank-profile alpha weighting in production.
- [HuggingFace model card — sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) — 384-dim confirmation, Inference API availability.
- [HuggingFace Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing) — free tier, PRO, dedicated endpoint tiers.
- [Google Gemini Embeddings docs](https://ai.google.dev/gemini-api/docs/embeddings) — MRL, supported dimensions, recommendation that 384 is not in the validated set.
- [Milvus HyDE reference](https://milvus.io/ai-quick-reference/what-is-hyde-hypothetical-document-embeddings-and-when-should-i-use-it) — latency and when-to-use analysis.
- [Zilliz — Better RAG with HyDE](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings) — hallucination-risk mitigation.
- [BeyondScale — HyDE vs RAG retrieval comparison](https://beyondscale.tech/blog/hyde-vs-rag-retrieval-augmented-generation) — +25-60% latency numbers.
