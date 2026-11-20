import Modal from './Modal.tsx'
import { useTranslation } from '../i18n/index.ts'
import s from './ConfirmDialog.module.css'

/**
 * ConfirmDialog — centered two-button confirm on the shared Modal (DESIGN.md
 * §8.10, `centered` + `portal` so it clears the TabBar at every width).
 * Props: open, title, body, confirmLabel, cancelLabel, onConfirm, onCancel.
 */
interface ConfirmDialogProps {
  open: boolean
  title: string
  body: string
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({ open, title, body, confirmLabel, cancelLabel, onConfirm, onCancel }: ConfirmDialogProps) {
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
