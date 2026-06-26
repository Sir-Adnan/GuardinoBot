import { Col, Row, Spin, Tooltip, Typography, theme } from "antd";
import {
  ApartmentOutlined,
  ClockCircleOutlined,
  CloudServerOutlined,
  RiseOutlined,
  ShoppingOutlined,
  StopOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtNum, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { StatCard } from "../../components/StatCard";

const { Text } = Typography;

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(1, ...data);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 64 }}>
      {data.map((v, i) => (
        <Tooltip key={i} title={fmtToman(v)}>
          <div
            style={{
              flex: 1,
              minWidth: 5,
              height: `${Math.max(v > 0 ? 6 : 2, Math.round((v / max) * 100))}%`,
              background: color,
              opacity: v > 0 ? 0.9 : 0.25,
              borderRadius: "4px 4px 0 0",
              transition: "height .2s",
            }}
          />
        </Tooltip>
      ))}
    </div>
  );
}

function Section({ title }: { title: string }) {
  const { token } = theme.useToken();
  return (
    <div style={{ margin: "22px 0 12px", color: token.colorTextSecondary, fontSize: 12.5, fontWeight: 600 }}>
      {title}
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { data, isLoading } = useCustom<any>({ url: "/dashboard/summary", method: "get" });
  const d = data?.data ?? {};
  const primary = token.colorPrimary;

  if (isLoading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 240 }}>
        <Spin />
      </div>
    );
  }

  const sales = [
    { l: "totalIncome", v: fmtToman(d.total_income), i: <WalletOutlined />, c: primary },
    { l: "monthIncome", v: fmtToman(d.month_income), i: <RiseOutlined />, c: "#3b82f6" },
    { l: "totalSales", v: fmtToman(d.total_sales), i: <ShoppingOutlined />, c: "#8b5cf6" },
    { l: "todaySales", v: fmtToman(d.today_sales), i: <ShoppingOutlined />, c: "#06b6d4" },
  ];
  const ops = [
    { l: "usersTotal", v: fmtNum(d.users_total), i: <TeamOutlined />, c: primary, s: `${t("dashboard.usersToday")}: ${fmtNum(d.users_today)}` },
    { l: "activeUsers", v: fmtNum(d.active_users), i: <ThunderboltOutlined />, c: "#10b981" },
    { l: "proxiesActive", v: `${fmtNum(d.proxies_active)} / ${fmtNum(d.proxies_total)}`, i: <CloudServerOutlined />, c: "#06b6d4" },
    { l: "resellersTotal", v: fmtNum(d.resellers_total), i: <ApartmentOutlined />, c: "#8b5cf6" },
    { l: "servers", v: `${fmtNum(d.servers_enabled)} / ${fmtNum(d.servers_total)}`, i: <CloudServerOutlined />, c: "#3b82f6" },
    { l: "pendingPayments", v: fmtNum(d.pending_payments), i: <ClockCircleOutlined />, c: "#f59e0b" },
    { l: "blockedUsers", v: fmtNum(d.blocked_users), i: <StopOutlined />, c: "#ef4444" },
  ];

  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      <div
        style={{
          background: `linear-gradient(135deg, ${primary}1f, ${primary}05)`,
          border: `1px solid ${token.colorBorderSecondary}`,
          borderRadius: token.borderRadiusLG,
          padding: 22,
        }}
      >
        <Row gutter={[20, 20]} align="middle">
          <Col xs={24} md={9}>
            <Text style={{ color: token.colorTextSecondary, fontSize: 12.5 }}>
              {t("dashboard.todayIncome")}
            </Text>
            <div
              style={{
                fontWeight: 800,
                fontSize: 34,
                lineHeight: 1.15,
                color: primary,
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.02em",
              }}
            >
              {fmtToman(d.today_income)}
            </div>
            <Text style={{ color: token.colorTextTertiary, fontSize: 12 }}>
              {t("dashboard.todaySales")}: {fmtToman(d.today_sales)} · {t("dashboard.ordersToday")}:{" "}
              {fmtNum(d.orders_today)}
            </Text>
          </Col>
          <Col xs={24} md={15}>
            <Text style={{ color: token.colorTextSecondary, fontSize: 12 }}>
              {t("dashboard.last14")}
            </Text>
            <Sparkline data={d.revenue_spark ?? []} color={primary} />
          </Col>
        </Row>
      </div>

      <Section title={t("dashboard.secSales")} />
      <Row gutter={[16, 16]}>
        {sales.map((c) => (
          <Col xs={12} sm={12} md={6} key={c.l}>
            <StatCard label={t(`dashboard.${c.l}`)} value={c.v} icon={c.i} color={c.c} />
          </Col>
        ))}
      </Row>

      <Section title={t("dashboard.secOps")} />
      <Row gutter={[16, 16]}>
        {ops.map((c) => (
          <Col xs={12} sm={8} md={6} xl={6} key={c.l}>
            <StatCard label={t(`dashboard.${c.l}`)} value={c.v} icon={c.i} color={c.c} sub={(c as any).s} />
          </Col>
        ))}
      </Row>
    </div>
  );
}
