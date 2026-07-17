/**
 * api/works.js
 * Works (portfolio upload) API — presign, R2 direct upload, finalize.
 */

import { callApi } from './core.js'

/**
 * Request presigned R2 PUT URLs for the given files.
 * @param {Array<{filename: string, content_type: string, file_size: number}>} files
 * @returns {Promise<Array<{key: string, url: string}>>}
 */
export async function presignFiles(files) {
  const res = await callApi('POST', '/works/presign/', { files })
  return res.presign_results
}

/**
 * Upload a single Blob directly to R2 via a presigned PUT URL.
 * Uses XMLHttpRequest so upload progress can be reported.
 *
 * R2 does not support presigned POST (returns 501 NotImplemented) — the
 * backend signs a PUT URL with Content-Type baked into the signature, so the
 * Content-Type header set here MUST exactly match what was sent as
 * `content_type` in the presignFiles() request for this file, or R2 rejects
 * the PUT with a signature mismatch. A successful PUT returns 200 (not 204).
 * @param {{key: string, url: string}} presignResult
 * @param {Blob} blob
 * @param {string} contentType - must match the content_type declared to presignFiles() for this file
 * @param {(percent: number) => void} onProgress
 * @returns {Promise<void>}
 */
export function uploadToR2(presignResult, blob, contentType, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve()
      } else {
        reject(new Error(`R2 upload failed: ${xhr.status}`))
      }
    }

    xhr.onerror = () => reject(new Error('Network error'))

    xhr.open('PUT', presignResult.url)
    xhr.setRequestHeader('Content-Type', contentType)
    xhr.send(blob)
  })
}

/**
 * Finalize a work upload after all R2 uploads complete.
 * @param {{title: string, program: string, location_city?: string, location_country?: string, project_year?: number, r2_keys: string[], is_copyright_confirmed: boolean}} payload
 * @returns {Promise<{upload_id: string, status: string}>}
 */
export async function finalizeWork(payload) {
  const res = await callApi('POST', '/works/', payload)
  return res
}

/**
 * Fetch the current user's uploaded works.
 * @returns {Promise<{works: Array<{upload_id: string, title: string, program: string, cover_url: string|null, is_publishable: boolean, gate_reason: string|null, created_at: string}>, total: number}>}
 */
export async function getMyWorks() {
  const res = await callApi('GET', '/works/')
  return res
}
