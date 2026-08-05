/**
 * DbCheckDetailModal.jsx — ADMIN-DBCHECK-1 full-row detail modal.
 *
 * Fetches GET /inspect/buildings/<id>/ on open and renders every listed
 * column grouped into sections. Missing/null fields render a visible
 * "—" / "null" marker — never omitted, since spotting data gaps is the point.
 */

import { useEffect, useRef, useState } from 'react'
import { getInspectBuilding } from '../../api/inspect.js'
import { rightSizeImageUrl } from '../../api/rightSizeImageUrl.js'
import styles from './DbCheck.module.css'

const EM_DASH = '—'

function Field({ label, value }) {
  const isEmpty = value === null || value === undefined || value === ''
  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      {isEmpty ? (
        <span className={styles.fieldValueMuted}>{EM_DASH}</span>
      ) : (
        <span className={styles.fieldValue}>{String(value)}</span>
      )}
    </div>
  )
}

function ChipList({ label, items }) {
  const list = Array.isArray(items) ? items.filter(v => v != null && v !== '') : []
  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      {list.length === 0 ? (
        <span className={styles.fieldValueMuted}>{EM_DASH}</span>
      ) : (
        <div className={styles.chipList}>
          {list.map((v, i) => (
            <span key={i} className={styles.chip}>{String(v)}</span>
          ))}
        </div>
      )}
    </div>
  )
}

const COVER_SLOTS = [
  { key: 'exterior', label: 'Exterior' },
  { key: 'interior', label: 'Interior' },
  { key: 'drawing', label: 'Drawing' },
  { key: 'aerial', label: 'Aerial' },
  { key: 'detail', label: 'Detail' },
]

