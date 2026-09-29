/**
 * utils/reportText.js
 *
 * FULL-REPORT-BILINGUAL — the persona report's Gemini call now returns both
 * ko and en text (final_report.i18n = { ko: {...}, en: {...} }) alongside the
 * legacy flat top-level fields (persona_type / one_liner / pattern_paragraph
 * / description), which stay populated for backward compatibility with old
 * consumers (SaveBoardModal default name, share text, etc.) and old reports
 * that never had an i18n block at all.
 *
 * localizeReport() lets the UI switch report text instantly when the user
 * flips the language toggle — no API call, no regeneration — by reading the
 * matching i18n[language] block per field, falling back to the report's own
 * top-level field when that particular field (or the whole block) is absent.
 */

// The 4 human-readable text fields that vary by language. dominant_programs /
// dominant_styles / dominant_materials are intentionally excluded — those
// stay single-language English arrays per the backend contract and must not
// be touched here.
const TEXT_FIELDS = ['persona_type', 'one_liner', 'pattern_paragraph', 'description']

/**
 * localizeReport(report, language)
 *
 * Returns a new report object with TEXT_FIELDS overridden from
 * report.i18n[language] wherever that field is present (non-null,
 * non-undefined) there. Any field missing from the i18n block — or the
 * i18n block/language itself being absent — falls back to the report's own
 * top-level value, so old single-language reports (no `i18n` key at all)
 * are returned unchanged.
 *
 * Never mutates the input report.
 */
export function localizeReport(report, language) {
  if (!report || typeof report !== 'object') return report

  const block = report.i18n && typeof report.i18n === 'object' ? report.i18n[language] : null
  if (!block || typeof block !== 'object') return report

  const next = { ...report }
  for (const field of TEXT_FIELDS) {
    const value = block[field]
    if (value !== undefined && value !== null) {
      next[field] = value
    }
  }
  return next
}
