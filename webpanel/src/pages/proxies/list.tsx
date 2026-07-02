import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Dropdown,
  Input,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  DeleteOutlined,
  MoreOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useGetIdentity, useInvalidate, useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { ROLE_ADMIN, fmtDate, fmtToman } from "../../utils/format";
import { PageHeader } from "../../components/PageHeader";
import { ResponsiveTable } from "../../components/ResponsiveTable";

const { Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  active: "green",
  disabled: "default",
  limited: "orange",
  expired: "red",
  on_hold: "blue",
};
const STATUSES = ["active", "disabled", "limited", "expired", "on_hold"];

export function ProxyList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<any>();
  const isAdmin = (me?.role ?? 0) >= ROLE_ADMIN;

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string | undefined>();

  const { data, isLoading } = useList<any>({
    resource: "proxies",
    pagination: { current: page, pageSize },
    filters: [
      search ? { field: "search", operator: "contains", value: search } : null,
      status ? { field: "status", operator: "eq", value: status } : null,
    ].filter(Boolean) as any,
  });

  const refresh = () => invalidate({ resource: "proxies", invalidates: ["list"] });
  const stLabel = (s: string) => {
    const k = `proxies.st_${s}`;
    const tr = t(k);
    return tr === k ? s : tr;
  };

  const act = async (id: number, action: string) => {
    try {
      await api.post(`/proxies/${id}/action`, { action });
      message.success(t("actions.done"));
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const del = async (id: number) => {
    try {
      await api.delete(`/proxies/${id}`);
      message.success(t("actions.deleted"));
      refresh();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    }
  };

  const columns = [
    {
      title: t("proxies.username"),
      dataIndex: "username",
      render: (v: string, r: any) => (
        <Space direction="vertical" size={0}>
          <Text strong copyable className="mono">{v}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {r.custom_name ? `${r.custom_name} · ` : ""}
            {[r.service_name, r.server_name].filter(Boolean).join(" · ") || "—"}
          </Text>
        </Space>
      ),
    },
    {
      title: t("proxies.status"),
      dataIndex: "status",
      width: 120,
      render: (v: string) => <Tag color={STATUS_COLORS[v] || "default"}>{stLabel(v)}</Tag>,
    },
    {
      title: t("proxies.price"),
      dataIndex: "cost",
      width: 130,
      className: "mono",
      render: (v: number) => (v ? fmtToman(v) : "—"),
    },
    {
      title: t("proxies.user"),
      dataIndex: "user_id",
      width: 90,
      render: (v: number) => (
        <Button type="link" size="small" style={{ padding: 0 }} onClick={() => navigate(`/users/show/${v}`)}>
          {v}
        </Button>
      ),
    },
    {
      title: t("proxies.createdAt"),
      dataIndex: "created_at",
      width: 150,
      render: (v: string) => fmtDate(v),
    },
    {
      title: "",
      key: "actions",
      width: 90,
      render: (_: any, r: any) => (
        <Space size={2}>
          <Dropdown
            trigger={["click"]}
            menu={{
              items: [
                r.status === "active"
                  ? { key: "disable", icon: <PauseCircleOutlined />, label: t("actions.disable") }
                  : { key: "enable", icon: <PlayCircleOutlined />, label: t("actions.enable") },
                { key: "reset_usage", icon: <ReloadOutlined />, label: t("actions.resetUsage") },
                { key: "revoke", icon: <SafetyOutlined />, label: t("actions.revoke") },
              ],
              onClick: ({ key }) => act(r.id, key),
            }}
          >
            <Button type="text" icon={<MoreOutlined />} />
          </Dropdown>
          {isAdmin && (
            <Popconfirm
              title={t("actions.deleteConfirm")}
              okButtonProps={{ danger: true }}
              onConfirm={() => del(r.id)}
            >
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <PageHeader title={t("proxies.title")} subtitle={t("proxies.subtitle")} />
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder={t("proxies.search")}
          value={search}
          onChange={(e) => {
            setPage(1);
            setSearch(e.target.value);
          }}
          style={{ width: 240 }}
        />
        <Select
          allowClear
          placeholder={t("proxies.status")}
          value={status}
          onChange={(v) => {
            setPage(1);
            setStatus(v);
          }}
          style={{ width: 160 }}
          options={STATUSES.map((s) => ({ value: s, label: stLabel(s) }))}
        />
      </Space>
      <ResponsiveTable
        size="small"
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 760 }}
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
