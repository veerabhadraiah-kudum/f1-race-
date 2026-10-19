/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        f1red: "#E10600",
        carbon: "#0F0F0F",
        pitwall: "#1A1A1A",
      }
    }
  },
  plugins: []
}
