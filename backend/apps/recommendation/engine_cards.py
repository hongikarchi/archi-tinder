"""
engine_cards.py -- DB row → card shaping and cache-key helpers.

Extracted from engine.py (FULL-REFACTOR-1). No DB access, no RC reads,
no engine imports.
"""

_VALID_IMAGE_FOCUS = frozenset({'exterior', 'interior', 'drawing', 'aerial', 'detail'})

# Bump _CARD_CACHE_SCHEMA when _row_to_card output shape changes so older Redis
# entries are not silently served as stale shape after a deploy.
_CARD_CACHE_SCHEMA = 'v2'


def _row_to_card(row, image_focus=None):
    """Convert a DB row dict (canonical_v2_buildings) to ImageCard format.

    Image resolution (canonical_v2 schema):
    - cover: covers_by_type[image_focus] when caller requested a focus and it
      resolves to a URL; otherwise fallback chain:
        display_cover_url -> cover_image_url_default -> covers_by_type.exterior
        -> all_images[0].url -> ''.
    - gallery: all_images sorted by (kind: cover→gallery→drawing, then
      image_order, then rank). The URL chosen as cover is removed from gallery.
    - gallery_drawing_start: index of first item with kind=='drawing' in gallery
      (== len(gallery) when no drawings). Frontend renders items at index >=
      gallery_drawing_start with contain-sizing on white background.
    - image_focus: echoed verbatim in the returned dict so the frontend can
      make objectFit decisions (e.g. 'contain' for drawings, 'cover' for
      exterior/interior). None when caller did not specify a focus.
    """
    canonical_bld_id = row['canonical_bld_id']
    covers_by_type = row.get('covers_by_type') or {}
    if isinstance(covers_by_type, str):
        import json as _json
        try:
            covers_by_type = _json.loads(covers_by_type)
        except (ValueError, TypeError):
            covers_by_type = {}
    all_images_raw = row.get('all_images') or []
    if isinstance(all_images_raw, str):
        import json as _json
        try:
            all_images_raw = _json.loads(all_images_raw)
        except (ValueError, TypeError):
            all_images_raw = []
    source_urls = row.get('source_urls') or {}
    if isinstance(source_urls, str):
        import json as _json
        try:
            source_urls = _json.loads(source_urls)
        except (ValueError, TypeError):
            source_urls = {}

    # Cover resolution
    image_url = ''
    if image_focus and image_focus in _VALID_IMAGE_FOCUS:
        image_url = covers_by_type.get(image_focus) or ''
    if not image_url:
        image_url = (
            row.get('display_cover_url')
            or row.get('cover_image_url_default')
            or covers_by_type.get('exterior')
            or ''
        )
    if not image_url and all_images_raw:
        first = all_images_raw[0] if isinstance(all_images_raw[0], dict) else {}
        image_url = first.get('url') or ''

    # Detect actual kind of resolved image_url (for frontend aspect handling).
    # Sources, in order: covers_by_type reverse-lookup, all_images entry match.
    image_kind = None
    if image_url and isinstance(covers_by_type, dict):
        for k, u in covers_by_type.items():
            if u == image_url:
                image_kind = k
                break
    if image_kind is None and image_url:
        for img in all_images_raw:
            if isinstance(img, dict) and img.get('url') == image_url:
                image_kind = img.get('kind')
                break

    # Gallery from all_images: sort by (kind rank, image_order, rank)
    kind_order = {'cover': 0, 'gallery': 1, 'drawing': 2}
    images = [img for img in all_images_raw if isinstance(img, dict) and img.get('url')]
    images.sort(key=lambda img: (
        kind_order.get(img.get('kind') or '', 1),
        img.get('image_order') if img.get('image_order') is not None else 9999,
        img.get('rank') if img.get('rank') is not None else 9999,
    ))
    gallery_urls = []
    gallery_meta = []
    seen = {image_url} if image_url else set()
    drawing_start = None
    for img in images:
        url = img.get('url')
        if not url or url in seen:
            continue
        seen.add(url)
        if drawing_start is None and img.get('kind') == 'drawing':
            drawing_start = len(gallery_urls)
        gallery_urls.append(url)
        gallery_meta.append({'url': url, 'kind': img.get('kind') or 'gallery'})
    if drawing_start is None:
        drawing_start = len(gallery_urls)

    # source_urls is jsonb like {"divisare": ["https://..."]}; pick first URL.
    src_url = None
    if isinstance(source_urls, dict):
        for vals in source_urls.values():
            if isinstance(vals, list) and vals:
                src_url = vals[0]
                break

    architect_names = row.get('architect_names') or []
    if isinstance(architect_names, str):
        # If DB driver returned text[] as raw text (rare); fall back to architects_text.
        architect_names = []
    architects_display = (
        row.get('architects_text')
        or (', '.join(architect_names) if architect_names else None)
    )

    return {
        'canonical_bld_id':       canonical_bld_id,
        'name':                   row.get('name') or '',
        'image_url':              image_url,
        'image_focus':            image_focus,
        'image_kind':             image_kind,
        'covers_by_type':         covers_by_type,
        'url':                    src_url,
        'gallery':                gallery_urls,
        'gallery_meta':           gallery_meta,
        'gallery_drawing_start':  drawing_start,
        'metadata': {
            'axis_typology':       row.get('program'),
            'axis_architects':     architects_display,
            'axis_country':        row.get('location_country'),
            'axis_city':           row.get('location_city'),
            'axis_year':           row.get('project_year'),
            'axis_style':          row.get('style'),
            'axis_atmosphere':     row.get('atmosphere'),
            'axis_color_tone':     row.get('color_tone'),
            'axis_material_visual': list(row.get('material_visual') or []),
            'axis_typology_primary':       row.get('typology_primary'),
            'axis_typology_tags':          list(row.get('typology_tags') or []),
            'axis_architectural_elements': list(row.get('architectural_elements') or []),
            'visual_description':  row.get('visual_description') or '',
        },
    }


