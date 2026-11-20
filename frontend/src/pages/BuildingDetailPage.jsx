import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getBuildings } from '../api/client.js'
import ErrorState from './buildingDetail/ErrorState.jsx'
import Header from './buildingDetail/Header.jsx'
import LoadingState from './buildingDetail/LoadingState.jsx'
import { CHIP_KEYS, kindLabel, metadataItems } from './buildingDetail/helpers.js'
import PhotoLightbox from './buildingDetail/PhotoLightbox.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import {
  ReportScope, ReportSection, ReportHeading, ReportTags, ReportRow, ReportCard,
} from '../components/PersonaReportPage.jsx'
import { useTranslation } from '../i18n/index.js'
import styles from './BuildingDetailPage.module.css'

const COMPACT_MAX = 5
const BUILDING_ID_RE = /^[A-Za-z0-9_-]{1,32}$/

export default function BuildingDetailPage({ onLogout }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const rawBuildingId = useParams().buildingId
  const buildingId = BUILDING_ID_RE.test(String(rawBuildingId || '')) ? rawBuildingId : null
  const [building, setBuilding] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [lightboxIndex, setLightboxIndex] = useState(null) // null = closed

  useEffect(() => {
    if (!buildingId) {
      setBuilding(null)
      setLoading(false)
      setError('Invalid building ID.')
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    getBuildings([buildingId])
      .then(results => {
        if (cancelled) return
        const next = results?.[0] || null
        setBuilding(next)
        setError(next ? null : 'No building matched this ID.')
      })
      .catch(err => {
        if (cancelled) return
        setBuilding(null)
        setError(err.message || 'Failed to load building detail.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [buildingId, reloadKey])

  const gallery = useMemo(() => {
    if (!building) return []
    const merged = building.gallery?.length ? building.gallery : []
    return merged.length ? merged : [building.cover_full_url || building.image_url].filter(Boolean)
  }, [building])

  const galleryMeta = useMemo(() => {
    if (!building) return []
    return building.gallery_meta?.length ? building.gallery_meta : []
  }, [building])

  const photos = useMemo(() => galleryMeta.filter(g => g.kind !== 'drawing'), [galleryMeta])
  const drawings = useMemo(() => galleryMeta.filter(g => g.kind === 'drawing'), [galleryMeta])
  // Per-section view: 'compact' (one scroll row) | 'full' (2-col masonry). Default compact.
  const [photosView, setPhotosView] = useState('compact')
  const [drawingsView, setDrawingsView] = useState('compact')

  const title = building?.image_title || buildingId || 'Building'

  // Flat lightbox list: photos then drawings. Compact rows show a prefix of each
  // section, so the same indices (photos idx, photos.length + drawing idx) hold in both views.
  const lightboxImages = useMemo(() => {
    if (galleryMeta.length > 0) {
      return [...photos, ...drawings].map(g => ({ url: g.url, alt: kindLabel(g.kind, t) }))
    }
    return gallery.map(url => ({ url, alt: title }))
  }, [galleryMeta, photos, drawings, gallery, title, t])
  const architect = building?.metadata?.axis_architects
  const architectId = building?.metadata?.architect_id || null
  // Description / atmosphere stay English as returned by the DB in both languages;
  // translation will come from the DB later (do not add client dictionaries).
  const detailDescription = building?.metadata?.visual_description || building?.metadata?.description || null
  const atmosphere = building?.metadata?.axis_atmosphere || t('detailB3.noAtmosphere')
  const items = metadataItems(building)

  function handleBack() {
    navigate(-1)
  }

  if (loading) {
    return (
      <>
        <PageTopControls onLogout={onLogout} leading={<Header onBack={handleBack} />} />
        <LoadingState />
      </>
    )
  }
  if (error || !building) {
    return (
      <>
        <PageTopControls onLogout={onLogout} leading={<Header onBack={handleBack} />} />
        <ErrorState
          message={error || 'No building matched this ID.'}
          onRetry={() => setReloadKey(k => k + 1)}
        />
      </>
    )
  }

  const openArchitect = () => navigate(`/architects/${architectId}`)

  function renderGallerySection(list, offset, heading, view, setView, isDrawing) {
    if (list.length === 0) return null
    const n = list.length
    const showMore = view === 'compact' && n > COMPACT_MAX
    const label = item => kindLabel(item.kind, t)
    const alt = (item, idx) => `${title} ${label(item)} ${idx + 1}`
    const sw = (
      <span className={styles.vs}>
        {['compact', 'full'].map(m => (
          <button
            key={m}
            type="button"
            className={view === m ? styles.on : undefined}
            aria-pressed={view === m}
            onClick={() => setView(m)}
          >
            {t(m === 'compact' ? 'detailB3.viewCompact' : 'detailB3.viewFull')}
          </button>
        ))}
      </span>
    )
    return (
      <ReportSection>
        <ReportHeading count={n} right={sw}>{heading}</ReportHeading>
        {view === 'compact' ? (
          <ReportRow>
            {list.slice(0, COMPACT_MAX).map((item, idx) => (
              <ReportCard
                key={`${item.url}-${idx}`}
                className={`${styles.zoom} ${isDrawing ? styles.drawingCard : ''}`}
                onClick={() => setLightboxIndex(offset + idx)}
              >
                <img
                  className={styles.cardImg}
                  src={item.url}
                  alt={alt(item, idx)}
                  loading={!isDrawing && idx < 2 ? 'eager' : 'lazy'}
                />
                <span className={styles.badge}>{label(item)}</span>
              </ReportCard>
            ))}
            {showMore && (
              <button type="button" className={styles.more} onClick={() => setView('full')}>
                {t('detailB3.moreCount', { n: n - COMPACT_MAX })}
              </button>
            )}
          </ReportRow>
        ) : (
          <div className={styles.mas}>
            {list.map((item, idx) => (
              <div
                key={`${item.url}-${idx}`}
                className={styles.mi}
                onClick={() => setLightboxIndex(offset + idx)}
              >
                <img
                  className={`${styles.masImg} ${isDrawing ? styles.drawingImg : ''}`}
                  src={item.url}
                  alt={alt(item, idx)}
                  loading={!isDrawing && idx < 2 ? 'eager' : 'lazy'}
                />
                <span className={styles.badge}>{label(item)}</span>
              </div>
            ))}
          </div>
        )}
      </ReportSection>
    )
  }

  return (
    <div className={styles.page}>
      <PageTopControls onLogout={onLogout} leading={<Header onBack={handleBack} />} />
      <PageLogoHeader />

      {lightboxIndex !== null && lightboxImages.length > 0 && (
        <PhotoLightbox
          images={lightboxImages}
          activeIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onNavigate={setLightboxIndex}
        />
      )}

      <div className={styles.column}>
        <ReportScope>
          <section className={styles.hero}>
            <p className={styles.eyebrow}>{t('detailB3.buildingDetailEyebrow')}</p>
            <h1 className={styles.name}>{title}</h1>
            {architect && (
              <p className={styles.sub}>
                {architectId ? (
                  <button type="button" className={styles.architectLink} onClick={openArchitect}>
                    {architect}
                  </button>
                ) : architect}
              </p>
            )}
          </section>

          <ReportSection style={{ paddingTop: 20 }}>
            <ReportHeading>{t('detailB3.infoHeading')}</ReportHeading>
            <div className={styles.mlist}>
              {items.map(([key, value]) => (
                <div key={key} className={styles.mrow}>
                  <span className={styles.k}>{t(`detailB3.label${key}`)}</span>
                  <div className={styles.v}>
                    {CHIP_KEYS.includes(key) ? (
                      <div className={styles.chipV}>
                        <ReportTags items={Array.isArray(value) ? value : [value]} />
                      </div>
                    ) : key === 'Architect' && architectId ? (
                      <button type="button" className={styles.architectLink} onClick={openArchitect}>
                        {value}
                      </button>
                    ) : value}
                  </div>
                </div>
              ))}
            </div>
            {building.source_url && (
              <a
                className={styles.srcLink}
                href={building.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t('detailB3.viewSource')}
                <span aria-hidden="true">↗</span>
              </a>
            )}
          </ReportSection>

          {detailDescription && (
            <ReportSection style={{ paddingTop: 8 }}>
              <ReportHeading>{t('detailB3.descriptionHeading')}</ReportHeading>
              <p className={styles.desc}>{detailDescription}</p>
            </ReportSection>
          )}

          <ReportSection style={{ paddingTop: 8 }}>
            <ReportHeading>{t('detailB3.atmosphereHeading')}</ReportHeading>
            <p className={styles.desc}>{atmosphere}</p>
          </ReportSection>

          {galleryMeta.length > 0 ? (
            <>
              {renderGallerySection(photos, 0, t('detailB3.photosHeading'), photosView, setPhotosView, false)}
              {renderGallerySection(drawings, photos.length, t('detailB3.drawingsHeading'), drawingsView, setDrawingsView, true)}
            </>
          ) : gallery.length > 0 ? (
            <section className="hide-scrollbar" style={{
              height: '50vh',
              minHeight: 320,
              display: 'flex',
              overflowX: 'auto',
              scrollSnapType: 'x mandatory',
              background: 'var(--color-surface)',
            }}>
              {gallery.map((url, index) => (
                <div
                  key={`${url}-${index}`}
                  onClick={() => setLightboxIndex(index)}
                  style={{
                    position: 'relative',
                    minWidth: '100%',
                    height: '100%',
                    scrollSnapAlign: 'start',
                    background: '#050505',
                    cursor: 'zoom-in',
                  }}
                >
                  <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0 }} />
                  <img
                    src={url}
                    alt={`${title} ${index + 1}`}
                    loading={index === 0 ? 'eager' : 'lazy'}
                    style={{
                      position: 'absolute',
                      inset: 0,
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                    }}
                  />
                </div>
              ))}
            </section>
          ) : null}
        </ReportScope>
      </div>
    </div>
  )
}
