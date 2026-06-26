import type { ReactNode } from "react";
import { theme } from "antd";

/**
 * Polished KPI card used on the dashboard + reports. The value uses the INHERITED
 * (configured) app font — not a hard-coded mono — with tabular-nums for aligned
 * digits, so changing the font in the header applies here too.
 */
export function StatCard({
  label,
  value,
  icon,
  color,
  sub,
}: {
  label: ReactNode;
  value: ReactNode;
  icon?: ReactNode;
  color?: string;
  sub?: ReactNode;
}) {
  const { token } = theme.useToken();
  const c = color || token.colorPrimary;
  return (
    <div
      style={{
        background: token.colorBgContainer,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: token.borderRadiusLG,
        padding: 16,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {icon && (
          <span
            style={{
              display: "inline-grid",
              placeItems: "center",
              width: 34,
              height: 34,
              borderRadius: 10,
              background: `${c}1f`,
              color: c,
              fontSize: 17,
              flex: "none",
            }}
          >
            {icon}
          </span>
        )}
        <span style={{ color: token.colorTextSecondary, fontSize: 12.5, fontWeight: 500 }}>
          {label}
        </span>
      </div>
      <div
        style={{
          fontWeight: 700,
          fontSize: 21,
          lineHeight: 1.15,
          fontVariantNumeric: "tabular-nums",
          letterSpacing: "-0.01em",
        }}
      >
        {value}
      </div>
      {sub != null && (
        <div style={{ color: token.colorTextTertiary, fontSize: 11.5, marginTop: -4 }}>
          {sub}
        </div>
      )}
    </div>
  );
}
