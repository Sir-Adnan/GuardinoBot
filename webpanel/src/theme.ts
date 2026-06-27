import { theme as antdTheme, type ThemeConfig } from "antd";
import type { ColorMode } from "./contexts/color-mode";

// Selectable UI font (loaded in index.html). All fall back to Vazirmatn → system.
export const FONTS: Record<string, string> = {
  vazirmatn: "'Vazirmatn', system-ui, -apple-system, sans-serif",
  vazir: "'Vazir', 'Vazirmatn', system-ui, sans-serif",
  sahel: "'Sahel', 'Vazirmatn', system-ui, sans-serif",
  samim: "'Samim', 'Vazirmatn', system-ui, sans-serif",
  system: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};
export const FONT_KEYS = Object.keys(FONTS);
export const fontFamily = (key: string): string => FONTS[key] ?? FONTS.vazirmatn;

// Translated from the Dashboard-Example-Theme-UI mockup: Vazirmatn UI font,
// rounded corners, dark + light, with a selectable accent palette.
const shared: ThemeConfig["token"] = {
  borderRadius: 10,
  colorSuccess: "#10b981",
  colorError: "#ef4444",
  colorWarning: "#f59e0b",
  colorInfo: "#3b82f6",
};

export type AccentKey = "emerald" | "blue" | "violet" | "rose" | "amber";

// Accent primary per mode (light / dark). Emerald is the default brand colour.
const ACCENTS: Record<AccentKey, { light: string; dark: string }> = {
  emerald: { light: "#059669", dark: "#34d399" },
  blue: { light: "#2563eb", dark: "#60a5fa" },
  violet: { light: "#7c3aed", dark: "#a78bfa" },
  rose: { light: "#e11d48", dark: "#fb7185" },
  amber: { light: "#d97706", dark: "#fbbf24" },
};

export const ACCENT_KEYS = Object.keys(ACCENTS) as AccentKey[];

export function accentColor(accent: string, mode: ColorMode): string {
  const a = (ACCENTS as Record<string, { light: string; dark: string }>)[accent];
  return (a ?? ACCENTS.emerald)[mode];
}

// UI density — "compact" layers AntD's compactAlgorithm for tighter tables/forms.
export type Density = "default" | "compact";

// One-click look presets (accent + mode bundled). Shown in the Appearance menu.
export const PRESETS: { key: string; accent: AccentKey; mode: ColorMode }[] = [
  { key: "emerald_dark", accent: "emerald", mode: "dark" },
  { key: "emerald_light", accent: "emerald", mode: "light" },
  { key: "ocean_dark", accent: "blue", mode: "dark" },
  { key: "violet_dark", accent: "violet", mode: "dark" },
  { key: "rose_light", accent: "rose", mode: "light" },
  { key: "amber_light", accent: "amber", mode: "light" },
];

export function makeTheme(
  accent: string,
  mode: ColorMode,
  font: string = "vazirmatn",
  density: Density = "default",
): ThemeConfig {
  const primary = accentColor(accent, mode);
  const base =
    mode === "dark" ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm;
  return {
    algorithm: density === "compact" ? [base, antdTheme.compactAlgorithm] : base,
    token: {
      ...shared,
      fontFamily: fontFamily(font),
      colorPrimary: primary,
      ...(mode === "dark"
        ? { colorBgLayout: "#13161c", colorBgContainer: "#1b1f27" }
        : { colorBgLayout: "#f6f7f9" }),
    },
  };
}
