import SegmentedControl from './SegmentedControl.jsx'
import styles from './Tabs.module.css'

/**
 * Tabs — shared underline tab bar (DESIGN.md decisions log item, "one
 * underline Tabs component (profile style)").
 *
 * UI-CONSISTENCY-B Phase 2d: now a thin wrapper over SegmentedControl
 * (variant="underline", as="tabs") so the active underline SLIDES between
 * tabs instead of jumping. Public API is unchanged for callers:
 * `tabs`: [{ id, label }]. `value`: the active tab id. `onChange(id)`: fired
 * on click — callers that lazy-load tab content (UserProfilePage's
 * Studios/Liked/Created tabs) keep their own fetch-on-first-select logic in
 * the `onChange` handler, exactly as before.
 */
export default function Tabs({ tabs, value, onChange, style, className = '' }) {
  return (
    <SegmentedControl
      as="tabs"
      variant="underline"
      fullWidth
      className={`${styles.tabs} ${className}`}
      style={style}
      options={tabs.map((tab) => ({ value: tab.id, label: tab.label }))}
      value={value}
      onChange={onChange}
      optionClassName={(opt, isActive) => `${styles.tab} ${isActive ? styles.tabActive : ''}`}
      highlightStyle={{ background: 'var(--color-text)' }}
      renderOption={(opt) => opt.label}
    />
  )
}
