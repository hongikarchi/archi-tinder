import { useState } from 'react'
import { GalleryOverlay } from '../components/GalleryOverlay.jsx'
import * as api from '../api/client.js'

const PAGE_SIZE = 10

export default function FavoritesPage({ projects, onDeleteProject, onResumeProject, onGenerateReport, onImageGenerated, openId, onOpenIdChange }) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const openProject = projects.find(p => p.id === openId) || null

  if (openProject) {
    return (
      <FolderDetail
        project={openProject}
        onBack={() => onOpenIdChange(null)}
        onDelete={() => { onDeleteProject(openProject.id); onOpenIdChange(null) }}
        onResume={() => onResumeProject(openProject.id)}
        onGenerateReport={() => onGenerateReport(openProject.id)}
        onImageGenerated={(imageData) => onImageGenerated && onImageGenerated(openProject.id, imageData)}
      />
    )
  }

  const sorted  = [...projects].reverse()
  const visible = sorted.slice(0, visibleCount)
  const hasMore = visibleCount < projects.length

  return (
    <div style={{ height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflowY: 'auto', background: 'var(--color-bg)', padding: '40px 20px 100px' }}>
      <div style={{ maxWidth: 480, margin: '0 auto' }}>
        <h2 style={{ color: 'var(--color-text)', fontSize: 22, fontWeight: 800, margin: '0 0 4px' }}>
          Project Folders
        </h2>
        <p style={{ color: 'var(--color-text-dimmer)', fontSize: 13, margin: '0 0 24px' }}>
          {projects.length} saved session{projects.length !== 1 ? 's' : ''}
        </p>

        {projects.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>📁</div>
            <p style={{ color: 'var(--color-text-dimmer)', fontSize: 15, fontWeight: 500 }}>No projects yet</p>
            <p style={{ color: 'var(--color-text-dimmest)', fontSize: 13, marginTop: 6 }}>
              Start a new session from the Home tab
            </p>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {visible.map(project => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onClick={() => onOpenIdChange(project.id)}
                />
              ))}
            </div>
            {hasMore && (
              <button
                onClick={() => setVisibleCount(c => c + PAGE_SIZE)}
                style={{
                  width: '100%', marginTop: 16, padding: '12px',
                  background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                  borderRadius: 12, color: 'var(--color-text-dim)',
                  fontSize: 13, cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                Load more ({projects.length - visibleCount} remaining)
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function ProjectCard({ project, onClick }) {
  const liked   = project.likedBuildings?.length || 0
  const swiped  = project.swipedIds?.length || 0
  const program = (project.filters || {}).program || null

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--color-surface-2)', borderRadius: 16,
        padding: '18px 20px', cursor: 'pointer',
        border: '1px solid var(--color-border)',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--color-border-soft)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--color-border)'}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ color: 'var(--color-text)', fontSize: 16, fontWeight: 700, margin: '0 0 4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {project.projectName}
          </p>
          <p style={{ color: 'var(--color-text-dim)', fontSize: 12, margin: '0 0 10px' }}>
            {new Date(project.createdAt).toLocaleDateString()} · {swiped} swiped
          </p>
          {program ? (
            <span style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 999,
              background: 'var(--color-surface-3)', color: 'var(--color-text-muted)',
            }}>
              {program}
            </span>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--color-text-dimmest)' }}>All buildings</span>
          )}
        </div>

        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          background: liked > 0 ? 'rgba(236,72,153,0.15)' : 'var(--color-surface-3)',
          borderRadius: 12, padding: '8px 14px', marginLeft: 12, flexShrink: 0,
        }}>
          <span style={{ fontSize: 18 }}>♥</span>
          <span style={{ color: liked > 0 ? '#f472b6' : 'var(--color-text-dimmer)', fontSize: 13, fontWeight: 700 }}>
            {liked}
          </span>
        </div>
      </div>
    </div>
  )
}

