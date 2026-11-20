import { Component } from 'react'
import type { ReactNode } from 'react'

/* ── Error Boundary ─────────────────────────────────────────────────────── */
export default class ErrorBoundary extends Component<{ children?: ReactNode }, { error: unknown }> {
  constructor(props: { children?: ReactNode }) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(e: unknown) { return { error: e } }
  render() {
    if (this.state.error) return (
      <div style={{ color: 'var(--color-text)', padding: 24, background: 'var(--color-bg)', minHeight: '100vh' }}>
        <h2>Something went wrong</h2>
        <pre style={{ color: 'tomato', marginTop: 12, whiteSpace: 'pre-wrap', fontSize: 12 }}>
          {this.state.error.toString()}
        </pre>
      </div>
    )
    return this.props.children
  }
}
