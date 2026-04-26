/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#0F1B2D',
        panel: '#1A2B42',
        card: '#1E3352',
        accent: '#2E7CF6',
        success: '#22C55E',
        warning: '#F59E0B',
        critical: '#EF4444',
        textPrimary: '#F0F4FF',
        textSecondary: '#94A3B8',
        borderTone: '#2A3F5F',
      },
      boxShadow: {
        critical: '0 0 20px rgba(239,68,68,0.3)',
      },
      transitionDuration: {
        200: '200ms',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['Courier New', 'monospace'],
      },
      keyframes: {
        pulseSoft: {
          '0%': { transform: 'scale(1)', opacity: '0.85' },
          '50%': { transform: 'scale(1.25)', opacity: '0.2' },
          '100%': { transform: 'scale(1)', opacity: '0.85' },
        },
        blink: {
          '0%, 50%': { opacity: '1' },
          '51%, 100%': { opacity: '0.2' },
        },
        slideFadeIn: {
          '0%': { transform: 'translateY(-8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        pulseSoft: 'pulseSoft 1.5s infinite',
        blink: 'blink 1s infinite',
        slideFadeIn: 'slideFadeIn 200ms ease',
      },
    },
  },
  plugins: [],
};
