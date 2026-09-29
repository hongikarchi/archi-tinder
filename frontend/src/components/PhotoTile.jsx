import styles from './PhotoTile.module.css'

/**
 * PhotoTile — shared 4:5 photo card with an overlaid bottom-gradient
 * caption (plan decision 6, 2026-09-26: "caption OVERLAID on the photo
 * bottom ... 4:5 portrait, radius lg 20").
 *
 * Consolidates LikedProjectsPage's local `LikedBuildingCard` and
 * UserProfilePage's Liked-tab card (previously caption-BELOW-image) onto one
 * component. Deliberately NOT based on `photoCardShell.js` — that shell is a
 * different card (2:3 aspect, `--radius-sm`-scale 12px radius, 10/9px fonts
 * for ResultsPage/PersonCard's denser grid); retuning it to 4:5/radius-lg
 * would restyle those two unrelated pages, which is out of this PR's scope.
 * Also NOT adopted by BoardDetail's `BuildingTile` (RICH PATTERN: architect/
 * year info grid + edit-mode select overlay) — that is a page-restructure
 * candidate for phase 3, not a straight swap.
 *
 * Props:
 *   imageUrl    — photo src. Falls back to `placeholder` when absent.
 *   title       — building name, 2-line clamp, `--fs-body`/`--fw-semibold`.
 *   subtitle    — architect / meta line, `--fs-caption`.
 *   onClick     — click handler; tile only shows a pointer cursor + hover
 *                 lift/outline when set (a tile with no `onClick` renders as
 *                 a plain static block — no cursor, no hover, no button role,
 *                 matching a non-owner's read-only view).
 *   topRight    — optional overlay slot (e.g. a bookmark/select badge).
 *   placeholder — optional node shown instead of the scrim+caption when
 *                 there is no `imageUrl` (e.g. `<BuildingIconEmpty/>`).
 *   aspect      — override the default 4/5 ratio.
 */
export default function PhotoTile({
  imageUrl,
  title,
  subtitle,
  onClick,
  topRight,
  placeholder,
  aspect = '4 / 5',
  className = '',
}) {
  return (
    <div
      onClick={onClick}
      className={`${styles.tile} ${onClick ? styles.interactive : ''} ${className}`}
      style={{ aspectRatio: aspect, cursor: onClick ? 'pointer' : 'default' }}
    >
      {imageUrl ? (
        <img src={imageUrl} alt={title || ''} loading="lazy" className={styles.image} />
      ) : placeholder ? (
        <div className={styles.placeholder}>{placeholder}</div>
      ) : null}

      <div aria-hidden="true" className={styles.scrim} />

      {topRight && <div className={styles.topRight}>{topRight}</div>}

      <div className={styles.caption}>
        {title && <h4 className={styles.title}>{title}</h4>}
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>
    </div>
  )
}
