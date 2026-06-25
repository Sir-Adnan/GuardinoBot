import { useState } from "react";
import { Button, Card, Input, Space, Table, Tag } from "antd";
import { useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
        scroll={{ x: 820 }}
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
