module.exports = {
  darkMode: 'class',
  content: [
    './frontend/templates/**/*.html',
    './frontend/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: '#090a0d',
          900: '#12151c',
          850: '#181c26',
          800: '#202633',
          700: '#333c4f',
        },
        violet: {
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
        },
        titanium: {
          100: '#f8fafc',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
        },
      },
    },
  },
  plugins: [],
};
