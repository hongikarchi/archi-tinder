import { useTheme } from '../hooks/useTheme.js'
import { useLanguage } from '../hooks/useLanguage.js'
import { useTranslation } from '../i18n/index.js'

/*
 * Theme chip config — bg + accent-1 per theme (design.md §5.2)
 * bg is the chip background preview; accent is the overlaid accent circle.
 */
const THEMES = [
  { id: 'github-light',  label: 'GitHub Light',  bg: '#FFFFFF',  accent: '#0969DA' },
  { id: 'github-dark',   label: 'GitHub Dark',   bg: '#0d1117',  accent: '#2f81f7' },
  { id: 'ayu-light',     label: 'Ayu Light',     bg: '#FCFCFC',  accent: '#FA8D3E' },
  { id: 'synthwave-84',  label: 'SynthWave \'84', bg: '#262335',  accent: '#FF7EDB' },
]

/*
 * Font toggle config (design.md §6)
 * The button label always reads "Font" but is rendered in the font it will
 * switch TO — so clicking shows what the app will look like after the switch.
 */
const FONT_OPTIONS = [
  {
    id: 'plex',
    // When plex is active, button switches to noto-serif → show noto-serif stack
    nextFontFamily: '"Noto Serif KR", "본명조", Georgia, serif',
    nextLabel: 'noto-serif',
  },
  {
    id: 'noto-serif',
    // When noto-serif is active, button switches to plex → show plex stack
    nextFontFamily: '"IBM Plex Sans KR", "Noto Sans KR", system-ui, sans-serif',
    nextLabel: 'plex',
  },
]

const LANGUAGE_OPTIONS = [
  { id: 'ko', label: '한국어' },
  { id: 'en', label: 'English' },
]

export default function AppearanceSettings() {
  const { theme, font, setTheme, setFont } = useTheme()
  const { language, setLanguage } = useLanguage()
  const { t } = useTranslation()

  const currentFont = FONT_OPTIONS.find(f => f.id === font) || FONT_OPTIONS[0]

  return (
    <section style={{ padding: '0 0 24px' }}>
      <h3 style={{
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--color-text-muted)',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        margin: '0 0 16px',
      }}>
        {t('settings.appearance')}
      </h3>

      {/* Theme row */}
      <div style={{ marginBottom: 20 }}>
        <p style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--color-text-2)',
          margin: '0 0 10px',
        }}>
          Theme
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {THEMES.map(thm => {
            const isActive = theme === thm.id
            return (
              <button
                key={thm.id}
                onClick={() => setTheme(thm.id)}
                title={thm.label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 14px',
                  borderRadius: 999,
                  border: isActive
                    ? '2px solid var(--accent-1)'
                    : '1.5px solid var(--color-border-soft)',
                  background: isActive
                    ? 'var(--color-surface-2)'
                    : 'var(--color-surface)',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  color: 'var(--color-text-2)',
                  transition: 'border-color 0.18s, background 0.18s',
                  outline: 'none',
                }}
              >
                {/* Stacked preview circles: bg base + accent dot */}
                <span style={{ position: 'relative', width: 20, height: 20, flexShrink: 0 }}>
                  {/* bg circle */}
                  <span style={{
                    position: 'absolute',
                    inset: 0,
                    borderRadius: '50%',
                    background: thm.bg,
                    border: '1px solid rgba(0,0,0,0.12)',
                  }} />
                  {/* accent dot — bottom-right overlap */}
                  <span style={{
                    position: 'absolute',
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background: thm.accent,
                    bottom: -2,
                    right: -2,
                    border: '1.5px solid var(--color-bg)',
                  }} />
                </span>
                {thm.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Font row */}
      <div>
        <p style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--color-text-2)',
          margin: '0 0 10px',
        }}>
          Font
        </p>
        <button
          onClick={() => setFont(currentFont.nextLabel)}
          style={{
            padding: '6px 14px',
            borderRadius: 999,
            border: '1.5px solid var(--color-border-soft)',
            background: 'var(--color-surface)',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--color-text-2)',
            fontFamily: currentFont.nextFontFamily,
            transition: 'border-color 0.18s',
            outline: 'none',
          }}
        >
          Font
        </button>
        <span style={{
          marginLeft: 10,
          fontSize: 12,
          color: 'var(--color-text-muted)',
          fontStyle: 'italic',
        }}>
          {font === 'plex' ? 'IBM Plex Sans KR' : 'Noto Serif KR'} — click to switch
        </span>
      </div>

      {/* Language row */}
      <div style={{ marginTop: 20 }}>
        <p style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--color-text-2)',
          margin: '0 0 10px',
        }}>
          {t('settings.language')}
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {LANGUAGE_OPTIONS.map(opt => {
            const isActive = language === opt.id
            return (
              <button
                key={opt.id}
                onClick={() => setLanguage(opt.id)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 999,
                  border: isActive
                    ? '2px solid var(--accent-1)'
                    : '1.5px solid var(--color-border-soft)',
                  background: isActive
                    ? 'var(--color-surface-2)'
                    : 'var(--color-surface)',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  color: 'var(--color-text-2)',
                  transition: 'border-color 0.18s, background 0.18s',
                  outline: 'none',
                }}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
