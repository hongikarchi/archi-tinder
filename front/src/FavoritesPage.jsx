import { useState } from 'react'
import { GalleryOverlay } from './SwipePage'

export default function FavoritesPage({ projects, onDeleteProject, onResumeProject, openId, onOpenIdChange }) {
  const openProject = projects.find(p => p.id === openId) || null

  if (openProject) {
    return (
      <FolderDetail
        project={openProject}
        onBack={() => onOpenIdChange(null)}
        onDelete={() => { onDeleteProject(openProject.id); onOpenIdChange(null) }}
        onResume={() => onResumeProject(openProject.id)}
      />
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f0f0f', padding: '40px 20px 100px' }}>
      <div style={{ maxWidth: 480, margin: '0 auto' }}>
        <h2 style={{ color: '#fff', fontSize: 22, fontWeight: 800, margin: '0 0 4px' }}>
          Project Folders
        </h2>
        <p style={{ color: '#4b5563', fontSize: 13, margin: '0 0 24px' }}>
          {projects.length} saved session{projects.length !== 1 ? 's' : ''}
        </p>

        {projects.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>📁</div>
            <p style={{ color: '#4b5563', fontSize: 15, fontWeight: 500 }}>No projects yet</p>
            <p style={{ color: '#374151', fontSize: 13, marginTop: 6 }}>
              Start a new session from the Home tab
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[...projects].reverse().map(project => (
              <ProjectCard
                key={project.id}
                project={project}
                onClick={() => onOpenIdChange(project.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ProjectCard({ project, onClick }) {
  const liked   = project.likedBuildings?.length || 0
  const swiped  = project.swipedIds?.length || 0
  const { typologies = [] } = project.filters || {}

  return (
    <div
      onClick={onClick}
      style={{
        background: '#1c1c1c', borderRadius: 16,
        padding: '18px 20px', cursor: 'pointer',
        border: '1px solid rgba(255,255,255,0.06)',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.18)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ color: '#fff', fontSize: 16, fontWeight: 700, margin: '0 0 4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {project.projectName}
          </p>
          <p style={{ color: '#6b7280', fontSize: 12, margin: '0 0 10px' }}>
            {new Date(project.createdAt).toLocaleDateString()} · {swiped} swiped
          </p>
          {typologies.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {typologies.slice(0, 4).map(f => (
                <span key={f} style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 999,
                  background: 'rgba(255,255,255,0.08)', color: '#9ca3af',
                }}>
                  {f}
                </span>
              ))}
              {typologies.length > 4 && (
                <span style={{ fontSize: 11, color: '#4b5563' }}>+{typologies.length - 4}</span>
              )}
            </div>
          ) : (
            <span style={{ fontSize: 11, color: '#374151' }}>All buildings</span>
          )}
        </div>

        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          background: liked > 0 ? 'rgba(59,130,246,0.15)' : 'rgba(255,255,255,0.05)',
          borderRadius: 12, padding: '8px 14px', marginLeft: 12, flexShrink: 0,
        }}>
          <span style={{ fontSize: 18 }}>♥</span>
          <span style={{ color: liked > 0 ? '#60a5fa' : '#4b5563', fontSize: 13, fontWeight: 700 }}>
            {liked}
          </span>
        </div>
      </div>
    </div>
  )
}

function FolderDetail({ project, onBack, onDelete, onResume }) {
  const liked      = project.likedBuildings || []
  const predicted  = project.predictedLikes || []
  const report     = project.analysisReport || null
  return (
    <div style={{ minHeight: '100vh', background: '#0f0f0f', paddingBottom: 100 }}>
      {/* Header */}
      <div style={{ padding: '20px 20px 0', maxWidth: 480, margin: '0 auto' }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none', color: '#6b7280',
          fontSize: 13, cursor: 'pointer', padding: '8px 0', fontFamily: 'inherit',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          ← Back
        </button>

        <div style={{ margin: '12px 0 6px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2 style={{ color: '#fff', fontSize: 20, fontWeight: 800, margin: 0 }}>
              {project.projectName}
            </h2>
            <p style={{ color: '#4b5563', fontSize: 12, marginTop: 4 }}>
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

        {/* Resume swiping */}
        <button onClick={onResume} style={{
          width: '100%', padding: '12px', borderRadius: 12, marginBottom: 20,
          background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
          color: '#fff', fontSize: 14, fontWeight: 600,
          border: 'none', cursor: 'pointer', fontFamily: 'inherit',
        }}>
          Resume Swiping →
        </button>

        {/* 분석 리포트 */}
        {report && report.summary_text && (
          <div style={{
            background: '#1a1a1a', borderRadius: 12, padding: '14px 16px', marginBottom: 20,
            border: '1px solid rgba(255,255,255,0.07)',
          }}>
            <p style={{ color: '#9ca3af', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 8px' }}>
              분석 리포트
            </p>
            <p style={{ color: '#e2e8f0', fontSize: 13, margin: '0 0 10px', lineHeight: 1.6 }}>
              {report.summary_text}
            </p>
            {report.keywords?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {report.keywords.map(kw => (
                  <span key={kw} style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 999,
                    background: 'rgba(139,92,246,0.2)', color: '#a78bfa',
                    border: '1px solid rgba(139,92,246,0.3)',
                  }}>{kw}</span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Liked buildings */}
      <SectionLabel title="저장한 건물" count={liked.length} />
      {liked.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🏛️</div>
          <p style={{ color: '#4b5563', fontSize: 15 }}>No liked buildings yet</p>
          <p style={{ color: '#374151', fontSize: 13, marginTop: 4 }}>Swipe right to save buildings here</p>
        </div>
      ) : (
        <ImageGrid images={liked} />
      )}

      {/* Predicted likes */}
      {predicted.length > 0 && (
        <>
          <SectionLabel title="추천 건물" count={predicted.length} accent />
          <ImageGrid images={predicted} />
        </>
      )}
    </div>
  )
}

function SectionLabel({ title, count, accent }) {
  return (
    <div style={{ padding: '16px 20px 10px', maxWidth: 480, margin: '0 auto' }}>
      <span style={{
        color: accent ? '#a78bfa' : '#9ca3af',
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
  // ImageCard 스키마와 구 building 스키마 모두 지원
  const title    = image.image_title  || image.title
  const imageUrl = image.image_url    || image.imageUrl
  const country  = image.metadata?.axis_country || image.country

  return (
    <div
      onClick={onTap}
      style={{ borderRadius: 12, overflow: 'hidden', background: '#1c1c1c', position: 'relative', cursor: 'pointer' }}
    >
      <img
        src={imageUrl}
        alt={title}
        style={{ width: '100%', aspectRatio: '3/4', objectFit: 'cover', display: 'block' }}
        loading="lazy"
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
