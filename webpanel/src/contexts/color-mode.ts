import { createContext } from "react";

export type ColorMode = "light" | "dark";

export const ColorModeContext = createContext<{
  mode: ColorMode;
  toggle: () => void;
}>({ mode: "dark", toggle: () => {} });
