/** Colours and fonts from the original NEON//CORE design. */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#04070d',
        panel: '#080d16',
        panel2: '#0b121e',
        line: '#193142',
        cyan: '#00f6ff',
        pink: '#ff2bd6',
        lime: '#75ff68',
        danger: '#ff416c',
        amber: '#ffd66b',
        ink: '#dcecff',
        muted: '#7d95a6',
      },
      fontFamily: {
        display: ['Orbitron', 'system-ui', 'sans-serif'],
        sans: ['Rajdhani', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 24px rgba(0, 246, 255, 0.08)',
      },
    },
  },
  plugins: [],
};
