"""
normalization.py -- TEMPORARY raw-DB-value maps for country and material.

The building DB (Make DB) stores the same country under several spellings
('Turkey' / 'Türkiye') and material_visual as free-form strings ('wood' /
'timber' / 'oak'). Until Make DB ships the cleanup requested in
docs/db-data-quality-handoff.md, we expand a canonical value into every raw
spelling so the later EXACT-match filters still find all rows.

REMOVE this module (and the raw_*_values call sites in recognizer.py) once
that cleanup lands and the DB columns are canonical.
"""

# canonical English country -> raw DB spellings (excluding the canonical itself).
COUNTRY_ALIASES = {
    'Turkey': ['Türkiye'],
    'Iran': ['Iran, Islamic Republic of', 'Tabriz'],
    'United Arab Emirates': ['Dubai - United Arab Emirates', 'Dubai - UAE',
                             'Abu Dhabi - United Arab Emirates'],
    'Saudi Arabia': ['Riyadh Saudi Arabia', 'AlUla Saudi Arabia'],
    'Spain': ['España'],
    'Bahamas': ['The Bahamas'],
    'Laos': ["Lao People's Democratic Republic"],
    'Myanmar': ['Myanmar (Burma)'],
    'France': ['France -'],
    'Singapore': ['Singapore 299583'],
    'Japan': ['Tokyo', '1 Chome−3−15 関電不動産西本町ビル'],
    'China': ['Chongqing', 'SHUNDE'],
    'Kosovo': ['Prishtinë', 'Pristina'],
    'Serbia': ['- Nis'],
    'Palestine': ['Palestine, State of'],
    'North Korea': ["Korea, Democratic People's Republic of"],
    'DR Congo': ['Congo, The Democratic Republic of the'],
}


def raw_country_values(canonical):
    """Canonical country plus every raw DB spelling, for exact matching."""
    return [canonical] + list(COUNTRY_ALIASES.get(canonical, []))


def _group(name, *values):
    return {v: name for v in values}


# raw material_visual value (lowercase) -> material group. Landscape/furniture/
# building-part words (water, vegetation, stairs, windows, ...) are deliberately absent.
MATERIAL_GROUP_MAP = {}
MATERIAL_GROUP_MAP.update(_group(
    'wood', 'wood', 'timber', 'plywood', 'oak', 'bamboo', 'larch wood', 'oak wood',
    'pine wood', 'birch plywood', 'wood slats', 'wood cladding', 'cedar', 'wood panels',
    'walnut', 'pine', 'parquet', 'wood flooring', 'wood paneling', 'wooden slats',
    'painted wood', 'cross-laminated timber', 'glulam', 'timber frame', 'reclaimed wood',
    'timber cladding', 'wood beams', 'wood veneer', 'mass timber', 'teak', 'wooden facade',
    'dark wood', 'solid wood', 'douglas fir', 'clt', 'wooden floors', 'charred wood', 'larch'))
MATERIAL_GROUP_MAP.update(_group(
    'metal', 'steel', 'metal', 'aluminum', 'aluminium', 'metal cladding', 'iron',
    'stainless steel', 'corten steel', 'cor-ten steel', 'corten', 'perforated metal',
    'brass', 'copper', 'zinc', 'bronze', 'metal mesh', 'galvanized steel',
    'corrugated metal', 'sheet metal', 'cast iron', 'metal panels', 'painted metal',
    'black steel', 'black metal', 'metal railings', 'metal roof'))
MATERIAL_GROUP_MAP.update(_group(
    'concrete', 'concrete', 'reinforced concrete', 'exposed concrete', 'precast concrete',
    'cement', 'polished concrete', 'white concrete', 'prefabricated concrete',
    'concrete block', 'concrete blocks', 'raw concrete', 'colored concrete',
    'pigmented concrete', 'microcement'))
MATERIAL_GROUP_MAP.update(_group(
    'stone', 'stone', 'marble', 'granite', 'limestone', 'rock', 'natural stone',
    'sandstone', 'stone walls', 'slate', 'travertine', 'local stone', 'white marble',
    'stone masonry', 'stone floors', 'stone paving', 'basalt'))
MATERIAL_GROUP_MAP.update(_group(
    'brick', 'brick', 'masonry', 'historic masonry', 'terracotta', 'red brick',
    'exposed brick', 'brickwork'))
MATERIAL_GROUP_MAP.update(_group(
    'plaster', 'plaster', 'white plaster', 'stucco', 'render', 'lime plaster',
    'painted plaster', 'lime', 'plasterboard'))
MATERIAL_GROUP_MAP.update(_group(
    'tile', 'tile', 'tiles', 'ceramic tile', 'ceramic', 'terrazzo', 'ceramic tiles',
    'roof tiles', 'roof tile', 'ceramic floors', 'mosaic', 'mosaic tile', 'terracotta tile'))
MATERIAL_GROUP_MAP.update(_group(
    'earth', 'earth', 'rammed earth', 'soil', 'clay', 'adobe', 'mud'))
MATERIAL_GROUP_MAP.update(_group(
    'glass', 'glass', 'mirror', 'mirrors', 'glass partitions', 'translucent glass',
    'stained glass', 'frosted glass', 'colored glass', 'glazing', 'curtain wall'))
MATERIAL_GROUP_MAP.update(_group(
    'fabric', 'fabric', 'textile', 'textiles', 'carpet', 'velvet', 'upholstery'))
MATERIAL_GROUP_MAP.update(_group(
    'plastic', 'polycarbonate', 'acrylic', 'plastic', 'resin', 'membrane'))
MATERIAL_GROUP_MAP.update(_group(
    'other', 'composite', 'paper', 'cork', 'leather', 'linoleum', 'recycled materials',
    'thatch'))


def raw_material_values(group):
    """All raw (lowercase) material_visual values belonging to `group`."""
    return sorted(raw for raw, g in MATERIAL_GROUP_MAP.items() if g == group)
