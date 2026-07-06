import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rightSizeImageUrl, buildCardSrcSet, buildLqipUrl } from './rightSizeImageUrl.js'

// -- Divisare ------------------------------------------------------------------

test('Divisare: replaces w_auto with w_840,c_limit; keeps f_auto,q_auto and double-slash', () => {
  const input    = 'https://images.divisare.com//images/f_auto,q_auto,w_auto/v1531306470/abc/x.jpg'
  const expected = 'https://images.divisare.com//images/f_auto,q_auto,w_840,c_limit/v1531306470/abc/x.jpg'
  assert.equal(rightSizeImageUrl(input), expected)
})

test('Divisare: project_images path — replaces w_auto', () => {
  const input    = 'https://images.divisare.com/images/f_auto,q_auto,w_auto/v1/project_images/3844144/Name/x.jpg'
  const expected = 'https://images.divisare.com/images/f_auto,q_auto,w_840,c_limit/v1/project_images/3844144/Name/x.jpg'
  assert.equal(rightSizeImageUrl(input), expected)
})

test('Divisare: already-sized (no w_auto) — unchanged (idempotent)', () => {
  const input = 'https://images.divisare.com/images/f_auto,q_auto,w_840,c_limit/v1/abc/x.jpg'
  assert.equal(rightSizeImageUrl(input), input)
})

test('Divisare: gallery sibling /image/upload/c_fit,f_jpg,q_80,w_1200/ — unchanged (no w_auto)', () => {
  const input = 'https://images.divisare.com//image/upload/c_fit,f_jpg,q_80,w_1200/v1/project_images/2276517/2.jpg'
  assert.equal(rightSizeImageUrl(input), input)
})

// -- imgix ---------------------------------------------------------------------

test('imgix: sets w=840, fit=max, preserves q and cs params', () => {
  const input  = 'https://architizer-prod.imgix.net/media/foo/x.jpg?w=1680&q=60&auto=format,compress&cs=strip'
  const result = rightSizeImageUrl(input)
  const u      = new URL(result)
  assert.equal(u.searchParams.get('w'),   '840')
  assert.equal(u.searchParams.get('fit'), 'max')
  assert.equal(u.searchParams.get('q'),   '60')
  assert.equal(u.searchParams.get('cs'),  'strip')
  // raw-string assertions: imgix's canonical comma must NOT be percent-encoded,
  // otherwise the emitted URL is a different CDN cache key than the canonical form.
  assert.ok(!result.includes('%2C'), 'commas must stay literal, not %2C')
  assert.ok(result.includes('auto=format,compress'), 'auto=format,compress preserved verbatim')
})

test('imgix: already-sized — idempotent (w=840, fit=max, q=60 preserved)', () => {
  const input  = 'https://architizer-prod.imgix.net/media/foo/x.jpg?w=840&fit=max&q=60'
  const result = rightSizeImageUrl(input)
  const u      = new URL(result)
  assert.equal(u.searchParams.get('w'),   '840')
  assert.equal(u.searchParams.get('fit'), 'max')
  assert.equal(u.searchParams.get('q'),   '60')
})

test('imgix: bare URL (no query) — adds w=840, fit=max', () => {
  const input  = 'https://x.imgix.net/a.jpg'
  const result = rightSizeImageUrl(input)
  const u      = new URL(result)
  assert.equal(u.searchParams.get('w'),   '840')
  assert.equal(u.searchParams.get('fit'), 'max')
})

// -- Non-CDN / passthrough -----------------------------------------------------

test('non-imgix architizer.com — unchanged', () => {
  const input = 'https://architizer.com/foo.jpg'
  assert.equal(rightSizeImageUrl(input), input)
})

test('archello S3 host — unchanged', () => {
  const input = 'https://archello.s3.eu-central-1.amazonaws.com/x.jpg'
  assert.equal(rightSizeImageUrl(input), input)
})

test('http Divisare — rewritten, scheme stays http', () => {
  const input    = 'http://images.divisare.com/images/f_auto,q_auto,w_auto/v1/abc/x.jpg'
  const expected = 'http://images.divisare.com/images/f_auto,q_auto,w_840,c_limit/v1/abc/x.jpg'
  assert.equal(rightSizeImageUrl(input), expected)
})

