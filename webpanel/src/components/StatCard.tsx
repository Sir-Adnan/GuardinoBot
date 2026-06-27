import { useContext } from "react";
import type { CSSProperties, ReactNode } from "react";
import { theme } from "antd";
import { ColorModeContext } from "../contexts/color-mode";

/**
 * Polished, cohesive KPI card (dashboard + reports + lists). Hover lifts the card,
 * highlights the border + icon chip in the **theme accent**, and the value uses
 * the INHERITED (configured) font with tabular-nums. Styling lives in index.css
 * (.stat-card / .stat-icon); colours come in via CSS variables so :hover works.
 */
export function StatCard({
  label,
  value,
  icon,
  sub,
}: {
  label: ReactNode;
  value: ReactNode;
  icon?: ReactNode;
  sub?: ReactNode;
}) {
  const { token } = theme.useToken();
  const { mode } = useContext(ColorModeContext);
  const vars = {
    "--sc-bg": token.colorBgContainer,
    "--sc-border": token.colorBorderSecondary,
    "--sc-chip-bg": token.colorFillTertiary,
    "--sc-chip-fg": token.colorTextSecondary,
    "--sc-accent": token.colorPrimary,
    "--sc-shadow": mode === "dark" ? "0 1px 3px rgba(0,0,0,.4)" : "0 1px 3px rgba(16,24,40,.06)",
    "--sc-shadow-hover": mode === "dark" ? "0 14px 30px rgba(0,0,0,.5)" : "0 14px 30px rgba(16,24,40,.13)",
  } as CSSProperties;

  return (
    <div className="stat-card" style={vars}>
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        {icon && <span className="stat-icon">{icon}</span>}
        <span style={{ color: token.colorTextSecondary, fontSize: 12.5, fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontWeight: 700, fontSize: 21, lineHeight: 1.1, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em" }}>
        {value}
      </div>
      {sub != null && <div style={{ color: token.colorTextTertiary, fontSize: 11.5, marginTop: -6 }}>{sub}</div>}
    </div>
  );
}
