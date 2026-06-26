import type { ReactNode } from "react";
import { Typography } from "antd";

const { Title, Text } = Typography;

/**
 * Consistent page header used across panel pages: title (+ optional subtitle) on
 * one side, actions on the other. Responsive (wraps on small screens). Adopt this
 * in pages during the P5+ phases so every section looks the same.
 */
export function PageHeader({
  title,
  subtitle,
  extra,
  icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  extra?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 12,
        marginBottom: 16,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
        {icon}
        <div style={{ minWidth: 0 }}>
          <Title level={4} style={{ margin: 0, lineHeight: 1.2 }}>
            {title}
          </Title>
          {subtitle && (
            <Text type="secondary" style={{ fontSize: 12.5 }}>
              {subtitle}
            </Text>
          )}
        </div>
      </div>
      {extra && <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{extra}</div>}
    </div>
  );
}