// -- Edge cases ----------------------------------------------------------------

test("malformed string 'not a url' — unchanged", () => {
  assert.equal(rightSizeImageUrl('not a url'), 'not a url')
})

test("relative '/local/x.jpg' — unchanged", () => {
  assert.equal(rightSizeImageUrl('/local/x.jpg'), '/local/x.jpg')
})

test("empty string '' — returns ''", () => {
  assert.equal(rightSizeImageUrl(''), '')
})

test('null — returned as-is', () => {
  assert.equal(rightSizeImageUrl(null), null)
})

test('undefined — returned as-is', () => {
  assert.equal(rightSizeImageUrl(undefined), undefined)
})

// -- Idempotency assertions ----------------------------------------------------

test('idempotency: Divisare — double-call equals single-call', () => {
  const u = 'https://images.divisare.com//images/f_auto,q_auto,w_auto/v1531306470/abc/x.jpg'
  assert.equal(rightSizeImageUrl(rightSizeImageUrl(u)), rightSizeImageUrl(u))
})

test('idempotency: imgix — double-call equals single-call', () => {
  const u = 'https://architizer-prod.imgix.net/media/foo/x.jpg?w=1680&q=60'
  assert.equal(rightSizeImageUrl(rightSizeImageUrl(u)), rightSizeImageUrl(u))
})

// -- F1: optional quality param ------------------------------------------------

test('F1 imgix + quality=40 — result has q=40', () => {
  const input  = 'https://architizer-prod.imgix.net/media/foo/x.jpg?auto=format,compress'
  const result = rightSizeImageUrl(input, 840, 40)
  const u      = new URL(result)
  assert.equal(u.searchParams.get('q'), '40')
  assert.equal(u.searchParams.get('w'), '840')
  assert.equal(u.searchParams.get('fit'), 'max')
  assert.ok(!result.includes('%2C'), 'commas must stay literal, not %2C')
})

test('F1 Divisare + quality arg — NO q= added (q_auto handles it, quality intentionally ignored)', () => {
  const input  = 'https://images.divisare.com//images/f_auto,q_auto,w_auto/v1/abc/x.jpg'
  const result = rightSizeImageUrl(input, 840, 40)
  assert.ok(!result.includes('q='), 'Divisare must NOT have a q= param')
  assert.ok(result.includes('q_auto'), 'Divisare must retain q_auto')
})

// -- F2: buildCardSrcSet -------------------------------------------------------

test('F2 Divisare w_auto — returns correct 1x/2x srcset, no q in either descriptor', () => {
  const raw    = 'https://images.divisare.com//images/f_auto,q_auto,w_auto/v1/abc/x.jpg'
  const srcset = buildCardSrcSet(raw)
  assert.ok(srcset !== null, 'should return a srcset string')
  // Must contain both descriptors
  assert.ok(srcset.includes(' 1x,'), 'must have 1x descriptor')
  assert.ok(srcset.includes(' 2x'), 'must have 2x descriptor')
  // 1x and 2x should use w_420 and w_840 respectively
  assert.ok(srcset.includes('w_420,c_limit'), '1x URL must have w_420,c_limit')
  assert.ok(srcset.includes('w_840,c_limit'), '2x URL must have w_840,c_limit')
  // No q= param (Divisare uses q_auto, not q=N)
  assert.ok(!srcset.includes('q='), 'Divisare srcset must NOT include q=')
  // q_auto preserved
  assert.ok(srcset.includes('q_auto'), 'Divisare srcset must retain q_auto')
})

test('F2 Divisare gallery-sibling/already-sized (no w_auto) — returns null', () => {
  const raw = 'https://images.divisare.com//image/upload/c_fit,f_jpg,q_80,w_1200/v1/project_images/2276517/2.jpg'
  assert.equal(buildCardSrcSet(raw), null)
})

