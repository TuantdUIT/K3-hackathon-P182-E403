/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef4ff',
          100: '#dbe6ff',
          200: '#bed0ff',
          300: '#91b0ff',
          400: '#5d84fb',
          500: '#3759f0',
          600: '#2039d8',
          700: '#1b2ead',
          800: '#1b2b8a',
          900: '#1c2a6d',
          950: '#141c42',
        },
        ink: {
          900: '#0b1020',
          800: '#141a2e',
          700: '#1e2740',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        lift: '0 20px 45px -20px rgba(16, 24, 64, 0.35)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.45s ease-out both',
      },
      zIndex: {
        200: '200',
      },
    },
  },
  plugins: [],
};
