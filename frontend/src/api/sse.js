/**
 * api/sse.js
 * Minimal incremental Server-Sent-Events frame parser (no dependencies).
 *
 * EventSource cannot POST or send an Authorization header, so streaming
 * endpoints are consumed via fetch() + ReadableStream and parsed here.
 *
 * Frame format: `event: <name>\ndata: <payload>\n\n`. Lines starting with ':'
 * are comments (`: stream-open`, `: keepalive`) and are ignored. Frames without
 * a data line are dropped.
 *
 * Usage:
 *   const p = createSseParser((event, data) => { ... })
 *   p.push(textChunk)   // call for every decoded chunk (any split position)
 *   p.flush()           // call once at end of stream
 */

export function createSseParser(onEvent) {
  let buf = ''
  let heldCR = ''

  function dispatch(block) {
    let event = 'message'
    const data = []
    for (const line of block.split('\n')) {
      if (!line || line.startsWith(':')) continue
      const idx = line.indexOf(':')
      const field = idx === -1 ? line : line.slice(0, idx)
      let value = idx === -1 ? '' : line.slice(idx + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    if (data.length === 0) return
    onEvent(event, data.join('\n'))
  }

  function drain() {
    let i
    while ((i = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, i)
      buf = buf.slice(i + 2)
      dispatch(block)
    }
  }

  return {
    push(chunk) {
      let text = heldCR + chunk
      heldCR = ''
      // A trailing '\r' may be the first half of a CRLF split across chunks.
      // Normalizing it now would turn the '\n' that starts the next chunk into
      // a second newline (spurious frame boundary), so hold it back.
      if (text.endsWith('\r')) {
        heldCR = '\r'
        text = text.slice(0, -1)
      }
      buf += text.replace(/\r\n?/g, '\n')
      drain()
    },
    flush() {
      // A held '\r' at EOF is a lone (bare-CR) line terminator.
      if (heldCR) {
        buf += '\n'
        heldCR = ''
        drain()
      }
      // A well-formed stream ends on a blank line; dispatch any trailing frame
      // that was terminated by EOF instead.
      if (buf.trim()) dispatch(buf)
      buf = ''
    },
  }
}
