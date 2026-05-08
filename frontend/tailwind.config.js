/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // ADIB deep navy — hero/bg, primary identity
        brand: {
          DEFAULT: '#062F62',
          soft: '#0E4282',
          deep: '#022048',
          tint: '#1E548F',
        },
        // ADIB bright sky blue — the iconic mid-blue used in the menu bar / login button
        adib: {
          DEFAULT: '#009CDA',
          soft: '#4DBAE7',
          deep: '#0078A8',
          glow: '#9DDBF0',
        },
        // Gold accent (sparingly used)
        gold: {
          DEFAULT: '#C9A961',
          soft: '#E5D0A0',
          deep: '#A88840',
          glow: '#F4E5BD',
        },
        cream: {
          DEFAULT: '#F8FBFE',
          soft: '#FFFFFF',
          deeper: '#E8F2FA',
          frame: '#F1F6FB',
          border: '#D8E5EE',
          edge: '#BFD3E2',
        },
        ink: {
          DEFAULT: '#0F1B2D',
          muted: '#5A6776',
          faint: '#94A2B0',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        serif: ['Fraunces', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        caretPulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.25' },
        },
      },
      animation: {
        fadeIn: 'fadeIn 0.4s ease-out forwards',
        slideIn: 'slideIn 0.25s ease-out forwards',
        caretPulse: 'caretPulse 1s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
