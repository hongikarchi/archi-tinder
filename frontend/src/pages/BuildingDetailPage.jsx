import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { bookmarkBuilding, getBuildings } from '../api/client.js'
import SaveToBoardModal from '../components/SaveToBoardModal.jsx'
import ErrorState from './buildingDetail/ErrorState.jsx'
import Header from './buildingDetail/Header.jsx'
import LoadingState from './buildingDetail/LoadingState.jsx'
import { isValidRank, kindLabel, metadataItems } from './buildingDetail/helpers.js'
import PhotoLightbox from './buildingDetail/PhotoLightbox.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'

const BUILDING_ID_RE = /^[A-Za-z0-9_-]{1,32}$/

export default function BuildingDetailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const rawBuildingId = useParams().buildingId
  const buildingId = BUILDING_ID_RE.test(String(rawBuildingId || '')) ? rawBuildingId : null
  const fromProjectId = location.state?.fromProjectId || null
  const fromSessionId = location.state?.fromSessionId || null
  const referrer = location.state?.referrer || null
  const fromRecommended = !!location.state?.fromRecommended
  const rank = isValidRank(location.state?.rank) ? location.state.rank : null
  const savedIds = useMemo(
    () => (Array.isArray(location.state?.savedIds) ? location.state.savedIds : []),
    [location.state?.savedIds]
  )
  const initialBookmarked = !!buildingId && savedIds.includes(buildingId)
  const initialBookmarkedRef = useRef(initialBookmarked)
  const [building, setBuilding] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [isBookmarked, setIsBookmarked] = useState(initialBookmarked)
  const [bookmarkPending, setBookmarkPending] = useState(false)
  const [saveModalOpen, setSaveModalOpen] = useState(false)
  const [isSaved, setIsSaved] = useState(false)
  const [lightboxIndex, setLightboxIndex] = useState(null) // null = closed

  useEffect(() => {
    const next = !!buildingId && savedIds.includes(buildingId)
    initialBookmarkedRef.current = next
    setIsBookmarked(next)
  }, [buildingId, savedIds])

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
    const meta = building.gallery_meta?.length ? building.gallery_meta : []
    return meta
  }, [building])

  const photos = useMemo(() => galleryMeta.filter(g => g.kind !== 'drawing'), [galleryMeta])
  const drawings = useMemo(() => galleryMeta.filter(g => g.kind === 'drawing'), [galleryMeta])
  const [galleryFilter, setGalleryFilter] = useState('all')  // 'all' | 'photos' | 'drawings'

  const title = building?.image_title || buildingId || 'Building'

  // Flat image list for lightbox, ordered to match what's visible under current filter
  const lightboxImages = useMemo(() => {
    if (galleryMeta.length > 0) {
      const visiblePhotos   = galleryFilter !== 'drawings' ? photos   : []
      const visibleDrawings = galleryFilter !== 'photos'   ? drawings : []
      return [...visiblePhotos, ...visibleDrawings].map(g => ({ url: g.url, alt: kindLabel(g.kind) }))
    }
    return gallery.map(url => ({ url, alt: title }))
  }, [galleryMeta, galleryFilter, photos, drawings, gallery, title])
  const architect = building?.metadata?.axis_architects
  const detailDescription = building?.metadata?.visual_description || building?.metadata?.description || null
  const description = building?.metadata?.axis_atmosphere || 'No atmosphere description is available yet.'
  const items = metadataItems(building)

  function handleBack() {
    const netChanged = isBookmarked !== initialBookmarkedRef.current
    if (netChanged && referrer && buildingId) {
      navigate(referrer, {
        replace: true,
        state: {
          bookmarkChanged: {
            buildingId,
            action: isBookmarked ? 'save' : 'unsave',
          },
        },
      })
    } else {
      navigate(-1)
    }
  }

  async function handleToggleBookmark() {
    if (!fromProjectId || !buildingId || !rank || bookmarkPending) return
    const wasBookmarked = isBookmarked
    setBookmarkPending(true)
    setIsBookmarked(!wasBookmarked)
    try {
      await bookmarkBuilding(fromProjectId, buildingId, wasBookmarked ? 'unsave' : 'save', rank, fromSessionId)
    } catch {
      setIsBookmarked(wasBookmarked)
    } finally {
      setBookmarkPending(false)
    }
  }

  if (loading) return <LoadingState onBack={handleBack} />
  if (error || !building) {
    return (
      <ErrorState
        message={error || 'No building matched this ID.'}
        onBack={handleBack}
        onRetry={() => setReloadKey(k => k + 1)}
      />
    )
  }

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      background: 'var(--color-bg)',
      color: 'var(--color-text)',
      overflowY: 'auto',
      paddingBottom: 'calc(84px + env(safe-area-inset-bottom, 0px))',
    }}>
      <PageLogoHeader />

      <Header
        onBack={handleBack}
        onSaveToBoard={() => !isSaved && setSaveModalOpen(true)}
        isSaved={isSaved}
        saveEnabled={fromRecommended}
        bookmarkEnabled={!!fromProjectId && !!rank}
        bookmarkPending={bookmarkPending}
        isBookmarked={isBookmarked}
        onToggleBookmark={handleToggleBookmark}
      />

      {saveModalOpen && building && (
        <SaveToBoardModal
          card={{ ...building, canonical_bld_id: buildingId }}
          onClose={() => setSaveModalOpen(false)}
          onSaved={() => { setSaveModalOpen(false); setIsSaved(true) }}
        />
      )}

      {lightboxIndex !== null && lightboxImages.length > 0 && (
        <PhotoLightbox
          images={lightboxImages}
          activeIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onNavigate={setLightboxIndex}
        />
      )}

      <main style={{ maxWidth: 820, margin: '0 auto', padding: '24px 20px 16px' }}>
        <p style={{
          color: 'var(--color-text-muted)',
          fontSize: 11,
          fontWeight: 800,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          margin: '0 0 8px',
        }}>
          Building detail
        </p>
        <h1 style={{
          color: 'var(--color-text)',
          fontSize: 'clamp(28px, 7vw, 42px)',
          fontWeight: 800,
          lineHeight: 1.08,
          margin: '0 0 8px',
        }}>
          {title}
        </h1>
        {architect && (
          <p style={{
            color: 'var(--color-text-dim)',
            fontSize: 15,
            fontStyle: 'italic',
            lineHeight: 1.45,
            margin: '0 0 20px',
          }}>
            {architect}
          </p>
        )}

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(138px, 1fr))',
          gap: 10,
          marginBottom: 24,
        }}>
          {items.map(([label, value]) => (
            <div key={label} style={{
              minHeight: 58,
              borderRadius: 12,
              border: '1px solid var(--color-border-soft)',
              background: 'var(--color-surface)',
              padding: '10px 12px',
            }}>
              <div style={{
                color: 'var(--color-text-muted)',
                fontSize: 10,
                fontWeight: 800,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                marginBottom: 4,
              }}>
                {label}
              </div>
              <div style={{
                color: 'var(--color-text)',
                fontSize: 13,
                fontWeight: 700,
                lineHeight: 1.3,
              }}>
                {value}
              </div>
            </div>
          ))}
        </div>

        {building.source_url && (
          <a
            href={building.source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              color: 'var(--color-text-dim)',
              fontSize: 13,
              fontWeight: 700,
              textDecoration: 'none',
              marginBottom: 24,
            }}
          >
            View on source
            <span aria-hidden="true">↗</span>
          </a>
        )}
      </main>

      {galleryMeta.length > 0 ? (
        <>
          {/* Filter toggle chips */}
          <div style={{
            display: 'flex',
            gap: 8,
            padding: '14px 20px 0',
            maxWidth: 820,
            margin: '0 auto',
            width: '100%',
            boxSizing: 'border-box',
          }}>
            {[
              { id: 'all', label: 'All' },
              { id: 'photos', label: 'Photos' },
              { id: 'drawings', label: 'Drawings' },
            ].map(chip => {
              const active = galleryFilter === chip.id
              const disabled = (chip.id === 'photos' && photos.length === 0)
                || (chip.id === 'drawings' && drawings.length === 0)
              return (
                <button
                  key={chip.id}
                  type="button"
                  onClick={() => setGalleryFilter(chip.id)}
                  disabled={disabled}
                  style={{
                    padding: '7px 14px',
                    borderRadius: 999,
                    border: active ? '1px solid var(--accent-1)' : '1px solid var(--color-border-soft)',
                    background: active ? 'color-mix(in srgb, var(--accent-1) 14%, transparent)' : 'var(--color-surface)',
                    color: disabled ? 'var(--color-text-dimmer)' : (active ? 'var(--accent-1)' : 'var(--color-text)'),
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: disabled ? 'default' : 'pointer',
                    fontFamily: 'inherit',
                    opacity: disabled ? 0.45 : 1,
                  }}
                >
                  {chip.label}
                </button>
              )
            })}
          </div>

          {/* 2-section masonry */}
          <div style={{
            maxWidth: 820,
            margin: '0 auto',
            padding: '14px 20px 0',
            width: '100%',
            boxSizing: 'border-box',
          }}>
            {photos.length > 0 && galleryFilter !== 'drawings' && (
              <section style={{ marginBottom: 24 }}>
                <h2 style={{
                  color: 'var(--color-text)',
                  fontSize: 14,
                  fontWeight: 700,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  margin: '0 0 10px',
                }}>
                  Photos
                </h2>
                <div style={{ columnCount: 2, columnGap: 8 }} className="building-masonry">
                  {photos.map((item, idx) => (
                    <div
                      key={`${item.url}-${idx}`}
                      onClick={() => setLightboxIndex(idx)}
                      style={{
                        breakInside: 'avoid',
                        marginBottom: 8,
                        position: 'relative',
                        borderRadius: 8,
                        overflow: 'hidden',
                        background: 'var(--color-surface)',
                        cursor: 'zoom-in',
                      }}
                    >
                      <img
                        src={item.url}
                        alt={`${title} ${kindLabel(item.kind)} ${idx + 1}`}
                        loading={idx < 2 ? 'eager' : 'lazy'}
                        style={{
                          width: '100%',
                          height: 'auto',
                          display: 'block',
                        }}
                      />
                      <span style={{
                        position: 'absolute',
                        bottom: 6,
                        left: 6,
                        background: 'rgba(0,0,0,0.6)',
                        color: '#fff',
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: 4,
                        letterSpacing: '0.04em',
                      }}>
                        {kindLabel(item.kind)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {drawings.length > 0 && galleryFilter !== 'photos' && (
              <section style={{ marginBottom: 24 }}>
                <h2 style={{
                  color: 'var(--color-text)',
                  fontSize: 14,
                  fontWeight: 700,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  margin: '0 0 10px',
                }}>
                  Drawings
                </h2>
                <div style={{ columnCount: 2, columnGap: 8 }} className="building-masonry">
                  {drawings.map((item, idx) => (
                    <div
                      key={`${item.url}-${idx}`}
                      onClick={() => setLightboxIndex(galleryFilter === 'drawings' ? idx : photos.length + idx)}
                      style={{
                        breakInside: 'avoid',
                        marginBottom: 8,
                        position: 'relative',
                        borderRadius: 8,
                        overflow: 'hidden',
                        background: '#fff',
                        cursor: 'zoom-in',
                      }}
                    >
                      <img
                        src={item.url}
                        alt={`${title} Drawing ${idx + 1}`}
                        loading="lazy"
                        style={{
                          width: '100%',
                          height: 'auto',
                          display: 'block',
                          objectFit: 'contain',
                        }}
                      />
                      <span style={{
                        position: 'absolute',
                        bottom: 6,
                        left: 6,
                        background: 'rgba(0,0,0,0.6)',
                        color: '#fff',
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: 4,
                        letterSpacing: '0.04em',
                      }}>
                        Drawing
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
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

      <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 20px' }}>
        {detailDescription && (
          <section style={{
            borderTop: '1px solid var(--color-border-soft)',
            paddingTop: 20,
            marginBottom: 20,
          }}>
            <h2 style={{
              color: 'var(--color-text)',
              fontSize: 16,
              fontWeight: 800,
              margin: '0 0 10px',
            }}>
              Description
            </h2>
            <p style={{
              color: 'var(--color-text-dim)',
              fontSize: 15,
              lineHeight: 1.65,
              margin: 0,
              whiteSpace: 'pre-wrap',
            }}>
              {detailDescription}
            </p>
          </section>
        )}

        <section style={{
          borderTop: '1px solid var(--color-border-soft)',
          paddingTop: 20,
        }}>
          <h2 style={{
            color: 'var(--color-text)',
            fontSize: 16,
            fontWeight: 800,
            margin: '0 0 10px',
          }}>
            Atmosphere
          </h2>
          <p style={{
            color: 'var(--color-text-dim)',
            fontSize: 15,
            lineHeight: 1.65,
            margin: 0,
          }}>
            {description}
          </p>
        </section>
      </div>
    </div>
  )
}
