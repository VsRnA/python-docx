import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        app: {
          bg: '#f7f6f3',
          panel: '#ffffff',
          border: '#e5e1dc',
          borderStrong: '#d4cec7',
          text: '#171717',
          muted: '#7b7772',
          subtle: '#f1efec',
          shell: '#f1efec',
          accent: '#f36f21',
          accentSoft: '#fff0e6',
          brand: '#f36f21',
          brandHover: '#d95d16',
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
