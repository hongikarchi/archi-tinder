import { createContext } from 'react'

export type Language = 'ko' | 'en'

export interface LanguageContextValue {
  language: Language
  setLanguage: (next: string) => void
  hydrate: (serverLanguage: unknown) => void
}

/** Raw React context — consumed via hooks/useLanguage.js, provided by context/LanguageContext.jsx */
export const LanguageContext = createContext<LanguageContextValue | null>(null)
