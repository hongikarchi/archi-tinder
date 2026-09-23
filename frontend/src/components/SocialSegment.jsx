/**
 * SocialSegment.jsx — Social 탭 안의 [사람] / [공모전] 전환 (PROTOTYPE)
 *
 * 설계: docs/plans/2026-09-17-competition-team-design.md §7
 *
 * 새 탭을 만들지 않는다. TabBar 3개(디스커버리 / Taste / 프로필) 구조는
 * 건드리지 않고, Social 탭 루트 안에서만 갈라진다.
 *
 * 아이콘만 쓰고 글자는 없다. 아이콘은 TabBar 와 같은 언어를 따른다 —
 * 24 viewBox · stroke=currentColor · strokeWidth 2 · round cap/join.
 * 다만 TabBar 의 social 아이콘(여러 사람)과 겹치지 않도록 여기서는 1인을 쓴다.
 * 글자가 없으므로 aria-label 과 title 로 이름을 남긴다 — 스크린리더와
 * 데스크탑 hover 양쪽에서 뜻이 드러나야 한다.
 */
import { useNavigate } from 'react-router-dom'
import styles from './SocialSegment.module.css'

const ICONS = {
  // 1인 — TabBar 의 social(여러 사람)과 구분된다
  people: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
  // 트로피 — 공모전
  competitions: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
      <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" />
      <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
      <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
      <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
    </svg>
  ),
}

const ITEMS = [
  { id: 'people', label: '사람', path: '/people' },
  { id: 'competitions', label: '공모전', path: '/competitions' },
]

export default function SocialSegment({ active }) {
  const navigate = useNavigate()
  return (
    <div className={styles.row} role="tablist" aria-label="소셜 보기 전환">
      {ITEMS.map(it => (
        <button
          key={it.id}
          type="button"
          role="tab"
          aria-selected={active === it.id}
          aria-label={it.label}
          title={it.label}
          className={`${styles.seg} ${active === it.id ? styles.segActive : ''}`}
          onClick={() => { if (active !== it.id) navigate(it.path) }}
        >
          {ICONS[it.id]}
        </button>
      ))}
    </div>
  )
}
