import type { Config } from 'tailwindcss';

// 🆕 NEW DECISION (2026-09-22): Design system resolved
// This replaces the placeholder tokens from ui-context.md with a complete
// design system fit for a document-trust product. See design spec for rationale.
const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Primary palette (trust/authority)
        primary: {
          DEFAULT: '#1d4ed8', // blue-700
          hover: '#1e40af',   // blue-800
          50: '#eff6ff',
          100: '#dbeafe',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
        },
        // Risk levels (WCAG-compliant with icon patterns, not color-only)
        risk: {
          low: {
            DEFAULT: '#16a34a',    // green-600
            bg: '#f0fdf4',         // green-50
            border: '#16a34a',
          },
          medium: {
            DEFAULT: '#d97706',    // amber-600
            bg: '#fffbeb',         // amber-50
            border: '#d97706',
          },
          high: {
            DEFAULT: '#dc2626',    // red-600
            bg: '#fef2f2',         // red-50
            border: '#dc2626',
          },
        },
        // Materiality levels (pattern + border + weight variation)
        materiality: {
          none: {
            DEFAULT: '#6b7280',    // gray-500
            bg: '#f3f4f6',         // gray-100
            border: '#6b7280',
          },
          minor: {
            DEFAULT: '#2563eb',    // blue-600
            bg: '#eff6ff',         // blue-50
            border: '#2563eb',
          },
          significant: {
            DEFAULT: '#d97706',    // amber-600
            bg: '#fef3c7',         // amber-100
            border: '#d97706',
          },
          critical: {
            DEFAULT: '#dc2626',    // red-600
            bg: '#fee2e2',         // red-100
            border: '#dc2626',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'display': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.02em', fontWeight: '700' }],
        'title': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.01em', fontWeight: '600' }],
        'heading': ['1.125rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        'body': ['1rem', { lineHeight: '1.5rem', fontWeight: '400' }],
        'body-sm': ['0.875rem', { lineHeight: '1.25rem', fontWeight: '400' }],
        'caption': ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.01em', fontWeight: '500' }],
      },
      spacing: {
        'xs': '0.25rem',    // 4px
        'sm': '0.5rem',     // 8px
        'md': '1rem',       // 16px
        'lg': '1.5rem',     // 24px
        'xl': '2rem',       // 32px
        '2xl': '3rem',      // 48px
      },
      borderRadius: {
        'sm': '4px',
        'md': '8px',
        'lg': '12px',
      },
      boxShadow: {
        'sm': '0 1px 2px rgba(0, 0, 0, 0.05)',
        'md': '0 4px 6px rgba(0, 0, 0, 0.07)',
        'lg': '0 10px 15px rgba(0, 0, 0, 0.1)',
      },
    },
  },
  plugins: [],
};

export default config;
