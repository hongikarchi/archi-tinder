// Exit direction of an answered assessment card. Follows the RAW Likert value
// of the tapped option (not the stored/reversed score): agree-side and neutral
// (>= 0) leave right, disagree-side (< 0) leave left.
export function exitDirectionForRaw(rawValue) {
  return rawValue >= 0 ? 'right' : 'left'
}

// Recover the raw tapped value from a stored response (reversal is its own inverse).
export function rawFromStored(stored, reversed) {
  return reversed ? stored * -1 : stored
}
