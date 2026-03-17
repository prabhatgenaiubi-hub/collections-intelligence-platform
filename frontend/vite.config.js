import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [
      'sal-overbashful-jaxton.ngrok-free.dev'
    ]
  }
})



// export default defineConfig({
//   server: {
//     allowedHosts: [
//       'sal-overbashful-jaxton.ngrok-free.dev'
//     ]
//   }
// })