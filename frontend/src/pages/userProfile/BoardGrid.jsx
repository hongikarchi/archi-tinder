import BoardCard from '../../components/profile/BoardCard'
import { useTranslation } from '../../i18n/index.js'

export default function BoardGrid({
  boards,
  isMe,
  selectMode,
  selectedBoards,
  onSelectToggle,
  boardsHasMore,
  boardsLoading,
}) {
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
