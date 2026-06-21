import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rightSizeImageUrl } from './rightSizeImageUrl.js'

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