function CoversByType({ covers }) {
  const data = covers && typeof covers === 'object' ? covers : {}
  return (
    <div className={styles.thumbStrip}>
      {COVER_SLOTS.map(slot => {
        const url = data[slot.key]
        return (
          <div key={slot.key} className={styles.coverSlot}>
            <span className={styles.coverSlotLabel}>{slot.label}</span>
            {url ? (
              <div className={styles.thumbItem} style={{ width: '100%', height: 90 }}>
                <img
                  src={rightSizeImageUrl(url, 160)}
                  alt={slot.label}
                  loading="lazy"
                  className={styles.thumbImg}
                />
              </div>
            ) : (
              <div className={styles.coverSlotEmpty}>null</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function AllImagesStrip({ images }) {
  const list = Array.isArray(images) ? images : []
  if (list.length === 0) return <span className={styles.fieldValueMuted}>{EM_DASH}</span>
  return (
    <div className={styles.thumbStrip}>
      {list.map((img, i) => {
        const url = typeof img === 'string' ? img : (img?.url || img?.image_url)
        const kind = typeof img === 'object' ? (img?.kind || img?.image_kind) : null
        if (!url) return null
        return (
          <div key={i} className={styles.thumbItem}>
            <img
              src={rightSizeImageUrl(url, 160)}
              alt=""
              loading="lazy"
              className={styles.thumbImg}
            />
            {kind && <span className={styles.thumbBadge}>{kind}</span>}
          </div>
        )
      })}
    </div>
  )
}

function SourceUrls({ sourceUrls }) {
  if (!sourceUrls || typeof sourceUrls !== 'object' || Array.isArray(sourceUrls)) {
    // Array or unexpected shape — render generic list fallback
    const list = Array.isArray(sourceUrls) ? sourceUrls : []
    if (list.length === 0) return <span className={styles.fieldValueMuted}>{EM_DASH}</span>
    return (
      <div className={styles.chipList}>
        {list.map((u, i) => (
          <a key={i} href={u} target="_blank" rel="noopener noreferrer" className={styles.sourceLink}>{u}</a>
        ))}
      </div>
    )
  }
  const keys = Object.keys(sourceUrls)
  if (keys.length === 0) return <span className={styles.fieldValueMuted}>{EM_DASH}</span>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {keys.map(key => {
        const val = sourceUrls[key]
        const urls = Array.isArray(val) ? val : [val]
        return (
          <div key={key} className={styles.sourceGroup}>
            <span className={styles.sourceGroupKey}>{key}</span>
            {urls.filter(Boolean).map((u, i) => (
              <a key={i} href={u} target="_blank" rel="noopener noreferrer" className={styles.sourceLink}>{u}</a>
            ))}
          </div>
        )
      })}
    </div>
  )
}

export default function DbCheckDetailModal({ id, onClose }) {
  const [data, setData] = useState(undefined) // undefined=loading, null=error, object=loaded
  const overlayRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    setData(undefined)
    getInspectBuilding(id)
      .then(d => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setData(null) })
    return () => { cancelled = true }
  }, [id])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const isLoading = data === undefined
  const isError = data === null
  const d = isLoading || isError ? null : data

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={`Building detail — ${id}`}
      className={styles.modalOverlay}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className={styles.modalBox} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h3 className={styles.modalTitle}>{id}</h3>
          <button type="button" className={styles.modalCloseBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className={styles.modalBody}>
          {isLoading && (
            <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Loading…</p>
          )}
          {isError && (
            <p style={{ color: 'var(--color-destructive)', fontSize: 13 }}>Failed to load building (404 or network error).</p>
          )}

          {d && (
            <>
              {/* Identity */}
              <div className={styles.section}>
                <h4 className={styles.sectionTitle}>Identity</h4>
                <div className={styles.fieldGrid}>
                  <Field label="canonical_bld_id" value={d.canonical_bld_id} />
                  <Field label="name" value={d.name} />
                  <Field label="identity_source" value={d.identity_source} />
                  <Field label="confidence_tier" value={d.confidence_tier} />
                  <Field label="n_sources" value={d.n_sources} />
                  <Field label="updated_at" value={d.updated_at} />
                </div>
                <ChipList label="names_alts" items={d.names_alts} />
              </div>

              {/* Location / Meta */}
              <div className={styles.section}>
                <h4 className={styles.sectionTitle}>Location / Meta</h4>
                <div className={styles.fieldGrid}>
                  <Field label="location_country" value={d.location_country} />
                  <Field label="location_city" value={d.location_city} />
                  <Field label="project_year" value={d.project_year} />
                  <Field label="architects_text" value={d.architects_text} />
                </div>
                <ChipList label="architect_names" items={d.architect_names} />
                <ChipList label="architect_canonical_ids" items={d.architect_canonical_ids} />
              </div>

              {/* Axes */}
              <div className={styles.section}>
                <h4 className={styles.sectionTitle}>Axes</h4>
                <div className={styles.fieldGrid}>
                  <Field label="program" value={d.program} />
                  <Field label="typology_primary" value={d.typology_primary} />
                  <Field label="style" value={d.style} />
                  <Field label="atmosphere" value={d.atmosphere} />
                  <Field label="color_tone" value={d.color_tone} />
                </div>
                <ChipList label="material_visual" items={d.material_visual} />
                <ChipList label="typology_tags" items={d.typology_tags} />
                <ChipList label="architectural_elements" items={d.architectural_elements} />
              </div>

              {/* Description */}
              <div className={styles.section}>
                <h4 className={styles.sectionTitle}>Description</h4>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>visual_description</span>
                  {d.visual_description ? (
                    <span className={styles.fieldValue} style={{ whiteSpace: 'pre-wrap' }}>{d.visual_description}</span>
                  ) : (
                    <span className={styles.fieldValueMuted}>{EM_DASH}</span>
                  )}
                </div>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>image_derived</span>
                  {d.image_derived ? (
                    <pre className={styles.rawJsonPre} style={{ maxHeight: 220 }}>
                      {JSON.stringify(d.image_derived, null, 2)}
                    </pre>
                  ) : (
                    <span className={styles.fieldValueMuted}>{EM_DASH}</span>
                  )}
                </div>
              </div>

              {/* Images */}
              <div className={styles.section}>
                <h4 className={styles.sectionTitle}>Images</h4>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>covers_by_type</span>
                  <CoversByType covers={d.covers_by_type} />
                </div>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>all_images</span>
                  <AllImagesStrip images={d.all_images} />
                </div>
              </div>

              {/* Sources */}
              <div className={styles.section}>
                <h4 className={styles.sectionTitle}>Sources</h4>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>source_urls</span>
                  <SourceUrls sourceUrls={d.source_urls} />
                </div>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>source_refs</span>
                  {d.source_refs ? (
                    <pre className={styles.rawJsonPre} style={{ maxHeight: 200 }}>
                      {JSON.stringify(d.source_refs, null, 2)}
                    </pre>
                  ) : (
                    <span className={styles.fieldValueMuted}>{EM_DASH}</span>
                  )}
                </div>
              </div>

              {/* Publishability */}
              <div className={styles.section}>
                <h4 className={styles.sectionTitle}>Publishability</h4>
                <div className={styles.fieldGrid}>
                  <div className={styles.field}>
                    <span className={styles.fieldLabel}>is_publishable</span>
                    <span className={`${styles.publishBadge} ${d.is_publishable ? styles.publishBadgeTrue : styles.publishBadgeFalse}`}>
                      {d.is_publishable ? 'true' : 'false'}
                    </span>
                  </div>
                  <Field label="needs_image_derived_backfill" value={d.needs_image_derived_backfill === null || d.needs_image_derived_backfill === undefined ? null : String(d.needs_image_derived_backfill)} />
                  <Field label="embedding_present" value={d.embedding_present === null || d.embedding_present === undefined ? null : String(d.embedding_present)} />
                  <Field label="embedding_dim" value={d.embedding_dim} />
                </div>
                <ChipList label="publishability_reasons" items={d.publishability_reasons} />
              </div>

              {/* Raw JSON */}
              <details className={styles.rawJson}>
                <summary className={styles.rawJsonSummary}>Raw JSON</summary>
                <pre className={styles.rawJsonPre}>{JSON.stringify(d, null, 2)}</pre>
              </details>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
