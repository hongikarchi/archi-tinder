import { useSyncExternalStore } from 'react'
import { generateReportImage } from '../api/projects.js'
import { createReportImageJobs } from '../utils/reportImageJobs.js'

// App-wide persona-image job store (see utils/reportImageJobs.js).
// 70s timeout: the backend holds a duplicate request up to ~25s before a 202.
export const reportImageJobs = createReportImageJobs(
  (id) => generateReportImage(id, { timeoutMs: 70000 }),
)

/** Subscribe to one project's persona-image job. Returns { status, image, mime }. */
export function useReportImageJob(projectId) {
  return useSyncExternalStore(
    reportImageJobs.subscribe,
    () => reportImageJobs.get(projectId),
    () => reportImageJobs.get(projectId),
  )
}
