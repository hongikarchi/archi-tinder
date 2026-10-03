"""
_stream.py -- PERF-SEARCH-1: incremental JSON scanner + parse-stream sink.

Self-contained (no sibling imports, no new dependency). Used by the streaming
variant of POST /api/v1/parse-query/ to react to the LLM's partial output:

  * PartialJSONScanner  -- feed() text chunks of ONE top-level JSON object as they
    arrive; it reports (a) when a top-level key starts, (b) the parsed value of each
    top-level key the moment that value is CLOSED (objects/arrays/strings/scalars),
    and (c) decoded incremental text of watched top-level string keys (`reply`).
  * ParseStreamSink     -- glue between the LLM stream and the SSE layer: records
    time-to-first-token, fires `on_filters_ready` once `filter_priority` closes
    (with whichever of filters / filter_delta already closed), and forwards `reply` text deltas.

The scanner never raises on malformed input; it just stops reporting (the caller
always re-parses the full text with json.loads at the end, which stays authoritative).
"""
import json
import logging
import time

logger = logging.getLogger('apps.recommendation')

# Keys feeding the early `filters` event (see ParseStreamSink). The event fires the
# moment `filter_priority` closes (the last of the trio in the schema order), carrying
# whichever of `filters` / `filter_delta` were already closed.
FILTER_TRIO = ('filters', 'filter_delta', 'filter_priority')
# PERF-SEARCH-2: scalar keys that sit BEFORE `filter_priority` in the strict schema
# and ride along in the early `partial` when already closed (they feed the speculative
# results search, which needs image_focus to match the final search exactly).
FILTER_EXTRA_KEYS = ('image_focus',)
_FILTER_TRIGGER = 'filter_priority'
_FILTER_BODY_KEYS = ('filters', 'filter_delta')


def _sanitize(text):
    """Drop lone surrogates so the text is always UTF-8 encodable."""
    return text.encode('utf-8', 'replace').decode('utf-8')


class PartialJSONScanner:
    """Incremental scanner over a single top-level JSON object.

    feed(chunk) -> list of events:
        ('key', name)            a top-level key name was read (its value follows)
        ('value', name, parsed)  the top-level value for `name` is now complete
        ('delta', name, text)    new decoded text of a watched string key

    Text before the first '{' (code fences, whitespace) is ignored.
    """

    def __init__(self, stream_keys=('reply',)):
        self._stream_keys = frozenset(stream_keys)
        self._text = ''
        self._i = 0
        self._depth = 0          # 0 = before top-level '{', 1 = inside it, 2 = done
        self._phase = 'key'      # key | colon | value_start | value
        self._in_str = False     # inside ANY string (key, top-level value, nested)
        self._esc = False
        self._uni_left = 0       # remaining hex digits of a \uXXXX escape
        self._uni_hex = ''
        self._pending_high = False
        self._key_chars = []
        self._key = None
        self._kind = None        # str | container | scalar
        self._val_start = 0
        self._cdepth = 0         # nesting depth inside a container value
        self._safe_end = 0       # index up to which a string value is fully decoded-safe
        self._emitted_len = 0    # decoded chars already emitted for the current string
        self.broken = False

    # -- public -------------------------------------------------------------

    def feed(self, chunk):
        events = []
        if not chunk or self.broken or self._depth == 2:
            return events
        self._text += chunk
        try:
            while self._i < len(self._text) and self._depth != 2:
                self._step(self._text[self._i], events)
                self._i += 1
            self._flush_delta(events)
        except Exception as exc:  # noqa: BLE001 -- scanner must never break the LLM call
            logger.debug('PartialJSONScanner broke: %s', exc)
            self.broken = True
        return events

    # -- internals ----------------------------------------------------------

    def _emit_value(self, raw, events):
        try:
            events.append(('value', self._key, json.loads(raw)))
        except ValueError:
            self.broken = True
        self._phase = 'key'
        self._key = None
        self._kind = None

    def _flush_delta(self, events):
        if not (self._phase == 'value' and self._kind == 'str'
                and self._key in self._stream_keys and self._in_str):
            return
        raw = self._text[self._val_start + 1:self._safe_end]
        try:
            decoded = json.loads('"' + raw + '"')
        except ValueError:
            return
        if len(decoded) > self._emitted_len:
            events.append(('delta', self._key, _sanitize(decoded[self._emitted_len:])))
            self._emitted_len = len(decoded)

    def _string_char(self, c, i):
        """Advance string escape state for char c at index i.

        Returns True if c is the closing (unescaped) quote."""
        if self._uni_left:
            self._uni_hex += c
            self._uni_left -= 1
            if self._uni_left == 0:
                try:
                    code = int(self._uni_hex, 16)
                except ValueError:
                    code = 0
                if 0xD800 <= code <= 0xDBFF:
                    self._pending_high = True       # wait for the low surrogate
                else:
                    self._pending_high = False
                    self._safe_end = i + 1
            return False
        if self._esc:
            self._esc = False
            if c == 'u':
                self._uni_left = 4
                self._uni_hex = ''
            else:
                self._safe_end = i + 1
            return False
        if c == '\\':
            self._esc = True
            return False
        if c == '"':
            return True
        if not self._pending_high:
            self._safe_end = i + 1
        return False

    def _step(self, c, events):
        i = self._i
        if self._depth == 0:
            if c == '{':
                self._depth = 1
                self._phase = 'key'
            return

        if self._phase == 'key':
            if self._in_str:
                if self._string_char(c, i):
                    self._in_str = False
                    self._key = ''.join(self._key_chars)
                    self._key_chars = []
                    self._phase = 'colon'
                    events.append(('key', self._key))
                else:
                    self._key_chars.append(c)
            elif c == '"':
                self._in_str = True
                self._key_chars = []
            elif c == '}':
                self._depth = 2
            return

        if self._phase == 'colon':
            if c == ':':
                self._phase = 'value_start'
            return

        if self._phase == 'value_start':
            if c in ' \t\r\n':
                return
            self._val_start = i
            self._phase = 'value'
            if c == '"':
                self._kind = 'str'
                self._in_str = True
                self._esc = False
                self._safe_end = i + 1
                self._emitted_len = 0
                self._pending_high = False
            elif c in '{[':
                self._kind = 'container'
                self._cdepth = 1
            else:
                self._kind = 'scalar'
            return

        # phase == 'value'
        if self._kind == 'str':
            if self._string_char(c, i):
                self._in_str = False
                if self._key in self._stream_keys:
                    # flush the tail (everything before the closing quote)
                    self._safe_end = i
                    self._in_str = True
                    self._flush_delta(events)
                    self._in_str = False
                self._emit_value(self._text[self._val_start:i + 1], events)
            return

        if self._kind == 'container':
            if self._in_str:
                if self._string_char(c, i):
                    self._in_str = False
                return
            if c == '"':
                self._in_str = True
                self._esc = False
            elif c in '{[':
                self._cdepth += 1
            elif c in '}]':
                self._cdepth -= 1
                if self._cdepth == 0:
                    self._emit_value(self._text[self._val_start:i + 1], events)
            return

        # scalar: ends at ',', '}' or whitespace
        if c in ',}' or c in ' \t\r\n':
            self._emit_value(self._text[self._val_start:i], events)
            if c == '}':
                self._depth = 2


