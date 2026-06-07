import { useTheme } from '../hooks/useTheme.js'
import { useLanguage } from '../hooks/useLanguage.js'
import { useTranslation } from '../i18n/index.js'
import styles from './AppearanceSettings.module.css'

/*
 * THEMES — bg + 3 accent dots (literal hex from tokens.css per-theme blocks).
 * Used for the static swatch preview tiles — NOT theme-reactive intentionally,
 * so each tile always shows its own colors regardless of active theme.
 *
 * Accent hex sourced directly from tokens.css [data-theme="..."] blocks.
 */
const THEMES = [
  {
    id: 'github-light',
    label: 'GitHub Light',
    bg: '#FFFFFF',
    text: '#1F2328',
    accents: ['#0969DA', '#8250DF', '#953800'],
  },
  {
    id: 'github-dark',
    label: 'GitHub Dark',
    bg: '#0d1117',
    text: '#e6edf3',
    accents: ['#2f81f7', '#a371f7', '#e3b341'],
  },
  {
    id: 'ayu-light',
    label: 'Ayu Light',
    bg: '#FCFCFC',
    text: '#3D4047',
    accents: ['#FA8D3E', '#86B300', '#E6BA7E'],
  },
  {
    id: 'synthwave-84',
    label: "SynthWave '84",
    bg: '#262335',
    text: '#f0eff1',
    accents: ['#FF7EDB', '#36F9F6', '#FDE24F'],
  },
]

/*
 * Font toggle config (design.md §6)
 * The button label always reads "Font" but is rendered in the font it will
 * switch TO — so clicking shows what the app will look like after the switch.
 */
const FONT_OPTIONS = [
  {
    id: 'plex',
    nextFontFamily: '"Noto Serif KR", "본명조", Georgia, serif',
    nextLabel: 'noto-serif',
  },
  {
    id: 'noto-serif',
    nextFontFamily: '"IBM Plex Sans KR", "Noto Sans KR", system-ui, sans-serif',
    nextLabel: 'plex',
  },
]

const LANGUAGE_OPTIONS = [
  { id: 'ko', label: '한국어' },
  { id: 'en', label: 'English' },
]

/*
 * SwatchTile — static preview of a theme's bg + accent dots.
 * Selection state: 2px accent border + glow shadow (design.md §5.2 swatch style).
 * --accent-1 here is the LIVE theme's accent (reactive to active theme), which
 * is intentional — the glow color tracks the current session theme.
 */
function SwatchTile({ thm, isSelected, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(thm.id)}
      title={thm.label}
      aria-label={thm.label}
      aria-pressed={isSelected}
      className={styles.swatchButton}
    >
      <div
        className={styles.swatchTile}
        style={{
          background: thm.bg,
          border: isSelected
            ? '2px solid var(--accent-1)'
            : '1px solid rgba(127,127,127,0.2)',
          boxShadow: isSelected
            ? '0 0 0 3px color-mix(in srgb, var(--accent-1) 22%, transparent)'
            : 'none',
        }}
      >
        {/* Text sample — always uses the theme's own text color (static preview) */}
        <span style={{
          fontSize: 15,
          fontWeight: 700,
          color: thm.text,
          lineHeight: 1,
        }}>
          Aa
        </span>
        {/* 3 accent dots */}
        <div style={{ display: 'flex', gap: 6 }}>
          {thm.accents.map((c) => (
            <span
              key={c}
              style={{
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: c,
                boxShadow: 'inset 0 0 0 1px rgba(127,127,127,0.25)',
              }}
            />
          ))}
        </div>
      </div>
    </button>
  )
}

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

      {/* Theme row — 2-column swatch grid */}
      <div style={{ marginBottom: 20 }}>
        <p style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--color-text-2)',
          margin: '0 0 10px',
        }}>
          Theme
        </p>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
        }}>
          {THEMES.map(thm => (
            <SwatchTile
              key={thm.id}
              thm={thm}
              isSelected={theme === thm.id}
              onSelect={setTheme}
            />
          ))}
        </div>
      </div>

      {/* Font row — unchanged wiring, chip class for hover/focus */}
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
          className={styles.chip}
          style={{
            border: '1.5px solid var(--color-border-soft)',
            background: 'var(--color-surface)',
            fontWeight: 500,
            color: 'var(--color-text-2)',
            fontFamily: currentFont.nextFontFamily,
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

      {/* Language row — unchanged wiring, chip class for hover/focus */}
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
                className={styles.chip}
                style={{
                  border: isActive
                    ? '2px solid var(--accent-1)'
                    : '1.5px solid var(--color-border-soft)',
                  background: isActive
                    ? 'var(--color-surface-2)'
                    : 'var(--color-surface)',
                  fontWeight: isActive ? 600 : 400,
                  color: 'var(--color-text-2)',
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
