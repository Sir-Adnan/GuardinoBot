import { useContext, useState, type CSSProperties, type ReactNode } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Row,
  Segmented,
  Skeleton,
  Space,
  Tooltip,
  Typography,
  theme,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudUploadOutlined,
  ClusterOutlined,
  CrownOutlined,
  DollarOutlined,
  DownloadOutlined,
  PauseCircleOutlined,
  PercentageOutlined,
  RiseOutlined,
  ShoppingOutlined,
  StopOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtNum, fmtToman } from "../../utils/format";
import { formatDay } from "../../utils/datetime";
import { PageHeader } from "../../components/PageHeader";
import { StatCard } from "../../components/StatCard";
import { JalaliRangePicker } from "../../components/JalaliRangePicker";
import { FilterBar } from "../../components/FilterBar";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { useIsMobile } from "../../hooks/useIsMobile";
import { ColorModeContext } from "../../contexts/color-mode";

const { RangePicker } = DatePicker;
const { Text } = Typography;

const fmtGb = (v?: number) => `${fmtNum(Math.round(v ?? 0))} GB`;

const PROXY_STATUS_META: Record<string, { icon: ReactNode; color: string }> = {
  active: { icon: <CheckCircleOutlined />, color: "#10b981" },
  on_hold: { icon: <ThunderboltOutlined />, color: "#3b82f6" },
  disabled: { icon: <PauseCircleOutlined />, color: "#9ca3af" },
  limited: { icon: <StopOutlined />, color: "#f59e0b" },
  expired: { icon: <CloseCircleOutlined />, color: "#ef4444" },
};

const RANK = ["🥇", "🥈", "🥉"];
const rank = (i: number) => (
  <span style={{ fontVariantNumeric: "tabular-nums" }}>{RANK[i] ?? i + 1}</span>
);

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <Text strong style={{ display: "block", marginTop: 22, marginBottom: 10, fontSize: 13 }}>
      {children}
    </Text>
  );
}