test('F2 imgix — 1x has w=420 q=80, 2x has w=840 q=40, fit=max, no %2C', () => {
  const raw    = 'https://architizer-prod.imgix.net/media/foo/x.jpg?auto=format,compress&cs=strip'
  const srcset = buildCardSrcSet(raw)
  assert.ok(srcset !== null, 'should return a srcset string')
  // Split on descriptor boundary without splitting on commas inside URL
  const [part1x, part2x] = srcset.split(' 1x, ')
  const u1 = new URL(part1x.trim())
  const u2 = new URL(part2x.replace(' 2x', '').trim())
  // 1x checks
  assert.equal(u1.searchParams.get('w'),   '420')
  assert.equal(u1.searchParams.get('q'),   '80')
  assert.equal(u1.searchParams.get('fit'), 'max')
  // 2x checks
  assert.equal(u2.searchParams.get('w'),   '840')
  assert.equal(u2.searchParams.get('q'),   '40')
  assert.equal(u2.searchParams.get('fit'), 'max')
  // No percent-encoded commas in either descriptor
  assert.ok(!srcset.includes('%2C'), 'commas must stay literal, not %2C')
  // auto=format,compress preserved verbatim in both
  assert.ok(srcset.includes('auto=format,compress'), 'auto=format,compress preserved verbatim')
})

test('F2 non-CDN URL — returns null', () => {
  assert.equal(buildCardSrcSet('https://archello.s3.eu-central-1.amazonaws.com/x.jpg'), null)
})

test('F2 malformed/relative URL — returns null', () => {
  assert.equal(buildCardSrcSet('not a url'), null)
  assert.equal(buildCardSrcSet('/local/x.jpg'), null)
})

test('F2 SECURITY: whitespace in URL — returns null (no srcset injection)', () => {
  // A literal space would terminate the srcset URL token and let a trailing
  // ", http://evil.example/p.jpg 1x" parse as an extra candidate (allowlist bypass).
  const evil = 'https://images.divisare.com//images/f_auto,q_auto,w_auto/v1/x a, http://evil.example/p.jpg'
  assert.equal(buildCardSrcSet(evil), null)
  // also tab / newline
  assert.equal(buildCardSrcSet('https://images.divisare.com//images/f_auto,q_auto,w_auto/v1/x\ty.jpg'), null)
})

test('F2 empty string — returns null', () => {
  assert.equal(buildCardSrcSet(''), null)
})

test('F2 null — returns null', () => {
  assert.equal(buildCardSrcSet(null), null)
})

// -- B1: buildLqipUrl -----------------------------------------------------

test('LQIP Divisare w_auto — returns w_20,c_limit URL', () => {
  const input    = 'https://images.divisare.com//images/f_auto,q_auto,w_auto/v1531306470/abc/x.jpg'
  const expected = 'https://images.divisare.com//images/f_auto,q_auto,w_20,c_limit/v1531306470/abc/x.jpg'
  assert.equal(buildLqipUrl(input), expected)
})

test('LQIP Divisare without w_auto — returns null (would equal full-size URL)', () => {
  const input = 'https://images.divisare.com/images/f_auto,q_auto,w_840,c_limit/v1/abc/x.jpg'
  assert.equal(buildLqipUrl(input), null)
})

test('LQIP Divisare gallery sibling (no w_auto) — returns null', () => {
  const input = 'https://images.divisare.com//image/upload/c_fit,f_jpg,q_80,w_1200/v1/project_images/2276517/2.jpg'
  assert.equal(buildLqipUrl(input), null)
})

test('LQIP imgix — sets w=20, fit=max', () => {
  const input  = 'https://architizer-prod.imgix.net/media/foo/x.jpg?w=1680&q=60'
  const result = buildLqipUrl(input)
  assert.ok(result !== null, 'should return a URL')
  const u = new URL(result)
  assert.equal(u.searchParams.get('w'),   '20')
  assert.equal(u.searchParams.get('fit'), 'max')
})

test('LQIP non-CDN host — returns null', () => {
  assert.equal(buildLqipUrl('https://architizer.com/foo.jpg'), null)
  assert.equal(buildLqipUrl('https://archello.s3.eu-central-1.amazonaws.com/x.jpg'), null)
})

test('LQIP malformed/relative URL — returns null', () => {
  assert.equal(buildLqipUrl('not a url'), null)
  assert.equal(buildLqipUrl('/local/x.jpg'), null)
})

test('LQIP empty/null/undefined — returns null', () => {
  assert.equal(buildLqipUrl(''), null)
  assert.equal(buildLqipUrl(null), null)
  assert.equal(buildLqipUrl(undefined), null)
})
