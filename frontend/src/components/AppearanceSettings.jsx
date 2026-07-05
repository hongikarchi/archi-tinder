import { useTheme } from '../hooks/useTheme.js'
import { useLanguage } from '../hooks/useLanguage.js'
import { useTranslation } from '../i18n/index.js'
import ThemePreviewCard from './ThemePreviewCard.jsx'
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
 * Font chip config (SETTINGS-POLISH-1 §C — replaces the single always-says-
 * "Font" toggle button with two chips, one per candidate). Each chip is
 * rendered in its OWN font so the user can see the difference at a glance.
 * fontFamily stacks mirror tokens.css --font-family / [data-font="noto-serif"].
 */
const FONT_OPTIONS = [
  {
    id: 'plex',
    label: 'IBM Plex Sans KR',
    fontFamily: '"IBM Plex Sans KR", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "맑은 고딕", system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
  },
  {
    id: 'noto-serif',
    label: 'Noto Serif KR',
    fontFamily: '"Noto Serif KR", "본명조", "Nanum Myeongjo", "나눔명조", "AppleMyungjo", "Batang", "바탕", Georgia, serif',
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
          {t('settings.theme')}
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

        {/* Mini app-screen mockup previewing the selected theme (SETTINGS-POLISH-1 §D) */}
        <div style={{ marginTop: 14 }}>
          <p style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--color-text-muted)',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            margin: '0 0 8px',
          }}>
            {t('settings.preview')}
          </p>
          <ThemePreviewCard theme={theme} />
        </div>
      </div>

      {/* Font row — two chips, each rendered in its own font (SETTINGS-POLISH-1 §C) */}
      <div>
        <p style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--color-text-2)',
          margin: '0 0 10px',
        }}>
          {t('settings.font')}
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {FONT_OPTIONS.map(opt => {
            const isActive = font === opt.id
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setFont(opt.id)}
                aria-pressed={isActive}
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
                  fontFamily: opt.fontFamily,
                }}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
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
