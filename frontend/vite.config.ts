import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'

const frontendRoot = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  root: frontendRoot,
  test: {
    environment: 'jsdom',
    setupFiles: fileURLToPath(new URL('./src/test-setup.ts', import.meta.url)),
  },
})
