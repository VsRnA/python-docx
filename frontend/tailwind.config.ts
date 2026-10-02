import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        app: {
          bg: '#f6f7f9',
          panel: '#ffffff',
          border: '#d9dde3',
          borderStrong: '#c7ced8',
          text: '#20242a',
          muted: '#68717b',
          subtle: '#f1f3f6',
          accent: '#2464c5',
          brand: '#f47720',
          brandHover: '#dc6413',
          danger: '#a61b1b',
          dangerBg: '#fff0f0',
          success: '#247a45',
          warning: '#a35f00',
        },
      },
      borderRadius: {
        control: '6px',
        panel: '8px',
      },
      boxShadow: {
        control: '0 1px 3px rgb(15 23 42 / 12%)',
        page: '0 2px 10px rgb(0 0 0 / 14%)',
        popover: '0 10px 28px rgb(30 38 48 / 16%)',
      },
      spacing: {
        toolbar: '44px',
        panel: '360px',
      },
    },
  },
  plugins: [],
} satisfies Config
