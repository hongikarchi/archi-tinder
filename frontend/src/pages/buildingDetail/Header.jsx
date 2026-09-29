import PageBackButton from '../../components/PageBackButton.jsx'

/**
 * Header — floating back button only (canvas-design-port.md §6d item 6).
 * The old sticky bar (back button + save-to-board pill + bookmark toggle) is
 * gone; building-detail.html shows the save/bookmark cluster relocated to
 * sit beside the page's own <h1> instead (BuildingDetailPage.jsx owns that
 * row now). This component keeps only what every state (LoadingState,
 * ErrorState, and the loaded page) shares: the back button.
 */
export default function Header({ onBack }) {
  return <PageBackButton onClick={onBack} label="Back" />
}
