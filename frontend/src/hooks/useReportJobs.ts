import { generateReport } from '../api/projects.ts'
import { createReportJobs } from '../utils/reportJobs.ts'

// App-wide in-flight store for report regenerations (see utils/reportJobs.js).
export const reportJobs = createReportJobs(generateReport)
