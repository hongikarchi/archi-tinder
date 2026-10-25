import Modal from './Modal.jsx'
import { useTranslation } from '../i18n/index.js'
import s from './ConfirmDialog.module.css'

/**
 * ConfirmDialog — centered two-button confirm on the shared Modal (DESIGN.md
 * §8.10, `centered` + `portal` so it clears the TabBar at every width).
 * Props: open, title, body, confirmLabel, cancelLabel, onConfirm, onCancel.
 */
export default function ConfirmDialog({ open, title, body, confirmLabel, cancelLabel, onConfirm, onCancel }) {
  const { t } = useTranslation()
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      width={360}
      centered
      portal
      zIndex={10001}
      closeLabel={t('modalB3.close')}
    >
      <p className={s.body}>{body}</p>
      <div className={s.actions}>
        <button type="button" className={`${s.btn} ${s.cancel}`} onClick={onCancel}>
          {cancelLabel}
        </button>
        <button type="button" className={`${s.btn} ${s.ok}`} onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </Modal>
  )
}
