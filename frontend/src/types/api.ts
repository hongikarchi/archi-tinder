
// ---- L1 group 1: src/api/** ------------------------------------------------
export interface Paginated<T> { results: T[]; count: number }
export interface AdminFlag { key: string; label_ko: string; description_ko: string; value: boolean | string }
export interface AdminMigrations { count: number; unapplied: string[] }
export interface AdminFlagsResponse { flags: AdminFlag[] }
export interface AdminServicesResponse { services: Record<string, unknown>[]; fetched_at: string }
export interface PeopleDiscoveryResponse { results: Record<string, unknown>[]; has_more: boolean; next_cursor: string | null }
export interface BoardReportImage { image_data: string; mime_type: string }
export interface BoardReportImageThrottled { throttled: true; retryAfter?: number }
export interface UnreadCountResponse { unread_count?: number; count?: number }

// ---- L3 group 4: components/messaging + components/profile ------------------
export interface MessagingUser { user_id?: number | string; avatar_url?: string | null; display_name?: string; handle?: string; [k: string]: unknown }
export interface ChatMessage {
  id: number
  kind?: 'user' | 'system' | string
  system_type?: string
  body?: string
  is_mine?: boolean
  created_at?: string
  [k: string]: unknown
}
/** GET/POST users/<id>/follow/ (SNS-FOLLOW-1). `reason` only for a guest requester. */
export interface FollowStatus {
  is_following: boolean
  is_followed_by: boolean
  can_follow: boolean
  blocked_by_me: boolean
  /** An open (unclosed) conversation exists between me and the target. */
  has_conversation: boolean
  reason?: 'verify_required'
}
/** POST conversations/ {peer_user_id} (201 created / 200 existing). */
export interface OpenConversationResult { id: number; other: MessagingUser; closed: boolean }
export interface ConversationItem {
  id: number | string
  other?: MessagingUser
  closed?: boolean
  unread_count?: number
  last_message?: ChatMessage | null
  last_message_at?: string | null
  [k: string]: unknown
}
export interface MessagesPage { results?: ChatMessage[]; closed?: boolean }
export interface ProfileBoard {
  board_id: string
  name?: string
  visibility?: string
  building_count?: number
  has_report_image?: boolean
  cover_image_url?: string | null
  [k: string]: unknown
}
export interface ProfileUser {
  user_id?: number | string
  role?: string
  onboarding_role?: string
  affiliation?: string
  bio?: string
  external_links?: Record<string, string>
  [k: string]: unknown
}
export interface ProfileEditPatch {
  onboarding_role?: string
  role?: string
  affiliation: string
  bio: string
  external_links: Record<string, string>
}

// ---- L3 group 3 (components S-W): taste-start card shapes ----
export type TranslateFn = (key: string, params?: Record<string, unknown>) => string
export interface TasteTagRef { axis: unknown; value: unknown; [k: string]: unknown }
export interface TasteChipItem { tag: TasteTagRef; matched?: boolean }
export interface TasteStartCard {
  image_id?: string
  image_title?: string
  // TODO(ts): backend metadata bag (axis_* keys), not modelled field by field
  metadata?: Record<string, any>
  gallery?: string[]
  gallery_srcset?: (string | null | undefined)[]
  gallery_drawing_start?: number
  [k: string]: unknown
}
export interface TasteReportForm {
  reason: string | null
  sub: string[]
  tags: { axis: unknown; value: unknown }[]
  text: string
}
// Swipe card payload (normalized card consumed by SwipeCard)
export interface SwipeCardData extends TasteStartCard {
  image_url?: string
  image_srcset?: string | null
  lqip_url?: string | null
  image_kind?: string
  covers_by_type?: Record<string, string | undefined>
}
// Uploaded work detail (GET /works/:id/)
export interface WorkDetail {
  title?: string
  cover_url?: string
  gallery_urls?: string[]
  program?: string
  location_city?: string
  location_country?: string
  project_year?: number | string
  status?: string
  [k: string]: unknown
}
// Studio card: architect/office row + carousel buildings
export interface StudioOffice { name?: string; logo_url?: string | null; cover_image_url?: string | null; [k: string]: unknown }
export interface StudioBuilding { canonical_bld_id?: string; image_url?: string | null; name_en?: string; [k: string]: unknown }

