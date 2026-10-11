/**
 * BoardCover — contained cover-photo card for BoardDetailPage (option a,
 * .claude/plans/archive/ui-consistency-b.md decision 7).
 *
 * Isolated into its own tiny component with a SINGLE render condition (no
 * image -> render nothing, no grey placeholder slab) so switching to
 * option b (drop the cover entirely) is a one-line change at the call site
 * — see BoardDetailPage.jsx's `SHOW_COVER` flag.
 *
 * Aspect 16:10, capped at 260px tall (aspect-ratio + max-height together:
 * the browser still uses 100% width, so on a wide desktop column the box
 * is simply shorter than the ratio would dictate — object-fit:cover keeps
 * the image filling it with no distortion). Plain photo, no gradient, no
 * text (that lives below it now — see BoardDetailPage's title block).
 */
export default function BoardCover({ imageUrl, alt }) {
  if (!imageUrl) return null

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '16 / 10',
        maxHeight: 260,
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        background: 'var(--color-surface)',
        marginTop: 8,
      }}
    >
      <img
        src={imageUrl}
        alt={alt || ''}
        fetchpriority="high"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
        }}
      />
    </div>
  )
}
