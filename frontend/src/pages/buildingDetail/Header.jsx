import PageBackButton from '../../components/PageBackButton.jsx'

/**
 * Header — back button only (rendered inline via PageTopControls `leading`) (canvas-design-port.md §6d item 6).
 * This component keeps only what every state (LoadingState, ErrorState, and
 * the loaded page) shares: the back button.
 */
export default function Header({ onBack }) {
  return <PageBackButton inline onClick={onBack} label="Back" />
}
