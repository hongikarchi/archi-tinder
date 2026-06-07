export function isValidRank(value) {
  return Number.isInteger(value) && value >= 1 && value <= 100
}

export function metadataItems(card) {
  const metadata = card?.metadata || {}
  const materialVisual = Array.isArray(metadata.axis_material_visual)
    ? metadata.axis_material_visual.join(', ')
    : metadata.axis_material_visual

  const location = [metadata.axis_city, metadata.axis_country]
    .filter(Boolean).join(', ')

  // canonical_v2 schema drops `axis_material` and `axis_area_m2`. Material
  // rendering now reads exclusively from material_visual[]; area is omitted.
  return [
    ['Architect', metadata.axis_architects],
    ['Year', metadata.axis_year],
    ['Program', metadata.axis_typology],
    ['Style', metadata.axis_style],
    ['Material', materialVisual],
    ['Location', location || null],
  ].filter(([, value]) => value)
}

export function kindLabel(kind) {
  const map = {
    exterior: 'Exterior',
    interior: 'Interior',
    drawing: 'Drawing',
    aerial: 'Aerial',
    detail: 'Detail',
    cover: 'Cover',
    gallery: 'Photo',
  }
  return map[kind] || 'Photo'
}
