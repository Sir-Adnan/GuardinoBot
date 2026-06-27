import { createContext } from "react";

export type ColorMode = "light" | "dark";
export type Calendar = "jalali" | "gregorian";
export type Density = "default" | "compact";

export const ColorModeContext = createContext<{
  mode: ColorMode;
  toggle: () => void;
  setMode: (m: ColorMode) => void;
  accent: string;
  setAccent: (a: string) => void;
  calendar: Calendar;
  setCalendar: (c: Calendar) => void;
  font: string;
  setFont: (f: string) => void;
  density: Density;
  setDensity: (d: Density) => void;
}>({
  mode: "dark",
  toggle: () => {},
  setMode: () => {},
  accent: "emerald",
  setAccent: () => {},
  calendar: "jalali",
  setCalendar: () => {},
  font: "vazirmatn",
  setFont: () => {},
  density: "default",
  setDensity: () => {},
});
