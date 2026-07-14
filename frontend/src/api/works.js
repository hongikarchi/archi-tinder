/**
 * api/works.js
 * Works (portfolio upload) API — presign, R2 direct upload, finalize.
 */

import { callApi } from './core.js'

/**
 * Request presigned S3/R2 POST URLs for the given files.
 * @param {Array<{filename: string, content_type: string, file_size: number}>} files
 * @returns {Promise<Array<{key: string, url: string, fields: object}>>}
 */
export async function presignFiles(files) {
  const res = await callApi('POST', '/works/presign/', { files })
  return res.presign_results
}

/**
 * Upload a single Blob directly to R2 via a presigned POST.
 * Uses XMLHttpRequest so upload progress can be reported.
 * @param {{key: string, url: string, fields: object}} presignResult
 * @param {Blob} blob
 * @param {(percent: number) => void} onProgress
 * @returns {Promise<void>}
 */
export function uploadToR2(presignResult, blob, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    Object.entries(presignResult.fields).forEach(([k, v]) => formData.append(k, v))
    formData.append('file', blob)  // 'file' field must be last per S3 spec

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

    xhr.open('POST', presignResult.url)
    xhr.send(formData)
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
