import { useState } from "react";
import { App as AntdApp, Button, Card, Table, Tag } from "antd";
import { ApiOutlined } from "@ant-design/icons";
import { useList } from "@refinedev/core";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";
import { fmtNum } from "../../utils/format";

const PANEL_COLORS: Record<string, string> = {
  marzban: "blue",
  pasarguard: "purple",
  guardino: "green",
};

export function ServerList() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const { data, isLoading } = useList<any>({
    resource: "servers",
    pagination: { current: 1, pageSize: 100 },
  });
  const [checking, setChecking] = useState<number | null>(null);

  const checkHealth = async (id: number) => {
    setChecking(id);
    try {
      const res = await api.get(`/servers/${id}/health`);
      if (res.data.ok) {
        message.success(`${t("servers.healthy")} — ${res.data.username ?? ""}`);
      } else {
        message.error(
          `${t("servers.unhealthy")}${res.data.status_code ? ` (${res.data.status_code})` : ""}`,
        );
      }
    } catch {
      message.error(t("servers.unhealthy"));
    } finally {
      setChecking(null);
    }
  };

  const columns = [
    { title: t("servers.id"), dataIndex: "id", width: 80, className: "mono" },
    { title: t("servers.name"), key: "name", render: (_: any, r: any) => r.name || r.host },
    { title: t("servers.host"), dataIndex: "host", className: "mono" },
    {
      title: t("servers.panelType"),
      dataIndex: "panel_type",
      render: (v: string) => <Tag color={PANEL_COLORS[v] || "default"}>{v}</Tag>,
    },
    {
      title: t("servers.proxies"),
      dataIndex: "total_proxies",
      className: "mono",
      render: (v: number) => fmtNum(v),
    },
    {
      title: t("servers.status"),
      dataIndex: "is_enabled",
      render: (v: boolean) =>
        v ? <Tag color="green">{t("servers.enabled")}</Tag> : <Tag>{t("servers.disabled")}</Tag>,
    },
    {
      title: "",
      key: "actions",
      width: 130,
      render: (_: any, r: any) => (
        <Button
          size="small"
          icon={<ApiOutlined />}
          loading={checking === r.id}
          onClick={() => checkHealth(r.id)}
        >
          {t("servers.health")}
        </Button>
      ),
    },
  ];

  return (
    <Card>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.data ?? []}
        columns={columns}
        scroll={{ x: 780 }}
        pagination={false}
      />
    </Card>
  );
}
