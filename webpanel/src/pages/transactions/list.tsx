import { useState } from "react";
import { App as AntdApp, Button, Card, Input, Popconfirm, Select, Space, Tag, Tooltip, Typography } from "antd";
import { CheckCircleOutlined, CopyOutlined, SearchOutlined, SyncOutlined } from "@ant-design/icons";
import { useGetIdentity, useInvalidate, useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ROLE_SUPER, fmtDate, fmtToman } from "../../utils/format";
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
  const isSuper = (me?.role ?? 0) >= ROLE_SUPER;
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

  const queueGateway = async (id: number, gateway: string, action: "check" | "manual-approve") => {
    try {
      await api.post(`/transactions/${id}/${gateway}/${action}`);
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
    {
      title: t("tx.id"),
      dataIndex: "id",
      width: 180,
      render: (_: number, r: any) => (
        <Space direction="vertical" size={0}>
          <Text strong className="mono">#{r.id}</Text>
          <Space size={4} wrap>
            <Tag>{r.type_name}</Tag>
            <Tag color={STATUS_COLORS[r.status_name] || "default"}>{r.status_name}</Tag>
            {r.provider && <Tag>{r.provider}</Tag>}
            {r.provider_status && <Tag color="blue">{r.provider_status}</Tag>}
          </Space>
        </Space>
      ),
    },
    {
      title: t("tx.tracking"),
      dataIndex: "tracking_code",
      width: 240,
      render: (v: string, r: any) => (
        <Space direction="vertical" size={2} style={{ maxWidth: 230 }}>
          <Space size={4}>
            <Text className="mono" copyable={false}>{v || `GB-${r.id}`}</Text>
            <Tooltip title={t("tx.copy")}>
              <Button size="small" type="text" icon={<CopyOutlined />} onClick={() => copy(v || `GB-${r.id}`)} />
            </Tooltip>
          </Space>
          {r.provider_txn_id && (
            <Text type="secondary" className="mono" style={{ fontSize: 12 }} ellipsis>
              {r.provider_txn_id}
            </Text>
          )}
          {r.invoice_url && (
            <Button type="link" size="small" href={r.invoice_url} target="_blank" style={{ padding: 0, height: 20 }}>
              {t("tx.invoice")}
            </Button>
          )}
        </Space>
      ),
    },
    {
      title: t("tx.amount"),
      dataIndex: "amount",
      width: 190,
      render: (v: number, r: any) => (
        <Space direction="vertical" size={0}>
          <Text className="mono">{fmtToman(v)}</Text>
          {r.pay_amount ? (
            <Text type="secondary" className="mono" style={{ fontSize: 12 }}>
              {r.pay_amount} {r.invoice_currency || r.pay_currency || ""}
            </Text>
          ) : null}
          {r.amount_paid ? (
            <Text type="secondary" className="mono" style={{ fontSize: 12 }}>
              {fmtToman(r.amount_paid)}
            </Text>
          ) : null}
        </Space>
      ),
    },
    {
      title: t("tx.user"),
      dataIndex: "user_id",
      width: 170,
      render: (v: number, r: any) => (
        <Space direction="vertical" size={0}>
          <Button type="link" size="small" onClick={() => navigate(`/users/show/${v}`)} style={{ padding: 0 }}>
            {r.user_name || r.username || v}
          </Button>
          <Text type="secondary" className="mono" style={{ fontSize: 12 }}>
            {r.username ? `@${r.username}` : `ID ${v}`}
          </Text>
        </Space>
      ),
    },
    { title: t("tx.createdAt"), dataIndex: "created_at", width: 150, render: (v: string) => fmtDate(v) },
    {
      title: "",
      dataIndex: "actions",
      width: 120,
      render: (_: any, r: any) =>
        isSuper && ["plisio", "nowpayments"].includes(r.provider) ? (
          <Space size={4}>
            <Tooltip title={t("tx.check_gateway")}>
              <Button size="small" icon={<SyncOutlined />} onClick={() => queueGateway(r.id, r.provider, "check")} />
            </Tooltip>
            {r.status_name !== "finished" && (
              <Popconfirm
                title={t("tx.manual_approve_q")}
                okText={t("actions.done")}
                cancelText={t("actions.cancel")}
                onConfirm={() => queueGateway(r.id, r.provider, "manual-approve")}
              >
                <Button size="small" danger icon={<CheckCircleOutlined />} />
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
        size="small"
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 720 }}
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
