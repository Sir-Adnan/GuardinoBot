import { useContext } from "react";
import type { CSSProperties, ReactNode } from "react";
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
import { ColorModeContext } from "../../contexts/color-mode";

const { Text } = Typography;

/** Neumorphic shadow helpers (dual soft shadows on a same-colour surface). */
function useNeu() {
  const { mode } = useContext(ColorModeContext);
  const { token } = theme.useToken();
  const bg = token.colorBgLayout;
  const dark = mode === "dark" ? "rgba(0,0,0,0.55)" : "rgba(163,177,198,0.55)";
  const light = mode === "dark" ? "rgba(255,255,255,0.045)" : "rgba(255,255,255,0.95)";
  const raised = (r = 18): CSSProperties => ({
    background: bg,
    borderRadius: r,
    boxShadow: `7px 7px 16px ${dark}, -7px -7px 16px ${light}`,
  });
  const inset = (r = 14): CSSProperties => ({
    background: bg,
    borderRadius: r,
    boxShadow: `inset 4px 4px 9px ${dark}, inset -4px -4px 9px ${light}`,
  });
  return { bg, raised, inset };
}

function Section({ title }: { title: string }) {
  const { token } = theme.useToken();
  return (
    <div style={{ margin: "26px 2px 14px", color: token.colorTextSecondary, fontSize: 12.5, fontWeight: 700, letterSpacing: "0.02em" }}>
      {title}
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const neu = useNeu();
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

  const NeuStat = ({ label, value, icon, color, sub }: { label: ReactNode; value: ReactNode; icon: ReactNode; color: string; sub?: ReactNode }) => (
    <div style={{ ...neu.raised(16), padding: 16, height: "100%", display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <span style={{ ...neu.inset(11), width: 38, height: 38, display: "grid", placeItems: "center", color, fontSize: 18, flex: "none" }}>
          {icon}
        </span>
        <span style={{ color: token.colorTextSecondary, fontSize: 12.5, fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontWeight: 700, fontSize: 21, lineHeight: 1.1, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em" }}>
        {value}
      </div>
      {sub != null && <div style={{ color: token.colorTextTertiary, fontSize: 11.5, marginTop: -6 }}>{sub}</div>}
    </div>
  );

  const HeroMini = ({ label, value }: { label: string; value: ReactNode }) => (
    <div style={{ ...neu.inset(12), padding: "10px 14px", flex: 1, minWidth: 120 }}>
      <div style={{ color: token.colorTextTertiary, fontSize: 11 }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: 16, fontVariantNumeric: "tabular-nums" }}>{value}</div>
    </div>
  );

  const spark: number[] = d.revenue_spark ?? [];
  const sparkMax = Math.max(1, ...spark);

  const sales = [
    { l: "totalIncome", v: fmtToman(d.total_income), i: <WalletOutlined />, c: primary },
    { l: "totalSales", v: fmtToman(d.total_sales), i: <ShoppingOutlined />, c: "#8b5cf6" },
    { l: "monthIncome", v: fmtToman(d.month_income), i: <RiseOutlined />, c: "#3b82f6" },
    { l: "activeUsers", v: fmtNum(d.active_users), i: <ThunderboltOutlined />, c: "#10b981" },
  ];
  const ops = [
    { l: "usersTotal", v: fmtNum(d.users_total), i: <TeamOutlined />, c: primary, s: `${t("dashboard.usersToday")}: ${fmtNum(d.users_today)}` },
    { l: "proxiesActive", v: `${fmtNum(d.proxies_active)} / ${fmtNum(d.proxies_total)}`, i: <CloudServerOutlined />, c: "#06b6d4" },
    { l: "resellersTotal", v: fmtNum(d.resellers_total), i: <ApartmentOutlined />, c: "#8b5cf6" },
    { l: "servers", v: `${fmtNum(d.servers_enabled)} / ${fmtNum(d.servers_total)}`, i: <CloudServerOutlined />, c: "#3b82f6" },
    { l: "pendingPayments", v: fmtNum(d.pending_payments), i: <ClockCircleOutlined />, c: "#f59e0b" },
    { l: "blockedUsers", v: fmtNum(d.blocked_users), i: <StopOutlined />, c: "#ef4444" },
  ];

  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      <div style={{ ...neu.raised(22), padding: 24 }}>
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} md={10}>
            <Text style={{ color: token.colorTextSecondary, fontSize: 12.5 }}>{t("dashboard.todayIncome")}</Text>
            <div style={{ fontWeight: 800, fontSize: 36, lineHeight: 1.1, color: primary, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em", margin: "4px 0 14px" }}>
              {fmtToman(d.today_income)}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <HeroMini label={t("dashboard.todaySales")} value={fmtToman(d.today_sales)} />
              <HeroMini label={t("dashboard.ordersToday")} value={fmtNum(d.orders_today)} />
            </div>
          </Col>
          <Col xs={24} md={14}>
            <div style={{ ...neu.inset(16), padding: "14px 16px 12px" }}>
              <Text style={{ color: token.colorTextSecondary, fontSize: 12 }}>{t("dashboard.last14")}</Text>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 92, marginTop: 8 }}>
                {spark.map((v, i) => (
                  <Tooltip key={i} title={fmtToman(v)}>
                    <div style={{ flex: 1, minWidth: 5, height: `${Math.max(v > 0 ? 6 : 2, Math.round((v / sparkMax) * 100))}%`, background: `linear-gradient(180deg, ${primary}, ${primary}88)`, opacity: v > 0 ? 1 : 0.25, borderRadius: "5px 5px 0 0", transition: "height .2s" }} />
                  </Tooltip>
                ))}
              </div>
            </div>
          </Col>
        </Row>
      </div>

      <Section title={t("dashboard.secSales")} />
      <Row gutter={[18, 18]}>
        {sales.map((c) => (
          <Col xs={12} sm={12} md={6} key={c.l}>
            <NeuStat label={t(`dashboard.${c.l}`)} value={c.v} icon={c.i} color={c.c} />
          </Col>
        ))}
      </Row>

      <Section title={t("dashboard.secOps")} />
      <Row gutter={[18, 18]}>
        {ops.map((c) => (
          <Col xs={12} sm={8} md={8} xl={4} key={c.l}>
            <NeuStat label={t(`dashboard.${c.l}`)} value={c.v} icon={c.i} color={c.c} sub={(c as any).s} />
          </Col>
        ))}
      </Row>
    </div>
  );
}
