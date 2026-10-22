import BoardCard from '../../components/profile/BoardCard'

export default function BoardGrid({
  boards,
  isMe,
  selectMode,
  selectedBoards,
  onSelectToggle,
  boardsHasMore,
  boardsLoading,
}) {
  return (
    <>
      {/* Boards grid — exactly 2 columns at every width */}
      {boards.length > 0 ? (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 12,
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
          No boards yet.
        </div>
      ))}
    </>
  )
}
