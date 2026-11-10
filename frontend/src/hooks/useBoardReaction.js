import { useEffect, useState } from 'react'
import { reactToProject, unreactToProject } from '../api/social.js'
import { useTranslation } from '../i18n/index.js'

/**
 * useBoardReaction — viewer "love this board" state + optimistic toggle with
 * rollback. Shared by BoardDetailPage and the merged report page.
 *
 *   const { isReacted, reactionCount, isPending, error, toggle } = useBoardReaction(board)
 *
 * `board` is the useBoard payload (needs project_id, is_reacted, reaction_count).
 * State re-initialises whenever a new board object arrives.
 */
export function useBoardReaction(board) {
  const { t } = useTranslation()
  const [isReacted, setIsReacted] = useState(false)
  const [reactionCount, setReactionCount] = useState(0)
  const [isPending, setIsPending] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!board) return
    setIsReacted(!!board.is_reacted)
    setReactionCount(board.reaction_count ?? 0)
    setError(null)
  }, [board])

  async function toggle() {
    if (!board || isPending) return

    const wasReacted = isReacted
    const previousCount = reactionCount
    const nextReacted = !wasReacted
    setIsPending(true)
    setError(null)
    setIsReacted(nextReacted)
    setReactionCount(prev => Math.max(0, prev + (nextReacted ? 1 : -1)))

    try {
      const resp = nextReacted
        ? await reactToProject(board.project_id)
        : await unreactToProject(board.project_id)
      if (resp?.reaction_count !== undefined) setReactionCount(resp.reaction_count)
      if (resp?.reacted !== undefined) setIsReacted(!!resp.reacted)
    } catch (err) {
      setIsReacted(wasReacted)
      setReactionCount(previousCount)
      setError(err.message || t('board.reactionFailed'))
    } finally {
      setIsPending(false)
    }
  }

  return { isReacted, reactionCount, isPending, error, toggle }
}
