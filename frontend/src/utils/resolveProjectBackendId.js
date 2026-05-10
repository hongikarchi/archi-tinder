/**
 * resolveProjectBackendId — extract the backend UUID for a project object.
 *
 * Projects created before the UUID backfill may carry only a local `id` that
 * is itself a UUID string. `backendId` is preferred (set explicitly by the
 * backend sync), but we fall back to `id` when it looks like a UUID (contains
 * a hyphen, which UUIDs always do and local sequential IDs never do).
 *
 * @param {object|null|undefined} project
 * @returns {string|null}
 */
export function resolveProjectBackendId(project) {
  return project?.backendId || (project?.id?.includes('-') ? project.id : null)
}
