/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ig: {
          background: '#121212',
          surface: '#1e1e1e',
          border: '#2a2a2a',
          text: '#fafafa',
          muted: '#a0a0a0',
          accent: '#0095f6',
        }
      }
    },
  },
  plugins: [],
}
