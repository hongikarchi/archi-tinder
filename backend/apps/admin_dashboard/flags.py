"""Static feature-flag registry for the admin dashboard (read-only, values only).

Each entry exposes ONLY: key, Korean label, Korean one-line description, current value
(bool or short enum string). Values are read from ``settings`` at request time. Never
add an entry whose value could be a key/token/secret.
"""
from django.conf import settings


def _rec(name):
    return lambda: bool(settings.RECOMMENDATION.get(name, False))


def _attr_bool(name):
    return lambda: bool(getattr(settings, name, False))


def _attr_str(name):
    return lambda: str(getattr(settings, name, ''))


# (key, label_ko, description_ko, getter)
_REGISTRY = [
    ('MESSAGING_ENABLED', '쪽지/연락 요청',
     '켜면 연락 요청과 쪽지 기능이 열리고, 끄면 관련 API가 모두 404를 돌려줍니다.',
     _attr_bool('MESSAGING_ENABLED')),
    ('PERF_TIMING_ENABLED', '성능 타이밍 로그',
     '켜면 요청 단계별 소요 시간을 서버 로그에 남깁니다. 약간의 오버헤드가 있어 측정할 때만 켭니다.',
     _attr_bool('PERF_TIMING_ENABLED')),
    ('PREWARM_ENABLED', '서버 예열',
     '서버가 시작될 때 자주 쓰는 연결과 캐시를 미리 준비해 첫 요청을 빠르게 합니다.',
     _attr_bool('PREWARM_ENABLED')),
    ('DB_POOL_ENABLED', 'DB 커넥션 풀',
     '데이터베이스 연결을 재사용해 응답을 빠르게 합니다. 문제가 생기면 끄고 이전 방식으로 되돌립니다.',
     _attr_bool('DB_POOL_ENABLED')),
    ('STAGE_DECOUPLE_ENABLED', '검색 2단계 분리',
     '켜면 검색어 해석을 필터 단계와 시각 묘사 단계로 나눠 첫 카드가 더 빨리 나옵니다.',
     _rec('stage_decouple_enabled')),
    ('LLM_PROVIDER', '텍스트 AI 제공자',
     '검색어 해석과 보드 이름 생성에 쓰는 AI 회사입니다 (gemini 또는 openai).',
     _attr_str('LLM_PROVIDER')),
    ('LLM_IMAGE_PROVIDER', '이미지 AI 제공자',
     '취향 이미지 생성에 쓰는 AI 회사입니다 (gemini 또는 openai).',
     _attr_str('LLM_IMAGE_PROVIDER')),
    ('gemini_rerank_enabled', 'Gemini 재정렬',
     '켜면 추천 결과를 마지막에 Gemini가 한 번 더 정렬합니다. 품질은 오르지만 응답이 느려질 수 있습니다.',
     _rec('gemini_rerank_enabled')),
    ('dpp_topk_enabled', '다양성 보정(DPP)',
     '켜면 비슷한 건물만 몰리지 않도록 최종 추천 목록의 다양성을 수학적으로 맞춥니다.',
     _rec('dpp_topk_enabled')),
    ('context_caching_enabled', 'Gemini 컨텍스트 캐싱(IMP-5)',
     '켜면 긴 고정 프롬프트를 Gemini 서버에 캐시해 비용과 지연을 줄입니다. Gemini 제공자일 때만 동작합니다.',
     _rec('context_caching_enabled')),
]


def get_flags():
    return [
        {'key': key, 'label_ko': label, 'description_ko': desc, 'value': getter()}
        for key, label, desc, getter in _REGISTRY
    ]
