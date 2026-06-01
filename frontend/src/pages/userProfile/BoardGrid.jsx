import BoardCard from '../../components/profile/BoardCard'

export default function BoardGrid({
  boards,
  isMe,
  selectMode,
  selectedBoards,
  onVisibilityChange,
  onDelete,
  onSelectToggle,
  boardsHasMore,
  boardsLoading,
  onResumeProject,
  onNewProjectSession,
}) {
  return (
    <>
      {/* Boards grid — same unified container, responsive auto-fill */}
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
              onVisibilityChange={(next) => onVisibilityChange(board.board_id, next)}
              onDelete={() => onDelete(board.board_id)}
              selectMode={selectMode}
              isSelected={selectedBoards.has(board.board_id)}
              onSelectToggle={onSelectToggle}
              directNavigate={!board.latest_session_meta}
              onResume={onResumeProject ? () => onResumeProject(board.board_id) : undefined}
              onStartNew={onNewProjectSession ? () => onNewProjectSession(board.board_id) : undefined}
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
