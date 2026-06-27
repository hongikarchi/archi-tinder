import { useParams } from 'react-router-dom'
import LLMSearchPage from '../pages/LLMSearchPage.jsx'

/* ── LLMSearch update-mode wrapper ──────────────────────────────────────── */
export default function LLMSearchUpdateWrapper({ onBack, onStart, onUpdate }) {
  const { projectId } = useParams()
  return (
    <LLMSearchPage
      mode="update"
      projectId={projectId}
      onBack={onBack}
      onStart={onStart}
      onUpdate={onUpdate}
    />
  )
}
