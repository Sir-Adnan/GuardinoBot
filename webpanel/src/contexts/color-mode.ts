import { createContext } from "react";

export type ColorMode = "light" | "dark";
export type Calendar = "jalali" | "gregorian";

export const ColorModeContext = createContext<{
  mode: ColorMode;
  toggle: () => void;
  accent: string;
  setAccent: (a: string) => void;
  calendar: Calendar;
  setCalendar: (c: Calendar) => void;
  font: string;
  setFont: (f: string) => void;
}>({
  mode: "dark",
  toggle: () => {},
  accent: "emerald",
  setAccent: () => {},
  calendar: "jalali",
  setCalendar: () => {},
  font: "vazirmatn",
  setFont: () => {},
});
