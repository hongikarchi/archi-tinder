/**
 * utils/shareBoard.js
 * Share the current board link: native share sheet when available, clipboard
 * copy otherwise (same behaviour as BoardDetailPage's handleShare).
 *   onCopied / onCopyFailed  () => void   toast hooks for the clipboard path
 */
export async function shareBoardLink({ title, text, url = window.location.href, onCopied, onCopyFailed }) {
  const shareData = { title, text, url }
  if (navigator.share && navigator.canShare?.(shareData)) {
    try { await navigator.share(shareData) } catch { /* user cancelled */ }
    return
  }
  try {
    await navigator.clipboard.writeText(url)
    onCopied?.()
  } catch {
    onCopyFailed?.()
  }
}
