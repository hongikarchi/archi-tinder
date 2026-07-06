/**
 * constants/roles.js
 * Bundled fallback role list — mirrors backend UserProfile.ONBOARDING_ROLE_CHOICES
 * + ONBOARDING_ROLE_LABELS_KO exactly (SETTINGS-POLISH-1).
 *
 * This is the offline fallback used by api/meta.js getRoles() when
 * GET /api/v1/meta/roles/ is unreachable, and the historical single
 * source of truth kept in sync manually — if backend adds a role, this
 * array should be updated to match (though getRoles() will already surface
 * the live backend list to the UI on a successful fetch).
 */
export const ROLES = [
  { value: 'student',    label_en: 'Student',                 label_ko: '학생' },
  { value: 'architect',  label_en: 'Architect',               label_ko: '건축가' },
  { value: 'designer',   label_en: 'Designer',                label_ko: '디자이너' },
  { value: 'enthusiast', label_en: 'Architecture Enthusiast', label_ko: '건축 애호가' },
  { value: 'other',      label_en: 'Other',                   label_ko: '기타' },
]
