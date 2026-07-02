import type { ReactNode } from "react";
import { theme } from "antd";

/**
 * Token-styled filter strip used above list tables (users, transactions,
 * audit, …): soft fill, rounded, wraps + stacks on mobile. Give each child a
 * flex basis (e.g. `style={{ flex: "1 1 220px" }}`) for responsive sizing.
 */
export function FilterBar({ children }: { children: ReactNode }) {
  const { token } = theme.useToken();
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        marginBottom: 16,
        padding: 10,
        borderRadius: 12,
        background: token.colorFillQuaternary,
        border: `1px solid ${token.colorBorderSecondary}`,
      }}
    >
      {children}
    </div>
  );
}
