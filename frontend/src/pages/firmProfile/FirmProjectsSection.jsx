import { useState } from 'react'
import ProjectCard from '../../components/profile/ProjectCard'

export default function FirmProjectsSection({ projects, onSave, savedIds = null }) {
  const [activeTab, setActiveTab] = useState('built')

  const allProjects = projects || []
  const builtProjects = allProjects.filter(p => p.year_kind === 'completed')
  const unbuiltProjects = allProjects.filter(p => p.year_kind !== 'completed')
  const displayed = activeTab === 'built' ? builtProjects : unbuiltProjects

  return (
    <>
      {/* Projects section header — same style as UserProfile "Curated Boards · N" */}
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 12,
        marginBottom: 16, padding: '0 4px',
      }}>
        <h3 style={{
          color: 'var(--color-text)', fontSize: 20, fontWeight: 700,
          margin: 0, letterSpacing: '-0.01em',
        }}>
          Projects
        </h3>
        <span style={{
          color: 'var(--color-text-dimmer)', fontSize: 13, fontWeight: 600,
        }}>
          {allProjects.length}
        </span>
      </div>

      {/* Built / Unbuilt pill tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
        <button
          onClick={() => setActiveTab('built')}
          style={{
            padding: '6px 16px',
            borderRadius: 999,
            border: activeTab === 'built' ? 'none' : '1px solid var(--color-border-soft)',
            background: activeTab === 'built' ? 'var(--color-text)' : 'transparent',
            color: activeTab === 'built' ? 'var(--color-bg)' : 'var(--color-text-muted)',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
            minHeight: 32,
          }}
        >
          Built · {builtProjects.length}
        </button>
        <button
          onClick={() => setActiveTab('unbuilt')}
          style={{
            padding: '6px 16px',
            borderRadius: 999,
            border: activeTab === 'unbuilt' ? 'none' : '1px solid var(--color-border-soft)',
            background: activeTab === 'unbuilt' ? 'var(--color-text)' : 'transparent',
            color: activeTab === 'unbuilt' ? 'var(--color-bg)' : 'var(--color-text-muted)',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
            minHeight: 32,
          }}
        >
          Unbuilt · {unbuiltProjects.length}
        </button>
      </div>

      {/* Projects grid or empty state */}
      {displayed.length === 0 ? (
        <p style={{
          color: 'var(--color-text-dim)',
          fontSize: 14,
          textAlign: 'center',
          padding: '40px 0',
          margin: 0,
        }}>
          No projects yet
        </p>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 20,
            marginBottom: 36,
          }}
        >
          {displayed.map((project) => (
            <ProjectCard
              key={project.canonical_bld_id || project.building_id}
              project={project}
              onSave={onSave ? () => onSave(project) : null}
              isSaved={savedIds ? savedIds.has(project.canonical_bld_id || project.building_id) : false}
            />
          ))}
        </div>
      )}
    </>
  )
}
