/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_API_TIMEOUT_MS: string
  readonly VITE_AI_REQUEST_TIMEOUT_MS: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
