import { useEffect, useState } from "react";
import { Card, Input, Select, Space, Table, Tag, Typography } from "antd";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate, fmtToman } from "../../utils/format";

const { Text } = Typography;

const SOURCE_COLORS: Record<string, string> = {
  web: "blue",
  bot: "green",
  system: "default",
};
const ROLE_COLORS: Record<number, string> = {
  0: "default",
  1: "cyan",
  2: "geekblue",
  3: "magenta",
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

  useEffect(() => {
    setLoading(true);
    api
      .get("/audit", {
        params: {
          page,
          per_page: pageSize,
          source: source || undefined,
          search: search || undefined,
        },
      })
      .then((r) => {
        setRows(r.data.items ?? []);
        setTotal(r.data.total ?? 0);
      })
      .finally(() => setLoading(false));
  }, [page, pageSize, source, search]);

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
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder={t("audit.search")}
          style={{ width: 240 }}
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
          }}
        />
        <Select
          allowClear
          placeholder={t("audit.source")}
          style={{ width: 150 }}
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
      </Space>
      <Table
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
