/* global process */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import dotenv from 'dotenv'
import path from 'path'
const __dirname = import.meta.dirname;

// Load .env from the project root
dotenv.config({ path: path.resolve(__dirname, '../.env'), override: true })

const urlPath = process.env.URLPATH || 'panel'

export default defineConfig({
  plugins: [react()],
  base: `/${urlPath}/`,
  build: {
    outDir: 'dist',
  },
})
