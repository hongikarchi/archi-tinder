/**
 * photoCardShell.js — the single source of truth for the app's photo-tile card.
 *
 * Extracted (2026-08-29) from ResultsPage's `ResultCard` — the recommendation
 * tiles shown after a taste report is generated. That card was a LOCAL
 * function inside ResultsPage.jsx with no export, so it could not be reused by
 * import; pulling its measurements here lets /people's PersonCard render the
 * same tile instead of a look-alike. ResultCard now consumes these constants
 * too, so a change here moves both surfaces together.
 *
 * Values are ResultCard's originals, unchanged.
 */

/** Grid the tiles sit in. Columns are responsive — see the note below. */
export const PHOTO_GRID_GAP = 8
export const PHOTO_GRID_PADDING = '0 12px 18px'

/**
 * ResultsPage pins its grid at `repeat(4, 1fr)` with no breakpoints, which on a
 * 390px phone yields 86px-wide tiles. That is fine for a pure photo tile, but
 * /people's tile flips to a personality chart, which needs room to stay
 * legible — so the people feed steps its column count down on narrow screens
 * (4 / 3 / 2) via PeopleDiscoveryPage.module.css rather than reusing this
 * fixed value.
 */
export const PHOTO_GRID_COLUMNS_FIXED = 'repeat(4, 1fr)'

/** The tile surface: footprint, radius, border, shadow. */
export const photoCardShellStyle = {
  position: 'relative',
  width: '100%',
  aspectRatio: '2 / 3',
  borderRadius: 12,
  overflow: 'hidden',
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border-soft)',
  boxShadow: '0 18px 42px rgba(0,0,0,0.35)',
  cursor: 'pointer',
}

/** Full-bleed image inside the tile. */
export const photoCardImageStyle = {
  position: 'absolute',
  inset: 0,
  width: '100%',
  height: '100%',
  objectFit: 'cover',
}

/** Bottom scrim that keeps overlaid text readable against any photo. */
export const photoCardScrimStyle = {
  position: 'absolute',
  inset: 0,
  background:
    'linear-gradient(to top, rgba(0,0,0,0.94) 0%, rgba(0,0,0,0.52) 48%, rgba(0,0,0,0.08) 100%)',
}

/** Text block pinned to the tile's bottom edge. */
export const photoCardCaptionStyle = {
  position: 'absolute',
  left: 0,
  right: 0,
  bottom: 0,
  padding: '6px 8px 8px',
}

/** Caption title — 1-line clamp. */
export const photoCardTitleStyle = {
  color: '#fff',
  fontSize: 10,
  fontWeight: 700,
  lineHeight: 1.2,
  margin: '0 0 2px',
  display: '-webkit-box',
  WebkitLineClamp: 1,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
}

/** Caption subtitle (architect / handle). */
export const photoCardSubtitleStyle = {
  color: 'rgba(255,255,255,0.68)',
  fontSize: 9,
  fontStyle: 'italic',
  margin: '0 0 6px',
}
