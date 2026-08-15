import { useNavigate } from 'react-router-dom'
import { useImageTelemetry } from '../../hooks/useImageTelemetry.js'
import InfoCol from '../../components/profile/InfoCol'
import s from './BuildingTile.module.css'

/**
 * BuildingTile — image-overlay card per §3.5.1 + §3.5.2 RICH PATTERN.
 *   - No default border (transparent), hover lifts -4px and adds pink border (§3.5.1).
 *   - Title 18/700 + "Building" sub-italic + divider + 2-col ARCHITECT/YEAR grid.
 *   - NO program corner chip per §3.5.3 — program is metadata, not status; chips are
 *     reserved for binary status state. Matches the rationale used in FirmProfile
 *     ProjectCard (also drops program chip).
 */
export default function BuildingTile({ building, fromProjectId, rank, savedIds, referrer, isEditMode, isSelected, onToggleSelect }) {
  const navigate = useNavigate()
  // FIX F7 (Codex retest 2026-05-26): board saved_ids arrive from the API as
  // {id: "bld_..."} objects. Added building.id as the final fallback so real
  // API items can navigate correctly. MOCK_BOARD uses building_id; new API shape
  // uses id; image_id / canonical_bld_id keep backwards compat.
  const buildingId = building.image_id || building.canonical_bld_id || building.building_id || building.id
  const { onLoad, onError } = useImageTelemetry({
    buildingId,
    context: 'board_detail_gallery',
  })

  return (
    <div
      onClick={() => {
        if (isEditMode) { onToggleSelect?.(buildingId); return }
        if (!buildingId) return
        const state = fromProjectId
          ? { fromProjectId, rank, savedIds, referrer, fromBoard: true }
          : { fromBoard: true }
        navigate(`/buildings/${buildingId}`, { state })
      }}
      className={s.tile}
      style={{
        position: 'relative',
        aspectRatio: '4 / 5',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: 'pointer',
        background: 'rgba(255,255,255,0.03)',
        boxShadow: '0 10px 25px rgba(0,0,0,0.3)', // §3.5.1 mandatory depth (static)
        userSelect: 'none',
      }}
    >
      <img
        src={building.image_url}
        alt={building.image_title || building.name_en}
        loading="lazy"
        onLoad={onLoad}
        onError={onError}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
        }}
      />

      {/* §3.5.1 mandatory bottom gradient overlay */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)',
        pointerEvents: 'none',
      }} aria-hidden="true" />

      {/* Edit mode selection overlay */}
      {isEditMode && (
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: isSelected ? 'rgba(236,72,153,0.28)' : 'rgba(0,0,0,0.18)',
          transition: 'background 0.15s',
          display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end',
          padding: 12,
        }}>
          <div style={{
            width: 26, height: 26, borderRadius: '50%',
            border: `2px solid ${isSelected ? '#ec4899' : 'rgba(255,255,255,0.7)'}`,
            background: isSelected ? '#ec4899' : 'rgba(0,0,0,0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, color: '#fff', fontWeight: 700,
            transition: 'all 0.15s',
          }}>
            {isSelected ? '✓' : ''}
          </div>
        </div>
      )}

      {/* §3.5.2 RICH PATTERN: title + "Building" sub-italic + divider + 2-col ARCHITECT/YEAR grid */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: '16px 18px 20px',
      }}>
        <h4 style={{
          color: '#fff',
          fontSize: 18,
          fontWeight: 700,
          margin: '0 0 3px',
          lineHeight: 1.3,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {building.image_title || building.name_en}
        </h4>
        <p style={{
          color: 'rgba(255,255,255,0.55)',
          fontSize: 12,
          fontStyle: 'italic',
          margin: '0 0 12px',
        }}>
          Building
        </p>
        <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
          <InfoCol label="ARCHITECT" value={building.metadata?.axis_architects} />
          <InfoCol label="YEAR" value={building.metadata?.axis_year} />
        </div>
      </div>
    </div>
  )
}
