/**
 * CalibrationChat.jsx
 * Shown during the 'chat_initializing' phase of a swipe session.
 *
 * Layout (top → bottom):
 *   1. Priority badges — extracted_metadata priority_ordered + program
 *   2. AI message bubble — llm_response_message
 *   3. Quick-reply chips — suggested_quick_replies (horizontal scroll)
 *   4. Free-text input bar + send button
 *
 * Interactions:
 *   - Chip click → calls onCalibrate(chipText) immediately
 *   - Send button / Enter → calls onCalibrate(inputText)
 *
 * Design: DESIGN.md §4 (tokens + CSS Modules + inline for layout/dynamic)
 */

import { useState, useRef, useEffect } from 'react'
import s from './CalibrationChat.module.css'

/* ── Priority badge strip ────────────────────────────────────────────────── */
function PriorityBadges({ extractedMetadata }) {
  if (!extractedMetadata) return null

  const items = []

  // priority_ordered is the primary source (spec priority_ordered field)
  const ordered = extractedMetadata.priority_ordered
  if (Array.isArray(ordered) && ordered.length > 0) {
    ordered.slice(0, 4).forEach(label => {
      if (label) items.push(String(label))
    })
  } else {
    // Fallback: surface individual fields
    if (extractedMetadata.program)            items.push(extractedMetadata.program)
    if (extractedMetadata.style)              items.push(extractedMetadata.style)
    if (extractedMetadata.atmosphere)         items.push(extractedMetadata.atmosphere)
    if (extractedMetadata.typology_primary)   items.push(extractedMetadata.typology_primary)
    if (extractedMetadata.location_country)   items.push(extractedMetadata.location_country)
  }

  if (items.length === 0) return null

  return (
    <div className={s.badgesRow} role="list" aria-label="Extracted taste priorities">
      {items.map((label, i) => (
        <span key={`${label}_${i}`} className={s.priorityBadge} role="listitem">
          {i === 0 ? '★ ' : ''}{label}
        </span>
      ))}
    </div>
  )
}

/* ── Typing indicator ────────────────────────────────────────────────────── */
function TypingIndicator() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 4,
      padding: '10px 14px',
      background: 'var(--color-ai-bubble)',
      border: '1px solid var(--color-ai-bubble-border)',
      borderRadius: 'var(--radius-lg)',
      borderBottomLeftRadius: 'var(--radius-sm)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      width: 'fit-content',
    }}>
      <span className={s.typingDot} />
      <span className={s.typingDot} />
      <span className={s.typingDot} />
    </div>
  )
}

/* ── CalibrationChat ─────────────────────────────────────────────────────── */
export default function CalibrationChat({
  llmMessage,
  quickReplies = [],
  extractedMetadata = null,
  onCalibrate,
  isLoading = false,
}) {
  const [inputText, setInputText]   = useState('')
  const inputRef                    = useRef(null)

  // Auto-focus the input when the component mounts or llmMessage changes
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus()
    }
  }, [isLoading, llmMessage])

  function handleSend() {
    const msg = inputText.trim()
    if (!msg || isLoading) return
    setInputText('')
    onCalibrate(msg)
  }

  function handleChipClick(text) {
    if (isLoading) return
    onCalibrate(text)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className={s.container}>
      {/* Scrollable chat area — grows to fill space */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 8 }}>

        {/* Priority badges — live updates as the LLM extracts metadata */}
        {extractedMetadata && (
          <PriorityBadges extractedMetadata={extractedMetadata} />
        )}

        {/* AI message bubble or typing indicator */}
        {isLoading ? (
          <TypingIndicator />
        ) : llmMessage ? (
          <div className={s.bubble} role="status" aria-live="polite">
            {llmMessage}
          </div>
        ) : null}

        {/* Quick reply chips */}
        {!isLoading && quickReplies.length > 0 && (
          <div
            className={s.quickRepliesWrapper}
            role="group"
            aria-label="Quick reply options"
          >
            {quickReplies.map((reply, i) => (
              <button
                key={`${reply}_${i}`}
                className={s.chip}
                onClick={() => handleChipClick(reply)}
                disabled={isLoading}
                aria-label={`Quick reply: ${reply}`}
              >
                {reply}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Input bar — fixed at bottom of the chat area */}
      <div className={s.inputBar}>
        <input
          ref={inputRef}
          className={s.input}
          type="text"
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="건축 취향을 자유롭게 입력하세요…"
          disabled={isLoading}
          aria-label="Calibration message input"
        />
        <button
          className={s.sendBtn}
          onClick={handleSend}
          disabled={!inputText.trim() || isLoading}
          aria-label="Send message"
        >
          {/* Up-arrow send icon */}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2.5"
               strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="19" x2="12" y2="5" />
            <polyline points="5 12 12 5 19 12" />
          </svg>
        </button>
      </div>
    </div>
  )
}