function FolderDetail({ project, onBack, onDelete, onResume, onGenerateReport, onImageGenerated }) {
  const [reportLoading, setReportLoading] = useState(false)
  const [imageLoading, setImageLoading] = useState(false)
  const [reportImage, setReportImage] = useState(project.reportImage || null)
  const [imageError, setImageError] = useState(null)
  const liked      = project.likedBuildings || []
  const predicted  = project.predictedLikes || []
  const finalReport = project.finalReport || null

  async function handleGenerateReport() {
    setReportLoading(true)
    try { await onGenerateReport() } finally { setReportLoading(false) }
  }

  async function handleGenerateImage() {
    const backendId = project.backendId || project.id
    if (!backendId || !backendId.includes('-')) return
    setImageLoading(true)
    setImageError(null)
    try {
      const result = await api.generateReportImage(backendId)
      setReportImage(result.image_data)
      if (onImageGenerated) onImageGenerated(result.image_data)
    } catch (err) {
      console.error('[FavoritesPage] generateReportImage failed:', err)
      setImageError(err.message || 'Image generation failed')
    } finally {
      setImageLoading(false)
    }
  }

  return (
    <div style={{ height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflowY: 'auto', background: 'var(--color-bg)', paddingBottom: 100 }}>
      <div style={{ padding: '20px 20px 0', maxWidth: 480, margin: '0 auto' }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none', color: 'var(--color-text-dim)',
          fontSize: 13, cursor: 'pointer', padding: '8px 0', fontFamily: 'inherit',
          display: 'flex', alignItems: 'center', gap: 6, minHeight: 44,
        }}>
          ← Back
        </button>

        <div style={{ margin: '12px 0 6px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2 style={{ color: 'var(--color-text)', fontSize: 20, fontWeight: 800, margin: 0 }}>
              {project.projectName}
            </h2>
            <p style={{ color: 'var(--color-text-dimmer)', fontSize: 12, marginTop: 4 }}>
              {liked.length} liked · {project.swipedIds?.length || 0} swiped
            </p>
          </div>
          <button onClick={onDelete} style={{
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
            color: '#f87171', borderRadius: 8, padding: '6px 12px',
            fontSize: 12, cursor: 'pointer', fontFamily: 'inherit',
          }}>
            Delete
          </button>
        </div>

        <button onClick={onResume} style={{
          width: '100%', padding: '12px', borderRadius: 12, marginBottom: 12,
          background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
          color: '#fff', fontSize: 14, fontWeight: 600,
          border: 'none', cursor: 'pointer', fontFamily: 'inherit',
        }}>
          Resume Swiping →
        </button>

        {/* Persona Report */}
        {finalReport ? (
          <PersonaReport
            report={finalReport}
            reportImage={reportImage}
            imageLoading={imageLoading}
            imageError={imageError}
            onGenerateImage={handleGenerateImage}
          />
        ) : (
          liked.length > 0 && (
            <button
              onClick={handleGenerateReport}
              disabled={reportLoading}
              style={{
                width: '100%', padding: '11px', borderRadius: 12, marginBottom: 20,
                background: reportLoading ? 'var(--color-surface-2)' : 'rgba(139,92,246,0.15)',
                color: reportLoading ? 'var(--color-text-dimmer)' : '#a78bfa',
                fontSize: 13, fontWeight: 600, border: '1px solid rgba(139,92,246,0.3)',
                cursor: reportLoading ? 'default' : 'pointer', fontFamily: 'inherit',
              }}
            >
              {reportLoading ? 'Generating persona report...' : '✦ Generate Persona Report'}
            </button>
          )
        )}
      </div>

      <SectionLabel title="Saved Buildings" count={liked.length} />
      {liked.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🏛️</div>
          <p style={{ color: 'var(--color-text-dimmer)', fontSize: 15 }}>No liked buildings yet</p>
          <p style={{ color: 'var(--color-text-dimmest)', fontSize: 13, marginTop: 4 }}>Swipe right to save buildings here</p>
        </div>
      ) : (
        <ImageGrid images={liked} />
      )}

      {predicted.length > 0 && (
        <>
          <SectionLabel title="Recommended Buildings" count={predicted.length} accent />
          <ImageGrid images={predicted} />
        </>
      )}
    </div>
  )
}

