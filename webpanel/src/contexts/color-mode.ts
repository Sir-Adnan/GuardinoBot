import { createContext } from "react";

export type ColorMode = "light" | "dark";

export const ColorModeContext = createContext<{
  mode: ColorMode;
  toggle: () => void;
  accent: string;
  setAccent: (a: string) => void;
}>({ mode: "dark", toggle: () => {}, accent: "emerald", setAccent: () => {} });
