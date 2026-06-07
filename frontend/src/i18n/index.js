import { useLanguage } from '../hooks/useLanguage.js'
import { locales } from './locales.js'

/**
 * Resolve a dot-path key against a locale dict.
 * Returns undefined if the path does not exist.
 * Example: resolvePath('tabbar.discovery', locales.en) → 'Discovery'
 */
function resolvePath(key, dict) {
  return key.split('.').reduce((node, segment) => {
    if (node == null || typeof node !== 'object') return undefined
    return node[segment]
  }, dict)
}

/**
 * useTranslation() — returns { t, language }
 *
 * t(key) resolution order:
 *   1. locales[language][...path]  — current language
 *   2. locales.ko[...path]         — ko fallback (Korea-first default)
 *   3. literal key string          — last resort
 */
export function useTranslation() {
  const { language } = useLanguage()

  function t(key) {
    const primary = resolvePath(key, locales[language])
    if (primary !== undefined) return primary
    const fallback = resolvePath(key, locales.ko)
    if (fallback !== undefined) return fallback
    return key
  }

  return { t, language }
}
