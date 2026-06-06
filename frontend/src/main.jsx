import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { BrowserRouter } from 'react-router-dom'
import './tokens.css'
import './index.css'
import { ThemeProvider } from './context/ThemeContext.jsx'
import { LanguageProvider } from './context/LanguageContext.jsx'
import App from './App.jsx'

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID

// Conditional provider mount — if VITE_GOOGLE_CLIENT_ID is empty or unset,
// render App directly (no GoogleOAuthProvider wrapper, no literal fallback string).
// If set, wrap with GoogleOAuthProvider so @react-oauth/google hooks work.
const tree = (
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <LanguageProvider>
          <App />
        </LanguageProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>
)

createRoot(document.getElementById('root')).render(
  clientId
    ? <GoogleOAuthProvider clientId={clientId}>{tree}</GoogleOAuthProvider>
    : tree
)
