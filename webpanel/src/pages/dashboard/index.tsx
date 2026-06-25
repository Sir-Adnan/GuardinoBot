import { Card, Col, Row, Spin, Statistic, Typography, theme } from "antd";
import {
  CalendarOutlined,
  CloudServerOutlined,
  RiseOutlined,
  StopOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtNum } from "../../utils/format";

const { Title, Text } = Typography;

export function DashboardPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { data, isLoading } = useCustom<any>({
    url: "/dashboard/summary",
    method: "get",
  });
  const d = data?.data ?? {};

  const cards = [
    { k: "users_total", tk: "usersTotal", icon: <TeamOutlined />, color: token.colorPrimary },
    { k: "users_today", tk: "usersToday", icon: <RiseOutlined />, color: "#3b82f6" },
    { k: "users_month", tk: "usersMonth", icon: <CalendarOutlined />, color: "#8b5cf6" },
    { k: "proxies_total", tk: "proxiesTotal", icon: <CloudServerOutlined />, color: "#06b6d4" },
    { k: "proxies_active", tk: "proxiesActive", icon: <ThunderboltOutlined />, color: "#10b981" },
    { k: "blocked_users", tk: "blockedUsers", icon: <StopOutlined />, color: "#ef4444" },
  ];

  return (
    <div>
      <div style={{ marginBottom: 18 }}>
        <Title level={4} style={{ margin: 0 }}>
          {t("dashboard.title")}
        </Title>
        <Text type="secondary">{t("dashboard.subtitle")}</Text>
      </div>

      {isLoading ? (
        <div style={{ display: "grid", placeItems: "center", minHeight: 240 }}>
          <Spin />
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {cards.map((c) => (
            <Col xs={12} sm={12} md={8} xl={4} key={c.k}>
              <Card>
                <Statistic
                  title={t(`dashboard.${c.tk}`)}
                  value={fmtNum(d?.[c.k])}
                  valueStyle={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600 }}
                  prefix={
                    <span
                      style={{
                        display: "inline-grid",
                        placeItems: "center",
                        width: 30,
                        height: 30,
                        borderRadius: 8,
                        marginInlineEnd: 8,
                        background: `${c.color}22`,
                        color: c.color,
                      }}
                    >
                      {c.icon}
                    </span>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
