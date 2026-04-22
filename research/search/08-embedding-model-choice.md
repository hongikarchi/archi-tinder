# Embedding Model Choice: 384-dim Multilingual MiniLM vs 768+ Text / Multi-Modal CLIP-Class

## Status
Research — Coordination Item (Make DB–dominant decision)

## Question
Our corpus is embedded with `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, text-only, multilingual; 118 M params). Should the 3,465-row `architecture_vectors` corpus be re-embedded with a higher-dimensional text model (768–1024), a domain-specific architectural encoder, or a multi-modal CLIP-class model that also sees `image_photos`? What are the quality / cost / migration trade-offs, and how do we respect `CLAUDE.md`'s boundary that `architecture_vectors` is owned by Make DB?

## TL;DR
- **Do not swap the text encoder alone.** A text-only replacement (BGE-M3 1024, multilingual-E5-large-instruct 1024) delivers measurable MTEB gains but (a) invalidates topic 03's HyDE plan, which specifically relies on the MiniLM vector space, (b) forces a schema migration on a Make-DB-owned table, and (c) does nothing about the genuinely missing channel — **the building images are never used for retrieval**.
- **Recommended direction**: propose to the Make DB team an **additive multi-modal channel**: a new `image_embedding VECTOR(768)` or `VECTOR(1024)` column populated by **SigLIP 2** (Google, Feb 2025) or **jina-clip-v2** (Jina AI, Dec 2024). The existing 384-dim text `embedding` column stays put; topics 01–06 continue to work; a future hybrid can blend text-cosine and image-cosine via RRF once the column exists.
- **Reject** a domain-specific architectural encoder (no off-the-shelf exists; fine-tuning 3,465 unlabeled buildings is a research project, not a ship item) and **reject** Matryoshka-truncating a new 1024-dim encoder to 384 to avoid schema change (cross-space cosine — same class of error as Gemini→MiniLM already ruled out in topic 03).
- **Cost is trivially small** (3,465 images × ~0.5 s on T4 ≈ 30 min; storage delta 384→1024 ≈ 5 MB → 14 MB total). The barrier is coordination with Make DB and downstream re-tuning, not compute or dollars.

## Context (Current State)

- **Schema** (`CLAUDE.md:199-228`): `architecture_vectors.embedding VECTOR(384) NOT NULL`, owned by Make DB, read-only from this repo.
- **Encoder lineage** (`research/algorithm.md:13-16`): corpus embeddings were produced by `paraphrase-multilingual-MiniLM-L12-v2` on the `visual_description` + metadata concatenation. The same model is assumed by topic 03's HyDE plan for query-side vectors.
- **Corpus size** (`.claude/Report.md:26`): **3,465 buildings**. Brute-force cosine at this scale is ~3 ms on pgvector even without HNSW (topic 07).
- **Image fields present but unused for retrieval**: `architecture_vectors.image_photos TEXT[]`, `image_drawings TEXT[]` (`CLAUDE.md:222-223`). Currently consumed only by `_row_to_card()` (`backend/apps/recommendation/engine.py:28-50`) to build Cloudflare R2 URLs for display. **No vector, no rank signal, ever derived from the images.**
- **Konstraints** (`CLAUDE.md:8-12`): SentenceTransformers is not a local dependency here; re-embedding cannot happen in Make Web. Any encoder change is a Make DB migration.
- **Downstream contracts**: topic 01 (hybrid tsvector + cosine), topic 02 (Gemini setwise rerank), topic 03 (HyDE V_initial via HF Inference API on the same MiniLM), topic 04 (DPP on the embedding column), topic 06 (K-Means on 384-dim likes). Topics 03 and 06 have geometry-specific dependencies on the current 384-dim MiniLM space; topics 01, 02, 04, 07 are encoder-agnostic.

## Findings

### 1. MiniLM is a legitimate weak baseline in 2026 multilingual MTEB
MiniLM-L12 (22–33 M params for the distilled family) is a distilled encoder designed for speed — "lightning-fast but less semantic depth than larger models... not ideal for long documents or nuanced multi-paragraph retrieval" ([Modal, top MTEB models](https://modal.com/blog/mteb-leaderboard-article)). On MMTEB it is routinely outperformed by the open-source multilingual E5 family and BGE-M3 ([MMTEB, arXiv 2502.13595](https://arxiv.org/abs/2502.13595); [Towards Data Science, multilingual embedding survey](https://towardsdatascience.com/how-to-find-the-best-multilingual-embedding-model-for-your-rag-40325c308ebb/)). The degradation is sharpest on low-resource languages and on long, nuanced prose — which describes our `visual_description` field exactly.

### 2. Text-encoder upgrades: BGE-M3 and multilingual-E5 lead, both at 1024-dim
- **BGE-M3** (BAAI, 568 M params, 1024-dim, XLM-Roberta backbone, 8,192-token context): state-of-the-art on multilingual and long-document MTEB retrieval; explicit Korean benchmark leadership ([HuggingFace model card](https://huggingface.co/BAAI/bge-m3); [arXiv 2402.03216](https://arxiv.org/abs/2402.03216)). Simultaneously supports dense, multi-vector (ColBERT-style) and sparse retrieval from one forward pass.
- **multilingual-E5-large-instruct** (Microsoft, 560 M params, 1024-dim): top publicly available model on MMTEB, outperforming much larger Mistral-based embedders on MTEB(Europe) ([MMTEB paper](https://arxiv.org/html/2502.13595v4)).
- Both are 1024-dim; neither is MRL-trained at its base release; truncating either to 384 to reuse our column **is not geometry-preserving** (the first 384 dims were never optimized as a standalone retrieval space). This is the exact failure class identified in topic 03 §7 (Gemini→MiniLM) and must not be repeated.
- A full text-encoder swap forces: (a) all 3,465 rows re-embedded in Make DB, (b) `embedding` column type changed `VECTOR(384) → VECTOR(1024)`, (c) topic 03's HF-Inference query-side path re-pointed at the new encoder, (d) K-Means centroids stored in session DB become meaningless (different geometry) — active sessions would need to be flushed or migrated.

### 3. Multi-modal: the channel we're currently ignoring
Architecture is, almost tautologically, a visually-driven domain. Text descriptions are incomplete — massing, material texture, light quality, scale, and tectonic expression are partially captured in `visual_description` at best. The images are the primary artifact. Three viable multilingual multi-modal encoders exist as of April 2026:

- **SigLIP 2** (Google DeepMind, Feb 2025, arXiv 2502.14786): multilingual ViT-B/L/So400m/g family; 768-dim default at ViT-B; trained on WebLI (10 B images, 12 B alt-texts, 109 languages) with a Gemma-tokenizer text tower; "outperforms SigLIP at all model scales in zero-shot classification, image-text retrieval, and VLM transfer" ([arXiv 2502.14786](https://arxiv.org/abs/2502.14786); [HuggingFace blog](https://huggingface.co/blog/siglip2)). Korean falls inside the 109-language training mix.
- **jina-clip-v2** (Jina AI, Dec 2024, arXiv 2412.08802): 1024-dim, **Matryoshka-native down to 64 dims** — "94% dimension reduction yields only 8% drop in top-5 accuracy" ([Jina blog](https://jina.ai/news/jina-clip-v2-multilingual-multimodal-embeddings-for-text-and-images/)). Korean is on the explicitly tuned language list alongside 29 others ([HuggingFace card](https://huggingface.co/jinaai/jina-clip-v2)). Achieves 98.0 % on Flickr30k image-to-text, beating NLLB-CLIP-SigLIP and its own v1.
- **NLLB-CLIP / M-CLIP**: older multilingual CLIPs; useful on low-resource languages but systematically behind jina-clip-v2 and SigLIP 2 on mainstream multilingual retrieval ([NLLB-CLIP paper, NeurIPS ENLSP](https://neurips2023-enlsp.github.io/papers/paper_2.pdf); [Jina v2 comparison](https://arxiv.org/html/2412.08802v2)).

Fashion and real-estate platforms have shown ≥ double-digit lifts from CLIP-class multi-modal search over text-only baselines on visually-dense corpora ([Medium, multimodal real-estate search with CLIP](https://medium.com/@etechoptimist/real-estate-with-multimodal-search-langchain-clip-semantic-search-and-chromadb-while-ensuring-factual-accuracy-in-ai-outputs-43fb42291812); [Towards Data Science, fine-tuning multimodal embedding models](https://towardsdatascience.com/fine-tuning-multimodal-embedding-models-bf007b1c5da5/)). Architecture is the same kind of domain.

### 4. Domain-specific architectural encoder: reject, not defer
There is no publicly released encoder fine-tuned on an architectural corpus. Fine-tuning a CLIP-class model on our 3,465 buildings would require (a) paired (image, text) supervision, which we have as `(image_photos[i], visual_description)`, and (b) ideally preference or triplet data, which we do **not** have — the swipe logs are not yet volumed or structured for training ([topic 05 notes on absent labels](research/search/05-preference-weight-learning.md)). Fine-tuning ≥ 1,000 pair examples does yield meaningful domain adaptation ([Shaw Talebi, fine-tuning multimodal embeddings](https://towardsdatascience.com/fine-tuning-multimodal-embedding-models-bf007b1c5da5/)), but that is a separate project, not a swap. **Ship a strong general-purpose multimodal first; fine-tune later if the general model underperforms.**

### 5. Cost framing: re-embed is not the bottleneck, coordination is
- **Image re-embed**: ViT-L CLIP runs ~0.5 s/image on a T4 ([Roboflow Inference, CLIP benchmarks](https://inference.roboflow.com/foundation/clip/)); 3,465 buildings × average 3 photos ≈ 10,400 images ≈ 1.4 h on T4, minutes on an A100. Jina's hosted API or the HuggingFace Inference API can re-embed the entire corpus for < $50.
- **Text re-embed** (if we also swap the text encoder): 3,465 rows × a 1024-dim encoder forward pass ≈ seconds on any GPU, trivially cheap through API.
- **Storage**: 384→1024 dim is 1.5 KB → 4 KB per row × 3,465 ≈ 14 MB. Adding a second 1024-dim image column ≈ 14 MB additional. Neon tier cost impact: negligible. HNSW index memory at this scale (`N × D × 4 × 2` rule of thumb, [pgvector scaling guide](https://dev.to/philip_mcclarence_2ef9475/scaling-pgvector-memory-quantization-and-index-build-strategies-8m2)): ~55 MB per column — still negligible.
- **What actually costs**: (a) Make DB team approving a new column on a shared schema, (b) choosing which photo per building (cover? all? mean-pooled?), (c) a migration plan that does not break live sessions, (d) re-tuning Optuna hyperparameters against the new geometry.

### 6. Korean preservation narrows the list hard
Monolingual OpenCLIP / OpenAI CLIP are English-only and must be ruled out (our query path, via topic 03's HyDE generator and Gemini rewriter, can emit Korean or bilingual text). Viable multimodal: **SigLIP 2 (109 langs)** and **jina-clip-v2 (89 langs, Korean on explicit-tune list)**. Viable text replacement: **BGE-M3** (Korean-SOTA among open multilingual), **multilingual-E5-large-instruct**. Everything else on the current leaderboard is either English-only or untested on Korean.

### 7. The cross-topic conflict with topic 03 (HyDE) matters
Topic 03 ships flag-gated HyDE via HF Inference on the *same* MiniLM that produced the corpus. If the corpus is re-embedded with a non-MiniLM encoder (Options C or D below), topic 03's HF call must be re-pointed at whatever the new encoder is — a real-but-contained change. However, if the new encoder is **additive only** (Option B), topic 03 is unaffected: the text column stays MiniLM, HyDE stays MiniLM, the new image channel is orthogonal.

## Options

### Option A — Do nothing; stay on 384-dim MiniLM (null)
- Pros: Zero coordination cost; all seven prior research topics keep their geometric assumptions.
- Cons: Image content is never ranked; multilingual text retrieval underperforms SOTA by measurable MTEB margins; the "nuanced multi-paragraph" weakness directly bites our `visual_description` field.
- Complexity: None.
- Expected impact: Zero — and zero is the honest number if we don't decide.

### Option B — Additive image channel (RECOMMENDED direction)
Keep `embedding VECTOR(384)` as-is. Add a new `image_embedding VECTOR(768)` (SigLIP 2) or `VECTOR(1024)` (jina-clip-v2) column on `architecture_vectors`, populated from the cover photo or a mean of all `image_photos`. Query-side: generate an image-aligned text query via the same multimodal encoder's text tower; retrieve via both channels and fuse (RRF or weighted rank).
- Pros: Non-destructive — existing text channel and all seven prior research recommendations still hold; preserves topic 03's MiniLM HyDE intact; unlocks the visual channel that was always the obvious gap; Korean preserved in both encoder families.
- Cons: Schema addition requires Make DB coordination (per `CLAUDE.md:9`, the table is Make-DB-owned). Introduces a choice of "which photo" per building. Make Web needs a query-side multimodal embedding call (new API surface — but consistent with topic 03's pattern of HF Inference calls).
- Complexity: **Medium** on the Make DB side (new column + re-embed pipeline); **Medium** on Make Web (query embed + RRF fusion in pool creation).
- Expected impact: **Highest among options on corpus quality**, because it closes the "images never ranked" gap. Text-only MTEB wins would be incremental; adding an orthogonal channel is categorical.

### Option C — Text-encoder upgrade (BGE-M3 or multilingual-E5-large-instruct, 1024-dim)
Replace `embedding VECTOR(384) → VECTOR(1024)` by re-embedding all 3,465 rows with BGE-M3 or multilingual-E5-large-instruct.
- Pros: Measurable MTEB lift on multilingual retrieval; BGE-M3's 8,192-token context lets the full `visual_description` fit without truncation; both models are state-of-the-art on Korean benchmarks.
- Cons: Forces schema change on a Make-DB-owned table; invalidates topic 03's HyDE plan until the HF-Inference endpoint is re-pointed; stored session K-Means centroids become geometrically meaningless (must flush or migrate); does not address the visual channel at all — best case the images remain decorative.
- Complexity: **High** (schema migration + HF endpoint swap + session data invalidation + Optuna re-tune across 12 hyperparameters).
- Expected impact: Medium on text-only retrieval quality; zero on the visual gap.

### Option D — Unified multimodal replacement (jina-clip-v2 or SigLIP 2)
Replace `embedding VECTOR(384)` entirely with a multi-modal encoder's output (1024 for jina-clip-v2, 768 for SigLIP 2). Populate per-building as a fused vector (e.g., `(text_emb + mean_image_emb) / 2` inside the shared multimodal space, or just the image vector if the text tower is weak for paragraph queries).
- Pros: Single column; text and image queries share one space; clean downstream pipeline.
- Cons: Strictly stronger version of Option C's downsides — same schema/session/Optuna burden **plus** the fusion-at-embed-time step discards the option to weight text-vs-image dynamically at query time. jina-clip-v2's text tower is tuned for shorter captions, not paragraph descriptions; SigLIP 2's text tower is similarly caption-oriented. Risk: the multimodal text tower is *worse* than our current MiniLM on `visual_description`-style paragraphs, and we gain image coverage at a text-quality cost.
- Complexity: **High** (same migration cost as C, plus early commitment to a fusion strategy without A/B telemetry).
- Expected impact: Uncertain. Could be net-positive if images dominate; net-negative if our long-form descriptions carry more signal than short captions. Option B defers the decision and buys the telemetry.

## Recommendation

**Pursue Option B as a coordination proposal to the Make DB team.** Additive multimodal is the only option that (a) respects `CLAUDE.md`'s Make-DB ownership boundary without asking them to destructively migrate a column 3,465 other-consumers may depend on, (b) preserves topics 01/02/03/04/06/07's geometric assumptions, (c) closes the biggest missing retrieval signal (images never ranked), and (d) leaves the door open to a later text-encoder upgrade independently. Choose **jina-clip-v2** over SigLIP 2 as the default candidate because (i) Matryoshka-native truncation lets pgvector storage scale from 1024→256 with ~4 % quality loss if Neon storage ever becomes an issue ([Jina MRL report](https://jina.ai/news/jina-clip-v2-multilingual-multimodal-embeddings-for-text-and-images/)), (ii) Korean is on the explicit-tune list, (iii) Jina's hosted API avoids standing up our own GPU for query-side embedding.

Explicitly **defer Option C** until Option B is measured: if the new image channel already closes the multilingual-MTEB gap empirically, a text-encoder swap adds pain without marginal benefit. **Reject Option D**: no path to validate the multimodal text tower on long-form descriptions before committing the migration.

## Open Questions

- **Per-building image representation.** Each building has 1 – N photos. Options: cover photo only (cheap, loses nuance); mean-pooled over all photos (standard, robust); max-pooled attention (requires a reranker). Defer to Make DB; recommend cover + mean as the first implementation.
- **Query-side multimodal embed provider.** Topic 03 already introduces the HuggingFace Inference pattern for MiniLM text queries. Extending to jina-clip-v2 adds one more endpoint, same rate-limit & warmup concerns. Alternative: Jina's own hosted API. Which has better Korean latency & SLO?
- **RRF weighting.** With text-cosine (384-dim MiniLM) and image-cosine (jina-clip-v2 1024) on the same corpus, RRF constant `k=60` works as a null ([topic 01 §Findings](01-hybrid-retrieval.md)), but whether to up-weight image for pure-visual queries ("copper roof") vs text for affective queries ("feels protective") is an Optuna question.
- **Does the image channel change K-Means centroids?** Topic 06's centroids are computed on the 384-dim text column. If user likes are logged with *both* channels, a per-channel centroid + per-channel MMR becomes possible — but also makes convergence detection (topic 06) more complex. Defer to a follow-up.
- **Coordination cadence with Make DB.** Do they accept additive columns on `architecture_vectors` without a formal migration policy? `CLAUDE.md:9` implies yes for index additions (topic 01 task BACK-HYB-4 is already a coordination item); re-embedding is heavier. Needs a direct conversation.
- **Imagen 3 is already integrated in Make Web** (`backend/apps/recommendation/services.py:202-247`) for persona-image generation. Does Google Vertex AI have a multimodal embedding counterpart we should evaluate alongside jina-clip-v2/SigLIP 2? Worth a line-item check, though historically Google's multimodal embeddings have been English-leaning.

## Proposed Tasks — Coordination Items (Make DB–Dominant)

Per the task hint's explicit scope: this topic proposes **coordination items**, not Make Web code edits. All items below are to be carried into a Make DB conversation or scoped as benchmark harnesses.

1. **COORD-EMB-1** — Draft a one-pager for the Make DB team: "Additive multimodal column on `architecture_vectors`: rationale, candidate encoders (jina-clip-v2 vs SigLIP 2), schema change (`ALTER TABLE architecture_vectors ADD COLUMN image_embedding VECTOR(1024)`), re-embed script reference, and a rollback plan." Route it to the Make DB owner before any Make Web code change lands.
2. **COORD-EMB-2** — Benchmark harness (read-only; writes only to `research/search/08-*`): pick 20 held-out personas from `algorithm_tester.py`, generate 3 query phrasings each (one specific/"concrete courtyard", one affective/"feels protective", one Korean), measure precision@20 of the current 384-dim MiniLM pool vs an offline jina-clip-v2-only baseline computed with a small Python notebook outside the Django app. No schema change needed for the benchmark — compute on a shadow table or an in-memory np.ndarray.
3. **COORD-EMB-3** — Migration/re-tune checklist (for the case Option C or D becomes preferred later): (a) flush all active `AnalysisSession` rows before cutover — their `like_vectors` and `preference_vector` are MiniLM-384-geometry-specific; (b) re-run Optuna on all 12 hyperparameters against the new encoder; (c) re-benchmark topic 03's HyDE latency on the new HF endpoint; (d) gate the cutover behind a `EMBEDDING_MODEL_VERSION` feature flag so we can A/B for at least 72 h.
4. **COORD-EMB-4** — Explicit non-task: **do not propose** Matryoshka-truncating BGE-M3 or jina-clip-v2 to 384 to reuse the existing column. That is a cross-space cosine (BGE-M3 is not MRL-native; even for jina-clip-v2, MRL protects the *relative geometry within jina space*, not compatibility with MiniLM space). Same error class as the Gemini-truncation rejection in topic 03 §7.
5. **DOC-EMB-1** — Once Make DB agrees to a direction, update `research/algorithm.md` §Phase 0 to reflect the new encoder name/dimension and update `CLAUDE.md:226` schema block. Left as a reporter-agent item.

## Sources

- [MMTEB: Massive Multilingual Text Embedding Benchmark — arXiv 2502.13595](https://arxiv.org/abs/2502.13595) — multilingual retrieval benchmark context.
- [MMTEB paper HTML, v4](https://arxiv.org/html/2502.13595v4)
- [MTEB leaderboard, Hugging Face Spaces](https://huggingface.co/spaces/mteb/leaderboard)
- [Modal — Top embedding models on MTEB leaderboard](https://modal.com/blog/mteb-leaderboard-article) — characterization of MiniLM vs larger encoders.
- [Towards Data Science — Best multilingual embedding model for RAG](https://towardsdatascience.com/how-to-find-the-best-multilingual-embedding-model-for-your-rag-40325c308ebb/) — comparison including MiniLM.
- [HuggingFace model card — paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) — 384-dim, 50 languages.
- [BAAI — BGE-M3 model card](https://huggingface.co/BAAI/bge-m3) — 1024-dim, 8192 context.
- [Chen et al. 2024 — BGE M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity (arXiv 2402.03216)](https://arxiv.org/abs/2402.03216)
- [intfloat/multilingual-e5-large — Hugging Face](https://huggingface.co/intfloat/multilingual-e5-large)
- [SigLIP 2 — arXiv 2502.14786](https://arxiv.org/abs/2502.14786) — multilingual vision-language encoders, 109 languages.
- [SigLIP 2 — Hugging Face blog](https://huggingface.co/blog/siglip2)
- [jina-clip-v2 — arXiv 2412.08802](https://arxiv.org/abs/2412.08802) — 1024-dim MRL multilingual multimodal, 89 languages with Korean tuned.
- [jina-clip-v2 — model card](https://huggingface.co/jinaai/jina-clip-v2)
- [Jina AI — jina-clip-v2 announcement](https://jina.ai/news/jina-clip-v2-multilingual-multimodal-embeddings-for-text-and-images/) — MRL 1024→64 benchmarks.
- [Kusupati et al. 2022 — Matryoshka Representation Learning (arXiv 2205.13147)](https://arxiv.org/abs/2205.13147) — MRL foundation paper.
- [HuggingFace — Introduction to Matryoshka embedding models](https://huggingface.co/blog/matryoshka)
- [NLLB-CLIP — NeurIPS ENLSP 2023](https://neurips2023-enlsp.github.io/papers/paper_2.pdf) — budget multilingual CLIP for low-resource languages.
- [mCLIP — ACL 2023](https://aclanthology.org/2023.acl-long.728/)
- [Shaw Talebi — Fine-Tuning Multimodal Embedding Models, Towards Data Science](https://towardsdatascience.com/fine-tuning-multimodal-embedding-models-bf007b1c5da5/) — sample-efficiency of CLIP fine-tune.
- [Real-estate multimodal search with CLIP + ChromaDB — Medium](https://medium.com/@etechoptimist/real-estate-with-multimodal-search-langchain-clip-semantic-search-and-chromadb-while-ensuring-factual-accuracy-in-ai-outputs-43fb42291812)
- [Scaling pgvector — DEV Community](https://dev.to/philip_mcclarence_2ef9475/scaling-pgvector-memory-quantization-and-index-build-strategies-8m2) — storage/index memory per dimension.
- [Roboflow Inference — CLIP benchmarks](https://inference.roboflow.com/foundation/clip/) — ~0.5 s/image on T4.
