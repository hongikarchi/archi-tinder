import styles from './Tabs.module.css'

/**
 * Tabs — shared underline tab bar (DESIGN.md decisions log item, "one
 * underline Tabs component (profile style)").
 *
 * Matches UserProfilePage's tab markup 1:1 (extracted, not redesigned):
 * `role="tablist"` wrapper, `role="tab"` + `aria-selected` buttons, flex-1
 * equal-width tabs, ink-underline active state.
 *
 * `tabs`: [{ id, label }]. `value`: the active tab id. `onChange(id)`: fired
 * on click — callers that lazy-load tab content (UserProfilePage's
 * Studios/Liked/Created tabs) keep their own fetch-on-first-select logic in
 * the `onChange` handler, exactly as the inline `onClick` handlers did.
 */
export default function Tabs({ tabs, value, onChange, style, className = '' }) {
  return (
    <div role="tablist" className={`${styles.tabs} ${className}`} style={style}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={value === tab.id}
          onClick={() => onChange(tab.id)}
          className={`${styles.tab} ${value === tab.id ? styles.tabActive : ''}`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
