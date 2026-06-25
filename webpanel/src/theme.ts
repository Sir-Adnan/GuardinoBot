import { theme as antdTheme, type ThemeConfig } from "antd";

// Translated from the Dashboard-Example-Theme-UI mockup: emerald accent,
// Vazirmatn UI font, rounded corners, dark + light. (oklch → nearest hex.)
const shared: ThemeConfig["token"] = {
  fontFamily: "'Vazirmatn', system-ui, -apple-system, sans-serif",
  borderRadius: 10,
  colorSuccess: "#10b981",
  colorError: "#ef4444",
  colorWarning: "#f59e0b",
  colorInfo: "#3b82f6",
};

export const lightTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    ...shared,
    colorPrimary: "#059669",
    colorBgLayout: "#f6f7f9",
  },
};

export const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    ...shared,
    colorPrimary: "#34d399",
    colorBgLayout: "#13161c",
    colorBgContainer: "#1b1f27",
  },
};
