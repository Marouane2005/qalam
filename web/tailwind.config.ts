import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f3efe6",
        ink: "#1c1915",
        tide: "#0f5e59",
        "tide-deep": "#0c4541",
        seal: "#9d3b24",
        card: "#fffaf3",
        line: "#e3d6c4",
        moss: "#5c6b4a",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "sans-serif"],
        display: ["var(--font-display)", "serif"],
        arabic: ["var(--font-arabic)", "serif"],
      },
      boxShadow: {
        sheet: "0 1px 0 rgba(28,25,21,0.04), 0 18px 40px -28px rgba(28,25,21,0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