export function ReportsPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { calendar } = useContext(ColorModeContext);
  const isMobile = useIsMobile();
  const [days, setDays] = useState(30);
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);

  const query = range
    ? { start: range[0].format("YYYY-MM-DD"), end: range[1].format("YYYY-MM-DD") }
    : { days };

  const { data, isLoading } = useCustom<any>({ url: "/reports/summary", method: "get", config: { query } });
  const d = data?.data;
  const primary = token.colorPrimary;

  // Accent CSS vars for .gb-grid / .gb-avg / .gb-lift (index.css) — theme aware.
  const dashVars = {
    "--gbd-a": primary,
    "--gbd-a-2": `${primary}99`,
    "--gbd-a-soft": `${primary}2e`,
    "--gbd-a-faint": `${primary}14`,
    "--gbd-a-40": `${primary}66`,
    "--gbd-grid": token.colorFillSecondary,
  } as CSSProperties;

  // ---- derived KPIs (no extra API cost) ------------------------------------
  const avgOrder = d?.orders ? Math.round((d.sales_total ?? 0) / d.orders) : 0;
  const successRate = d?.total_transactions
    ? Math.round(((d.total_transactions - (d.failed_payments ?? 0)) / d.total_transactions) * 100)
    : null;

  const cards = [
    { k: "sales_total", icon: <DollarOutlined />, v: fmtToman(d?.sales_total) },
    { k: "income_total", icon: <WalletOutlined />, v: fmtToman(d?.income_total) },
    { k: "orders", icon: <ShoppingOutlined />, v: fmtNum(d?.orders) },
    { k: "gb_sold", icon: <CloudUploadOutlined />, v: fmtGb(d?.gb_sold) },
    { k: "new_users", icon: <TeamOutlined />, v: fmtNum(d?.new_users) },
    { k: "failed_payments", icon: <CloseCircleOutlined />, v: fmtNum(d?.failed_payments) },
    { k: "avg_order", icon: <RiseOutlined />, v: fmtToman(avgOrder) },
    {
      k: "success_rate",
      icon: <PercentageOutlined />,
      v: successRate == null ? "—" : `${fmtNum(successRate)}٪`,
    },
  ];

  const allTimeCards = [
    { k: "all_sales_total", icon: <DollarOutlined />, v: fmtToman(d?.all_sales_total) },
    { k: "all_income_total", icon: <WalletOutlined />, v: fmtToman(d?.all_income_total) },
    { k: "all_orders", icon: <ShoppingOutlined />, v: fmtNum(d?.all_orders) },
    { k: "all_users", icon: <TeamOutlined />, v: fmtNum(d?.all_users) },
    { k: "all_gb_sold", icon: <CloudUploadOutlined />, v: fmtGb(d?.all_gb_sold) },
  ];

  const byStatus: Record<string, number> = d?.proxies_by_status ?? {};
  const STATUS_ORDER = ["active", "on_hold", "disabled", "limited", "expired"];

  const series: any[] = d?.revenue_series ?? [];
  const seriesSum = series.reduce((s, p) => s + (p.amount || 0), 0);
  // Mobile: cap at the last 30 points — 60 hair-thin bars are untappable on a
  // phone. Scale/average/labels follow the SHOWN slice so bars stay readable.
  const shown = isMobile ? series.slice(-30) : series;
  const maxAmount = Math.max(1, ...shown.map((p) => p.amount));
  const shownSum = shown.reduce((s, p) => s + (p.amount || 0), 0);
  const seriesAvg = shown.length ? shownSum / shown.length : 0;
  const lastIdx = shown.length - 1;

  const breakdown: any[] = d?.payment_breakdown ?? [];
  const breakdownTotal = Math.max(1, breakdown.reduce((s, r) => s + r.amount, 0));
  const ordersByType: any[] = d?.orders_by_type ?? [];
  const ordersTypeTotal = Math.max(1, ordersByType.reduce((s, r) => s + r.amount, 0));
  const topServices: any[] = d?.top_services ?? [];
  const topServicesTotal = Math.max(1, topServices.reduce((s, r) => s + (r.revenue || 0), 0));
  const topBuyers: any[] = d?.top_buyers ?? [];

  const exportCsv = () => {
    if (!d) return;
    const lines: string[] = [`range,${d.start ?? ""},${d.end ?? ""}`];
    cards.forEach((c) =>
      lines.push(`${c.k},${c.k === "avg_order" ? avgOrder : c.k === "success_rate" ? successRate ?? "" : d[c.k] ?? 0}`),
    );
    lines.push(`total_transactions,${d.total_transactions ?? 0}`);
    lines.push("", "all_time_metric,value");
    allTimeCards.forEach((c) => lines.push(`${c.k},${d[c.k] ?? 0}`));
    lines.push("", "proxy_status,count");
    lines.push(`total,${d.proxies_total ?? 0}`);
    STATUS_ORDER.forEach((st) => lines.push(`${st},${byStatus[st] ?? 0}`));
    lines.push("", "payment_method,count,amount");
    breakdown.forEach((r) => lines.push(`${r.type_name},${r.count},${r.amount}`));
    lines.push("", "order_type,count,amount");
    ordersByType.forEach((r) => lines.push(`${r.type_name},${r.count},${r.amount}`));
    lines.push("", "service,orders,revenue");
    topServices.forEach((r) => lines.push(`"${String(r.name).replace(/"/g, '""')}",${r.count},${r.revenue ?? 0}`));
    lines.push("", "buyer_id,buyer,orders,amount");
    topBuyers.forEach((r) =>
      lines.push(`${r.user_id},"${String(r.name || r.username || "").replace(/"/g, '""')}",${r.orders},${r.amount}`),
    );
    lines.push("", "date,amount");
    series.forEach((p) => lines.push(`${p.date},${p.amount}`));
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `report_${d.start ?? ""}_${d.end ?? ""}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const shareBar = (pct: number) => (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: token.colorFillTertiary }}>
        <div
          style={{
            width: `${Math.min(100, pct)}%`,
            height: "100%",
            borderRadius: 3,
            background: `linear-gradient(90deg, ${primary}, ${primary}99)`,
          }}
        />
      </div>
      <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12, minWidth: 32, textAlign: "end" }}>
        {pct}%
      </span>
    </div>
  );

  const breakdownCols = [
    { title: t("reports.method"), dataIndex: "type_name", render: (v: string) => t(`audit.pm.${v}`, v) },
    {
      title: t("reports.share"),
      key: "share",
      width: 170,
      render: (_: any, r: any) => shareBar(Math.round((r.amount / breakdownTotal) * 100)),
    },
    { title: t("reports.count"), dataIndex: "count", className: "mono", width: 70, render: (v: number) => fmtNum(v) },
    { title: t("reports.amount"), dataIndex: "amount", className: "mono", render: (v: number) => fmtToman(v) },
  ];

  const ordersTypeCols = [
    { title: t("reports.orders_by_type"), dataIndex: "type_name", render: (v: string) => t(`reports.ot_${v}`, v) },
    {
      title: t("reports.share"),
      key: "share",
      width: 170,
      render: (_: any, r: any) => shareBar(Math.round((r.amount / ordersTypeTotal) * 100)),
    },
    { title: t("reports.count"), dataIndex: "count", className: "mono", width: 70, render: (v: number) => fmtNum(v) },
    { title: t("reports.amount"), dataIndex: "amount", className: "mono", render: (v: number) => fmtToman(v) },
  ];

  const topServiceCols = [
    { title: "#", key: "rank", width: 52, render: (_: any, __: any, i: number) => rank(i) },
    { title: t("reports.service"), dataIndex: "name", ellipsis: true },
    {
      title: t("reports.share"),
      key: "share",
      width: 150,
      responsive: ["md"] as any,
      render: (_: any, r: any) => shareBar(Math.round(((r.revenue || 0) / topServicesTotal) * 100)),
    },
    { title: t("reports.count"), dataIndex: "count", className: "mono", width: 80, render: (v: number) => fmtNum(v) },
    { title: t("reports.revenue"), dataIndex: "revenue", className: "mono", width: 130, render: (v: number) => fmtToman(v ?? 0) },
  ];

  const topBuyerCols = [
    { title: "#", key: "rank", width: 52, render: (_: any, __: any, i: number) => rank(i) },
    {
      title: t("reports.buyer"),
      key: "buyer",
      ellipsis: true,
      render: (_: any, r: any) => (
        <span>
          {r.name || r.username || r.user_id}
          {r.username && (
            <Text type="secondary" style={{ fontSize: 11, marginInlineStart: 6 }}>
              @{r.username}
            </Text>
          )}
        </span>
      ),
    },
    { title: t("reports.count"), dataIndex: "orders", className: "mono", width: 70, render: (v: number) => fmtNum(v) },
    { title: t("reports.amount"), dataIndex: "amount", className: "mono", width: 130, render: (v: number) => fmtToman(v) },
  ];

  const axisLabels = shown.length
    ? [shown[0], shown[Math.floor(shown.length / 2)], shown[shown.length - 1]]
    : [];

  const kpiSkeleton = (n: number) =>
    [...Array(n)].map((_, i) => (
      <Col xs={12} sm={8} md={8} lg={6} key={i}>
        <Card style={{ borderRadius: 16 }}>
          <Skeleton active title={false} paragraph={{ rows: 2 }} />
        </Card>
      </Col>
    ));

  return (
    <div style={dashVars}>
      <PageHeader
        title={t("reports.title")}
        subtitle={d?.start ? `${formatDay(d.start)} – ${formatDay(d.end)}` : t("reports.subtitle")}
        extra={
          <Button icon={<DownloadOutlined />} onClick={exportCsv} disabled={!d}>
            {t("reports.export")}
          </Button>
        }
      />
      <FilterBar>
        <Segmented
          block={isMobile}
          style={isMobile ? { flex: "1 1 100%" } : undefined}
          value={range ? "" : days}
          onChange={(v) => {
            setRange(null);
            setDays(v as number);
          }}
          options={[
            { label: t("reports.d7"), value: 7 },
            { label: t("reports.d30"), value: 30 },
            { label: t("reports.d90"), value: 90 },
          ]}
        />
        <div style={{ flex: isMobile ? "1 1 100%" : "0 1 auto", minWidth: 0 }}>
          {calendar === "jalali" ? (
            <JalaliRangePicker value={range} onChange={setRange} maxDate={dayjs()} />
          ) : (
            <RangePicker
              style={{ width: "100%" }}
              value={range as any}
              onChange={(v) => setRange(v && v[0] && v[1] ? [v[0], v[1]] : null)}
              allowClear
              maxDate={dayjs()}
            />
          )}
        </div>
      </FilterBar>

      {isLoading ? (
        <>
          <Row gutter={[16, 16]}>{kpiSkeleton(8)}</Row>
          <Card style={{ marginTop: 16, borderRadius: 16 }}>
            <Skeleton active paragraph={{ rows: 5 }} />
          </Card>
        </>
      ) : (
        <>
          <Row gutter={[16, 16]}>
            {cards.map((c) => (
              <Col xs={12} sm={8} md={8} lg={6} key={c.k}>
                <StatCard label={t(`reports.${c.k}`)} value={c.v} icon={c.icon} />
              </Col>
            ))}
          </Row>

          <Card
            className="gb-lift"
            style={{ marginTop: 16, borderRadius: 16 }}
            title={t("reports.revenueTrend")}
            styles={{ body: { paddingBottom: 12 } }}
            extra={
              seriesSum > 0 && (
                <Text type="secondary" style={{ fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
                  Σ <Text strong style={{ fontSize: 12 }}>{fmtToman(seriesSum)}</Text>
                </Text>
              )
            }
          >
            {shown.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <>
                <div className="gb-grid">
                  {seriesAvg > 0 && (
                    <div
                      className="gb-avg"
                      style={{ bottom: `${Math.min(96, Math.round((seriesAvg / maxAmount) * 100))}%` }}
                    />
                  )}
                  <div
                    className="bars"
                    style={{
                      height: isMobile ? 150 : 190,
                      gap: shown.length > 40 ? 3 : isMobile ? 4 : 6,
                    }}
                  >
                    {shown.map((p, i) => (
                      <Tooltip key={i} title={`${formatDay(p.date)} — ${fmtToman(p.amount)}`}>
                        <div className="barcol">
                          <div
                            className="chart-bar"
                            style={{
                              height: `${Math.max(p.amount > 0 ? 4 : 2, Math.round((p.amount / maxAmount) * 100))}%`,
                              background:
                                i === lastIdx
                                  ? `linear-gradient(180deg, ${primary}, ${primary}aa)`
                                  : `linear-gradient(180deg, ${primary}cc, ${primary}44)`,
                              boxShadow: i === lastIdx ? `0 0 14px ${primary}55` : undefined,
                              opacity: p.amount > 0 ? 1 : 0.25,
                            }}
                          />
                        </div>
                      </Tooltip>
                    ))}
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
                  {axisLabels.map((p, i) => (
                    <Text key={i} type="secondary" style={{ fontSize: 11 }}>
                      {formatDay(p.date)}
                    </Text>
                  ))}
                </div>
                {isMobile && (
                  // tooltips need a long-press on touch — surface the two key
                  // numbers of the visible window directly instead
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 8,
                      marginTop: 8,
                      padding: "6px 10px",
                      borderRadius: 10,
                      background: token.colorFillQuaternary,
                      fontSize: 11.5,
                    }}
                  >
                    <Text type="secondary" style={{ fontSize: 11.5 }}>
                      {t("reports.chart_max")}:{" "}
                      <Text strong style={{ fontSize: 11.5 }}>{fmtToman(maxAmount)}</Text>
                    </Text>
                    <Text type="secondary" style={{ fontSize: 11.5 }}>
                      {t("reports.chart_avg")}:{" "}
                      <Text strong style={{ fontSize: 11.5 }}>{fmtToman(Math.round(seriesAvg))}</Text>
                    </Text>
                  </div>
                )}
              </>
            )}
          </Card>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={13}>
              <Card className="gb-lift" style={{ borderRadius: 16, height: "100%" }} title={t("reports.paymentBreakdown")}>
                <ResponsiveTable
                  rowKey="type"
                  size="small"
                  pagination={false}
                  dataSource={breakdown}
                  columns={breakdownCols}
                  scroll={{ x: 420 }}
                  locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                />
              </Card>
            </Col>
            <Col xs={24} lg={11}>
              <Card className="gb-lift" style={{ borderRadius: 16, height: "100%" }} title={t("reports.orders_by_type")}>
                <ResponsiveTable
                  rowKey="type"
                  size="small"
                  pagination={false}
                  dataSource={ordersByType}
                  columns={ordersTypeCols}
                  scroll={{ x: 420 }}
                  locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={13}>
              <Card
                className="gb-lift"
                style={{ borderRadius: 16, height: "100%" }}
                title={
                  <Space size={8}>
                    <CrownOutlined style={{ color: primary }} />
                    {t("reports.topServices")}
                  </Space>
                }
              >
                <ResponsiveTable
                  rowKey="id"
                  size="small"
                  dataSource={topServices}
                  columns={topServiceCols}
                  scroll={{ x: 480 }}
                  pagination={
                    topServices.length > 10
                      ? { pageSize: 10, size: "small", showSizeChanger: false }
                      : false
                  }
                  locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                />
              </Card>
            </Col>
            <Col xs={24} lg={11}>
              <Card
                className="gb-lift"
                style={{ borderRadius: 16, height: "100%" }}
                title={
                  <Space size={8}>
                    <CrownOutlined style={{ color: primary }} />
                    {t("reports.top_buyers")}
                  </Space>
                }
              >
                <ResponsiveTable
                  rowKey="user_id"
                  size="small"
                  pagination={false}
                  dataSource={topBuyers}
                  columns={topBuyerCols}
                  scroll={{ x: 420 }}
                  locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                />
              </Card>
            </Col>
          </Row>

          <SectionTitle>{t("reports.allTime")}</SectionTitle>
          <Row gutter={[16, 16]}>
            {allTimeCards.map((c) => (
              <Col xs={12} sm={8} md={8} lg={4} xl={4} key={c.k}>
                <StatCard label={t(`reports.${c.k}`)} value={c.v} icon={c.icon} />
              </Col>
            ))}
          </Row>

          <SectionTitle>{t("reports.subsStats")}</SectionTitle>
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={8} md={8} lg={4}>
              <StatCard label={t("reports.proxies_total")} value={fmtNum(d?.proxies_total)} icon={<ClusterOutlined />} />
            </Col>
            {STATUS_ORDER.map((st) => (
              <Col xs={12} sm={8} md={8} lg={4} key={st}>
                <StatCard
                  label={t(`reports.st_${st}`)}
                  value={fmtNum(byStatus[st] ?? 0)}
                  icon={<span style={{ color: PROXY_STATUS_META[st]?.color }}>{PROXY_STATUS_META[st]?.icon}</span>}
                  sub={d?.proxies_total ? `${Math.round(((byStatus[st] ?? 0) / d.proxies_total) * 100)}%` : undefined}
                />
              </Col>
            ))}
          </Row>
        </>
      )}
    </div>
  );
}
