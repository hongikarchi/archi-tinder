import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { LanguageContext } from './_languageContext.ts'
import type { Language } from './_languageContext.ts'
import { getToken } from '../api/core.ts'
import { updateMyProfile } from '../api/profiles.ts'

const VALID_LANGUAGES: Language[] = ['ko', 'en']

/**
 * Migrate unknown language values:
 *   any value not in VALID_LANGUAGES → 'ko'
 */
function migrateLanguage(raw: unknown): Language {
  if (VALID_LANGUAGES.includes(raw as Language)) return raw as Language
  return 'ko'
}

export function LanguageProvider({ children }: { children?: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    const raw = localStorage.getItem('archithon_language')
    return migrateLanguage(raw)
  })

  // Persist language to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('archithon_language', language)
  }, [language])

  function setLanguage(next: string) {
    if (!VALID_LANGUAGES.includes(next as Language)) return
    setLanguageState(next as Language)
    if (getToken()) updateMyProfile({ language: next }).catch(() => {})
  }

  // Apply server-side language on login (cross-device sync).
  // Does NOT PATCH back — server is the source of truth here.
  function hydrate(serverLanguage: unknown) {
    setLanguageState(migrateLanguage(serverLanguage))
  }

  return (
    <LanguageContext.Provider value={{ language, setLanguage, hydrate }}>
      {children}
    </LanguageContext.Provider>
  )
}
