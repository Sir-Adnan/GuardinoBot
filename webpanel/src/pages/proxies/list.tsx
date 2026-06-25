import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Card,
  Dropdown,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
} from "antd";
import {
  DeleteOutlined,
  MoreOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import { useGetIdentity, useInvalidate, useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtDate } from "../../utils/format";

const STATUS_COLORS: Record<string, string> = {
  active: "green",
  disabled: "default",
  limited: "orange",
  expired: "red",
  on_hold: "blue",
};

export function ProxyList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<any>();
  const isAdmin = (me?.role ?? 0) >= 2;

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useList<any>({
    resource: "proxies",
    pagination: { current: page, pageSize },
    filters: search
      ? [{ field: "search", operator: "contains", value: search }]
      : [],
  });

  const refresh = () => invalidate({ resource: "proxies", invalidates: ["list"] });

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
    { title: t("proxies.username"), dataIndex: "username", className: "mono" },
    {
      title: t("proxies.status"),
      dataIndex: "status",
      render: (v: string) => <Tag color={STATUS_COLORS[v] || "default"}>{v}</Tag>,
    },
    { title: t("proxies.server"), dataIndex: "server_name", render: (v: string) => v || "—" },
    { title: t("proxies.service"), dataIndex: "service_name", render: (v: string) => v || "—" },
    {
      title: t("proxies.user"),
      dataIndex: "user_id",
      className: "mono",
      render: (v: number) => (
        <Button type="link" size="small" onClick={() => navigate(`/users/show/${v}`)}>
          {v}
        </Button>
      ),
    },
    { title: t("proxies.createdAt"), dataIndex: "created_at", render: (v: string) => fmtDate(v) },
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
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder={t("proxies.search")}
          allowClear
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
          }}
          style={{ width: 260 }}
        />
      </Space>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 880 }}
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
