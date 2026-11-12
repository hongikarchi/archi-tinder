// Info rows as [key, value] pairs; key maps to detailB3.label<Key>. Material is
// an array of chips (axis_material_visual is an array or a comma string).
export const CHIP_KEYS = ['Program', 'Style', 'Material']

export function metadataItems(card) {
  const metadata = card?.metadata || {}
  const material = Array.isArray(metadata.axis_material_visual)
    ? metadata.axis_material_visual
    : String(metadata.axis_material_visual || '').split(',')
  const materialChips = material.map(x => String(x).trim()).filter(Boolean)

  const location = [metadata.axis_city, metadata.axis_country]
    .filter(Boolean).join(', ')

  // canonical_v2 schema drops `axis_material` and `axis_area_m2`. Material
  // rendering now reads exclusively from material_visual[]; area is omitted.
  return [
    ['Architect', metadata.axis_architects],
    ['Year', metadata.axis_year],
    ['Program', metadata.axis_typology],
    ['Style', metadata.axis_style],
    ['Material', materialChips.length ? materialChips : null],
    ['Location', location || null],
  ].filter(([, value]) => value)
}

const KIND_KEYS = {
  exterior: 'detailB3.kindExterior',
  interior: 'detailB3.kindInterior',
  drawing: 'detailB3.kindDrawing',
  aerial: 'detailB3.kindAerial',
  detail: 'detailB3.kindDetail',
  cover: 'detailB3.kindCover',
}

// Pure: takes the i18n `t` so the badge / alt text follow the UI language.
export function kindLabel(kind, t) {
  return t(KIND_KEYS[kind] || 'detailB3.kindPhoto')
}
