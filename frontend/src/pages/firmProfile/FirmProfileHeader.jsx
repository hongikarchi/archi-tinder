import { useNavigate } from 'react-router-dom'
import PageBackButton from '../../components/PageBackButton.jsx'

/**
 * FirmProfileHeader — floating back button only (canvas-design-port.md §6d
 * item 6). The old sticky "back left · title center · placeholder right" bar
 * is gone; office.html shows no title in this slot at all (straight from the
 * floating back button into the profile hero below), so the static "Profile"
 * label is dropped, not relocated.
 */
export default function FirmProfileHeader() {
  const navigate = useNavigate()

  return <PageBackButton onClick={() => navigate(-1)} label="Go back" />
}
