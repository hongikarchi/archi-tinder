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

  function t(key, params) {
    let str = resolvePath(key, locales[language])
    if (str === undefined) str = resolvePath(key, locales.ko)
    if (str === undefined) return key
    if (params && typeof str === 'string') {
      Object.entries(params).forEach(([k, v]) => {
        str = str.split(`{${k}}`).join(String(v))
      })
    }
    return str
  }

  return { t, language }
}
