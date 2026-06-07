export default function Header({ onBack, onSaveToBoard, isSaved, saveEnabled, bookmarkEnabled, bookmarkPending, isBookmarked, onToggleBookmark }) {
  return (
    <div style={{
      position: 'sticky',
      top: 0,
      zIndex: 20,
      height: 56,
      display: 'flex',
      alignItems: 'center',
      padding: '6px 14px',
      background: 'var(--color-header-bg, rgba(10,10,12,0.72))',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--color-border-soft)',
    }}>
      <button
        type="button"
        onClick={onBack}
        aria-label="Back"
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          border: 'none',
          background: 'transparent',
          color: 'var(--color-text)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12" />
          <polyline points="12 19 5 12 12 5" />
        </svg>
      </button>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Save to Board — only on recommended buildings, not on board-saved ones */}
        {saveEnabled && <button
          type="button"
          onClick={onSaveToBoard}
          aria-label={isSaved ? 'Saved to board' : 'Save to board'}
          style={{
            height: 36,
            padding: '0 14px',
            borderRadius: 10,
            border: isSaved ? '1px solid rgba(251,191,36,0.5)' : 'none',
            background: isSaved ? 'rgba(251,191,36,0.12)' : 'linear-gradient(135deg, #ec4899, #f43f5e)',
            color: isSaved ? '#fbbf24' : '#fff',
            fontSize: 13,
            fontWeight: 700,
            cursor: isSaved ? 'default' : 'pointer',
            fontFamily: 'inherit',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            transition: 'background 0.2s, color 0.2s',
          }}
        >
          {isSaved ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              저장됨
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              보드에 추가
            </>
          )}
        </button>}

        {bookmarkEnabled && (
          <button
            type="button"
            onClick={onToggleBookmark}
            disabled={bookmarkPending}
            aria-label={isBookmarked ? 'Remove bookmark' : 'Save bookmark'}
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              border: isBookmarked ? '1px solid rgba(251,191,36,0.65)' : '1px solid var(--color-border-soft)',
              background: isBookmarked ? 'rgba(251,191,36,0.18)' : 'transparent',
              color: isBookmarked ? '#fbbf24' : 'var(--color-text)',
              cursor: bookmarkPending ? 'default' : 'pointer',
              opacity: bookmarkPending ? 0.65 : 1,
              fontSize: 20,
            }}
          >
            {isBookmarked ? '★' : '☆'}
          </button>
        )}
      </div>
    </div>
  )
}
