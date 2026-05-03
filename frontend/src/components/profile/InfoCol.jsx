/**
 * InfoCol — local primitive for §3.5.2 RICH PATTERN 2-col info grid.
 *   Caps label (10/600 uppercase 0.06em) + single-line ellipsis value (13/600 white).
 */
export default function InfoCol({ label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <span style={{
        color: 'rgba(255,255,255,0.5)',
        fontSize: 10, fontWeight: 600,
        letterSpacing: '0.06em', textTransform: 'uppercase',
        marginBottom: 2,
      }}>
        {label}
      </span>
      <span style={{
        color: '#fff', fontSize: 13, fontWeight: 600,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {value}
      </span>
    </div>
  )
}
