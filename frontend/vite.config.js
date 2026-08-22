import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // Bind every interface, not just localhost, so a device on the same
    // Tailscale tailnet can reach this dev server at the Mac's Tailscale
    // address. allowedHosts is wide open rather than an explicit allowlist
    // because Tailscale itself is the actual security boundary here - only
    // devices already on this private tailnet can route to this port at all.
    host: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        ws: true,
      },
      '/static': 'http://127.0.0.1:5001',
    },
  },
})