function PersonaReport({ report, reportImage, imageLoading, imageError, onGenerateImage }) {
  const chips = (items) => (items || []).slice(0, 5).map(item => (
    <span key={item} style={{
      fontSize: 11, padding: '3px 10px', borderRadius: 999,
      background: 'rgba(139,92,246,0.15)', color: '#a78bfa',
      border: '1px solid rgba(139,92,246,0.25)',
    }}>{item}</span>
  ))

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(139,92,246,0.08), rgba(236,72,153,0.06))',
      borderRadius: 14, padding: '16px 18px', marginBottom: 20,
      border: '1px solid rgba(139,92,246,0.25)',
    }}>
      <p style={{ color: '#a78bfa', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>
        Your Architectural Persona
      </p>
      {report.persona_type && (
        <p style={{ color: 'var(--color-text)', fontSize: 17, fontWeight: 800, margin: '0 0 4px' }}>
          {report.persona_type}
        </p>
      )}
      {report.one_liner && (
        <p style={{ color: '#ec4899', fontSize: 13, fontWeight: 500, fontStyle: 'italic', margin: '0 0 10px' }}>
          "{report.one_liner}"
        </p>
      )}
      {report.description && (
        <p style={{ color: 'var(--color-text-dim)', fontSize: 13, lineHeight: 1.6, margin: '0 0 12px' }}>
          {report.description}
        </p>
      )}
      {report.dominant_programs?.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 5px' }}>Typologies</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>{chips(report.dominant_programs)}</div>
        </div>
      )}
      {report.dominant_styles?.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 5px' }}>Styles</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>{chips(report.dominant_styles)}</div>
        </div>
      )}
      {report.dominant_materials?.length > 0 && (
        <div>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 5px' }}>Materials</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>{chips(report.dominant_materials)}</div>
        </div>
      )}

      {reportImage ? (
        <div style={{ marginTop: 14 }}>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 8px' }}>
            AI Generated Architecture
          </p>
          <img
            src={`data:image/png;base64,${reportImage}`}
            alt="AI generated architecture based on your taste"
            style={{
              width: '100%', borderRadius: 10, display: 'block',
              border: '1px solid rgba(139,92,246,0.15)',
            }}
          />
        </div>
      ) : (
        <div style={{ marginTop: 14 }}>
          {imageError && (
            <p style={{ color: '#f43f5e', fontSize: 11, margin: '0 0 8px' }}>{imageError}</p>
          )}
          <button
            onClick={onGenerateImage}
            disabled={imageLoading}
            style={{
              width: '100%', padding: '10px', borderRadius: 10,
              background: imageLoading ? 'var(--color-surface-2)' : 'rgba(139,92,246,0.1)',
              color: imageLoading ? 'var(--color-text-dimmer)' : '#a78bfa',
              fontSize: 12, fontWeight: 600,
              border: '1px solid rgba(139,92,246,0.2)',
              cursor: imageLoading ? 'default' : 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {imageLoading ? 'Generating image...' : 'Generate AI Architecture Image'}
          </button>
        </div>
      )}
    </div>
  )
}

function SectionLabel({ title, count, accent }) {
  return (
    <div style={{ padding: '16px 20px 10px', maxWidth: 480, margin: '0 auto' }}>
      <span style={{
        color: accent ? '#a78bfa' : 'var(--color-text-muted)',
        fontSize: 11, fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.1em',
      }}>
        {title} {count > 0 && `· ${count}`}
      </span>
    </div>
  )
}

function ImageGrid({ images }) {
  const [selectedImage, setSelectedImage] = useState(null)

  return (
    <>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
        gap: 10, padding: '0 20px', maxWidth: 480, margin: '0 auto',
      }}>
        {images.map(img => (
          <BuildingCard
            key={img.image_id || img.building_id}
            image={img}
            onTap={() => setSelectedImage(img)}
          />
        ))}
      </div>
      {selectedImage && (
        <GalleryOverlay
          card={selectedImage}
          onClose={() => setSelectedImage(null)}
          fullscreen
        />
      )}
    </>
  )
}

function BuildingCard({ image, onTap }) {
  const title    = image.image_title  || image.title
  const imageUrl = image.image_url    || image.imageUrl
  const country  = image.metadata?.axis_country || image.country
  const [imgLoading, setImgLoading] = useState(true)

  return (
    <div
      onClick={onTap}
      style={{ borderRadius: 12, overflow: 'hidden', background: 'var(--color-surface-2)', position: 'relative', cursor: 'pointer' }}
    >
      {imgLoading && (
        <div className="skeleton-shimmer" style={{ width: '100%', aspectRatio: '3/4' }} />
      )}
      <img
        src={imageUrl}
        alt={title}
        style={{
          width: '100%', aspectRatio: '3/4', objectFit: 'cover', display: 'block',
          opacity: imgLoading ? 0 : 1, transition: 'opacity 0.3s',
          position: imgLoading ? 'absolute' : 'static', top: 0, left: 0,
        }}
        loading="lazy"
        onLoad={() => setImgLoading(false)}
        onError={() => setImgLoading(false)}
      />
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 55%)',
        display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
        padding: '10px',
      }}>
        <p style={{ color: '#fff', fontSize: 11, fontWeight: 600, lineHeight: 1.3, margin: 0 }}>
          {title}
        </p>
        {country && (
          <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 10, margin: '2px 0 0' }}>
            {country}
          </p>
        )}
      </div>
    </div>
  )
}
