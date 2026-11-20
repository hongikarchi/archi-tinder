import BoardCard from '../../components/profile/BoardCard.tsx'
import { useTranslation } from '../../i18n/index.ts'
import type { ProfileBoard } from '../../types/api.ts'
import { atHandle } from '../../utils/userIdentity.ts'

interface BoardGridProps {
  boards: (ProfileBoard & { owner?: any })[]
  isMe?: boolean
  selectMode?: boolean
  selectedBoards: Set<string>
  onSelectToggle?: (boardId: string) => void
  boardsHasMore?: boolean
  boardsLoading?: boolean
  showOwner?: boolean
}

export default function BoardGrid({
  boards,
  isMe,
  selectMode,
  selectedBoards,
  onSelectToggle,
  boardsHasMore,
  boardsLoading,
  showOwner = false,
}: BoardGridProps) {
  const { t } = useTranslation()
  return (
    <>
      {/* Boards grid — responsive auto-fill, one tall tile per row on phones */}
      {boards.length > 0 ? (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 20,
        }}>
          {boards.map(board => (
            <BoardCard
              key={board.board_id}
              board={board}
              isOwner={isMe}
              selectMode={selectMode}
              isSelected={selectedBoards.has(board.board_id)}
              onSelectToggle={onSelectToggle}
              ownerLabel={showOwner ? atHandle(board.owner) : ''}
            />
          ))}
        </div>
      ) : (!boardsHasMore && !boardsLoading && (
        <div style={{
          color: 'var(--color-text-dim)', fontSize: 14, textAlign: 'center', padding: '40px 0',
        }}>
          {t('board.noBoards')}
        </div>
      ))}
    </>
  )
}
