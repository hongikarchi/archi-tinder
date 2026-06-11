import ProjectCard from '../../components/profile/ProjectCard'

export default function FirmProjectsSection({ projects, onSave }) {
  return (
    <>
      {/* Projects section header — same style as UserProfile "Curated Boards · N" */}
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 12,
        marginBottom: 20, padding: '0 4px',
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
          {(projects || []).length}
        </span>
      </div>

      {/* Projects grid — same unified container, responsive auto-fill, same column breakpoint as UserProfile boards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 20,
          marginBottom: 36,
        }}
      >
        {(projects || []).map((project) => (
          <ProjectCard key={project.canonical_bld_id || project.building_id} project={project} onSave={onSave ? () => onSave(project) : null} />
        ))}
      </div>
    </>
  )
}