class ParseStreamSink:
    """Receives the LLM's raw text deltas; derives early `filters` + `reply` events.

    Callbacks (both optional, exceptions inside them are swallowed):
        on_filters_ready(partial: dict)   once, when filter_priority closes; `partial`
                                          holds the parsed values of filter_priority and
                                          of whichever of filters / filter_delta / image_focus
                                          had already closed (raw model output, un-normalised).
                                          If the callback raises, `filters_emitted` stays
                                          False so the caller can emit the event itself.
        on_reply_delta(text: str)         incremental decoded `reply` text.

    Attributes after / during the stream:
        ttft_ms      ms from mark_start() to the first non-empty delta (None if none)
        filters_ms   ms from mark_start() to the early filters event (None if it
                     never fired -- e.g. non-stream fallback or non-conforming order)
        got_output   True once any delta arrived
        error        set by the streaming call when it raises out (mid-stream failure)
        completed    dict of top-level keys the scanner has seen closed
    """

    def __init__(self, on_filters_ready=None, on_reply_delta=None):
        self._on_filters_ready = on_filters_ready
        self._on_reply_delta = on_reply_delta
        self._scanner = PartialJSONScanner(stream_keys=('reply',))
        self._t0 = None
        self.ttft_ms = None
        self.filters_ms = None
        self.got_output = False
        self.error = None
        self.completed = {}
        self.filters_emitted = False

    def mark_start(self):
        self._t0 = time.perf_counter()

    def _elapsed_ms(self):
        if self._t0 is None:
            return None
        return round((time.perf_counter() - self._t0) * 1000, 2)

    def feed(self, text):
        if not text:
            return
        if not self.got_output:
            self.got_output = True
            self.ttft_ms = self._elapsed_ms()
        for ev in self._scanner.feed(text):
            kind = ev[0]
            if kind == 'value':
                self.completed[ev[1]] = ev[2]
                self._maybe_emit_filters(ev[1])
            elif kind == 'delta' and self._on_reply_delta:
                self._safe_call(self._on_reply_delta, ev[2])

    def _maybe_emit_filters(self, closed_key):
        if self.filters_emitted or closed_key != _FILTER_TRIGGER:
            return
        # Need at least one of filters / filter_delta; resolve_filters_from_partial
        # tolerates the other being absent (follow-up turns may omit `filters`).
        if not any(k in self.completed for k in _FILTER_BODY_KEYS):
            return
        partial = {
            k: self.completed[k] for k in FILTER_TRIO + FILTER_EXTRA_KEYS
            if k in self.completed
        }
        elapsed = self._elapsed_ms()
        if self._on_filters_ready is None:
            self.filters_emitted = True
            self.filters_ms = elapsed
            return
        # Mark emitted only after the callback succeeded: on failure the caller's
        # post-parse fallback must still emit the `filters` event before `final`.
        if self._safe_call(self._on_filters_ready, partial):
            self.filters_emitted = True
            self.filters_ms = elapsed

    @staticmethod
    def _safe_call(fn, arg):
        """Call fn(arg); return True on success, False if it raised (never re-raises)."""
        try:
            fn(arg)
        except Exception as exc:  # noqa: BLE001 -- never break the LLM stream
            logger.warning('ParseStreamSink callback failed: %s: %s', type(exc).__name__, exc)
            return False
        return True
