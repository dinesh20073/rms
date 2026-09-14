/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './ems_core/templates/**/*.html',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Roboto', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Arial', 'sans-serif'],
        display: ['Plus Jakarta Sans', 'Roboto', 'sans-serif'],
        mono: ['Roboto Mono', 'monospace'],
      },
      colors: {
        google: {
          blue: '#1a73e8',
          blueHover: '#1557b0',
          blueActive: '#174ea6',
          blueTint: '#e8f0fe',
          blueBorder: '#dadce0',
          green: '#1e8e3e',
          greenDark: '#137333',
          greenTint: '#e6f4ea',
          red: '#d93025',
          redDark: '#c5221f',
          redTint: '#fce8e6',
          yellow: '#f9ab00',
          yellowDark: '#b06000',
          yellowTint: '#fef7e0',
          gray: '#5f6368',
          dark: '#202124',
          border: '#dadce0',
          bg: '#f8f9fa',
        },
        brand: {
          DEFAULT: '#1a73e8',
          hover: '#1557b0',
          active: '#174ea6',
          tint: '#e8f0fe',
          border: '#dadce0',
        }
      }
    }
  },
  plugins: [],
}
