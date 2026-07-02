import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  DatePicker,
  Input,
  Select,
  Space,
  Tag,
  Typography,
  theme as antdTheme,
} from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import type { Dayjs } from "dayjs";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { useIsMobile } from "../../hooks/useIsMobile";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const SOURCE_COLORS: Record<string, string> = {
  web: "blue",
  bot: "green",
  system: "default",
};
const ROLE_COLORS: Record<number, string> = {
  0: "default",
  1: "cyan",
  2: "purple",
  3: "geekblue",
  4: "magenta",
};

// Colour an action tag by what it does (derived from the verb suffix) so the
// list scans at a glance: destructive = red, grants = green, edits = blue.
const actionColor = (a: string): string => {
  const v = a.split(".").pop() || "";
  if (/delete|remove|reject|revoke/.test(v)) return "error";
  if (/block|disable|decharge/.test(v)) return "warning";
  if (/add|create|enable|unblock|approve|promote|charge/.test(v)) return "success";
  if (/update|edit|reorder|duplicate|adjust|button/.test(v)) return "processing";
  return "default";
};

export function AuditPage() {
  const { t } = useTranslation();
  const { token } = antdTheme.useToken();
  const isMobile = useIsMobile();
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(30);
  const [source, setSource] = useState<string | undefined>();
  const [search, setSearch] = useState("");
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);
  const { message } = AntdApp.useApp();

  const filterParams = () => ({
    source: source || undefined,
    search: search || undefined,
    start: range ? range[0].format("YYYY-MM-DD") : undefined,
    end: range ? range[1].format("YYYY-MM-DD") : undefined,
  });

  useEffect(() => {
    setLoading(true);
    api
      .get("/audit", { params: { page, per_page: pageSize, ...filterParams() } })
      .then((r) => {
        setRows(r.data.items ?? []);
        setTotal(r.data.total ?? 0);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, source, search, range]);

  const exportCsv = async () => {
    try {
      const r = await api.get("/audit", { params: { page: 1, per_page: 1000, ...filterParams() } });
      const items: any[] = r.data.items ?? [];
      const esc = (s: any) => `"${String(s ?? "").replace(/"/g, '""')}"`;
      const lines = ["time,actor,role,source,action,target_type,target,amount,detail"];
      items.forEach((a) =>
        lines.push(
          [a.created_at, a.actor_name || a.actor_id, a.actor_role_name, a.source, a.action, a.target_type, a.target_label || a.target_id, a.amount ?? "", JSON.stringify(a.detail ?? {})]
            .map(esc)
            .join(","),
        ),
      );
      const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
      const el = document.createElement("a");
      el.href = URL.createObjectURL(blob);
      el.download = `audit_${new Date().toISOString().slice(0, 10)}.csv`;
      el.click();
      URL.revokeObjectURL(el.href);
    } catch {
      message.error(t("actions.failed"));
    }
  };

  const actionLabel = (a: string) => {
    const k = `audit.a.${a}`;
    const tr = t(k);
    return tr === k ? a : tr;
  };

  const columns = [
    {
      title: t("audit.time"),
      dataIndex: "created_at",
      width: 165,
      render: (v: string) => (
        <Text style={{ fontVariantNumeric: "tabular-nums", fontSize: 12.5 }}>{fmtDate(v)}</Text>
      ),
    },
    {
      title: t("audit.actor"),
      render: (_: any, r: any) => (
        <Space size={4} wrap>
          <span>{r.actor_name || r.actor_id || "—"}</span>
          <Tag color={ROLE_COLORS[r.actor_role] || "default"} style={{ margin: 0 }}>
            {t(`roles.${r.actor_role}`)}
          </Tag>
        </Space>
      ),
    },
    {
      title: t("audit.source"),
      dataIndex: "source",
      width: 95,
      render: (v: string) => (
        <Tag color={SOURCE_COLORS[v] || "default"} style={{ margin: 0 }}>
          {t(`audit.src.${v}`)}
        </Tag>
      ),
    },
    {
      title: t("audit.action"),
      dataIndex: "action",
      render: (v: string) => (
        <Tag color={actionColor(v)} style={{ margin: 0 }}>
          {actionLabel(v)}
        </Tag>
      ),
    },
    {
      title: t("audit.target"),
      render: (_: any, r: any) =>
        r.target_type ? (
          <Text>
            {r.target_label || r.target_id || "—"}{" "}
            <Text type="secondary" style={{ fontSize: 12 }}>
              ({r.target_type})
            </Text>
          </Text>
        ) : (
          "—"
        ),
    },
    {
      title: t("audit.amount"),
      dataIndex: "amount",
      className: "mono",
      width: 130,
      render: (v: number | null) =>
        v == null ? (
          "—"
        ) : (
          <Text
            style={{
              color: v > 0 ? token.colorSuccess : v < 0 ? token.colorError : undefined,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {fmtToman(v)}
          </Text>
        ),
    },
  ];

  return (
    <Card>
      <PageHeader
        title={t("audit.title")}
        subtitle={t("audit.subtitle")}
        extra={
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>
            {t("reports.export")}
          </Button>
        }
      />
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          marginBottom: 16,
          padding: 10,
          borderRadius: 12,
          background: token.colorFillQuaternary,
          border: `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <Input.Search
          allowClear
          placeholder={t("audit.search")}
          style={{ flex: "1 1 220px", minWidth: 180 }}
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
          }}
        />
        <Select
          allowClear
          placeholder={t("audit.source")}
          style={{ flex: isMobile ? "1 1 45%" : "0 0 140px" }}
          value={source}
          onChange={(v) => {
            setSource(v);
            setPage(1);
          }}
          options={[
            { value: "web", label: t("audit.src.web") },
            { value: "bot", label: t("audit.src.bot") },
            { value: "system", label: t("audit.src.system") },
          ]}
        />
        <RangePicker
          value={range as any}
          style={{ flex: isMobile ? "1 1 100%" : "0 0 auto" }}
          onChange={(v) => {
            setRange(v && v[0] && v[1] ? [v[0], v[1]] : null);
            setPage(1);
          }}
          allowClear
        />
      </div>
      <ResponsiveTable
        rowKey="id"
        loading={loading}
        dataSource={rows}
        columns={columns}
        size="middle"
        scroll={{ x: 900 }}
        expandable={{
          expandedRowRender: (r: any) => (
            <pre
              style={{
                margin: 0,
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                fontSize: 12,
                background: token.colorFillQuaternary,
                border: `1px solid ${token.colorBorderSecondary}`,
                borderRadius: 10,
                padding: "8px 12px",
              }}
            >
              {JSON.stringify(r.detail ?? {}, null, 2)}
            </pre>
          ),
          rowExpandable: (r: any) => Boolean(r.detail),
        }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (n: number) => t("audit.total", { n }),
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />
    </Card>
  );
}
