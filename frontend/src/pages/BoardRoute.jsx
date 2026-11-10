import { useEffect, useState } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useBoard } from '../hooks/useBoard.js'
import BoardDetailPage from './BoardDetailPage.jsx'
import BoardReportPage from './BoardReportPage.jsx'
import PersonaReportPage from '../components/PersonaReportPage.jsx'

/* ── BoardRoute ─────────────────────────────────────────────────────────── */
// Chooser mounted at /board/:boardId. Loads the board once, then renders:
//   - the merged persona-report page (BoardReportPage) when the board HAS a
//     final_report (owner -> owner tools, non-owner on a public board -> read-only),
//     or when the owner just saved a board (location.state.saved: the report page
//     generates / shows the report for it);
//   - the unchanged BoardDetailPage for boards WITHOUT a report (owner + viewer);
//   - the report page's own state screens (unavailable / load-fail) when the
//     board could not be loaded (private -> 403/404).
// The single useBoard load is shared with whichever page renders; BoardDetailPage
// only adds the owner-only session-result fetch on top.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// Keyed by the URL param so navigating between boards resets the chooser state.
export default function BoardRoute(props) {
  const { boardId } = useParams()
  return <BoardRouteInner key={boardId} {...props} />
}

function BoardRouteInner({ onResume, onLogout }) {
  const { boardId: rawBoardId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  // Malformed URL param -> null, never reaches the API layer.
  const boardId = UUID_RE.test(String(rawBoardId || '')) ? rawBoardId : null
  const boardData = useBoard(boardId, { fetchResult: false })
  const { board, loading } = boardData

  // Once the report page was chosen it stays chosen: the post-save landing drops
  // location.state.saved right after mount, and the fetched board copy still has
  // no report (the page holds the freshly generated one in local state).
  const wantsReport = !!board && (!!board.final_report || !!location.state?.saved)
  const [latched, setLatched] = useState(false)
  useEffect(() => { if (wantsReport) setLatched(true) }, [wantsReport])

  if (!boardId || (!board && !loading)) {
    return (
      <BoardReportPage boardId={boardId} boardData={boardData} onResume={onResume} onLogout={onLogout} />
    )
  }
  if (loading && !board) {
    return (
      <PersonaReportPage
        state="fetching"
        onLogout={onLogout}
        onBack={() => navigate(-1)}
      />
    )
  }
  if (wantsReport || latched) {
    return (
      <BoardReportPage boardId={boardId} boardData={boardData} onResume={onResume} onLogout={onLogout} />
    )
  }
  return <BoardDetailPage boardData={boardData} onResume={onResume} onLogout={onLogout} />
}
