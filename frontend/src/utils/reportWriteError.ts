/**
 * reportWriteError — surface a failed write (POST) as a global error toast.
 * Reuses the App-level globalToast (passed in as `showToast`); safe no-op if absent.
 */
export function reportWriteError(showToast: ((t: { message: string; type: string }) => void) | null | undefined, message: string = '저장 실패 — 다시 시도해주세요') {
  showToast?.({ message, type: 'error' })
}
