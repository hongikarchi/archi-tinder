import { createContext } from 'react'

export type Theme = 'github-light' | 'github-dark' | 'ayu-light' | 'synthwave-84'
export type Font = 'plex' | 'noto-serif'

export interface ThemeContextValue {
  theme: Theme
  font: Font
  setTheme: (next: string) => void
  setFont: (next: string) => void
  hydrate: (serverTheme: unknown, serverFont: unknown) => void
}

/** Raw React context — consumed via hooks/useTheme.js, provided by context/ThemeContext.jsx */
export const ThemeContext = createContext<ThemeContextValue | null>(null)
