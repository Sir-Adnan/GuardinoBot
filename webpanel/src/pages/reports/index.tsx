import { useState } from "react";
import {
  Card,
  Col,
  Row,
  Segmented,
  Spin,
  Statistic,
  Table,
  Tooltip,
  Typography,
  theme,
} from "antd";
import {
  DollarOutlined,
  ShoppingOutlined,
  TeamOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { useCustom } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { fmtNum, fmtToman } from "../../utils/format";

const { Title, Text } = Typography;

export function ReportsPage() {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const [days, setDays] = useState(30);

  const { data, isLoading } = useCustom<any>({
    url: "/reports/summary",
    method: "get",
    config: { query: { days } },
  });
  const d = data?.data;

  const cards = [
    { k: "sales_total", icon: <DollarOutlined />, color: token.colorPrimary, money: true },
    { k: "income_total", icon: <WalletOutlined />, color: "#3b82f6", money: true },
    { k: "orders", icon: <ShoppingOutlined />, color: "#8b5cf6", money: false },
    { k: "new_users", icon: <TeamOutlined />, color: "#06b6d4", money: false },
  ];

  const series: any[] = d?.revenue_series ?? [];
  const maxAmount = Math.max(1, ...series.map((p) => p.amount));

  const breakdownCols = [
    { title: t("reports.method"), dataIndex: "type_name" },
    {
      title: t("reports.count"),
      dataIndex: "count",
      className: "mono",
      render: (v: number) => fmtNum(v),
    },
    {
      title: t("reports.amount"),
      dataIndex: "amount",
      className: "mono",
      render: (v: number) => fmtToman(v),
    },
  ];
  const topCols = [
    { title: t("reports.service"), dataIndex: "name" },
    {
      title: t("reports.count"),
      dataIndex: "count",
      className: "mono",
      render: (v: number) => fmtNum(v),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 18,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <Title level={4} style={{ margin: 0 }}>
            {t("reports.title")}
          </Title>
          <Text type="secondary">{t("reports.subtitle")}</Text>
        </div>
        <Segmented
          value={days}
          onChange={(v) => setDays(v as number)}
          options={[
            { label: t("reports.d7"), value: 7 },
            { label: t("reports.d30"), value: 30 },
            { label: t("reports.d90"), value: 90 },
          ]}
        />
      </div>

      {isLoading ? (
        <div style={{ display: "grid", placeItems: "center", minHeight: 240 }}>
          <Spin />
        </div>
      ) : (
        <>
          <Row gutter={[16, 16]}>
            {cards.map((c) => (
              <Col xs={12} md={6} key={c.k}>
                <Card>
                  <Statistic
                    title={t(`reports.${c.k}`)}
                    value={c.money ? fmtToman(d?.[c.k]) : fmtNum(d?.[c.k])}
                    valueStyle={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontWeight: 600,
                      fontSize: 18,
                    }}
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

          <Card style={{ marginTop: 16 }} title={t("reports.revenueTrend")}>
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                gap: 4,
                height: 160,
                overflowX: "auto",
              }}
            >
              {series.map((p, i) => (
                <Tooltip key={i} title={`${p.date} — ${fmtToman(p.amount)}`}>
                  <div
                    style={{
                      flex: "1 0 8px",
                      minWidth: 8,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "flex-end",
                      height: "100%",
                    }}
                  >
                    <div
                      style={{
                        height: `${Math.round((p.amount / maxAmount) * 100)}%`,
                        minHeight: p.amount > 0 ? 3 : 0,
                        background: token.colorPrimary,
                        borderRadius: "4px 4px 0 0",
                        transition: "height .2s",
                      }}
                    />
                  </div>
                </Tooltip>
              ))}
            </div>
          </Card>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={12}>
              <Card title={t("reports.paymentBreakdown")}>
                <Table
                  rowKey="type"
                  size="small"
                  pagination={false}
                  dataSource={d?.payment_breakdown ?? []}
                  columns={breakdownCols}
                />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title={t("reports.topServices")}>
                <Table
                  rowKey="id"
                  size="small"
                  pagination={false}
                  dataSource={d?.top_services ?? []}
                  columns={topCols}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
