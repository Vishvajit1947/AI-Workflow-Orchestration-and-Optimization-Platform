/** @type {import('tailwindcss').Config} */
// Mercury design system (see DESIGN.md): a night-violet frame around a pale light canvas,
// one indigo action colour, translucent secondary pills, soft 12px cards and light type weights.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Mercury Indigo, the single saturated action colour
        primary: {
          DEFAULT: '#5266eb',
          50: '#f3f4fe',
          100: '#e7e9fd',
          200: '#cfd4fa',
          300: '#aab4f5',
          400: '#7d8cf0',
          500: '#5266eb',
          600: '#4355d8',
          700: '#3745b3',
          800: '#2e3a8e',
          900: '#272f6f',
        },
        periwinkle: '#9cb4e8',
        canvas: '#fbfcfd',
        surface: { DEFAULT: '#ffffff', tint: '#fbfbff' },
        lavender: { DEFAULT: '#edecfb', soft: '#f5f5fd' },
        night: { DEFAULT: '#171721', raised: '#1e1e2a', line: '#2d2d3c' },
        ink: {
          DEFAULT: '#28253b',
          secondary: '#554e7b',
          muted: '#6f6a8a',   // 5:1 on white; captions and meta text
          faint: '#9a97ad',   // decorative only (icons, placeholders)
        },
        'on-dark': '#ededf3',
        fog: '#c3c3cc',
        slate: '#70707d',
        hairline: { DEFAULT: '#e8e7f0', strong: '#d9d8e5' },
        // State colours: product content only (badges, logs, graph nodes), never chrome
        success: { DEFAULT: '#1d7f55', soft: '#e9f5ef', line: '#a9d8c1' },
        warning: { DEFAULT: '#9a5b0b', soft: '#fdf4e4', line: '#efcf96' },
        danger: { DEFAULT: '#c0392b', soft: '#fcecea', line: '#f1b8b0' },
        info: { DEFAULT: '#3745b3', soft: '#eef0fd', line: '#cfd4fa' },
      },
      fontFamily: {
        // arcadia / arcadiaDisplay are proprietary; Inter variable is the documented substitute
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
      fontWeight: {
        // Mercury never goes above 500: hierarchy comes from size and colour
        light: '360',
        normal: '400',
        book: '420',
        medium: '480',
        semibold: '500',
        bold: '500',
      },
      fontSize: {
        eyebrow: ['12px', { lineHeight: '1', letterSpacing: '0.06em' }],
        legal: ['12px', { lineHeight: '1.4', letterSpacing: '0.02em' }],
        'heading-2': ['28px', { lineHeight: '1.2', letterSpacing: '0.015em' }],
        lead: ['22px', { lineHeight: '1.25', letterSpacing: '0.02em' }],
        stat: ['30px', { lineHeight: '1.1', letterSpacing: '0.01em' }],
        display: ['40px', { lineHeight: '1.1', letterSpacing: '0.01em' }],
      },
      borderRadius: {
        xs: '4px',
        card: '12px',
        panel: '16px',
        pill: '40px',
      },
      boxShadow: {
        // Elevation is tonal; these are the hair-thin stacks the spec allows
        soft: '0 1px 2px rgba(40, 37, 59, 0.04), 0 2px 8px rgba(40, 37, 59, 0.04)',
        pop: '0 2px 6px rgba(23, 23, 33, 0.06), 0 16px 48px rgba(23, 23, 33, 0.14)',
      },
      maxWidth: {
        content: '1200px',
      },
      // Motion (see src/lib/motion.ts): curves measured on mercury.com
      transitionTimingFunction: {
        mercury: 'cubic-bezier(0.16, 0, 0.13, 1)',  // entrances, reveals, settling
        standard: 'cubic-bezier(0.4, 0, 0.2, 1)',  // state changes
        soft: 'cubic-bezier(0, 0, 0.2, 1)',        // hover colour shifts
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'fade-in-up': { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
        'pop-in': { from: { opacity: '0', transform: 'translateY(4px) scale(0.98)' }, to: { opacity: '1', transform: 'none' } },
        'grow-y': { from: { transform: 'scaleY(0)' }, to: { transform: 'scaleY(1)' } },
        'grow-x': { from: { transform: 'scaleX(0)' }, to: { transform: 'scaleX(1)' } },
        // stroke drawn along the path: pair with pathLength="1" and stroke-dasharray: 1
        draw: { from: { strokeDashoffset: '1' }, to: { strokeDashoffset: '0' } },
        'pulse-ring': { '0%': { opacity: '0.55', transform: 'scale(1)' }, '100%': { opacity: '0', transform: 'scale(1.09)' } },
        'flash-ring': { '0%': { opacity: '0.8', transform: 'scale(1)' }, '100%': { opacity: '0', transform: 'scale(1.14)' } },
        sheen: { from: { transform: 'translateX(-100%)' }, to: { transform: 'translateX(250%)' } },
        'flow-dash': { from: { strokeDashoffset: '20' }, to: { strokeDashoffset: '0' } },
      },
      animation: {
        'fade-in': 'fade-in 0.3s cubic-bezier(0.16, 0, 0.13, 1) both',
        'fade-in-up': 'fade-in-up 0.45s cubic-bezier(0.16, 0, 0.13, 1) both',
        'pop-in': 'pop-in 0.2s cubic-bezier(0.16, 0, 0.13, 1) both',
        'grow-y': 'grow-y 0.7s cubic-bezier(0.16, 0, 0.13, 1) both',
        'grow-x': 'grow-x 0.8s cubic-bezier(0.16, 0, 0.13, 1) both',
        draw: 'draw 1.1s cubic-bezier(0.16, 0, 0.13, 1) both',
        'pulse-ring': 'pulse-ring 1.8s cubic-bezier(0, 0, 0.2, 1) infinite',
        'flash-ring': 'flash-ring 0.9s cubic-bezier(0.16, 0, 0.13, 1) both',
        sheen: 'sheen 1.8s cubic-bezier(0.4, 0, 0.2, 1) infinite',
        'flow-dash': 'flow-dash 0.8s linear infinite',
      },
    },
  },
  plugins: [],
}
