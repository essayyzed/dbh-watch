/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        'deep-dark': '#1A1B1E',
        'deep-gray': '#2C2D31',
        'deep-blue': '#4B5EFC'
      },
    },
  },
  plugins: [],
}
