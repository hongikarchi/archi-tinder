/**
 * teamFit.js — 팀 적합도 점수.
 *
 * 설계: docs/plans/2026-09-17-competition-team-design.md §4
 *
 * 발견 피드는 "가까운 사람"을 보여주지만(유클리드 거리), 팀은 축마다 방향이
 * 반대다:
 *
 *   1 작업 방식 (개념↔실무)   보완 — 멀수록 좋다 (컨셉 + 도면)
 *   2 역할 성향 (리더↔서포터) 보완 — 멀수록 좋다 (리더만 셋이면 깨진다)
 *   3 협업 방식 (협업↔독립)   일치 — 가까울수록 좋다
 *   4 접근 태도 (혁신↔전통)   일치 — 가까울수록 좋다
 *   5 결정 속도               보너스, 점수에 미반영
 *
 * 그래서 발견 피드의 거리 함수를 그대로 쓸 수 없다.
 *
 * 이 계산은 팀이 만들어지기 **전**의 후보 정렬에만 쓴다. 만들어진 팀을
 * 평가하는 용도로는 쓰지 않는다 — 설계 §5-1 에서 기각됐다.
 */

/**
 * 보완 가중치. 나머지(1 - W)가 일치에 실려 일치 쪽이 더 무겁다.
 *
 * 2026-09-23 확정. 근거는 팀이 깨지는 원인 — 건축 공모전에서 팀이 무너지는
 * 건 보통 역할이 겹쳐서가 아니라 일하는 방식이 안 맞아서다. 역할은 작업하다
 * 보면 자연히 나뉘지만 협업 방식(3축)·접근 태도(4축)가 어긋나면 처음부터
 * 끝까지 부딪힌다.
 *
 * 0.5 에서 크게 벗어나지 않은 이유: 보완을 버리는 게 아니라 동점일 때 일치
 * 쪽을 택하게 하려는 값이다. 0.2 이하로 가면 비슷한 사람만 모여 역할이 겹친다.
 *
 * 가설이며 실제 팀 결성·완주 결과로 보정해야 한다(검증 지표 미정).
 */
export const COMPLEMENT_WEIGHT = 0.4

const COMPLEMENT_AXES = [0, 1] // 작업 방식, 역할 성향
const ALIGN_AXES = [2, 3]      // 협업 방식, 접근 태도

/** 축값은 -1..+1 이므로 두 값의 차는 0..2. 0..1 로 정규화한다. */
function normalizedGap(a, b) {
  return Math.min(Math.abs(a - b) / 2, 1)
}

/**
 * 0..1 팀 적합도. 높을수록 좋은 팀 후보.
 * 벡터가 없으면 null — 호출부가 "정렬 불가"로 처리한다.
 */
export function teamFitScore(myVector, theirVector) {
  if (!Array.isArray(myVector) || !Array.isArray(theirVector)) return null
  if (myVector.length < 4 || theirVector.length < 4) return null

  // 보완: 멀수록 점수가 높다 (gap 그대로)
  const complement =
    COMPLEMENT_AXES.reduce((sum, i) => sum + normalizedGap(myVector[i], theirVector[i]), 0) /
    COMPLEMENT_AXES.length

  // 일치: 가까울수록 점수가 높다 (gap 반전)
  const align =
    ALIGN_AXES.reduce((sum, i) => sum + (1 - normalizedGap(myVector[i], theirVector[i])), 0) /
    ALIGN_AXES.length

  return COMPLEMENT_WEIGHT * complement + (1 - COMPLEMENT_WEIGHT) * align
}

const AXIS_LABELS = ['작업 방식', '역할 성향', '협업 방식', '접근 태도', '결정 속도']

/**
 * 받침 유무로 주격 조사를 고른다. 축 이름이 '방식'(받침 O) / '태도'(받침 X)로
 * 섞여 있어 고정 조사를 쓰면 "접근 태도이" 같은 문장이 나온다.
 */
function subjectParticle(word) {
  const last = word.charCodeAt(word.length - 1)
  if (last < 0xac00 || last > 0xd7a3) return '이'   // 한글이 아니면 보수적으로
  return (last - 0xac00) % 28 === 0 ? '가' : '이'
}

/**
 * 카드에 붙일 한 줄 근거. 점수를 만든 가장 큰 요인을 고른다.
 *
 * 판정이 아니라 제안이므로 단정적인 표현("좋은 팀")을 피하고 관찰만 적는다.
 */
export function fitReason(myVector, theirVector) {
  if (!Array.isArray(myVector) || !Array.isArray(theirVector)) return null

  const complementGaps = COMPLEMENT_AXES.map(i => ({ i, v: normalizedGap(myVector[i], theirVector[i]) }))
  const alignGaps = ALIGN_AXES.map(i => ({ i, v: normalizedGap(myVector[i], theirVector[i]) }))

  const bestComplement = complementGaps.reduce((a, b) => (b.v > a.v ? b : a))
  const bestAlign = alignGaps.reduce((a, b) => (b.v < a.v ? b : a))

  // 보완이 뚜렷하면 그쪽을, 아니면 일치를 말한다.
  if (bestComplement.v >= 0.5) {
    const w = AXIS_LABELS[bestComplement.i]
    return `${w}${subjectParticle(w)} 서로 반대예요`
  }
  if (bestAlign.v <= 0.25) {
    const wa = AXIS_LABELS[bestAlign.i]
    return `${wa}${subjectParticle(wa)} 잘 맞아요`
  }
  const wb = AXIS_LABELS[bestAlign.i]
  return `${wb}${subjectParticle(wb)} 비슷해요`
}

/** 적합도 내림차순 정렬. 원본 배열은 건드리지 않는다. */
export function sortByFit(people, myVector) {
  return [...people].sort((a, b) => {
    const sa = teamFitScore(myVector, a.vector) ?? -1
    const sb = teamFitScore(myVector, b.vector) ?? -1
    return sb - sa
  })
}
