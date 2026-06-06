import { useState, useEffect } from 'react'
import { LanguageContext } from './_languageContext.js'
import { getToken } from '../api/core.js'
import { updateMyProfile } from '../api/profiles.js'

const VALID_LANGUAGES = ['ko', 'en']

/**
 * Migrate unknown language values:
 *   any value not in VALID_LANGUAGES → 'ko'
 */
function migrateLanguage(raw) {
  if (VALID_LANGUAGES.includes(raw)) return raw
  return 'ko'
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    const raw = localStorage.getItem('archithon_language')
    return migrateLanguage(raw)
  })

  // Persist language to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('archithon_language', language)
  }, [language])

  function setLanguage(next) {
    if (!VALID_LANGUAGES.includes(next)) return
    setLanguageState(next)
    if (getToken()) updateMyProfile({ language: next }).catch(() => {})
  }

  // Apply server-side language on login (cross-device sync).
  // Does NOT PATCH back — server is the source of truth here.
  function hydrate(serverLanguage) {
    setLanguageState(migrateLanguage(serverLanguage))
  }

  return (
    <LanguageContext.Provider value={{ language, setLanguage, hydrate }}>
      {children}
    </LanguageContext.Provider>
  )
}
