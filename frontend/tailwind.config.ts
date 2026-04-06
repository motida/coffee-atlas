import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        coffee: {
          50: "#fdf8f0",
          100: "#f9edd9",
          200: "#f2d8b0",
          300: "#e9bd7e",
          400: "#df9c4b",
          500: "#d4832d",
          600: "#b86a22",
          700: "#95521f",
          800: "#7a4320",
          900: "#65381d",
        },
      },
    },
  },
  plugins: [],
};

export default config;
