/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          900: "#071228",
          800: "#0b1730",
          700: "#0f1b2a",
          600: "#16263a",
          accent: "#7c5cff",
          accent2: "#6de2ff",
          panel: "#0f1b2a",
        },
      },
      fontFamily: {
        inter: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl: "14px",
      }
    },
  },
  plugins: [
    // optional: require('@tailwindcss/typography'), etc.
  ],
}
