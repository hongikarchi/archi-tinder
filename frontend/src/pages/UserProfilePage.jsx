import { useState } from 'react'

// TODO: Replace with API call
const MOCK_USER = {
  user_id: 1,
  display_name: "Kim Minseo",
  avatar_url: "https://ui-avatars.com/api/?name=Kim+Minseo&background=ec4899&color=fff&size=128",
  bio: "Architecture student at SNU, obsessed with brutalism and minimal design.",
  mbti: "INTJ",
  external_links: {
    instagram: "@kimarch",
    email: "kim@example.com"
  },
  follower_count: 42,
  following_count: 18,
  is_following: false,
  boards: [
    {
      board_id: "proj_123",
      name: "Museum References",
      visibility: "public",
      building_count: 15,
      cover_image_url: "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/photos/B00042_01.jpg"
    },
    {
      board_id: "proj_124",
      name: "Concrete Dreams",
      visibility: "private",
      building_count: 8,
      cover_image_url: "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/photos/22101_OMA_Taipei_Performing_Arts_Center_01.jpg"
    }
  ],
  persona_summary: {
    persona_type: "The Parametric Visionary",
    one_liner: "They seek purity where form and light converge",
    styles: ["Modern", "Parametric"],
    programs: ["Museum", "Public"]
  }
}

