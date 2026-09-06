/**
 * api/client.js
 * Re-export barrel — backward compatibility for all existing imports.
 * All implementation lives in the sub-modules below.
 *
 * Consumers: import { X } from '../api/client.js'  (unchanged)
 *            import * as api from '../api/client.js'  (unchanged)
 */

export { getToken, setTokens, clearTokens, getLastCall } from './core.js'
export { socialLogin, guestLogin, promoteAccount, devLogin, logout, getMe, login, register, setPassword, linkEmail } from './auth.js'
export { normalizeCard, getImageSource, emitImageLoadEvent } from './images.js'
export { startSession, getSessionState, recordSwipe, parseQuery, getResult, submitQuestionResponse } from './sessions.js'
export { listProjects, getProject, updateProject, deleteProject, getBuildings, getBoardBuildings, bookmarkBuilding, generateReport, generateReportImage, createProject, VerifyRequiredError } from './projects.js'
export { fetchDiscoveryFeed, discoveryFeedback, promoteToTaste, fetchBoardSurprise } from './discovery.js'
export { getUserProfile, updateMyProfile } from './profiles.js'
export { getProjectReactors, reactToProject, unreactToProject } from './social.js'
export { addLikedBuilding, getLikedBuildings } from './liked.js'
export { getRecommendedArchitects, getArchitectProfile, getUserSavedStudios } from './architects.js'
export { listNotifications, getUnreadCount, markRead } from './notifications.js'
export { getInspectBuildings, getInspectBuilding, inspectSearch } from './inspect.js'
