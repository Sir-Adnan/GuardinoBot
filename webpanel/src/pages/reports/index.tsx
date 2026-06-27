import { useContext, useState, type ReactNode } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Row,
  Segmented,
  Space,
  Spin,
  Table,
  Tooltip,
  Typography,
  theme,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudUploadOutlined,
  ClusterOutlined,
  DollarOutlined,
  DownloadOutlined,
  PauseCircleOutlined,
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

export function ReportsPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { calendar } = useContext(ColorModeContext);
  const [days, setDays] = useState(30);
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);

  const query = range
    ? { start: range[0].format("YYYY-MM-DD"), end: range[1].format("YYYY-MM-DD") }
    : { days };

  const { data, isLoading } = useCustom<any>({ url: "/reports/summary", method: "get", config: { query } });
  const d = data?.data;

  const cards = [
    { k: "sales_total", icon: <DollarOutlined />, fmt: "money" },
    { k: "income_total", icon: <WalletOutlined />, fmt: "money" },
    { k: "orders", icon: <ShoppingOutlined />, fmt: "num" },
    { k: "gb_sold", icon: <CloudUploadOutlined />, fmt: "gb" },
    { k: "new_users", icon: <TeamOutlined />, fmt: "num" },
    { k: "failed_payments", icon: <CloseCircleOutlined />, fmt: "num" },
  ];
  const fmtVal = (kind: string, v: any) =>
    kind === "money" ? fmtToman(v) : kind === "gb" ? fmtGb(v) : fmtNum(v);

  const allTimeCards = [
    { k: "all_sales_total", icon: <DollarOutlined />, fmt: "money" },
    { k: "all_income_total", icon: <WalletOutlined />, fmt: "money" },
    { k: "all_orders", icon: <ShoppingOutlined />, fmt: "num" },
    { k: "all_users", icon: <TeamOutlined />, fmt: "num" },
    { k: "all_gb_sold", icon: <CloudUploadOutlined />, fmt: "gb" },
  ];

  const byStatus: Record<string, number> = d?.proxies_by_status ?? {};
  const STATUS_ORDER = ["active", "on_hold", "disabled", "limited", "expired"];

  const series: any[] = d?.revenue_series ?? [];
  const maxAmount = Math.max(1, ...series.map((p) => p.amount));
  const breakdown: any[] = d?.payment_breakdown ?? [];
  const breakdownTotal = Math.max(1, ...[breakdown.reduce((s, r) => s + r.amount, 0)]);

  const exportCsv = () => {
    if (!d) return;
    const lines: string[] = [`range,${d.start ?? ""},${d.end ?? ""}`];
    cards.forEach((c) => lines.push(`${c.k},${d[c.k] ?? 0}`));
    lines.push("", "all_time_metric,value");
    allTimeCards.forEach((c) => lines.push(`${c.k},${d[c.k] ?? 0}`));
    lines.push("", "proxy_status,count");
    lines.push(`total,${d.proxies_total ?? 0}`);
    STATUS_ORDER.forEach((st) => lines.push(`${st},${byStatus[st] ?? 0}`));
    lines.push("", "payment_method,count,amount");
    breakdown.forEach((r) => lines.push(`${r.type_name},${r.count},${r.amount}`));
    lines.push("", "date,amount");
    series.forEach((p) => lines.push(`${p.date},${p.amount}`));
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `report_${d.start ?? ""}_${d.end ?? ""}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const breakdownCols = [
    { title: t("reports.method"), dataIndex: "type_name" },
    {
      title: t("reports.share"),
      key: "share",
      width: 160,
      render: (_: any, r: any) => {
        const pct = Math.round((r.amount / breakdownTotal) * 100);
        return (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ flex: 1, height: 6, borderRadius: 3, background: token.colorFillTertiary }}>
              <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: token.colorPrimary }} />
            </div>
            <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{pct}%</span>
          </div>
        );
      },
    },
    { title: t("reports.count"), dataIndex: "count", className: "mono", width: 70, render: (v: number) => fmtNum(v) },
    { title: t("reports.amount"), dataIndex: "amount", className: "mono", render: (v: number) => fmtToman(v) },
  ];
  const topCols = [
    { title: t("reports.service"), dataIndex: "name" },
    { title: t("reports.count"), dataIndex: "count", className: "mono", width: 90, render: (v: number) => fmtNum(v) },
  ];

  const axisLabels = series.length
    ? [series[0], series[Math.floor(series.length / 2)], series[series.length - 1]]
    : [];

  return (
    <div>
      <PageHeader
        title={t("reports.title")}
        subtitle={d?.start ? `${formatDay(d.start)} – ${formatDay(d.end)}` : t("reports.subtitle")}
        extra={
          <Space wrap>
            <Segmented
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
            {calendar === "jalali" ? (
              <JalaliRangePicker value={range} onChange={setRange} maxDate={dayjs()} />
            ) : (
              <RangePicker
                value={range as any}
                onChange={(v) => setRange(v && v[0] && v[1] ? [v[0], v[1]] : null)}
                allowClear
                maxDate={dayjs()}
              />
            )}
            <Button icon={<DownloadOutlined />} onClick={exportCsv} disabled={!d}>
              {t("reports.export")}
            </Button>
          </Space>
        }
      />

      {isLoading ? (
        <div style={{ display: "grid", placeItems: "center", minHeight: 240 }}>
          <Spin />
        </div>
      ) : (
        <>
          <Row gutter={[16, 16]}>
            {cards.map((c) => (
              <Col xs={12} sm={8} md={8} lg={4} key={c.k} flex="1">
                <StatCard
                  label={t(`reports.${c.k}`)}
                  value={fmtVal(c.fmt, d?.[c.k])}
                  icon={c.icon}
                />
              </Col>
            ))}
          </Row>

          <Card style={{ marginTop: 16 }} title={t("reports.revenueTrend")} styles={{ body: { paddingBottom: 12 } }}>
            {series.length === 0 ? (
              <Empty />
            ) : (
              <>
                <div className="bars" style={{ height: 180, overflowX: "auto" }}>
                  {series.map((p, i) => (
                    <Tooltip key={i} title={`${formatDay(p.date)} — ${fmtToman(p.amount)}`}>
                      <div className="barcol">
                        <div
                          className="chart-bar"
                          style={{
                            height: `${Math.round((p.amount / maxAmount) * 100)}%`,
                            minHeight: p.amount > 0 ? 3 : 0,
                            background: `linear-gradient(180deg, ${token.colorPrimary}, ${token.colorPrimary}99)`,
                          }}
                        />
                      </div>
                    </Tooltip>
                  ))}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                  {axisLabels.map((p, i) => (
                    <Text key={i} type="secondary" style={{ fontSize: 11 }}>
                      {formatDay(p.date)}
                    </Text>
                  ))}
                </div>
              </>
            )}
          </Card>

          <Text strong style={{ display: "block", marginTop: 22, marginBottom: 10, fontSize: 13 }}>
            {t("reports.allTime")}
          </Text>
          <Row gutter={[16, 16]}>
            {allTimeCards.map((c) => (
              <Col xs={12} sm={8} md={8} lg={4} xl={4} key={c.k} flex="1">
                <StatCard
                  label={t(`reports.${c.k}`)}
                  value={fmtVal(c.fmt, d?.[c.k])}
                  icon={c.icon}
                />
              </Col>
            ))}
          </Row>

          <Text strong style={{ display: "block", marginTop: 22, marginBottom: 10, fontSize: 13 }}>
            {t("reports.subsStats")}
          </Text>
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={8} md={8} lg={4} flex="1">
              <StatCard label={t("reports.proxies_total")} value={fmtNum(d?.proxies_total)} icon={<ClusterOutlined />} />
            </Col>
            {STATUS_ORDER.map((st) => (
              <Col xs={12} sm={8} md={8} lg={4} key={st} flex="1">
                <StatCard
                  label={t(`reports.st_${st}`)}
                  value={fmtNum(byStatus[st] ?? 0)}
                  icon={<span style={{ color: PROXY_STATUS_META[st]?.color }}>{PROXY_STATUS_META[st]?.icon}</span>}
                  sub={d?.proxies_total ? `${Math.round(((byStatus[st] ?? 0) / d.proxies_total) * 100)}%` : undefined}
                />
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={14}>
              <Card title={t("reports.paymentBreakdown")}>
                <Table rowKey="type" size="small" pagination={false} dataSource={breakdown} columns={breakdownCols} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} />
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card title={t("reports.topServices")}>
                <Table rowKey="id" size="small" pagination={false} dataSource={d?.top_services ?? []} columns={topCols} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
