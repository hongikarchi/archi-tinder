/**
 * api/client.js
 * Re-export barrel — backward compatibility for all existing imports.
 * All implementation lives in the sub-modules below.
 *
 * Consumers: import { X } from '../api/client.js'  (unchanged)
 *            import * as api from '../api/client.js'  (unchanged)
 */

export { getToken, setTokens, clearTokens, getLastCall } from './core.js'
export { socialLogin, devLogin, logout } from './auth.js'
export { normalizeCard, getImageSource, emitImageLoadEvent } from './images.js'
export { startSession, getSessionState, recordSwipe, parseQuery, getResult } from './sessions.js'
export { listProjects, deleteProject, getBuildings, bookmarkBuilding, generateReport, generateReportImage } from './projects.js'
export { getOffice, getUserProfile } from './profiles.js'
export { followUser, unfollowUser } from './social.js'
