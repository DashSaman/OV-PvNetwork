/* global process */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import dotenv from 'dotenv'
import path from 'path'
const __dirname = import.meta.dirname;

// Load .env from the project root
dotenv.config({ path: path.resolve(__dirname, '../.env') })

const urlPath = process.env.URLPATH || 'panel'
const outDir = process.env.PVNETWORK_BUILD_OUTDIR || 'dist'

export default defineConfig({
  plugins: [react()],
  base: `/${urlPath}/`,
  build: {
    outDir,
    rollupOptions: {
      output: {
        // Keep the patched HTTP client within the existing per-chunk budget.
        manualChunks: { 'http-client': ['axios'], 'react-runtime': ['react', 'react-dom', 'react-dom/client'] },
      },
    },
  },
})