export default function UserProfilePage({ theme, onToggleTheme, onLogout }) {
  const [isFollowing, setIsFollowing] = useState(MOCK_USER.is_following)
  const [followerCount, setFollowerCount] = useState(MOCK_USER.follower_count)

  const isMe = true // TODO(claude): check if profile user_id === active session user_id

  function handleToggleFollow() {
     // TODO(claude): POST /api/v1/users/{id}/follow/ or DELETE
     setIsFollowing(!isFollowing)
     setFollowerCount(prev => isFollowing ? prev - 1 : prev + 1)
  }

  return (
    <div style={{ 
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', 
      overflowY: 'auto',
      background: '#0a0a0c', /* Deep cinematic dark instead of flat bg */
      paddingBottom: 'calc(100px + env(safe-area-inset-bottom))' 
    }}>
      {/* Ambient background glow */}
      <div style={{ position: 'fixed', top: '-10%', left: '-10%', width: '120%', height: '50%', background: 'radial-gradient(circle at 50% 0%, rgba(236,72,153,0.08) 0%, transparent 70%)', pointerEvents: 'none' }} />
      
      {/* Sticky Header with Settings */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 10, 
        background: 'rgba(10, 10, 12, 0.75)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderBottom: '1px solid rgba(255,255,255,0.06)'
      }}>
        <h2 style={{ color: '#fff', fontSize: 20, fontWeight: 800, margin: 0 }}>Profile</h2>
        {isMe && (
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={onLogout} style={{ 
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, 
              padding: '8px 16px', color: 'rgba(255,255,255,0.8)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}>
              Log Out
            </button>
          </div>
        )}
      </div>

      <div style={{ maxWidth: 480, margin: '0 auto', padding: '32px 20px', position: 'relative', zIndex: 1 }}>
        {/* Profile Header */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: 40 }}>
          <div style={{ position: 'relative', marginBottom: 20 }}>
            <div style={{ position: 'absolute', inset: -4, borderRadius: '50%', background: 'linear-gradient(135deg, #ec4899, #8b5cf6)', opacity: 0.5, filter: 'blur(8px)' }} />
            <img src={MOCK_USER.avatar_url} alt="avatar" style={{ width: 104, height: 104, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.1)', objectFit: 'cover', position: 'relative', zIndex: 2, background: '#1a1a1a' }} />
          </div>
          <h1 style={{ color: '#fff', fontSize: 26, fontWeight: 800, margin: '0 0 8px', lineHeight: 1.2 }}>{MOCK_USER.display_name}</h1>
          <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 15, lineHeight: 1.6, margin: '0 0 24px', maxWidth: 300, fontWeight: 500 }}>{MOCK_USER.bio}</p>
          
          <div style={{ display: 'flex', gap: 32, padding: '16px 40px', background: 'rgba(255,255,255,0.03)', borderRadius: 24, border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 10px 30px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ color: '#fff', fontSize: 22, fontWeight: 800 }}>{MOCK_USER.following_count}</span> 
              <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 4 }}>Following</span>
            </div>
            <div style={{ width: 1, background: 'rgba(255,255,255,0.1)' }} />
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ color: '#fff', fontSize: 22, fontWeight: 800 }}>{followerCount}</span> 
              <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 4 }}>Followers</span>
            </div>
          </div>
        </div>

        {/* Social Actions */}
        {!isMe && (
          <button onClick={handleToggleFollow} style={{ 
            width: '100%', minHeight: 48, padding: '14px', borderRadius: 14, 
            background: isFollowing ? 'rgba(255,255,255,0.06)' : 'linear-gradient(135deg, #ec4899, #f43f5e)', 
            color: isFollowing ? 'rgba(255,255,255,0.8)' : '#fff', 
            fontSize: 15, fontWeight: 700, border: isFollowing ? '1px solid rgba(255,255,255,0.1)' : 'none', 
            cursor: 'pointer', marginBottom: 32, boxShadow: isFollowing ? 'none' : '0 8px 20px rgba(236,72,153,0.3)'
          }}>
            {isFollowing ? 'Following' : 'Follow'}
          </button>
        )}

        {/* Persona Segment */}
        <div style={{ 
          background: 'linear-gradient(135deg, rgba(30,41,59,0.4) 0%, rgba(15,23,42,0.4) 100%)', 
          borderRadius: 24, padding: '24px', border: '1px solid rgba(255,255,255,0.08)', 
          marginBottom: 48, boxShadow: '0 15px 35px rgba(0,0,0,0.4)' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <h3 style={{ color: '#fff', fontSize: 16, fontWeight: 800, margin: 0 }}>Architectural Persona</h3>
            <span style={{ background: 'rgba(236,72,153,0.15)', color: '#ec4899', fontSize: 12, fontWeight: 700, padding: '4px 10px', borderRadius: 8, border: '1px solid rgba(236,72,153,0.25)' }}>{MOCK_USER.mbti}</span>
          </div>
          
          <p style={{ color: '#f472b6', fontSize: 16, fontWeight: 700, margin: '0 0 6px', letterSpacing: '0.02em' }}>{MOCK_USER.persona_summary.persona_type}</p>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 14, margin: '0 0 20px', fontStyle: 'italic', fontWeight: 500 }}>"{MOCK_USER.persona_summary.one_liner}"</p>
          
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {[...MOCK_USER.persona_summary.styles, ...MOCK_USER.persona_summary.programs].map((t, idx) => (
               <span key={idx} style={{ 
                 background: 'rgba(0,0,0,0.3)', color: 'rgba(255,255,255,0.8)', fontSize: 12, fontWeight: 600, 
                 padding: '6px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)' 
               }}>{t}</span>
            ))}
          </div>
        </div>

        {/* Boards List */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ color: '#fff', fontSize: 20, fontWeight: 800, margin: 0 }}>Curated Boards</h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
          {MOCK_USER.boards.map(board => (
            <div key={board.board_id} style={{ 
              background: 'rgba(255,255,255,0.03)', borderRadius: 20, overflow: 'hidden', cursor: 'pointer', 
              border: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column',
              boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
            }}>
               <div style={{ width: '100%', aspectRatio: '1', position: 'relative' }}>
                 <img src={board.cover_image_url} alt={board.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                 <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to bottom, transparent 60%, rgba(0,0,0,0.8))' }} />
                 {board.visibility === 'private' && (
                   <div style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(0,0,0,0.6)', padding: '6px', borderRadius: '50%', backdropFilter: 'blur(4px)' }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                      </svg>
                   </div>
                 )}
               </div>
               <div style={{ padding: '16px' }}>
                 <h4 style={{ 
                   color: '#fff', fontSize: 15, fontWeight: 700, margin: '0 0 6px', lineHeight: 1.2, 
                   display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden', textOverflow: 'ellipsis' 
                 }}>{board.name}</h4>
                 <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13, margin: 0, fontWeight: 600 }}>{board.building_count} saved</p>
               </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  )
}
