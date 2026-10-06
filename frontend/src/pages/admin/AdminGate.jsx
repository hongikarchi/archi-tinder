/**
 * AdminGate — route guard for /admin/*. UX only: the backend IsAdminOperator
 * permission is the real gate. While /auth/me/ has not answered (null) render
 * the neutral route fallback; a non-admin is sent back to '/'.
 */
import { Suspense } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAdminStatus } from '../../hooks/useAdminStatus.js'
import RouteFallback from '../../components/RouteFallback.jsx'

export default function AdminGate() {
  const isAdmin = useAdminStatus()
  if (isAdmin === null) return <RouteFallback />
  if (isAdmin !== true) return <Navigate to="/" replace />
  return (
    <Suspense fallback={<RouteFallback />}>
      <Outlet />
    </Suspense>
  )
}
