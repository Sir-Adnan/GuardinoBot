import { Card, Col, Row, Spin, Statistic, Typography, theme } from "antd";
import {
  ClockCircleOutlined,
  CloudServerOutlined,
  RiseOutlined,
  ShoppingOutlined,
  StopOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import type { ReactNode } from "react";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtNum, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";

const { Text } = Typography;

function Kpi({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: ReactNode;
  icon: ReactNode;
  color: string;
}) {
  return (
    <Card styles={{ body: { padding: 16 } }}>
      <Statistic
        title={title}
        value={value as any}
        formatter={(v) => <>{v}</>}
        valueStyle={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, fontSize: 18 }}
        prefix={
          <span
            style={{
              display: "inline-grid",
              placeItems: "center",
              width: 32,
              height: 32,
              borderRadius: 9,
              marginInlineEnd: 10,
              background: `${color}1f`,
              color,
            }}
          >
            {icon}
          </span>
        }
      />
    </Card>
  );
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(1, ...data);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 48 }}>
      {data.map((v, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            minWidth: 4,
            height: `${Math.round((v / max) * 100)}%`,
            minHeight: v > 0 ? 3 : 1,
            background: v > 0 ? color : "var(--ant-color-border)",
            opacity: v > 0 ? 0.85 : 0.4,
            borderRadius: "3px 3px 0 0",
          }}
        />
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { data, isLoading } = useCustom<any>({ url: "/dashboard/summary", method: "get" });
  const d = data?.data ?? {};

  if (isLoading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 240 }}>
        <Spin />
      </div>
    );
  }

  const sales = [
    { tk: "todayIncome", v: fmtToman(d.today_income), icon: <WalletOutlined />, color: token.colorPrimary },
    { tk: "todaySales", v: fmtToman(d.today_sales), icon: <ShoppingOutlined />, color: "#3b82f6" },
    { tk: "monthIncome", v: fmtToman(d.month_income), icon: <RiseOutlined />, color: "#8b5cf6" },
    { tk: "ordersToday", v: fmtNum(d.orders_today), icon: <ShoppingOutlined />, color: "#06b6d4" },
  ];
  const ops = [
    { tk: "usersTotal", v: fmtNum(d.users_total), icon: <TeamOutlined />, color: token.colorPrimary },
    { tk: "usersToday", v: fmtNum(d.users_today), icon: <RiseOutlined />, color: "#3b82f6" },
    { tk: "proxiesActive", v: fmtNum(d.proxies_active), icon: <ThunderboltOutlined />, color: "#10b981" },
    { tk: "proxiesTotal", v: fmtNum(d.proxies_total), icon: <CloudServerOutlined />, color: "#06b6d4" },
    {
      tk: "servers",
      v: `${fmtNum(d.servers_enabled)} / ${fmtNum(d.servers_total)}`,
      icon: <CloudServerOutlined />,
      color: "#8b5cf6",
    },
    { tk: "pendingPayments", v: fmtNum(d.pending_payments), icon: <ClockCircleOutlined />, color: "#f59e0b" },
    { tk: "blockedUsers", v: fmtNum(d.blocked_users), icon: <StopOutlined />, color: "#ef4444" },
  ];

  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      <Card style={{ marginBottom: 16 }} styles={{ body: { padding: 20 } }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={9}>
            <Text type="secondary">{t("dashboard.todayIncome")}</Text>
            <div
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontWeight: 700,
                fontSize: 30,
                lineHeight: 1.2,
                color: token.colorPrimary,
              }}
            >
              {fmtToman(d.today_income)}
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t("dashboard.todaySales")}: {fmtToman(d.today_sales)} · {t("dashboard.ordersToday")}:{" "}
              {fmtNum(d.orders_today)}
            </Text>
          </Col>
          <Col xs={24} md={15}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t("dashboard.last14")}
            </Text>
            <Sparkline data={d.revenue_spark ?? []} color={token.colorPrimary} />
          </Col>
        </Row>
      </Card>

      <Text type="secondary" style={{ fontSize: 12, fontWeight: 600 }}>
        {t("dashboard.secSales")}
      </Text>
      <Row gutter={[16, 16]} style={{ margin: "8px 0 20px" }}>
        {sales.map((c) => (
          <Col xs={12} sm={12} md={6} key={c.tk}>
            <Kpi title={t(`dashboard.${c.tk}`)} value={c.v} icon={c.icon} color={c.color} />
          </Col>
        ))}
      </Row>

      <Text type="secondary" style={{ fontSize: 12, fontWeight: 600 }}>
        {t("dashboard.secOps")}
      </Text>
      <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
        {ops.map((c) => (
          <Col xs={12} sm={8} md={6} xl={4} key={c.tk}>
            <Kpi title={t(`dashboard.${c.tk}`)} value={c.v} icon={c.icon} color={c.color} />
          </Col>
        ))}
      </Row>
    </div>
  );
}
