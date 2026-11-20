/**
 * api/client.js
 * Re-export barrel — backward compatibility for all existing imports.
 * All implementation lives in the sub-modules below.
 *
 * Consumers: import { X } from '../api/client.ts'  (unchanged)
 *            import * as api from '../api/client.ts'  (unchanged)
 */

export { getToken, setTokens, clearTokens, getLastCall } from './core.ts'
export { socialLogin, completeOnboarding, promoteAccount, devLogin, logout, getMe, login, register, setPassword, linkEmail } from './auth.ts'
export { normalizeCard, getImageSource, emitImageLoadEvent } from './images.ts'
export { startSession, getSessionState, recordSwipe, getResult } from './sessions.ts'
export { listProjects, getProject, updateProject, deleteProject, getBuildings, getBoardBuildings, generateReport, generateReportImage, getProjectRecommendations, createProject, VerifyRequiredError } from './projects.ts'
export { fetchDiscoveryFeed, discoveryFeedback, promoteToTaste } from './discovery.ts'
export { getUserProfile, updateMyProfile } from './profiles.ts'
export { getProjectReactors, reactToProject, unreactToProject, getLikedBoards } from './social.ts'
export { listContests, getContest, addContestInterest, removeContestInterest } from './contests.ts'
export { getRecommendedArchitects, getArchitectProfile, getUserSavedStudios } from './architects.ts'
export { listNotifications, getUnreadCount, markRead } from './notifications.ts'
export { getInspectBuildings, getInspectBuilding, inspectSearch } from './inspect.ts'
export {
  sendContactRequest, listReceivedRequests, getContactStatus, acceptContactRequest, ignoreContactRequest,
  listConversations, listMessages, sendMessage, markConversationRead, getMessagesUnreadCount,
  blockUser, unblockUser, reportTarget,
} from './messaging.ts'
