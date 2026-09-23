/**
 * SocialSegment.jsx — Social 탭 안의 [사람] / [공모전] 전환 (PROTOTYPE)
 *
 * 설계: docs/plans/2026-09-17-competition-team-design.md §7
 *
 * 새 탭을 만들지 않는다. TabBar 3개(디스커버리 / Taste / 프로필) 구조는
 * 건드리지 않고, Social 탭 루트 안에서만 갈라진다.
 */
import { useNavigate } from 'react-router-dom'
import styles from './SocialSegment.module.css'

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
          className={`${styles.seg} ${active === it.id ? styles.segActive : ''}`}
          onClick={() => { if (active !== it.id) navigate(it.path) }}
        >
          {it.label}
        </button>
      ))}
    </div>
  )
}
