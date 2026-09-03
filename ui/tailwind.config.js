/** @type {import('tailwindcss').Config} */

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Clinical theme colors with rich contrast and real-world EHR aesthetics
        paper: "#F4F7F9",
        card: "#FFFFFF",
        ink: "#0F172A",
        muted: "#475569",
        rule: "#E2E8F0",
        sidebar: "#0F172A",

        // Semantic clinical states
        shown: "#0D9488", // Teal 600 - disclosed under active consent
        "shown-bg": "#F0FDFA",
        "shown-border": "#99F6E4",

        withheld: "#D97706", // Amber 600 - withheld boundary
        "withheld-bg": "#FFFBEB",
        "withheld-border": "#FDE68A",

        escalate: "#E11D48", // Rose 600 - safety critical / red flags
        "escalate-bg": "#FFF1F2",
        "escalate-border": "#FECDD3",

        clinical: "#1E40AF", // Blue 800 - clinical structural accent
        "clinical-light": "#EFF6FF",
        "clinical-border": "#BFDBFE",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      fontSize: {
        micro: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.05em" }],
        compact: ["0.8125rem", { lineHeight: "1.25rem" }],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.06)",
        dropdown: "0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.03)",
        glow: "0 0 15px rgba(30, 64, 175, 0.15)",
        "glow-red": "0 0 12px rgba(225, 29, 72, 0.25)",
      },
    },
  },
  plugins: [],
};
