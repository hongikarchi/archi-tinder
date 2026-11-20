/// <reference types="vite/client" />

declare module '*.module.css' {
  const classes: { readonly [key: string]: string }
  export default classes
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_DEV_LOGIN_SECRET?: string
  readonly VITE_GOOGLE_CLIENT_ID?: string
  readonly VITE_KAKAO_REST_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare const __COMMIT_SHA__: string
