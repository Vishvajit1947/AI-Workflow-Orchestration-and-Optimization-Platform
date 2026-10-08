/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // Supabase-inspired palette (see DESIGN.md): emerald brand + neutral greys
      colors: {
        primary: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#3ecf8e', // brand emerald
          500: '#24b47e', // emerald deep
          600: '#006239', // filled button (dashboard style, white text)
          700: '#004d2d',
          800: '#003a22',
          900: '#00291a',
          950: '#001a10',
        },
        surface: {
          50: '#fafafa',
          100: '#efefef',
          200: '#ededed',
          700: '#2e2e2e',
          800: '#1c1c1c',
          900: '#121212',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
