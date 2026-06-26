import { useContext } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Card, Col, Empty, Row, Spin, Tooltip, Typography, theme } from "antd";
import {
  ApartmentOutlined,
  BankOutlined,
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
import { formatDay } from "../../utils/datetime";
import { PageHeader } from "../../components/PageHeader";
import { ColorModeContext } from "../../contexts/color-mode";

const { Text } = Typography;

const STYLE = `
.dash-grid { --card-radius: 14px; }
.dash-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--card-radius);
  padding: 16px;
  height: 100%;
  display: flex; flex-direction: column; gap: 12px;
  box-shadow: var(--card-shadow);
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.dash-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--card-shadow-hover);
  border-color: var(--accent);
}
.dash-icon {
  width: 38px; height: 38px; flex: none;
  display: grid; place-items: center;
  border-radius: 11px;
  background: var(--chip-bg);
  color: var(--chip-fg);
  font-size: 18px;
  transition: background .18s ease, color .18s ease, transform .18s ease;
}
.dash-card:hover .dash-icon { background: var(--accent); color: #fff; transform: scale(1.06); }
.dash-bar { transition: filter .15s ease, opacity .15s ease; cursor: default; }
.dash-bar:hover { filter: brightness(1.18) saturate(1.1); }
`;

function Section({ title }: { title: string }) {
  const { token } = theme.useToken();
  return (
    <div style={{ margin: "24px 2px 14px", color: token.colorTextSecondary, fontSize: 12.5, fontWeight: 700, letterSpacing: "0.02em" }}>
      {title}
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { mode } = useContext(ColorModeContext);
  const { data, isLoading } = useCustom<any>({ url: "/dashboard/summary", method: "get" });
  const d = data?.data ?? {};
  const primary = token.colorPrimary;

  const rootVars = {
    "--card-bg": token.colorBgContainer,
    "--card-border": token.colorBorderSecondary,
    "--chip-bg": token.colorFillTertiary,
    "--chip-fg": token.colorTextSecondary,
    "--card-shadow": mode === "dark" ? "0 1px 3px rgba(0,0,0,.4)" : "0 1px 3px rgba(16,24,40,.06)",
    "--card-shadow-hover": mode === "dark" ? "0 14px 30px rgba(0,0,0,.55)" : "0 14px 30px rgba(16,24,40,.13)",
  } as CSSProperties;

  if (isLoading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 240 }}>
        <Spin />
      </div>
    );
  }

  const Stat = ({ label, value, icon, color, sub }: { label: ReactNode; value: ReactNode; icon: ReactNode; color: string; sub?: ReactNode }) => (
    <div className="dash-card" style={{ ["--accent" as any]: color }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <span className="dash-icon">{icon}</span>
        <span style={{ color: token.colorTextSecondary, fontSize: 12.5, fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontWeight: 700, fontSize: 21, lineHeight: 1.1, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em" }}>{value}</div>
      {sub != null && <div style={{ color: token.colorTextTertiary, fontSize: 11.5, marginTop: -6 }}>{sub}</div>}
    </div>
  );

  const spark: number[] = d.revenue_spark ?? [];
  const sparkMax = Math.max(1, ...spark);
  const today = new Date();
  const dayLabel = (back: number) => {
    const dt = new Date(today);
    dt.setDate(dt.getDate() - back);
    return formatDay(dt);
  };

  const finance = [
    { l: "todayIncome", v: fmtToman(d.today_income), i: <WalletOutlined />, c: primary },
    { l: "monthIncome", v: fmtToman(d.month_income), i: <RiseOutlined />, c: "#3b82f6" },
    { l: "totalIncome", v: fmtToman(d.total_income), i: <BankOutlined />, c: "#10b981" },
    { l: "totalSales", v: fmtToman(d.total_sales), i: <ShoppingOutlined />, c: "#8b5cf6" },
  ];
  const ops = [
    { l: "usersTotal", v: fmtNum(d.users_total), i: <TeamOutlined />, c: primary, s: `${t("dashboard.usersToday")}: ${fmtNum(d.users_today)}` },
    { l: "proxiesActive", v: `${fmtNum(d.proxies_active)} / ${fmtNum(d.proxies_total)}`, i: <ThunderboltOutlined />, c: "#10b981" },
    { l: "resellersTotal", v: fmtNum(d.resellers_total), i: <ApartmentOutlined />, c: "#8b5cf6" },
    { l: "servers", v: `${fmtNum(d.servers_enabled)} / ${fmtNum(d.servers_total)}`, i: <CloudServerOutlined />, c: "#3b82f6" },
    { l: "pendingPayments", v: fmtNum(d.pending_payments), i: <ClockCircleOutlined />, c: "#f59e0b" },
    { l: "blockedUsers", v: fmtNum(d.blocked_users), i: <StopOutlined />, c: "#ef4444" },
  ];

  return (
    <div className="dash-grid" style={rootVars}>
      <style>{STYLE}</style>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      <Section title={t("dashboard.secSales")} />
      <Row gutter={[16, 16]}>
        {finance.map((c) => (
          <Col xs={12} sm={12} md={6} key={c.l}>
            <Stat label={t(`dashboard.${c.l}`)} value={c.v} icon={c.i} color={c.c} />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card title={t("dashboard.last14")} style={{ borderRadius: 14 }} styles={{ body: { paddingBottom: 12 } }}>
            {spark.length === 0 || sparkMax <= 1 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 170 }}>
                  {spark.map((v, i) => (
                    <Tooltip key={i} title={`${dayLabel(spark.length - 1 - i)} — ${fmtToman(v)}`}>
                      <div style={{ flex: 1, minWidth: 6, display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%" }}>
                        <div
                          className="dash-bar"
                          style={{
                            height: `${Math.max(v > 0 ? 4 : 1, Math.round((v / sparkMax) * 100))}%`,
                            background: `linear-gradient(180deg, ${primary}, ${primary}88)`,
                            opacity: v > 0 ? 1 : 0.25,
                            borderRadius: "6px 6px 0 0",
                          }}
                        />
                      </div>
                    </Tooltip>
                  ))}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>{dayLabel(13)}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>{dayLabel(7)}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>{dayLabel(0)}</Text>
                </div>
              </>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title={t("dashboard.todaySummary")} style={{ borderRadius: 14, height: "100%" }}>
            <Text type="secondary" style={{ fontSize: 12 }}>{t("dashboard.todayIncome")}</Text>
            <div style={{ fontWeight: 800, fontSize: 30, lineHeight: 1.15, color: primary, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em", marginBottom: 14 }}>
              {fmtToman(d.today_income)}
            </div>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Text type="secondary" style={{ fontSize: 11.5 }}>{t("dashboard.todaySales")}</Text>
                <div style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{fmtToman(d.today_sales)}</div>
              </Col>
              <Col span={12}>
                <Text type="secondary" style={{ fontSize: 11.5 }}>{t("dashboard.ordersToday")}</Text>
                <div style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{fmtNum(d.orders_today)}</div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Section title={t("dashboard.secOps")} />
      <Row gutter={[16, 16]}>
        {ops.map((c) => (
          <Col xs={12} sm={8} md={8} xl={4} key={c.l}>
            <Stat label={t(`dashboard.${c.l}`)} value={c.v} icon={c.i} color={c.c} sub={(c as any).s} />
          </Col>
        ))}
      </Row>
    </div>
  );
}
