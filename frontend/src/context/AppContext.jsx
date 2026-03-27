/**
 * context/AppContext.jsx
 * Minimal context placeholder for spec compliance.
 * State management is handled in App.jsx via props.
 */
import { createContext, useContext } from 'react'

export const AppContext = createContext(null)

export function useAppContext() {
  return useContext(AppContext)
}
