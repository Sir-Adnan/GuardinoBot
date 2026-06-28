import { useState } from "react";
import { App as AntdApp, Button, Card, Input, Popconfirm, Select, Space, Tag, Tooltip, Typography } from "antd";
import { CheckCircleOutlined, CopyOutlined, SearchOutlined, SyncOutlined } from "@ant-design/icons";
import { useGetIdentity, useInvalidate, useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";

const { Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  finished: "green",
  waiting: "gold",
  rejected: "red",
  failed: "red",
  canceled: "default",
  partially_paid: "orange",
  sending: "blue",
  confirming: "blue",
};

export function TransactionList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<any>();
  const isSuper = (me?.role ?? 0) >= 3;
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<number | undefined>();
  const [type, setType] = useState<number | undefined>();
  const [provider, setProvider] = useState<string | undefined>();

  const { data, isLoading } = useList<any>({
    resource: "transactions",
    pagination: { current: page, pageSize },
    filters: [
      search ? { field: "search", operator: "contains", value: search } : null,
      status ? { field: "status", operator: "eq", value: status } : null,
      type ? { field: "type", operator: "eq", value: type } : null,
      provider ? { field: "provider", operator: "eq", value: provider } : null,
    ].filter(Boolean) as any,
  });

  const refresh = () => invalidate({ resource: "transactions", invalidates: ["list"] });

  const queuePlisio = async (id: number, action: "check" | "manual-approve") => {
    try {
      await api.post(`/transactions/${id}/plisio/${action}`);
      message.success(t("tx.queued"));
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const copy = async (value?: string | number | null) => {
    if (!value) return;
    await navigator.clipboard.writeText(String(value));
    message.success(t("tx.copied"));
  };

  const columns = [
    { title: t("tx.id"), dataIndex: "id", width: 80, className: "mono" },
    { title: t("tx.type"), dataIndex: "type_name" },
    {
      title: t("tx.provider"),
      dataIndex: "provider",
      render: (v: string, r: any) =>
        v ? (
          <span>
            <Tag>{v}</Tag>
            {r.provider_status && <Tag color="blue">{r.provider_status}</Tag>}
          </span>
        ) : (
          "-"
        ),
    },
    {
      title: t("tx.tracking"),
      dataIndex: "tracking_code",
      render: (v: string, r: any) => (
        <Space direction="vertical" size={0}>
          <Space size={4}>
            <Text className="mono">{v || `GB-${r.id}`}</Text>
            <Tooltip title={t("tx.copy")}>
              <Button size="small" type="text" icon={<CopyOutlined />} onClick={() => copy(v || `GB-${r.id}`)} />
            </Tooltip>
          </Space>
          {r.provider_txn_id && (
            <Text type="secondary" className="mono" style={{ fontSize: 12 }}>
              {r.provider_txn_id}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: t("tx.status"),
      dataIndex: "status_name",
      render: (v: string) => <Tag color={STATUS_COLORS[v] || "default"}>{v}</Tag>,
    },
    {
      title: t("tx.amount"),
      dataIndex: "amount",
      className: "mono",
      render: (v: number) => fmtToman(v),
    },
    {
      title: t("tx.payable"),
      dataIndex: "pay_amount",
      className: "mono",
      render: (v: number, r: any) =>
        v ? `${v} ${r.invoice_currency || r.pay_currency || ""}` : "-",
    },
    {
      title: t("tx.invoice"),
      dataIndex: "invoice_url",
      render: (v: string, r: any) =>
        v ? (
          <Button type="link" size="small" href={v} target="_blank">
            {r.provider_txn_id || t("tx.invoice")}
          </Button>
        ) : (
          <span className="mono">{r.provider_txn_id || "-"}</span>
        ),
    },
    {
      title: t("tx.user"),
      dataIndex: "user_id",
      className: "mono",
      render: (v: number) => (
        <Button type="link" size="small" onClick={() => navigate(`/users/show/${v}`)}>
          {v}
        </Button>
      ),
    },
    { title: t("tx.createdAt"), dataIndex: "created_at", render: (v: string) => fmtDate(v) },
    {
      title: "",
      dataIndex: "actions",
      render: (_: any, r: any) =>
        isSuper && r.provider === "plisio" ? (
          <Space size={4}>
            <Tooltip title={t("tx.check_plisio")}>
              <Button size="small" icon={<SyncOutlined />} onClick={() => queuePlisio(r.id, "check")} />
            </Tooltip>
            {r.status_name !== "finished" && (
              <Popconfirm
                title={t("tx.manual_approve_q")}
                okText={t("actions.done")}
                cancelText={t("actions.cancel")}
                onConfirm={() => queuePlisio(r.id, "manual-approve")}
              >
                <Button size="small" danger icon={<CheckCircleOutlined />}>
                  {t("tx.manual_approve")}
                </Button>
              </Popconfirm>
            )}
          </Space>
        ) : null,
    },
  ];

  return (
    <Card>
      <PageHeader title={t("tx.title")} subtitle={t("tx.subtitle")} />
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder={t("tx.search_ph")}
          value={search}
          onChange={(e) => {
            setPage(1);
            setSearch(e.target.value);
          }}
          style={{ width: 280 }}
        />
        <Select
          allowClear
          placeholder={t("tx.status")}
          value={status}
          onChange={(v) => {
            setPage(1);
            setStatus(v);
          }}
          style={{ width: 150 }}
          options={[
            { value: 1, label: "waiting" },
            { value: 8, label: "confirming" },
            { value: 5, label: "finished" },
            { value: 2, label: "failed" },
            { value: 3, label: "canceled" },
            { value: 6, label: "rejected" },
          ]}
        />
        <Select
          allowClear
          placeholder={t("tx.type")}
          value={type}
          onChange={(v) => {
            setPage(1);
            setType(v);
          }}
          style={{ width: 170 }}
          options={[
            { value: 1, label: "crypto" },
            { value: 2, label: "card_to_card" },
            { value: 4, label: "rial_gateway" },
            { value: 5, label: "by_admin" },
          ]}
        />
        <Select
          allowClear
          placeholder={t("tx.provider")}
          value={provider}
          onChange={(v) => {
            setPage(1);
            setProvider(v);
          }}
          style={{ width: 170 }}
          options={[
            { value: "plisio", label: "Plisio" },
            { value: "nowpayments", label: "NowPayments" },
            { value: "offline", label: "Offline" },
            { value: "swapino", label: "Swapino" },
          ]}
        />
      </Space>
      <ResponsiveTable
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 780 }}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
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
