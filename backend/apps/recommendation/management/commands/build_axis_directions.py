"""
Management command: build_axis_directions

FULL-PERSONA-SPECTRUM (2026-09-27): builds backend/fixtures/axis_directions.json
-- per-axis embedding-projection direction vectors + lo/hi normalization
bounds, derived from the sentence anchors in services/_axis_anchors.py.

Two build-time steps. The HuggingFace feature-extraction endpoint (same model
+ URL pattern as services/embeddings.py's HyDE path) is used ONLY here, at
build time -- never per request:

  1. Embed every axis's anchor sentences, L2-normalize each sentence
     embedding, then direction = normalize(mean(pos) - mean(neg)).
  2. Project every publishable building's embedding (raw SQL on
     connections['buildings'], chunked so memory stays bounded regardless of
     corpus size) onto each axis direction. lo/hi = 5th/95th percentile of
     the projections; used later by services/axis_scores.py to rescale a raw
     dot product into [-1, 1].

Usage:
    python manage.py build_axis_directions
    python manage.py build_axis_directions --batch-size 2000

Fails loudly (CommandError) when HF_TOKEN is missing, an anchor sentence
embeds to something other than 384 dims, or no publishable buildings with a
parseable embedding are found.
"""
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.recommendation.engine_vecmath import _parse_embedding_text
from apps.recommendation.services._axis_anchors import AXIS_ANCHORS

EMBED_DIM = 384
LO_PERCENTILE = 5
HI_PERCENTILE = 95
DEFAULT_BATCH_SIZE = 1000


