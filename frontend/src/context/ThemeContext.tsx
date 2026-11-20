import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { ThemeContext } from './_themeContext.ts'
import type { Theme, Font } from './_themeContext.ts'
import { getToken } from '../api/core.ts'
import { updateMyProfile } from '../api/profiles.ts'

const VALID_THEMES: Theme[] = ['github-light', 'github-dark', 'ayu-light', 'synthwave-84']
const VALID_FONTS: Font[]  = ['plex', 'noto-serif']

/**
 * Migrate legacy theme keys stored before the design-system redesign:
 *   'dark'  → 'github-dark'
 *   'light' → 'github-light'
 *   unknown → 'github-light'
 */
function migrateTheme(raw: unknown): Theme {
  if (raw === 'dark') return 'github-dark'
  if (raw === 'light') return 'github-light'
  if (VALID_THEMES.includes(raw as Theme)) return raw as Theme
  return 'github-light'
}

function migrateFont(raw: unknown): Font {
  if (VALID_FONTS.includes(raw as Font)) return raw as Font
  return 'plex'
}

export function ThemeProvider({ children }: { children?: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const raw = localStorage.getItem('archithon_theme')
    return migrateTheme(raw)
  })

  const [font, setFontState] = useState<Font>(() => {
    const raw = localStorage.getItem('archithon_font')
    return migrateFont(raw)
  })

  // Apply theme attribute + persist
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('archithon_theme', theme)
  }, [theme])

  // Apply font attribute + persist
  useEffect(() => {
    if (font === 'noto-serif') {
      document.documentElement.setAttribute('data-font', 'noto-serif')
    } else {
      document.documentElement.removeAttribute('data-font')
    }
    localStorage.setItem('archithon_font', font)
  }, [font])

  function setTheme(next: string) {
    if (!VALID_THEMES.includes(next as Theme)) return
    setThemeState(next as Theme)
    if (getToken()) updateMyProfile({ theme: next }).catch(() => {})
  }

  function setFont(next: string) {
    if (!VALID_FONTS.includes(next as Font)) return
    setFontState(next as Font)
    if (getToken()) updateMyProfile({ font: next }).catch(() => {})
  }

  // Apply server-side theme/font on login (cross-device sync).
  // Does NOT PATCH back — server is the source of truth here.
  function hydrate(serverTheme: unknown, serverFont: unknown) {
    setThemeState(migrateTheme(serverTheme))
    setFontState(migrateFont(serverFont))
  }

  return (
    <ThemeContext.Provider value={{ theme, font, setTheme, setFont, hydrate }}>
      {children}
    </ThemeContext.Provider>
  )
}

