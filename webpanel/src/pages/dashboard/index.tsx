import { useState } from "react";
import type { ReactNode } from "react";
import { Card, Col, Empty, Row, Segmented, Spin, Tooltip, Typography, theme } from "antd";
import {
  ApartmentOutlined,
  BankOutlined,
  ClockCircleOutlined,
  CloudServerOutlined,
  ShoppingOutlined,
  StopOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtNum, fmtToman } from "../../utils/format";
import { formatDay } from "../../utils/datetime";
import { PageHeader } from "../../components/PageHeader";
import { StatCard } from "../../components/StatCard";

const { Text } = Typography;

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
  const [period, setPeriod] = useState<"today" | "week" | "month">("today");
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

  const spark: number[] = d.revenue_spark ?? [];
  const sparkMax = Math.max(1, ...spark);
  const today = new Date();
  const dayLabel = (back: number) => {
    const dt = new Date(today);
    dt.setDate(dt.getDate() - back);
    return formatDay(dt);
  };

  const p = (period === "today" ? d.period_today : period === "week" ? d.period_week : d.period_month) ?? {};
  const sep = `1px solid ${token.colorBorderSecondary}`;
  const SummaryCell = ({ label, value, border }: { label: string; value: ReactNode; border?: boolean }) => (
    <div style={{ padding: "12px 14px", borderInlineStart: border ? sep : undefined }}>
      <div style={{ color: token.colorTextTertiary, fontSize: 11.5 }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: 16, fontVariantNumeric: "tabular-nums", marginTop: 2 }}>{value}</div>
    </div>
  );

  const ops = [
    { l: "totalIncome", v: fmtToman(d.total_income), i: <BankOutlined /> },
    { l: "totalSales", v: fmtToman(d.total_sales), i: <ShoppingOutlined /> },
    { l: "usersTotal", v: fmtNum(d.users_total), i: <TeamOutlined />, s: `${t("dashboard.usersToday")}: ${fmtNum(d.users_today)}` },
    { l: "proxiesActive", v: `${fmtNum(d.proxies_active)} / ${fmtNum(d.proxies_total)}`, i: <ThunderboltOutlined /> },
    { l: "resellersTotal", v: fmtNum(d.resellers_total), i: <ApartmentOutlined /> },
    { l: "servers", v: `${fmtNum(d.servers_enabled)} / ${fmtNum(d.servers_total)}`, i: <CloudServerOutlined /> },
    { l: "pendingPayments", v: fmtNum(d.pending_payments), i: <ClockCircleOutlined /> },
    { l: "blockedUsers", v: fmtNum(d.blocked_users), i: <StopOutlined /> },
  ];

  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={15}>
          <Card title={t("dashboard.last14")} style={{ borderRadius: 14 }} styles={{ body: { paddingBottom: 12 } }}>
            {spark.length === 0 || sparkMax <= 1 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <>
                <div className="bars" style={{ height: 172 }}>
                  {spark.map((v, i) => (
                    <Tooltip key={i} title={`${dayLabel(spark.length - 1 - i)} — ${fmtToman(v)}`}>
                      <div className="barcol">
                        <div
                          className="chart-bar"
                          style={{
                            height: `${Math.max(v > 0 ? 4 : 1, Math.round((v / sparkMax) * 100))}%`,
                            background: `linear-gradient(180deg, ${primary}, ${primary}88)`,
                            opacity: v > 0 ? 1 : 0.25,
                          }}
                        />
                      </div>
                    </Tooltip>
                  ))}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>{dayLabel(13)}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>{dayLabel(7)}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>{dayLabel(0)}</Text>
                </div>
              </>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={9}>
          <Card
            title={t("dashboard.summary")}
            style={{ borderRadius: 14, height: "100%" }}
            extra={
              <Segmented
                size="small"
                value={period}
                onChange={(v) => setPeriod(v as any)}
                options={[
                  { label: t("dashboard.p_today"), value: "today" },
                  { label: t("dashboard.p_week"), value: "week" },
                  { label: t("dashboard.p_month"), value: "month" },
                ]}
              />
            }
          >
            <Text type="secondary" style={{ fontSize: 12 }}>{t("dashboard.income")}</Text>
            <div style={{ fontWeight: 800, fontSize: 28, lineHeight: 1.15, color: primary, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em", marginBottom: 12 }}>
              {fmtToman(p.income)}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", border: sep, borderRadius: 12 }}>
              <SummaryCell label={t("dashboard.sales")} value={fmtToman(p.sales)} />
              <SummaryCell label={t("dashboard.orders")} value={fmtNum(p.orders)} border />
              <SummaryCell label={t("dashboard.gbSold")} value={`${fmtNum(p.gb)} GB`} border />
            </div>
          </Card>
        </Col>
      </Row>

      <Section title={t("dashboard.secOps")} />
      <Row gutter={[16, 16]}>
        {ops.map((c) => (
          <Col xs={12} sm={12} md={8} lg={6} xl={6} key={c.l}>
            <StatCard label={t(`dashboard.${c.l}`)} value={c.v} icon={c.i} sub={(c as any).s} />
          </Col>
        ))}
      </Row>
    </div>
  );
}
