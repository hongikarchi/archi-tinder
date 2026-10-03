import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createSseParser } from './sse.js'

function collect() {
  const events = []
  const parser = createSseParser((event, data) => events.push([event, data]))
  return { events, parser }
}

test('parses frames and ignores comments', () => {
  const { events, parser } = collect()
  parser.push(': stream-open\n\n')
  parser.push('event: reply\ndata: {"text":"hi"}\n\n: keepalive\n\nevent: final\ndata: {"a":1}\n\n')
  assert.deepEqual(events, [['reply', '{"text":"hi"}'], ['final', '{"a":1}']])
})

test('handles frames split across arbitrary chunk boundaries', () => {
  const { events, parser } = collect()
  const raw = 'event: filters\ndata: {"x":"한글"}\n\nevent: reply\ndata: {"text":"ab"}\n\n'
  for (const ch of raw) parser.push(ch)
  assert.deepEqual(events, [['filters', '{"x":"한글"}'], ['reply', '{"text":"ab"}']])
})

test('supports CRLF and multi-line data', () => {
  const { events, parser } = collect()
  parser.push('event: x\r\ndata: a\r\ndata: b\r\n\r\n')
  assert.deepEqual(events, [['x', 'a\nb']])
})

test('flush dispatches an unterminated trailing frame; comment-only frames dropped', () => {
  const { events, parser } = collect()
  parser.push('event: final\ndata: {"ok":true}')
  assert.equal(events.length, 0)
  parser.flush()
  assert.deepEqual(events, [['final', '{"ok":true}']])
  parser.push(': keepalive\n\n')
  assert.equal(events.length, 1)
})

test('CRLF split across chunks does not create a spurious frame boundary', () => {
  const { events, parser } = collect()
  // '\r' ends chunk 1, '\n' starts chunk 2: must be ONE line break, not two.
  parser.push('event: x\r')
  parser.push('\ndata: a\r\n\r\n')
  assert.deepEqual(events, [['x', 'a']])
})

test('CRLF split at every byte boundary yields the same events', () => {
  const raw = 'event: reply\r\ndata: {"text":"a"}\r\n\r\nevent: final\r\ndata: {"b":2}\r\n\r\n'
  const { events, parser } = collect()
  for (const ch of raw) parser.push(ch)
  assert.deepEqual(events, [['reply', '{"text":"a"}'], ['final', '{"b":2}']])
})

test('frame terminator CRLFCRLF split between the two CRLFs', () => {
  const { events, parser } = collect()
  parser.push('event: x\r\ndata: a\r\n\r')
  assert.equal(events.length, 0) // held '\r' must not complete the frame early
  parser.push('\n')
  assert.deepEqual(events, [['x', 'a']])
})

test('flush treats a held trailing CR as a line terminator', () => {
  const { events, parser } = collect()
  parser.push('event: final\ndata: {"ok":1}\r')
  assert.equal(events.length, 0)
  parser.flush()
  assert.deepEqual(events, [['final', '{"ok":1}']])
})
