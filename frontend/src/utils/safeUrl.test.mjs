/**
 * utils/safeUrl.test.mjs — node --test src/utils/safeUrl.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { safeHttpUrl, safeMailto } from './safeUrl.js'

describe('safeHttpUrl', () => {
  test('accepts http and https, returns normalized href', () => {
    assert.equal(safeHttpUrl('https://example.com/a?b=1#c'), 'https://example.com/a?b=1#c')
    assert.equal(safeHttpUrl('http://example.com'), 'http://example.com/')
    assert.equal(safeHttpUrl('  https://example.com/x  '), 'https://example.com/x')
    assert.equal(safeHttpUrl('HTTPS://Example.com/a'), 'https://example.com/a')
    assert.equal(safeHttpUrl('\n https://example.com/x \t'), 'https://example.com/x')
  })

  test('rejects malformed scheme separators, credentials and inner control chars', () => {
    assert.equal(safeHttpUrl('https:example.com'), null)
    assert.equal(safeHttpUrl('http:/example.com'), null)
    assert.equal(safeHttpUrl('https:\\\\host'), null)
    assert.equal(safeHttpUrl('https://'), null)
    assert.equal(safeHttpUrl('https://user:pass@host/x'), null)
    assert.equal(safeHttpUrl('https://user@host/x'), null)
    assert.equal(safeHttpUrl('https://exa\tmple.com/x'), null)
    assert.equal(safeHttpUrl('https://example.com/\nx'), null)
  })

  test('rejects dangerous and non-http schemes', () => {
    assert.equal(safeHttpUrl('javascript:alert(1)'), null)
    assert.equal(safeHttpUrl('JaVaScRiPt:alert(1)'), null)
    assert.equal(safeHttpUrl('  javascript:alert(1)'), null)
    assert.equal(safeHttpUrl('java\tscript:alert(1)'), null)
    assert.equal(safeHttpUrl('data:text/html,<script>1</script>'), null)
    assert.equal(safeHttpUrl('ftp://example.com/file'), null)
    assert.equal(safeHttpUrl('file:///etc/passwd'), null)
    assert.equal(safeHttpUrl('mailto:a@b.com'), null)
  })

  test('rejects protocol-relative, relative, empty and non-strings', () => {
    assert.equal(safeHttpUrl('//example.com/x'), null)
    assert.equal(safeHttpUrl('/path/only'), null)
    assert.equal(safeHttpUrl('example.com'), null)
    assert.equal(safeHttpUrl('../x'), null)
    assert.equal(safeHttpUrl(''), null)
    assert.equal(safeHttpUrl('   '), null)
    assert.equal(safeHttpUrl(null), null)
    assert.equal(safeHttpUrl(undefined), null)
    assert.equal(safeHttpUrl(42), null)
    assert.equal(safeHttpUrl('https://'), null)
  })
})

describe('safeMailto', () => {
  test('builds a mailto href for a plausible address', () => {
    assert.equal(safeMailto('takedown@example.com'), 'mailto:takedown@example.com')
    assert.equal(safeMailto(' a.b+c@sub.example.co.kr '), 'mailto:a.b+c@sub.example.co.kr')
  })

  test('encodes subject and body', () => {
    const href = safeMailto('a@example.com', '[Archibe] 포스터 삭제 요청 — X&Y', 'line1\nhttps://x.test/?a=1&b=2')
    assert.ok(href.startsWith('mailto:a@example.com?subject='))
    assert.ok(href.includes(`subject=${encodeURIComponent('[Archibe] 포스터 삭제 요청 — X&Y')}`))
    assert.ok(href.includes(`&body=${encodeURIComponent('line1\nhttps://x.test/?a=1&b=2')}`))
    // the only raw '?' and '&' are the ones we added
    assert.equal(href.split('?').length, 2)
    assert.equal(href.split('&').length, 2)
    assert.ok(!href.includes('\n'))
  })

  test('rejects injection and malformed addresses', () => {
    assert.equal(safeMailto('a@example.com\nbcc:evil@example.com'), null)
    assert.equal(safeMailto('a@example.com,b@example.com'), null)
    assert.equal(safeMailto('a@example.com?cc=evil@example.com'), null)
    assert.equal(safeMailto('a@example.com&bcc=x@y.zz'), null)
    assert.equal(safeMailto('a b@example.com'), null)
    assert.equal(safeMailto('<a@example.com>'), null)
    assert.equal(safeMailto('a@example'), null)
    assert.equal(safeMailto('@example.com'), null)
    assert.equal(safeMailto('plainstring'), null)
    assert.equal(safeMailto(''), null)
    assert.equal(safeMailto(null), null)
    assert.equal(safeMailto(undefined), null)
  })
})
