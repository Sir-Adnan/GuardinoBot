import { useState } from "react";
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
  CloseCircleOutlined,
  DollarOutlined,
  DownloadOutlined,
  ShoppingOutlined,
  TeamOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtNum, fmtToman } from "../../utils/format";
import { formatDay } from "../../utils/datetime";
import { PageHeader } from "../../components/PageHeader";
import { StatCard } from "../../components/StatCard";

const { RangePicker } = DatePicker;
const { Text } = Typography;

export function ReportsPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const [days, setDays] = useState(30);
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);

  const query = range
    ? { start: range[0].format("YYYY-MM-DD"), end: range[1].format("YYYY-MM-DD") }
    : { days };

  const { data, isLoading } = useCustom<any>({ url: "/reports/summary", method: "get", config: { query } });
  const d = data?.data;

  const cards = [
    { k: "sales_total", icon: <DollarOutlined />, color: token.colorPrimary, money: true },
    { k: "income_total", icon: <WalletOutlined />, color: "#3b82f6", money: true },
    { k: "orders", icon: <ShoppingOutlined />, color: "#8b5cf6", money: false },
    { k: "new_users", icon: <TeamOutlined />, color: "#06b6d4", money: false },
    { k: "failed_payments", icon: <CloseCircleOutlined />, color: "#ef4444", money: false },
  ];

  const series: any[] = d?.revenue_series ?? [];
  const maxAmount = Math.max(1, ...series.map((p) => p.amount));
  const breakdown: any[] = d?.payment_breakdown ?? [];
  const breakdownTotal = Math.max(1, ...[breakdown.reduce((s, r) => s + r.amount, 0)]);

  const exportCsv = () => {
    if (!d) return;
    const lines: string[] = [`range,${d.start ?? ""},${d.end ?? ""}`];
    cards.forEach((c) => lines.push(`${c.k},${d[c.k] ?? 0}`));
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
            <RangePicker
              value={range as any}
              onChange={(v) => setRange(v && v[0] && v[1] ? [v[0], v[1]] : null)}
              allowClear
              maxDate={dayjs()}
            />
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
                  value={c.money ? fmtToman(d?.[c.k]) : fmtNum(d?.[c.k])}
                  icon={c.icon}
                  color={c.color}
                />
              </Col>
            ))}
          </Row>

          <Card style={{ marginTop: 16 }} title={t("reports.revenueTrend")} styles={{ body: { paddingBottom: 12 } }}>
            {series.length === 0 ? (
              <Empty />
            ) : (
              <>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 180, overflowX: "auto" }}>
                  {series.map((p, i) => (
                    <Tooltip key={i} title={`${formatDay(p.date)} — ${fmtToman(p.amount)}`}>
                      <div style={{ flex: "1 0 8px", minWidth: 8, display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%" }}>
                        <div
                          style={{
                            height: `${Math.round((p.amount / maxAmount) * 100)}%`,
                            minHeight: p.amount > 0 ? 3 : 0,
                            background: `linear-gradient(180deg, ${token.colorPrimary}, ${token.colorPrimary}99)`,
                            borderRadius: "4px 4px 0 0",
                            transition: "height .2s",
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
