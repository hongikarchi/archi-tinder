import { useTranslation } from '../../i18n/index.js'

/**
 * EditActionBar — owner edit-mode floating bar (persona-report mock `editBar`):
 * no container, two solid buttons + a solid notice pill above them.
 * Shared by BoardDetailPage and the merged report page.
 *
 *   lastMsgOn      show the "last building can't be deleted" message
 *   regenNotice    string|null  secondary notice (e.g. deleting regenerates the report)
 *   selectedCount  number of selected buildings
 *   busy           null | 'saving-name' | 'deleting'
 */
export default function EditActionBar({ lastMsgOn, regenNotice = null, selectedCount, busy, onCancel, onDelete }) {
  const { t } = useTranslation()
  return (
    <div style={{
      position: 'fixed',
      left: 16, right: 16,
      bottom: 'var(--tabbar-clearance)',
      maxWidth: 420,
      margin: '0 auto',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 10,
      zIndex: 200,
    }}>
      <div role="status" aria-live="polite">
      {(lastMsgOn || regenNotice) && (
        <span style={{
          padding: '6px 12px',
          borderRadius: 'var(--radius-pill)',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-soft)',
          boxShadow: '0 4px 12px rgba(0,0,0,.12)',
          fontSize: 'var(--fs-caption)',
          color: lastMsgOn ? 'var(--color-text)' : 'var(--color-text-dim)',
          fontWeight: lastMsgOn ? 'var(--fw-semibold)' : 'var(--fw-regular)',
          textAlign: 'center',
        }}>
          {lastMsgOn ? t('board.lastBuilding') : regenNotice}
        </span>
      )}
      </div>
      <div style={{ display: 'flex', gap: 10, width: '100%' }}>
        <button
          onClick={onCancel}
          disabled={!!busy}
          style={{
            flex: 1, minHeight: 44, borderRadius: 'var(--radius-md)',
            background: 'var(--color-surface)', color: 'var(--color-text)',
            border: '1px solid var(--color-border)',
            boxShadow: '0 6px 18px rgba(0,0,0,.18)',
            fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
            fontFamily: 'inherit', cursor: 'pointer',
          }}
        >
          {t('board.cancel')}
        </button>
        <button
          onClick={onDelete}
          disabled={selectedCount === 0 || !!busy}
          style={{
            flex: 2, minHeight: 44, borderRadius: 'var(--radius-md)',
            background: selectedCount > 0 ? 'var(--color-text)' : 'var(--color-surface-2)',
            color: selectedCount > 0 ? 'var(--color-bg)' : 'var(--color-text-dim)',
            border: 'none',
            boxShadow: selectedCount > 0 ? '0 6px 18px rgba(0,0,0,.25)' : 'none',
            fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-semibold)',
            cursor: selectedCount === 0 ? 'default' : 'pointer',
            fontFamily: 'inherit',
            opacity: busy ? 0.6 : 1,
            transition: 'background var(--motion-normal) var(--motion-ease), color var(--motion-normal) var(--motion-ease)',
          }}
        >
          {busy === 'deleting'
            ? t('board.deleting')
            : selectedCount > 0
              ? t(selectedCount === 1 ? 'board.deleteCardOne' : 'board.deleteCardMany', { n: selectedCount })
              : t('board.selectToDelete')}
        </button>
      </div>
    </div>
  )
}
