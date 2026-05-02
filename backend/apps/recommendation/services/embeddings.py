"""
embeddings.py -- Stage 2 HuggingFace embedding for HyDE V_initial.

Topic 03 HyDE V_initial: embed text via HuggingFace Inference API.
Model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim).

Cross-module symbol access uses the late-bound package reference (_svc) so that
mock.patch('apps.recommendation.services.event_log') continues to work in tests.
"""
import json
import logging
import time
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger('apps.recommendation')


def embed_visual_description(text, session=None, user=None):
    """
    Topic 03 HyDE V_initial: embed `text` via HuggingFace Inference API.

    Model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim).
    Uses stdlib urllib.request -- no new dependencies.

    Returns list[float] of length 384 on success, None on any failure.
    Failures are always silent (logged + event emitted) and never raise.

    Flag guard is the caller's responsibility (hyde_vinitial_enabled).
    """
    # Late-bound package reference: mock.patch('apps.recommendation.services.event_log')
    # modifies the services module object; _svc.event_log reads it at call time.
    from apps.recommendation import services as _svc  # noqa: PLC0415

    hf_token = getattr(settings, 'HF_TOKEN', '')
    if not hf_token:
        _svc.event_log.emit_event(
            'failure',
            session=session,
            user=user,
            failure_type='hyde',
            recovery_path='no_hyde',
            reason='missing_token',
        )
        return None

    if not text or not text.strip():
        logger.debug('embed_visual_description: empty text, skipping HF call')
        return None

    rc = settings.RECOMMENDATION
    model = rc.get('hyde_hf_model', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    timeout = rc.get('hyde_hf_timeout_seconds', 5)
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

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        data = json.loads(raw)

        # Handle both 1-D [float*384] and 2-D (batched) [[float*384]] shapes
        if isinstance(data, list) and data and isinstance(data[0], list):
            vec = data[0]
        elif isinstance(data, list) and data and isinstance(data[0], (int, float)):
            vec = data
        else:
            logger.warning('embed_visual_description: unexpected HF response shape: %s', type(data))
            _svc.event_log.emit_event(
                'failure',
                session=session,
                user=user,
                failure_type='hyde',
                recovery_path='no_hyde',
                reason='unexpected_shape',
                elapsed_ms=elapsed_ms,
            )
            return None

        if len(vec) != 384:
            logger.warning('embed_visual_description: expected 384-dim, got %d', len(vec))
            _svc.event_log.emit_event(
                'failure',
                session=session,
                user=user,
                failure_type='hyde',
                recovery_path='no_hyde',
                reason=f'wrong_dim_{len(vec)}',
                elapsed_ms=elapsed_ms,
            )
            return None

        # Emit timing event on success
        _svc.event_log.emit_event(
            'hyde_call_timing',
            session=session,
            user=user,
            elapsed_ms=elapsed_ms,
            model=model,
        )
        return [float(v) for v in vec]

    except urllib.error.HTTPError as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        try:
            body = e.read().decode('utf-8', errors='replace')[:200]
        except Exception:
            body = ''
        logger.warning(
            'embed_visual_description: HF API returned HTTP %d',
            e.code,
        )
        _svc.event_log.emit_event(
            'failure',
            session=session,
            user=user,
            failure_type='hyde',
            recovery_path='no_v_initial',
            http_status=e.code,
            error_message=body,
            elapsed_ms=elapsed_ms,
        )
        return None
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.warning(
            'embed_visual_description: HF call failed (%s: %s)',
            type(e).__name__, str(e),
        )
        _svc.event_log.emit_event(
            'failure',
            session=session,
            user=user,
            failure_type='hyde',
            recovery_path='no_hyde',
            error_class=type(e).__name__,
            error_message=str(e)[:200],
            elapsed_ms=elapsed_ms,
        )
        return None
