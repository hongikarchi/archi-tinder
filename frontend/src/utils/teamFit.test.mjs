/**
 * utils/teamFit.test.mjs
 * Node 내장 테스트 러너(의존성 없음), loginFlow.test.mjs 와 같은 방식.
 * 실행: node --test frontend/src/utils/teamFit.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  COMPLEMENT_WEIGHT,
  teamFitScore,
  fitReason,
  sortByFit,
} from './teamFit.js'

const ME = [0.6, -0.3, 0.5, 0.7, 0]

describe('축 방향 — 발견 피드와 정반대', () => {
  test('1·2축은 멀수록 점수가 높다 (보완)', () => {
    const near = teamFitScore(ME, [0.6, -0.3, 0.5, 0.7, 0])
    const far = teamFitScore(ME, [-0.6, 0.3, 0.5, 0.7, 0])
    assert.ok(far > near, `보완축이 먼 쪽이 높아야 함: ${far} > ${near}`)
  })

  test('3·4축은 가까울수록 점수가 높다 (일치)', () => {
    const near = teamFitScore(ME, [0.6, -0.3, 0.5, 0.7, 0])
    const far = teamFitScore(ME, [0.6, -0.3, -0.5, -0.7, 0])
    assert.ok(near > far, `일치축이 가까운 쪽이 높아야 함: ${near} > ${far}`)
  })

  test('보완+일치를 모두 갖춘 사람이 복제형보다 높다', () => {
    const ideal = teamFitScore(ME, [-0.7, 0.8, 0.5, 0.7, 0])   // 1·2 반대, 3·4 동일
    const clone = teamFitScore(ME, [0.6, -0.3, 0.5, 0.7, 0])   // 전부 동일
    assert.ok(ideal > clone)
  })
})

describe('가중치 w = 0.4 — 일치 쪽이 무겁다', () => {
  test('상수가 0.4', () => {
    assert.equal(COMPLEMENT_WEIGHT, 0.4)
  })

  test('일치만 갖춘 사람이 보완만 갖춘 사람보다 높다', () => {
    // 보완만: 1·2축 정반대, 3·4축도 정반대
    const onlyComplement = teamFitScore(ME, [-1, 1, -0.5, -0.7, 0])
    // 일치만: 1·2축 동일, 3·4축 동일
    const onlyAlign = teamFitScore(ME, [0.6, -0.3, 0.5, 0.7, 0])
    assert.ok(
      onlyAlign > onlyComplement,
      `w<0.5 이므로 일치가 이겨야 함: ${onlyAlign} > ${onlyComplement}`
    )
  })
})

describe('점수 범위', () => {
  test('항상 0..1', () => {
    const cases = [
      [1, 1, 1, 1, 1], [-1, -1, -1, -1, -1], [0, 0, 0, 0, 0], ME,
    ]
    for (const v of cases) {
      const s = teamFitScore(ME, v)
      assert.ok(s >= 0 && s <= 1, `${s} 가 0..1 밖`)
    }
  })
})

describe('벡터가 없으면 null (크래시 금지)', () => {
  for (const [label, a, b] of [
    ['their 없음', ME, null],
    ['my 없음', null, ME],
    ['배열 아님', ME, 'x'],
    ['길이 부족', ME, [0.1, 0.2]],
  ]) {
    test(label, () => assert.equal(teamFitScore(a, b), null))
  }
})

describe('fitReason — 한국어 조사', () => {
  test("받침 없는 '태도' 뒤에는 '가'", () => {
    // 3·4축 아주 가깝고 1·2축도 가까워 일치 문장이 나오는 케이스
    const r = fitReason(ME, [0.6, -0.3, 0.5, 0.7, 0])
    assert.ok(!r.includes('태도이'), `조사 오류: ${r}`)
  })

  test("받침 있는 '방식' 뒤에는 '이'", () => {
    const r = fitReason(ME, [-1, -0.3, 0.5, 0.7, 0])
    assert.ok(r.includes('방식이'), `조사 오류: ${r}`)
  })

  test('벡터가 없으면 null', () => {
    assert.equal(fitReason(ME, null), null)
  })
})

describe('sortByFit', () => {
  test('적합도 내림차순', () => {
    const people = [
      { id: 'clone', vector: [0.6, -0.3, 0.5, 0.7, 0] },
      { id: 'ideal', vector: [-0.7, 0.8, 0.5, 0.7, 0] },
    ]
    assert.deepEqual(sortByFit(people, ME).map(p => p.id), ['ideal', 'clone'])
  })

  test('원본 배열을 변형하지 않는다', () => {
    const people = [
      { id: 'a', vector: [0.6, -0.3, 0.5, 0.7, 0] },
      { id: 'b', vector: [-0.7, 0.8, 0.5, 0.7, 0] },
    ]
    const before = people.map(p => p.id)
    sortByFit(people, ME)
    assert.deepEqual(people.map(p => p.id), before)
  })

  test('벡터 없는 사람은 뒤로 밀린다', () => {
    const people = [
      { id: 'broken', vector: null },
      { id: 'ok', vector: [-0.7, 0.8, 0.5, 0.7, 0] },
    ]
    assert.equal(sortByFit(people, ME)[0].id, 'ok')
  })
})
