import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // host:true so you can open the dev server from your phone on the same wifi.
  // The Web Speech API needs HTTPS or localhost — on a phone, test against the
  // deployed Vercel URL, not the LAN IP.
  server: { host: true, port: 5173 },
})