def _card_cache_key(canonical_bld_id):
    return f'bcard:{_CARD_CACHE_SCHEMA}:{canonical_bld_id}'


def _with_image_focus(card, image_focus):
    if not image_focus or image_focus not in _VALID_IMAGE_FOCUS or not card:
        return card

    focused = dict(card)
    focused['metadata'] = dict(card.get('metadata') or {})
    focused['covers_by_type'] = dict(card.get('covers_by_type') or {})
    focus_url = focused['covers_by_type'].get(image_focus)
    focused['image_focus'] = image_focus
    if not focus_url:
        return focused

    focused['image_url'] = focus_url
    focused['image_kind'] = image_focus
    gallery = list(card.get('gallery') or [])
    gallery_meta = list(card.get('gallery_meta') or [])

    original_drawing_start = card.get('gallery_drawing_start')
    try:
        removed_index = gallery.index(focus_url)
    except ValueError:
        removed_index = None

    filtered = [
        (url, meta) for url, meta in zip(gallery, gallery_meta)
        if url != focus_url
    ]
    focused['gallery'] = [url for url, _ in filtered]
    focused['gallery_meta'] = [meta for _, meta in filtered]

    # Shift drawing_start down when focus_url was strictly before the drawing
    # section (its removal pulls the drawing section forward by 1). Otherwise
    # leave drawing_start untouched. Clamp guards against malformed input.
    new_drawing_start = original_drawing_start
    if (new_drawing_start is not None
            and removed_index is not None
            and removed_index < new_drawing_start):
        new_drawing_start -= 1

    fallback = len(focused['gallery'])
    focused['gallery_drawing_start'] = min(
        new_drawing_start if new_drawing_start is not None else fallback,
        len(focused['gallery']),
    )
    return focused