// ---- L3 group 2: components K..S (PersonaReportPage / ResultCards / SaveBoardModal) ----
export interface ReportBuildingCard {
  image_id?: string
  canonical_bld_id?: string
  building_id?: string
  image_title?: string
  name_en?: string
  image_url?: string | null
  [k: string]: unknown
}
export interface ReportArchitect {
  architect_id?: number | string
  name?: string
  buildings?: { image_url?: string | null; name_en?: string; name?: string; [k: string]: unknown }[]
  [k: string]: unknown
}
export interface ReportMeta {
  visibility?: string
  buildingCount?: number
  reactionCount?: number
  ownerLabel?: string
  onOwner?: () => void
}
export interface FinalReport {
  persona_type?: string
  one_liner?: string
  description?: string
  pattern_paragraph?: string
  dominant_programs?: string[]
  dominant_styles?: string[]
  dominant_materials?: string[]
  [k: string]: unknown
}
export type AxisScoresMap = Record<string, unknown>

// ---- L4 group 2: pages/admin + pages/dbCheck ---------------------------------
export interface AdminCiRun { conclusion?: string | null; status?: string; html_url?: string }
export interface AdminVersionResponse {
  backend?: { sha?: string | null; environment?: string }
  github?: {
    main_sha?: string | null
    develop_sha?: string | null
    develop_ahead_by?: number
    error?: string
    ci?: { develop?: AdminCiRun | null; main?: AdminCiRun | null }
  }
}
export type AdminStatsResponse = Record<string, Record<string, number> | null>
export interface AdminAuditRow {
  id: number | string
  created_at: string
  actor_email?: string | null
  action: string
  target_type?: string
  target_id?: number | string
}
export interface AdminContest {
  id: number
  title?: string
  organizer?: string
  organizer_type?: string
  status?: string
  submission_deadline?: string | null
  apply_deadline?: string | null
  theme?: string
  summary?: string
  eligibility?: string
  team_size?: number | string | null
  source_url?: string
  listing_source?: string
  listing_url?: string
  poster_url?: string | null
  poster_credit?: string
  is_closed?: boolean
  interest_count?: number
  [k: string]: unknown
}
export interface AdminServiceUsageItem { label: string; value?: unknown; unit?: string }
export interface AdminService {
  slug: string
  dashboard_url?: string
  name?: string
  status?: { indicator?: string; description?: string; [k: string]: unknown }
  account?: { auto?: unknown; note?: string; [k: string]: unknown }
  usage?: {
    configured?: boolean
    items?: AdminServiceUsageItem[]
    cost?: { amount?: unknown; currency?: string; estimated?: boolean }
    error?: string
  }
  [k: string]: unknown
}
export interface InspectCard {
  image_id?: string
  canonical_bld_id?: string
  image_url?: string
  image_title?: string
  name?: string
  name_en?: string
  [k: string]: unknown
}
export interface InspectSearchMeta {
  structured_filters: Record<string, unknown>
  filter_priority: string[]
  is_fallback: boolean
}

// ---- L4 group 3: pages/boardDetail, boardReport, buildingDetail, settings, userProfile ----
export interface BoardBuilding {
  image_id?: string
  canonical_bld_id?: string
  building_id?: string
  id?: string
  image_url?: string
  image_title?: string
  name_en?: string
  // TODO(ts): backend metadata bag (axis_* keys), not modelled field by field
  metadata?: Record<string, any>
  [k: string]: unknown
}
export interface NotificationActor { user_id?: number | string; avatar_url?: string | null; display_name?: string; handle?: string; [k: string]: unknown }
export interface NotificationItem {
  id: number | string
  type?: string
  category?: string
  read_at?: string | null
  created_at?: string
  actor?: NotificationActor | null
  // TODO(ts): per-type payload bag
  payload?: Record<string, any> | null
  [k: string]: unknown
}
