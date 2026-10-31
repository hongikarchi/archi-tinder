/**
 * useNearViewport — latches true once the element comes within `margin` px of
 * its nearest scrolling ancestor (or the viewport when there is none).
 * Never resets, so callers can lazy-fetch once and keep the result.
 *
 * @param {{current: Element|null}} ref
 * @param {string} [margin]
 * @returns {boolean}
 */

import { useState, useEffect } from 'react'

function scrollParent(el) {
  let p = el?.parentElement
  while (p && p !== document.body) {
    const oy = getComputedStyle(p).overflowY
    if (oy === 'auto' || oy === 'scroll') return p
    p = p.parentElement
  }
  return null
}

export function useNearViewport(ref, margin = '300px') {
  const [near, setNear] = useState(false)
  useEffect(() => {
    if (near) return undefined
    const el = ref.current
    if (!el) return undefined
    if (typeof IntersectionObserver === 'undefined') {
      setNear(true)
      return undefined
    }
    const io = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) {
        setNear(true)
        io.disconnect()
      }
    }, { root: scrollParent(el), rootMargin: margin })
    io.observe(el)
    return () => io.disconnect()
  }, [ref, margin, near])
  return near
}
