import { useImageTelemetry } from '../../hooks/useImageTelemetry.js'
import InfoCol from './InfoCol'

/**
 * ProjectCard — image-overlay card per DESIGN.md §3.5.1 + §3.5.2 RICH PATTERN.
 *   - No default border (transparent), hover lifts -4px and adds pink border (§3.5.1).
 *   - Title 18/700 + "Project" sub-italic + divider + 2-col CITY/YEAR grid (§3.5.2 RICH).
 *   - NO corner chip per §3.5.3 — program is metadata, not status; chips are reserved for
 *     binary status state. CITY+YEAR in the info grid carry the relevant metadata.
 */
export default function ProjectCard({ project }) {
  const { onLoad, onError } = useImageTelemetry({
    buildingId: project.building_id,
    context: 'firm_profile_gallery',
  })

  return (
    <div
      // TODO(claude): navigate to project detail on click — e.g. navigate(`/buildings/${project.building_id}`)
      style={{
        position: 'relative',
        borderRadius: 20,
        overflow: 'hidden',
        cursor: 'pointer',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid transparent',          // §3.5.1: NO default light border
        aspectRatio: '4 / 5',
        boxShadow: '0 10px 25px rgba(0,0,0,0.3)', // §3.5.1 mandatory depth
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'transparent'
      }}
    >
      <img
        src={project.image_url}
        alt={project.name_en}
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
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)',
        }}
        aria-hidden="true"
      />

      {/* §3.5.2 RICH PATTERN: title + "Project" sub-italic + divider + 2-col CITY/YEAR grid */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '16px 18px 20px',
        }}
      >
        <h4
          style={{
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
          }}
        >
          {project.name_en}
        </h4>
        <p
          style={{
            color: 'rgba(255,255,255,0.55)',
            fontSize: 12,
            fontStyle: 'italic',
            margin: '0 0 12px',
          }}
        >
          Project
        </p>
        <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
          <InfoCol label="CITY" value={project.city} />
          <InfoCol label="YEAR" value={project.year} />
        </div>
      </div>
    </div>
  )
}
