import { useTheme } from '../hooks/useTheme.js'
import { useLanguage } from '../hooks/useLanguage.js'
import { useTranslation } from '../i18n/index.js'
import { discoveryNavigationGuard } from '../utils/discoveryGuard.js'
import FloatingIconButton from './FloatingIconButton.jsx'
import SegmentedControl from './SegmentedControl.jsx'
import styles from './PageTopControls.module.css'

/**
 * PageTopControls — shared top-right controls cluster: language pill + theme
 * pill + (optional) logout button.
 *
 * Design port (.claude/plans/canvas-design-port.md): 42 boards render this
 * exact cluster (frontend/public/__mocks/discovery.html markup) — the user
 * confirmed language/theme switching belongs top-right on every page, not
 * only Settings → Appearance (which keeps working unchanged; this is an
 * additional shortcut).
 *
 * Positioning is OWNED by this component (every caller wants the same spot).
 * The mock uses `position:absolute` inside its own 1440x900 canvas; the real
 * app has no positioned ancestor at that level, so `fixed` is the faithful
 * equivalent (LoginPage's prior `langToggleWrapStyle` made this exact call
 * first — this component generalizes it).
 *
 * Theme pill — sun/moon only (mock parity), NOT a 4-way switcher and NOT a
 * light/dark toggle-pair:
 *   - sun  -> setTheme('github-light')  (exact target, mirrors the mock's
 *             onclick literally setting data-theme to 'github-light')
 *   - moon -> setTheme('github-dark')   (same, 'github-dark')
 *   - "selected" style applies only on an EXACT theme match. On ayu-light or
 *     synthwave-84, NEITHER button shows selected — this is intentional: the
 *     sun button must never falsely claim ayu-light as "light mode selected"
 *     (clicking it would silently switch the user off ayu-light to
 *     github-light). Settings -> Appearance keeps the full 4-theme swatch
 *     grid; this pill is a 2-theme shortcut, not a replacement.
 *
 * Logout — renders ONLY when `onLogout` is passed. Reuses MainLayout's exact
 * wiring (discoveryNavigationGuard.check gate) rather than reimplementing it.
 * LoginPage passes no `onLogout` (unauthenticated page) -> no logout button,
 * even though the mock's markup includes one (meaningless pre-login).
 */
export default function PageTopControls({ onLogout, splitMobile = false }) {
  const { theme, setTheme } = useTheme()
  const { language, setLanguage } = useLanguage()
  const { t } = useTranslation()

  const stop = (e) => e.stopPropagation()

  function handleLogoutClick() {
    if (discoveryNavigationGuard.check) {
      discoveryNavigationGuard.check('logout', onLogout)
    } else {
      onLogout()
    }
  }

  return (
    <div
      onPointerDown={stop}
      onMouseDown={stop}
      onTouchStart={stop}
      className={`${styles.controls} ${splitMobile ? styles.splitMobile : ''}`}
      style={wrapStyle}
    >
      {/* Language pill — variant="pill" size="sm": the shared sliding
          highlight replaces the old per-button background swap (see
          SegmentedControl docblock); `pillHeight=22` matches the buttons'
          own height so the highlight fills them exactly (the outer 28px
          pill height belongs to the track, not the highlight). */}
      <SegmentedControl
        as="radio"
        variant="pill"
        size="sm"
        pillHeight={22}
        className={styles.languagePill}
        style={pillStyle}
        options={[
          { value: 'ko', label: t('login.common.langKo') },
          { value: 'en', label: t('login.common.langEn') },
        ]}
        value={language}
        onChange={setLanguage}
        optionClassName="pressable"
        optionStyle={(opt, isActive) => tgStyle(isActive)}
        highlightStyle={{ background: 'var(--color-bg)', boxShadow: '0 1px 3px rgba(0,0,0,0.14)' }}
        renderOption={(opt) => opt.label}
      />

      {/* Theme pill — sun / moon, mock parity (see module docblock).
          "selected" (and the sliding highlight) shows only on an EXACT theme
          match — `value={theme}` naturally has no match on ayu-light /
          synthwave-84, which SegmentedControl treats as "nothing selected"
          rather than falling back to one of the two buttons. */}
      <SegmentedControl
        as="radio"
        variant="pill"
        size="sm"
        pillHeight={22}
        style={pillStyle}
        options={[
          { value: 'github-light', ariaLabel: 'Light theme', icon: (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
            </svg>
          ) },
          { value: 'github-dark', ariaLabel: 'Dark theme', icon: (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) },
        ]}
        value={theme}
        onChange={setTheme}
        optionClassName="pressable"
        optionStyle={(opt, isActive) => tgIconStyle(isActive)}
        highlightStyle={{ background: 'var(--color-bg)', boxShadow: '0 1px 3px rgba(0,0,0,0.14)' }}
        renderOption={(opt) => opt.icon}
      />

      {/* Logout — only when a caller has one to wire up */}
      {onLogout && (
        <FloatingIconButton
          onClick={handleLogoutClick}
          title="Log out"
          ariaLabel="Log out"
          className={styles.logoutBtn}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </FloatingIconButton>
      )}
    </div>
  )
}

// ── Styles ──────────────────────────────────────────────────────────────────
// Layout / one-off / dynamic values -> inline per DESIGN.md §4. Colors are
// tokens throughout; the one literal is the mock's own selected-state shadow
// (shadows are a §4 exemption).

const wrapStyle = {
  position: 'fixed',
  top: 16,
  right: 12,
  zIndex: 300,
  display: 'flex',
  gap: 6,
  alignItems: 'center',
}

const pillStyle = {
  display: 'flex',
  alignItems: 'center',
  height: 28,
  boxSizing: 'border-box',
  padding: 2,
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-pill)',
}

// Mock .tg base rule, selected state from .tg-ko/.tg-en/.tg-light/.tg-dark.
// Background + box-shadow moved OUT of here — SegmentedControl's shared
// sliding highlight now owns that "selected" chrome (see its `highlightStyle`
// prop at each call site below); this stays foreground-only (color/type),
// matching the split documented in SegmentedControl's docblock.
function tgStyle(selected) {
  return {
    border: 0,
    background: 'transparent',
    color: selected ? 'var(--color-text)' : 'var(--color-text-muted)',
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '0.04em',
    cursor: 'pointer',
    borderRadius: 'var(--radius-pill)',
    height: 22,
    padding: '0 8px',
    display: 'flex',
    alignItems: 'center',
    fontFamily: 'inherit',
    lineHeight: 1,
  }
}

// Mock .tg.tgi icon-only variant — same base, tighter horizontal padding.
function tgIconStyle(selected) {
  return { ...tgStyle(selected), padding: '0 6px' }
}
