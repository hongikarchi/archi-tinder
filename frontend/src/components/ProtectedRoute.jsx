import { Navigate } from 'react-router-dom'

export default function ProtectedRoute({ userId, children }) {
  if (!userId) return <Navigate to="/login" replace />
  return children
}
