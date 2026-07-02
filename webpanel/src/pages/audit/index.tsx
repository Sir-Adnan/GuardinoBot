import { useEffect, useState } from "react";
import { App as AntdApp, Button, Card, DatePicker, Input, Select, Space, Tag, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import type { Dayjs } from "dayjs";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";

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

export function AuditPage() {
  const { t } = useTranslation();
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
      render: (v: string) => fmtDate(v),
    },
    {
      title: t("audit.actor"),
      render: (_: any, r: any) => (
        <Space size={4} wrap>
          <span>{r.actor_name || r.actor_id || "—"}</span>
          <Tag color={ROLE_COLORS[r.actor_role] || "default"}>
            {t(`roles.${r.actor_role}`)}
          </Tag>
        </Space>
      ),
    },
    {
      title: t("audit.source"),
      dataIndex: "source",
      width: 90,
      render: (v: string) => (
        <Tag color={SOURCE_COLORS[v] || "default"}>{t(`audit.src.${v}`)}</Tag>
      ),
    },
    {
      title: t("audit.action"),
      dataIndex: "action",
      render: (v: string) => <Tag>{actionLabel(v)}</Tag>,
    },
    {
      title: t("audit.target"),
      render: (_: any, r: any) =>
        r.target_type ? (
          <Text>
            {r.target_label || r.target_id || "—"}{" "}
            <Text type="secondary">({r.target_type})</Text>
          </Text>
        ) : (
          "—"
        ),
    },
    {
      title: t("audit.amount"),
      dataIndex: "amount",
      className: "mono",
      width: 120,
      render: (v: number | null) => (v == null ? "—" : fmtToman(v)),
    },
  ];

  return (
    <Card>
      <PageHeader
        title={t("audit.title")}
        subtitle={t("audit.subtitle")}
        extra={
          <Space wrap>
            <Input.Search
              allowClear
              placeholder={t("audit.search")}
              style={{ width: 220 }}
              onSearch={(v) => {
                setSearch(v);
                setPage(1);
              }}
            />
            <Select
              allowClear
              placeholder={t("audit.source")}
              style={{ width: 140 }}
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
              onChange={(v) => {
                setRange(v && v[0] && v[1] ? [v[0], v[1]] : null);
                setPage(1);
              }}
              allowClear
            />
            <Button icon={<DownloadOutlined />} onClick={exportCsv}>
              {t("reports.export")}
            </Button>
          </Space>
        }
      />
      <ResponsiveTable
        rowKey="id"
        loading={loading}
        dataSource={rows}
        columns={columns}
        scroll={{ x: 900 }}
        expandable={{
          expandedRowRender: (r: any) => (
            <pre
              style={{
                margin: 0,
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                fontSize: 12,
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
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />
    </Card>
  );
}
