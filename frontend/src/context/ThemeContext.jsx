import { useState, useEffect } from 'react'
import { ThemeContext } from './_themeContext.js'
import { getToken } from '../api/core.js'
import { updateMyProfile } from '../api/profiles.js'

const VALID_THEMES = ['github-light', 'github-dark', 'ayu-light', 'synthwave-84']
const VALID_FONTS  = ['plex', 'noto-serif']

/**
 * Migrate legacy theme keys stored before the design-system redesign:
 *   'dark'  → 'github-dark'
 *   'light' → 'github-light'
 *   unknown → 'github-light'
 */
function migrateTheme(raw) {
  if (raw === 'dark') return 'github-dark'
  if (raw === 'light') return 'github-light'
  if (VALID_THEMES.includes(raw)) return raw
  return 'github-light'
}

function migrateFont(raw) {
  if (VALID_FONTS.includes(raw)) return raw
  return 'plex'
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    const raw = localStorage.getItem('archithon_theme')
    return migrateTheme(raw)
  })

  const [font, setFontState] = useState(() => {
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

  function setTheme(next) {
    if (!VALID_THEMES.includes(next)) return
    setThemeState(next)
    if (getToken()) updateMyProfile({ theme: next }).catch(() => {})
  }

  function setFont(next) {
    if (!VALID_FONTS.includes(next)) return
    setFontState(next)
    if (getToken()) updateMyProfile({ font: next }).catch(() => {})
  }

  // Apply server-side theme/font on login (cross-device sync).
  // Does NOT PATCH back — server is the source of truth here.
  function hydrate(serverTheme, serverFont) {
    setThemeState(migrateTheme(serverTheme))
    setFontState(migrateFont(serverFont))
  }

  return (
    <ThemeContext.Provider value={{ theme, font, setTheme, setFont, hydrate }}>
      {children}
    </ThemeContext.Provider>
  )
}

