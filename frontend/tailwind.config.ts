import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#05070f",
          900: "#080d1a",
          800: "#0d1526",
          750: "#101b30",
          700: "#132038",
          600: "#1a2d4d",
          500: "#1e3a63",
          400: "#2952a3",
        },
        slate: {
          950: "#080c14",
          900: "#0f172a",
          850: "#131e33",
          800: "#1e293b",
          750: "#243044",
          700: "#334155",
          600: "#475569",
          500: "#64748b",
          400: "#94a3b8",
          300: "#cbd5e1",
          200: "#e2e8f0",
          100: "#f1f5f9",
        },
        accent: {
          DEFAULT: "#6366f1",
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        cyan: {
          DEFAULT: "#22d3ee",
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
        },
        emerald: {
          DEFAULT: "#10b981",
          400: "#34d399",
          500: "#10b981",
        },
        amber: {
          DEFAULT: "#f59e0b",
          400: "#fbbf24",
          500: "#f59e0b",
        },
        rose: {
          DEFAULT: "#f43f5e",
          400: "#fb7185",
          500: "#f43f5e",
        },
        surface: {
          DEFAULT: "#0d1526",
          elevated: "#132038",
          overlay: "#1a2d4d",
        },
        border: {
          DEFAULT: "rgba(99,102,241,0.15)",
          subtle: "rgba(99,102,241,0.08)",
          strong: "rgba(99,102,241,0.3)",
        },
      },
      fontFamily: {
        sans: ["Inter var", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "mesh-gradient":
          "radial-gradient(at 40% 20%, hsla(228,100%,74%,0.08) 0px, transparent 50%), radial-gradient(at 80% 0%, hsla(189,100%,56%,0.06) 0px, transparent 50%), radial-gradient(at 0% 50%, hsla(355,100%,93%,0.04) 0px, transparent 50%)",
        "accent-glow": "radial-gradient(ellipse at top, rgba(99,102,241,0.15), transparent 70%)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "ping-slow": "ping 2s cubic-bezier(0, 0, 0.2, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-in-out",
        "slide-up": "slideUp 0.3s ease-out",
        "slide-in": "slideIn 0.3s ease-out",
        "typing": "typing 1.4s infinite",
        "waveform": "waveform 0.8s ease-in-out infinite alternate",
        "glow": "glow 2s ease-in-out infinite alternate",
        "spin-slow": "spin 3s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        slideIn: {
          "0%": { transform: "translateX(-10px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        typing: {
          "0%, 60%, 100%": { opacity: "0.2", transform: "scale(0.85)" },
          "30%": { opacity: "1", transform: "scale(1)" },
        },
        waveform: {
          "0%": { height: "4px" },
          "100%": { height: "32px" },
        },
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(99,102,241,0.3)" },
          "100%": { boxShadow: "0 0 20px rgba(99,102,241,0.7), 0 0 40px rgba(99,102,241,0.3)" },
        },
      },
      boxShadow: {
        "glow-accent": "0 0 20px rgba(99,102,241,0.4)",
        "glow-cyan": "0 0 20px rgba(34,211,238,0.4)",
        "glow-emerald": "0 0 20px rgba(16,185,129,0.4)",
        "inner-glow": "inset 0 0 30px rgba(99,102,241,0.05)",
        "card": "0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3)",
        "card-hover": "0 10px 15px -3px rgba(0,0,0,0.5), 0 4px 6px -4px rgba(0,0,0,0.4)",
      },
      borderRadius: {
        "xl": "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
