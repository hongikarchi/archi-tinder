import { useState, useEffect } from 'react'
import { ThemeContext } from './_themeContext.js'

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
    // TODO(PR#2): if logged in, PATCH /users/me/ { theme } for cross-device sync
  }, [theme])

  // Apply font attribute + persist
  useEffect(() => {
    if (font === 'noto-serif') {
      document.documentElement.setAttribute('data-font', 'noto-serif')
    } else {
      document.documentElement.removeAttribute('data-font')
    }
    localStorage.setItem('archithon_font', font)
    // TODO(PR#2): if logged in, PATCH /users/me/ { font } for cross-device sync
  }, [font])

  function setTheme(next) {
    if (VALID_THEMES.includes(next)) setThemeState(next)
  }

  function setFont(next) {
    if (VALID_FONTS.includes(next)) setFontState(next)
  }

  return (
    <ThemeContext.Provider value={{ theme, font, setTheme, setFont }}>
      {children}
    </ThemeContext.Provider>
  )
}