def _anchors_sha256():
    """Stable hash of AXIS_ANCHORS -- lets axis_scores.py detect a stale
    axis_directions.json (anchors edited since the file was last built)."""
    payload = json.dumps(AXIS_ANCHORS, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _l2_normalize(vec):
    norm = float(np.linalg.norm(vec))
    if norm <= 0:
        raise CommandError('anchor sentence embedded to a zero vector -- cannot normalize')
    return vec / norm


class Command(BaseCommand):
    help = (
        'Build backend/fixtures/axis_directions.json: per-axis anchor-sentence '
        'projection directions + lo/hi normalization bounds. Uses the HF '
        'feature-extraction endpoint only at build time, never per request.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
            help=f'Row batch size for the chunked buildings-DB scan (default {DEFAULT_BATCH_SIZE}).',
        )

    def handle(self, *args, **options):
        hf_token = getattr(settings, 'HF_TOKEN', '')
        if not hf_token:
            raise CommandError('HF_TOKEN is not set -- cannot build axis directions.')

        rc = settings.RECOMMENDATION
        model = rc.get('hyde_hf_model', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        timeout = rc.get('hyde_hf_timeout_seconds', 5)
        batch_size = max(100, int(options['batch_size']))

        directions = self._build_directions(hf_token, model, timeout)
        axes_out, total = self._project_and_bound(directions, batch_size)

        output = {
            'model': model,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'anchors_sha256': _anchors_sha256(),
            'axes': axes_out,
        }

        output_path = settings.BASE_DIR / 'fixtures' / 'axis_directions.json'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
            f.write('\n')

        self.stdout.write(self.style.SUCCESS(
            f'Wrote {output_path} ({len(axes_out)} axes, {total} buildings projected).'
        ))

    # ── Step 1: anchor -> direction ─────────────────────────────────────────

    def _build_directions(self, hf_token, model, timeout):
        self.stdout.write(f'Embedding anchor sentences via {model} ...')
        directions = {}
        for axis, poles in AXIS_ANCHORS.items():
            neg_vecs = [
                self._embed_and_report(s, hf_token, model, timeout) for s in poles['neg']
            ]
            pos_vecs = [
                self._embed_and_report(s, hf_token, model, timeout) for s in poles['pos']
            ]
            neg_mean = np.mean(np.stack(neg_vecs), axis=0)
            pos_mean = np.mean(np.stack(pos_vecs), axis=0)
            direction = _l2_normalize(pos_mean - neg_mean)
            directions[axis] = direction
            self.stdout.write(
                f'  {axis}: direction built from {len(neg_vecs)} neg + {len(pos_vecs)} pos anchors'
            )
        return directions

    def _embed_and_report(self, sentence, hf_token, model, timeout):
        t0 = time.perf_counter()
        vec = _embed_sentence(sentence, hf_token, model, timeout)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        self.stdout.write(f'    embedded ({elapsed_ms}ms): {sentence[:70]}')
        return _l2_normalize(vec)

    # ── Step 2: direction -> lo/hi over the corpus ──────────────────────────

    def _project_and_bound(self, directions, batch_size):
        self.stdout.write('Projecting all publishable building embeddings (chunked scan) ...')
        projections = {axis: [] for axis in directions}
        total = 0
        offset = 0
        while True:
            with connections['buildings'].cursor() as cur:
                cur.execute(
                    """
                    SELECT embedding::text
                    FROM canonical_v2_buildings
                    WHERE is_publishable = true
                    ORDER BY canonical_bld_id
                    LIMIT %s OFFSET %s
                    """,
                    [batch_size, offset],
                )
                rows = cur.fetchall()
            if not rows:
                break
            for (emb_text,) in rows:
                vec = _parse_embedding_text(emb_text)
                if vec is None:
                    continue
                if vec.shape != (EMBED_DIM,):
                    raise CommandError(
                        f'building embedding has {vec.shape[0]} dims, expected {EMBED_DIM}'
                    )
                total += 1
                for axis, direction in directions.items():
                    projections[axis].append(float(np.dot(vec, direction)))
            offset += batch_size
            self.stdout.write(f'  ... scanned {offset} rows ({total} valid embeddings so far)')
            if len(rows) < batch_size:
                break

        if total == 0:
            raise CommandError('No publishable buildings with a parseable embedding were found.')

        axes_out = {}
        for axis, direction in directions.items():
            vals = np.asarray(projections[axis], dtype=np.float64)
            lo = float(np.percentile(vals, LO_PERCENTILE))
            hi = float(np.percentile(vals, HI_PERCENTILE))
            axes_out[axis] = {
                'direction': [round(float(v), 6) for v in direction],
                'lo': round(lo, 6),
                'hi': round(hi, 6),
            }
            self.stdout.write(f'  {axis}: lo={lo:.4f} hi={hi:.4f} (n={total})')

        return axes_out, total


def _embed_sentence(text, hf_token, model, timeout):
    """Embed a single sentence via the HF feature-extraction endpoint.

    Mirrors services/embeddings.py's request shape (same model/URL/headers),
    but raises CommandError on any failure instead of returning None -- this
    is a one-shot build script and must fail loudly rather than silently
    degrade like the per-request HyDE path does.
    """
    url = f'https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction'
    payload = json.dumps({'inputs': text}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Authorization': f'Bearer {hf_token}',
            'Content-Type': 'application/json',
            'X-Wait-For-Model': 'true',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8', errors='replace')[:200]
        except Exception:
            body = ''
        raise CommandError(f'HF embed failed for {text!r}: HTTP {e.code} {body}')
    except Exception as e:
        raise CommandError(f'HF embed failed for {text!r}: {type(e).__name__}: {e}')

    data = json.loads(raw)
    if isinstance(data, list) and data and isinstance(data[0], list):
        vec = data[0]
    elif isinstance(data, list) and data and isinstance(data[0], (int, float)):
        vec = data
    else:
        raise CommandError(f'HF embed for {text!r}: unexpected response shape {type(data)}')

    if len(vec) != EMBED_DIM:
        raise CommandError(f'HF embed for {text!r}: expected {EMBED_DIM} dims, got {len(vec)}')

    return np.asarray(vec, dtype=np.float64)
