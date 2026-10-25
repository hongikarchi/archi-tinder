import { generateReport } from '../api/projects.js'
import { createReportJobs } from '../utils/reportJobs.js'

// App-wide in-flight store for report regenerations (see utils/reportJobs.js).
export const reportJobs = createReportJobs(generateReport)
