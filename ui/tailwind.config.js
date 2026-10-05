/** @type {import('tailwindcss').Config} */

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // High-end dark/light theme palette
        slate: {
          850: "#172033",
          900: "#0F172A",
          925: "#0B1120",
          950: "#070D1B",
        },
        brand: {
          50: "#EEF2FF",
          100: "#E0E7FF",
          200: "#C7D2FE",
          300: "#A5B4FC",
          400: "#818CF8",
          500: "#6366F1", // Indigo core
          600: "#4F46E5",
          700: "#4338CA",
          800: "#3730A3",
          900: "#312E81",
        },
        teal: {
          glow: "#14B8A6",
          dark: "#042F2E",
        },
        rose: {
          glow: "#F43F5E",
          dark: "#4C0519",
        },
        amber: {
          glow: "#F59E0B",
          dark: "#451A03",
        },
        cyan: {
          glow: "#06B6D4",
          dark: "#083344",
        },
        // Clinical UI tokens
        paper: "#F8FAFC",
        card: "#FFFFFF",
        ink: "#0F172A",
        muted: "#64748B",
        rule: "#E2E8F0",
        sidebar: "#0B1120",

        // Semantic clinical states
        shown: "#0D9488",
        "shown-bg": "#F0FDFA",
        "shown-border": "#99F6E4",

        withheld: "#D97706",
        "withheld-bg": "#FFFBEB",
        "withheld-border": "#FDE68A",

        escalate: "#E11D48",
        "escalate-bg": "#FFF1F2",
        "escalate-border": "#FECDD3",

        clinical: "#4F46E5",
        "clinical-light": "#EEF2FF",
        "clinical-border": "#C7D2FE",
      },
      fontFamily: {
        sans: [
          "'Plus Jakarta Sans'",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "'JetBrains Mono'",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      fontSize: {
        micro: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.06em" }],
        compact: ["0.8125rem", { lineHeight: "1.25rem" }],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(15, 23, 42, 0.05), 0 1px 2px -1px rgba(15, 23, 42, 0.05)",
        float: "0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)",
        glow: "0 0 20px -3px rgba(99, 102, 241, 0.25)",
        "glow-emerald": "0 0 20px -3px rgba(16, 185, 129, 0.25)",
        "glow-rose": "0 0 20px -3px rgba(244, 63, 94, 0.25)",
        "glow-amber": "0 0 20px -3px rgba(245, 158, 11, 0.25)",
        "glow-cyan": "0 0 20px -3px rgba(6, 182, 212, 0.25)",
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "mesh-dark": "radial-gradient(at 100% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%), radial-gradient(at 0% 100%, rgba(13, 148, 136, 0.08) 0px, transparent 50%)",
        "mesh-light": "radial-gradient(at 100% 0%, rgba(238, 242, 255, 0.8) 0px, transparent 50%), radial-gradient(at 0% 100%, rgba(240, 253, 250, 0.8) 0px, transparent 50%)",
      },
    },
  },
  plugins: [],
};
