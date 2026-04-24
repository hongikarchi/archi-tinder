import { useState } from 'react'

// TODO: Replace with API call
const MOCK_OFFICE = {
  office_id: "OFF001",
  name: "OMA",
  verified: true,
  website_url: "https://oma.com",
  contact_email: "info@oma.com",
  description: "Office for Metropolitan Architecture is a leading international partnership practicing architecture, urbanism, and cultural analysis.",
  logo_url: "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/offices/oma_logo.jpg",
  location: "Rotterdam, Netherlands",
  founded_year: 1975,
  projects: [
    {
      building_id: "B00042",
      name_en: "Seattle Central Library",
      image_url: "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/photos/B00042_01.jpg",
      year: 2004,
      program: "Public",
      city: "Seattle"
    },
    {
      building_id: "B00119",
      name_en: "Taipei Performing Arts Center",
      image_url: "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/photos/22101_OMA_Taipei_Performing_Arts_Center_01.jpg",
      year: 2022,
      program: "Cultural",
      city: "Taipei"
    }
  ],
  articles: [
    {
      title: "OMA Unveils New Campus Design",
      source: "ArchDaily",
      url: "https://archdaily.com/",
      date: "2025-01-15"
    },
    {
      title: "Rem Koolhaas on the future of urbanism",
      source: "Dezeen",
      url: "https://dezeen.com/",
      date: "2024-11-20"
    }
  ]
}

export default function FirmProfilePage() {
  return (
    <div style={{ 
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', 
      overflowY: 'auto',
      background: '#0a0a0c', 
      paddingBottom: 'calc(100px + env(safe-area-inset-bottom))' 
    }}>
      <div style={{ position: 'fixed', top: '-10%', left: '-10%', width: '120%', height: '50%', background: 'radial-gradient(circle at 50% 0%, rgba(139,92,246,0.08) 0%, transparent 70%)', pointerEvents: 'none' }} />
      
      {/* Sticky Header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 10, 
        background: 'rgba(10, 10, 12, 0.75)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)'
      }}>
        <h2 style={{ color: '#fff', fontSize: 20, fontWeight: 800, margin: 0 }}>Firm Profile</h2>
      </div>

      <div style={{ maxWidth: 480, margin: '0 auto', padding: '32px 20px' }}>
        {/* Office Header Card */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 40, textAlign: 'center', position: 'relative', zIndex: 1 }}>
          {MOCK_OFFICE.logo_url ? (
            <div style={{ position: 'relative', marginBottom: 20 }}>
               <div style={{ position: 'absolute', inset: -4, borderRadius: 28, background: 'linear-gradient(135deg, #ec4899, #8b5cf6)', opacity: 0.3, filter: 'blur(10px)' }} />
               <img src={MOCK_OFFICE.logo_url} alt={MOCK_OFFICE.name} style={{ 
                 width: 104, height: 104, borderRadius: 24, objectFit: 'contain', background: '#fff', 
                 position: 'relative', zIndex: 2, border: '1px solid rgba(255,255,255,0.2)'
               }} />
            </div>
          ) : (
            <div style={{ 
              width: 104, height: 104, borderRadius: 24, background: 'rgba(255,255,255,0.03)', 
              border: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20, boxShadow: '0 10px 30px rgba(0,0,0,0.3)' 
            }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
                <line x1="9" y1="22" x2="15" y2="22"></line>
                <line x1="12" y1="6" x2="12" y2="6.01"></line>
                <line x1="12" y1="10" x2="12" y2="10.01"></line>
                <line x1="12" y1="14" x2="12" y2="14.01"></line>
              </svg>
            </div>
          )}
          <h1 style={{ color: '#fff', fontSize: 32, fontWeight: 900, margin: '0 0 8px', lineHeight: 1.2, display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
            {MOCK_OFFICE.name}
            {MOCK_OFFICE.verified && (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ec4899" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
              </svg>
            )}
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14, margin: '0 0 32px', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            {MOCK_OFFICE.location} • Est. {MOCK_OFFICE.founded_year}
          </p>
          
          <div style={{ display: 'flex', gap: 12, width: '100%' }}>
            {MOCK_OFFICE.website_url && (
              <a href={MOCK_OFFICE.website_url} target="_blank" rel="noreferrer" style={{ 
                flex: 1, padding: '14px', borderRadius: 14, background: 'rgba(255,255,255,0.04)', 
                color: '#fff', textDecoration: 'none', fontSize: 14, fontWeight: 700, 
                border: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8,
                boxShadow: '0 8px 16px rgba(0,0,0,0.2)'
              }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="2" y1="12" x2="22" y2="12"></line>
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                </svg>
                Website
              </a>
            )}
            {MOCK_OFFICE.contact_email && (
              <a href={`mailto:${MOCK_OFFICE.contact_email}`} style={{ 
                flex: 1, padding: '14px', borderRadius: 14, background: 'rgba(255,255,255,0.04)', 
                color: '#fff', textDecoration: 'none', fontSize: 14, fontWeight: 700, 
                border: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8,
                boxShadow: '0 8px 16px rgba(0,0,0,0.2)'
              }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                  <polyline points="22,6 12,13 2,6"></polyline>
                </svg>
                Email
              </a>
            )}
          </div>
        </div>

        {/* Description */}
        <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: 16, lineHeight: 1.6, marginBottom: 48, textAlign: 'center', fontWeight: 500 }}>
          {MOCK_OFFICE.description}
        </p>

        {/* Projects Grid */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ color: '#fff', fontSize: 20, fontWeight: 800, margin: 0 }}>Projects</h3>
          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, fontWeight: 700 }}>{MOCK_OFFICE.projects.length}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 48 }}>
          {MOCK_OFFICE.projects.map(project => (
            <div key={project.building_id} style={{ 
              background: 'rgba(255,255,255,0.03)', borderRadius: 20, overflow: 'hidden', cursor: 'pointer', 
              border: '1px solid rgba(255,255,255,0.08)', position: 'relative', boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
            }}>
               <div style={{ width: '100%', aspectRatio: '4/5', position: 'relative' }}>
                 <img src={project.image_url} alt={project.name_en} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                 <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to top, rgba(0,0,0,0.9) 0%, transparent 60%)' }} />
               </div>
               <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '16px' }}>
                 <p style={{ 
                   color: '#fff', fontSize: 14, fontWeight: 800, margin: '0 0 4px', 
                   display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', textOverflow: 'ellipsis' 
                 }}>{project.name_en}</p>
                 <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, margin: 0, fontWeight: 500 }}>{project.city}, {project.year}</p>
               </div>
            </div>
          ))}
        </div>

        {/* Articles List */}
        {MOCK_OFFICE.articles?.length > 0 && (
          <>
            <h3 style={{ color: '#fff', fontSize: 20, fontWeight: 800, margin: '0 0 20px' }}>Featured Articles</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {MOCK_OFFICE.articles.map((article, idx) => (
                <a key={idx} href={article.url} target="_blank" rel="noreferrer" style={{ 
                  textDecoration: 'none', background: 'rgba(255,255,255,0.03)', 
                  border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, padding: '24px', display: 'flex', flexDirection: 'column',
                  boxShadow: '0 10px 25px rgba(0,0,0,0.2)'
                }}>
                  <p style={{ color: '#fff', fontSize: 16, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.4 }}>{article.title}</p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#ec4899', fontSize: 13, fontWeight: 700 }}>{article.source}</span>
                    <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12, fontWeight: 600 }}>{article.date}</span>
                  </div>
                </a>
              ))}
            </div>
          </>
        )}

      </div>
    </div>
  )
}
