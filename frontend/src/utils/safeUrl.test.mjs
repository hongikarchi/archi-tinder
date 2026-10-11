/**
 * utils/safeUrl.test.mjs — node --test src/utils/safeUrl.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { safeHttpUrl } from './safeUrl.js'

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
